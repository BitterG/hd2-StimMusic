"""Assemble Source/mods/kugua/stim_music.lua and build 9ba626afa44a3aa3.patch_0.
"""
from __future__ import annotations

import base64
import math
import os
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from archive import make_archive, resource_hash
import loader_accept

RESOURCE = 'mods/kugua/stim_music'
VERSION = '2.2.0'

print(f"Building {RESOURCE} v{VERSION}...")

# 1. Generate default embedded audio (4s 22050Hz 16-bit mono PCM)
rate = 22050
duration = 4.0
samples_count = int(rate * duration)
audio_data = bytearray()
notes = [261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50]
for i in range(samples_count):
    t = i / rate
    drone = 0.25 * math.sin(2 * math.pi * 130.81 * t) + 0.15 * math.sin(2 * math.pi * 196.00 * t)
    note_idx = int(t * 8) % len(notes)
    note_freq = notes[note_idx]
    note_t = (t * 8) % 1.0
    note_env = math.exp(-note_t * 5.0)
    arp = 0.4 * math.sin(2 * math.pi * note_freq * t) * note_env
    sweep_freq = 200.0 + 600.0 * (t / duration)**1.5
    sweep = 0.15 * math.sin(2 * math.pi * sweep_freq * t)
    master_env = 1.0
    if t < 0.3:
        master_env = t / 0.3
    elif t > (duration - 0.5):
        master_env = (duration - t) / 0.5
    sample = (drone + arp + sweep) * master_env
    sample = max(-1.0, min(1.0, sample))
    sample_int = int(sample * 28000)
    audio_data.extend(struct.pack('<h', sample_int))

# Format WAVEFORMATEX: tag=1, ch=1, rate=22050, avg=44100, align=2, bits=16, extra=0 (18 bytes)
wfx_default = struct.pack('<HHIIHHH', 1, 1, rate, rate * 2, 2, 16, 0)
default_fmt_b64 = base64.b64encode(wfx_default).decode('ascii')
default_data_b64 = base64.b64encode(audio_data).decode('ascii')
print(f"Default format: {default_fmt_b64}, Audio b64 length: {len(default_data_b64)}")

converter_cmd_b64 = base64.b64encode((ROOT / 'convert_track.cmd').read_bytes()).decode('ascii')
converter_ps1_b64 = base64.b64encode((ROOT / 'convert_track.ps1').read_bytes()).decode('ascii')

# Split default_data_b64 into chunks of 1000 characters for Lua readability
chunk_size = 1000
b64_chunks = [default_data_b64[i:i + chunk_size] for i in range(0, len(default_data_b64), chunk_size)]
b64_literal_lines = ['    "' + c + '"' for c in b64_chunks]
b64_literal = 'table.concat({\n' + ',\n'.join(b64_literal_lines) + '\n})'

lua_template = f'''-- HD2-Addon: {RESOURCE}
-- StimMusic v{VERSION} for MDL3 (PUC Lua 5.1) + HD2 Data Hub >= 0.3.0 (HD2Data API 1).
-- Plays audio on stim / healing with segment resume and volume controls.
-- Pure Lua 5.1, zero FFI, zero memory writes, 7-bit ASCII only.

local KEY = '__KUGUA_STIM_MUSIC'
if type(rawget(_G, KEY)) == 'table' and rawget(_G, KEY).active == true then
    return rawget(_G, KEY)
end

local ADDON_ID = '{RESOURCE}'
local VERSION = '{VERSION}'

local sr = rawget(_G, 'stingray')
local App = sr and sr.Application
local ok_call = function(fn, ...)
    if type(fn) ~= 'function' then return nil end
    local ok, res = pcall(fn, ...)
    if ok then return res else return nil end
end

-- ---------------------------------------------------------------- Configuration
local CONFIG = {{
    enabled = true,
    volume = 100,
    stim_ms = 6000,
    fade_in_ms = 500,
    fade_out_ms = 1500,
    min_heal = 1,
    hot_reload = true,
    track = 'stim_music.wav',
    language = 'auto',
}}

-- String table: pure 7-bit ASCII using decimal escapes for Chinese UI labels
local ZH = {{
    mod_title = '\\230\\137\\147\\233\\146\\136\\230\\148\\190\\233\\159\\179\\228\\185\\144 (Stim Music)',
    mod_desc = '\\233\\156\\128\\232\\166\\129\\32\\77\\68\\76\\51\\32\\43\\32\\72\\68\\50\\32\\68\\97\\116\\97\\32\\72\\117\\98\\32\\40\\48\\46\\51\\46\\48\\43\\41\\32\\229\\137\\141\\231\\189\\174\\227\\128\\130\\230\\137\\147\\233\\146\\136\\239\\188\\136\\229\\155\\158\\232\\161\\128\\239\\188\\137\\232\\167\\166\\229\\143\\145\\233\\159\\179\\228\\185\\144\\230\\146\\173\\230\\148\\190\\239\\188\\140\\230\\148\\175\\230\\140\\129\\230\\175\\171\\231\\167\\146\\231\\186\\167\\229\\138\\168\\230\\128\\129\\230\\150\\173\\231\\130\\185\\230\\142\\165\\231\\187\\173\\228\\184\\142\\233\\159\\179\\233\\135\\143\\232\\176\\131\\232\\138\\130\\227\\128\\130\\229\\143\\175\\229\\156\\168\\32\\69\\83\\67\\32\\45\\62\\32\\77\\68\\76\\32\\232\\174\\190\\231\\189\\174\\228\\184\\173\\232\\176\\131\\232\\138\\130\\233\\128\\137\\233\\161\\185\\227\\128\\130',
    opt_enabled = '\\230\\128\\187\\229\\188\\128\\229\\133\\179 (Enabled)',
    opt_enabled_desc = '\\230\\137\\147\\233\\146\\136\\230\\148\\190\\233\\159\\179\\228\\185\\144\\230\\168\\161\\231\\187\\132\\230\\128\\187\\229\\188\\128\\229\\133\\179',
    opt_track = '\\233\\159\\179\\228\\185\\144\\230\\150\\135\\228\\187\\182 (Music Track)',
    opt_track_desc = '\\229\\189\\147\\229\\137\\141\\231\\148\\159\\230\\149\\136\\231\\154\\132\\233\\159\\179\\228\\185\\144\\230\\150\\135\\228\\187\\182\\229\\144\\141\\227\\128\\130\\229\\143\\175\\229\\156\\168\\230\\173\\164\\229\\136\\135\\230\\141\\162\\239\\188\\140\\230\\148\\175\\230\\140\\129\\231\\131\\173\\230\\155\\180\\230\\150\\176\\227\\128\\130',
    opt_volume = '\\233\\159\\179\\228\\185\\144\\233\\159\\179\\233\\135\\143 (Volume %)',
    opt_volume_desc = '\\233\\146\\136\\229\\137\\130\\233\\159\\179\\228\\185\\144\\230\\146\\173\\230\\148\\190\\233\\159\\179\\233\\135\\143 (0-100)',
    opt_stim_ms = '\\233\\146\\136\\229\\137\\130\\230\\151\\182\\233\\149\\191 (Stim Length ms)',
    opt_stim_ms_desc = '\\229\\141\\149\\230\\172\\161\\230\\137\\147\\233\\146\\136\\231\\148\\159\\230\\149\\136\\230\\140\\129\\231\\187\\173\\230\\151\\182\\233\\151\\180\\228\\184\\142\\233\\159\\179\\228\\185\\144\\230\\146\\173\\230\\148\\190\\231\\170\\151\\229\\143\\163\\239\\188\\136\\230\\175\\171\\231\\167\\146\\239\\188\\137\\227\\128\\130\\232\\176\\131\\230\\149\\180\\229\\144\\142\\228\\187\\141\\228\\188\\154\\230\\151\\160\\231\\188\\157\\230\\142\\165\\231\\187\\173\\228\\184\\138\\230\\172\\161\\230\\150\\173\\231\\130\\185\\227\\128\\130',
    opt_fade_in = '\\230\\184\\144\\229\\133\\165\\230\\151\\182\\233\\149\\191 (Fade In ms)',
    opt_fade_in_desc = '\\233\\159\\179\\228\\185\\144\\229\\188\\128\\229\\167\\139\\230\\146\\173\\230\\148\\190\\230\\151\\182\\231\\154\\132\\230\\183\\161\\229\\133\\165\\230\\151\\182\\233\\151\\180\\239\\188\\136\\230\\175\\171\\231\\167\\146\\239\\188\\137\\239\\188\\140\\48\\228\\184\\186\\231\\171\\139\\229\\141\\179\\229\\133\\168\\233\\159\\179\\233\\135\\143',
    opt_fade_out = '\\230\\184\\144\\229\\135\\186\\230\\151\\182\\233\\149\\191 (Fade Out ms)',
    opt_fade_out_desc = '\\233\\146\\136\\229\\137\\130\\230\\149\\136\\230\\158\\156\\231\\187\\147\\230\\157\\159\\229\\137\\141\\231\\154\\132\\230\\183\\161\\229\\135\\186\\230\\151\\182\\233\\151\\180\\239\\188\\136\\230\\175\\171\\231\\167\\146\\239\\188\\137\\239\\188\\140\\48\\228\\184\\186\\231\\155\\180\\230\\142\\165\\230\\136\\170\\230\\150\\173',
    opt_min_heal = '\\230\\156\\128\\229\\176\\143\\229\\155\\158\\232\\161\\128\\233\\135\\143\\229\\136\\164\\229\\174\\154 (Min Heal)',
    opt_min_heal_desc = '\\229\\141\\149\\230\\172\\161\\229\\136\\164\\229\\174\\154\\233\\146\\136\\229\\137\\130\\231\\148\\159\\230\\149\\136\\231\\154\\132\\230\\156\\128\\229\\176\\143\\229\\155\\158\\232\\161\\128\\230\\149\\176\\229\\128\\188 (1-50)',
    opt_hot_reload = '\\232\\135\\170\\229\\138\\168\\230\\163\\128\\230\\181\\139\\230\\155\\180\\230\\150\\176 (Hot Reload)',
    opt_hot_reload_desc = '\\230\\163\\128\\230\\181\\139\\229\\136\\176\\233\\159\\179\\233\\162\\145\\230\\150\\135\\228\\187\\182\\230\\136\\150\\233\\133\\141\\231\\189\\174\\229\\143\\152\\230\\155\\180\\230\\151\\182\\232\\135\\170\\229\\138\\168\\233\\135\\141\\230\\150\\176\\232\\189\\189\\229\\133\\165',
}}
local EN = {{
    mod_title = 'Stim Music',
    mod_desc = 'Plays audio on stim/healing with dynamic sample-accurate resume. Requires MDL3 + HD2 Data Hub (0.3.0+).',
    opt_enabled = 'Enabled',
    opt_enabled_desc = 'Master toggle for Stim Music mod.',
    opt_track = 'Music Track',
    opt_track_desc = 'Currently active music filename. You can switch tracks here with hot-reload.',
    opt_volume = 'Music Volume (%)',
    opt_volume_desc = 'Playback volume for stim music (0-100).',
    opt_stim_ms = 'Stim Length (ms)',
    opt_stim_ms_desc = 'Stim duration window and playback time per heal (ms). Resumes smoothly from breakpoint even when adjusted.',
    opt_fade_in = 'Fade In (ms)',
    opt_fade_in_desc = 'Volume fade-in duration when music starts (ms). 0 = full volume immediately.',
    opt_fade_out = 'Fade Out (ms)',
    opt_fade_out_desc = 'Volume fade-out duration before stim ends (ms). 0 = hard cut.',
    opt_min_heal = 'Minimum Heal Threshold',
    opt_min_heal_desc = 'Minimum health increase to count as stim effect (1-50).',
    opt_hot_reload = 'Hot Reload',
    opt_hot_reload_desc = 'Automatically reloads when music file or config changes.',
}}

local function is_chinese_ui()
    if type(CONFIG) == 'table' and type(CONFIG.language) == 'string' then
        local l = CONFIG.language:lower()
        if l:find('zh') or l:find('chinese') then return true end
        if l:find('en') or l:find('english') then return false end
    end
    local mdl3 = rawget(_G, 'MDL3')
    if type(mdl3) == 'table' then
        if type(mdl3.locale) == 'string' and #mdl3.locale >= 2 then
            local l = mdl3.locale:lower()
            if l:find('zh') or l:find('chinese') then return true end
            if l:find('en') or l:find('english') then return false end
        end
        local ui = type(mdl3.ui) == 'table' and mdl3.ui or (type(mdl3.config) == 'table' and mdl3.config.ui)
        if type(ui) == 'table' and type(ui.language) == 'string' then
            local l = ui.language:lower()
            if l:find('zh') or l:find('chinese') then return true end
            if l:find('en') or l:find('english') then return false end
        end
    end
    local bt = rawget(_G, 'BingusTranslations')
    if type(bt) == 'table' then
        local lang = bt.override or bt.game_language
        if type(lang) == 'string' and #lang >= 2 then
            local l = lang:lower()
            if l:find('zh') or l:find('chinese') or l:find('hans') or l:find('hant') then return true end
            if l:find('en') or l:find('english') then return false end
        end
    end
    local sr = rawget(_G, 'stingray')
    if sr and sr.Localization and type(sr.Localization.language) == 'function' then
        local ok, lang = pcall(sr.Localization.language)
        if ok and type(lang) == 'string' and #lang >= 2 then
            local l = lang:lower()
            if l:find('zh') or l:find('chinese') or l:find('hans') or l:find('hant') then return true end
            if l:find('en') or l:find('english') then return false end
        end
    end
    local loc = ok_call(os.setlocale, nil, 'collate') or ok_call(os.setlocale, nil, 'all')
    if type(loc) == 'string' then
        local l = loc:lower()
        if l:find('chinese') or l:find('china') or l:find('936') then return true end
    end
    return false -- default to English for international users (akamod / Nexus)
end

local function L(k)
    local t = is_chinese_ui() and ZH or EN
    return t[k] or EN[k] or k
end

-- ---------------------------------------------------------------- Logging & Paths
local log_dir, log_file
local candidates = {{}}
local app = ok_call(os.getenv, 'APPDATA')
local loc = ok_call(os.getenv, 'LOCALAPPDATA')
local tmp = ok_call(os.getenv, 'TEMP')

if loc then
    candidates[#candidates + 1] = loc .. '/MDL/Helldivers2/StimMusic'
    candidates[#candidates + 1] = loc .. '/MDL/Helldivers2'
    candidates[#candidates + 1] = loc .. '/CowboyBingus/Helldivers2/StimMusic'
    candidates[#candidates + 1] = loc .. '/MDL3/StimMusic'
end
candidates[#candidates + 1] = 'C:/ProgramData/MDL/Helldivers2/StimMusic'
candidates[#candidates + 1] = 'C:/ProgramData/MDL/Helldivers2'
if app then
    candidates[#candidates + 1] = app .. '/Arrowhead/Helldivers2/StimMusic'
end
if tmp then
    candidates[#candidates + 1] = tmp .. '/StimMusic'
end

for _, d in ipairs(candidates) do
    local f = io.open(d .. '/stim_music.log', 'a')
    if f then
        log_dir, log_file = d, f
        break
    end
end

local function log_msg(line)
    if not log_file then return end
    pcall(function()
        log_file:write(line, '\\n')
        log_file:flush()
    end)
end

local function log_fmt(fmt, ...)
    log_msg(string.format(fmt, ...))
end

log_fmt('=== StimMusic v%s (MDL3 + HD2 Data Hub) outdir=%s ===', VERSION, tostring(log_dir))

-- ---------------------------------------------------------------- Fingerprinting

local function get_file_fingerprint(path)
    if not path then return nil end
    local f = io.open(path, 'rb')
    if not f then return nil end
    local sz = f:seek('end') or 0
    local head = ''
    if sz > 0 then
        f:seek('set', 0)
        head = f:read(math.min(36, sz)) or ''
    end
    f:close()
    return tostring(sz) .. ':' .. tostring(head)
end

-- ---------------------------------------------------------------- Mod State
local M = {{
    version = VERSION,
    active = true,
    clock = 0,
    options_bound = false,
    config_ini_fp = nil,
    
    -- Hub state:
    hub_ref = nil,
    hub_version = 'unknown',
    hub_state = 'waiting_for_hub',
    hub_reason = nil,
    subs = {{}},
    
    -- Gameplay tracking:
    last_health = nil,
    last_stims = nil,
    last_alive = true,
    last_stim_consumed_clock = 0,
    
    -- Stim effect & playback timing:
    stim_active = false,
    stim_extended = false,
    is_playing = false,
    stim_end_clock = 0,
    play_start_clock = 0,
    play_start_pos = 0.0,
    cue_duration = 0.0,
    track_pos = 0.0,
    cue_idx = 0,
    current_key = nil,
    playing_ns = nil,
    play_retry_key = nil,
    play_retry_ns = nil,
    play_retry_dur = nil,
    play_retry_pos = nil,
    play_retry_clock = 0,
    play_retries = 0,
    
    -- Pre-uploaded idle cue:
    prepared_key = nil,
    prepared_dur = nil,
    prepared_ns = nil,
    prepared_pos = nil,
    next_prepare_clock = 0,
    
    -- Audio system:
    audio_format_defined = false,
    audio_api_probed = false,
    ns_slot = 0,
    current_ns = nil,
    audio_track_path = nil,
    audio_track_fp = nil,
    audio_track_filename = nil,
    audio_info = nil,
    using_default = false,
    track_gen = 0,
    
    -- Statistics:
    stims_count = 0,
    heals_count = 0,
    next_status_clock = 0,
    next_hot_reload_clock = 0,
    last_status_verdict = 'INITIALIZING',
}}
rawset(_G, KEY, M)

local function load_ini_config()
    if not log_dir then return end
    local p = log_dir .. '/STIM_MUSIC_CONFIG.ini'
    local f = io.open(p, 'r')
    if not f then
        local wf = io.open(p, 'w')
        if wf then
            wf:write('# StimMusic configuration\\n')
            wf:write('enabled = 1\\n')
            wf:write('volume = 100\\n')
            wf:write('stim_ms = 6000\\n')
            wf:write('fade_in_ms = 500\\n')
            wf:write('fade_out_ms = 1500\\n')
            wf:write('min_heal = 1\\n')
            wf:write('hot_reload = 1\\n')
            wf:write('track = stim_music.wav\\n')
            wf:write('language = auto\\n')
            wf:close()
            M.config_ini_fp = get_file_fingerprint(p)
        end
        return
    end
    for line in f:lines() do
        local k, v = line:match('^%s*([%w_]+)%s*=%s*(.-)%s*$')
        if k and v and not line:match('^%s*#') then
            k = k:lower()
            if k == 'enabled' then CONFIG.enabled = (v == '1' or v:lower() == 'true')
            elseif k == 'volume' then
                local val = tonumber(v)
                if val then CONFIG.volume = math.max(0, math.min(100, math.floor(val + 0.5))) end
            elseif k == 'stim_ms' then
                local val = tonumber(v)
                if val then CONFIG.stim_ms = math.max(1000, math.min(30000, math.floor(val + 0.5))) end
            elseif k == 'fade_in_ms' or k == 'fade_in' then
                local val = tonumber(v)
                if val then CONFIG.fade_in_ms = math.max(0, math.min(5000, math.floor(val + 0.5))) end
            elseif k == 'fade_out_ms' or k == 'fade_out' then
                local val = tonumber(v)
                if val then CONFIG.fade_out_ms = math.max(0, math.min(10000, math.floor(val + 0.5))) end
            elseif k == 'min_heal' then
                local val = tonumber(v)
                if val then CONFIG.min_heal = math.max(0, math.min(100, math.floor(val + 0.5))) end
            elseif k == 'hot_reload' then CONFIG.hot_reload = (v == '1' or v:lower() == 'true')
            elseif k == 'track' then CONFIG.track = v
            elseif k == 'language' or k == 'locale' then CONFIG.language = v:lower()
            end
        end
    end
    f:close()
    M.config_ini_fp = get_file_fingerprint(p)
end

local function persist_ini_config()
    if not log_dir then return end
    local p = log_dir .. '/STIM_MUSIC_CONFIG.ini'
    local f = io.open(p, 'w')
    if not f then return end
    f:write('# StimMusic configuration (Auto-saved by MDL menu)\\n')
    f:write('enabled = ', CONFIG.enabled and '1' or '0', '\\n')
    f:write('volume = ', tostring(math.floor(CONFIG.volume or 100)), '\\n')
    f:write('stim_ms = ', tostring(math.floor(CONFIG.stim_ms or 6000)), '\\n')
    f:write('fade_in_ms = ', tostring(math.floor(CONFIG.fade_in_ms or 500)), '\\n')
    f:write('fade_out_ms = ', tostring(math.floor(CONFIG.fade_out_ms or 1500)), '\\n')
    f:write('min_heal = ', tostring(math.floor(CONFIG.min_heal or 1)), '\\n')
    f:write('hot_reload = ', CONFIG.hot_reload and '1' or '0', '\\n')
    f:write('track = ', tostring(CONFIG.track or 'stim_music.wav'), '\\n')
    f:write('language = ', tostring(CONFIG.language or 'auto'), '\\n')
    f:close()
    M.config_ini_fp = get_file_fingerprint(p)
end

load_ini_config()

-- ---------------------------------------------------------------- Base64 & Audio Utils
local B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local B64_T = {{}}
for i = 1, #B64 do B64_T[i-1] = B64:sub(i, i) end

local function b64_encode(data)
    local out = {{}}
    local len = #data
    local rem = len % 3
    local full = len - rem
    local floor = math.floor
    local byte = string.byte
    local n = 0
    for i = 1, full, 3 do
        local b1, b2, b3 = byte(data, i, i + 2)
        local c1 = floor(b1 / 4)
        local c2 = (b1 % 4) * 16 + floor(b2 / 16)
        local c3 = (b2 % 16) * 4 + floor(b3 / 64)
        local c4 = b3 % 64
        n = n + 1
        out[n] = B64_T[c1] .. B64_T[c2] .. B64_T[c3] .. B64_T[c4]
    end
    if rem == 1 then
        local b1 = byte(data, len)
        out[n + 1] = B64_T[floor(b1 / 4)] .. B64_T[(b1 % 4) * 16] .. '=='
    elseif rem == 2 then
        local b1, b2 = byte(data, len - 1, len)
        out[n + 1] = B64_T[floor(b1 / 4)] .. B64_T[(b1 % 4) * 16 + floor(b2 / 16)] .. B64_T[(b2 % 16) * 4] .. '='
    end
    return table.concat(out)
end

local B64_REV = {{}}
for i = 1, #B64 do B64_REV[B64:byte(i)] = i - 1 end

local function b64_decode(data)
    data = data:gsub('[^A-Za-z0-9+/=]', '')
    local out = {{}}
    local len = #data
    local char = string.char
    local floor = math.floor
    local n = 0
    for i = 1, len, 4 do
        local b1 = data:byte(i)
        local b2 = data:byte(i+1)
        local b3 = data:byte(i+2)
        local b4 = data:byte(i+3)
        if not b1 or not b2 then break end
        local a = B64_REV[b1] or 0
        local b = B64_REV[b2] or 0
        local c = (b3 and b3 ~= 61) and B64_REV[b3] or nil
        local d = (b4 and b4 ~= 61) and B64_REV[b4] or nil
        
        n = n + 1
        out[n] = char((a * 4 + floor(b / 16)) % 256)
        if c then
            n = n + 1
            out[n] = char(((b % 16) * 16 + floor(c / 4)) % 256)
            if d then
                n = n + 1
                out[n] = char(((c % 4) * 64 + d) % 256)
            end
        end
    end
    return table.concat(out)
end

local CONVERTER_CMD_B64 = '{converter_cmd_b64}'
local CONVERTER_PS1_B64 = '{converter_ps1_b64}'

local function ensure_converter_scripts()
    if not log_dir then return end
    local cmd_p = log_dir .. '/convert_track.cmd'
    local ps1_p = log_dir .. '/convert_track.ps1'
    
    local f_cmd = io.open(cmd_p, 'r')
    if not f_cmd then
        local w = io.open(cmd_p, 'wb')
        if w then
            w:write(b64_decode(CONVERTER_CMD_B64))
            w:close()
            log_fmt('Auto-deployed converter script: %s', cmd_p)
        end
    else
        f_cmd:close()
    end
    
    local f_ps1 = io.open(ps1_p, 'r')
    if not f_ps1 then
        local w = io.open(ps1_p, 'wb')
        if w then
            w:write(b64_decode(CONVERTER_PS1_B64))
            w:close()
            log_fmt('Auto-deployed converter script: %s', ps1_p)
        end
    else
        f_ps1:close()
    end
end

ensure_converter_scripts()

local function le16(s, i)
    local a, b = s:byte(i, i + 1)
    if not a or not b then return 0 end
    return a + b * 256
end

local function le32(s, i)
    local a, b, c, d = s:byte(i, i + 3)
    if not a or not d then return 0 end
    return a + b * 256 + c * 65536 + d * 16777216
end

local function pack16(v)
    v = math.floor(v) % 65536
    return string.char(v % 256, math.floor(v / 256) % 256)
end

local function pack32(v)
    v = math.floor(v) % 4294967296
    local b0 = v % 256
    local b1 = math.floor(v / 256) % 256
    local b2 = math.floor(v / 65536) % 256
    local b3 = math.floor(v / 16777216) % 256
    return string.char(b0, b1, b2, b3)
end

local function apply_pcm_fade(raw, channels, rate, fade_in_sec, fade_out_sec)
    local floor = math.floor
    local byte = string.byte
    local char = string.char
    
    local bytes_per_sample = 2
    local frame_size = (channels or 1) * bytes_per_sample
    local total_len = #raw
    local total_frames = floor(total_len / frame_size)
    if total_frames <= 0 then return raw end
    
    local in_frames = floor((fade_in_sec or 0) * rate)
    local out_frames = floor((fade_out_sec or 0) * rate)
    
    if in_frames > total_frames then in_frames = total_frames end
    if out_frames > total_frames then out_frames = total_frames end
    if (in_frames + out_frames) > total_frames and total_frames > 0 then
        local ratio = total_frames / (in_frames + out_frames)
        in_frames = floor(in_frames * ratio)
        out_frames = total_frames - in_frames
    end
    
    if in_frames <= 0 and out_frames <= 0 then
        return raw
    end
    
    local out_parts = {{}}
    local part_n = 0
    
    if in_frames > 0 then
        local in_t = {{}}
        for f = 1, in_frames do
            local gain = f / in_frames
            local base = (f - 1) * frame_size + 1
            if channels == 1 then
                local b0, b1 = byte(raw, base, base + 1)
                local s = b0 + b1 * 256
                if s >= 32768 then s = s - 65536 end
                s = floor(s * gain + 0.5)
                if s < -32768 then s = -32768 elseif s > 32767 then s = 32767 end
                if s < 0 then s = s + 65536 end
                in_t[f] = char(s % 256, floor(s / 256) % 256)
            else
                local b0, b1, b2, b3 = byte(raw, base, base + 3)
                local s1 = b0 + b1 * 256
                if s1 >= 32768 then s1 = s1 - 65536 end
                s1 = floor(s1 * gain + 0.5)
                if s1 < -32768 then s1 = -32768 elseif s1 > 32767 then s1 = 32767 end
                if s1 < 0 then s1 = s1 + 65536 end
                
                local s2 = b2 + b3 * 256
                if s2 >= 32768 then s2 = s2 - 65536 end
                s2 = floor(s2 * gain + 0.5)
                if s2 < -32768 then s2 = -32768 elseif s2 > 32767 then s2 = 32767 end
                if s2 < 0 then s2 = s2 + 65536 end
                
                in_t[f] = char(s1 % 256, floor(s1 / 256) % 256, s2 % 256, floor(s2 / 256) % 256)
            end
        end
        part_n = part_n + 1
        out_parts[part_n] = table.concat(in_t)
    end
    
    local mid_start_byte = in_frames * frame_size + 1
    local mid_end_byte = (total_frames - out_frames) * frame_size
    if mid_start_byte <= mid_end_byte then
        part_n = part_n + 1
        out_parts[part_n] = raw:sub(mid_start_byte, mid_end_byte)
    end
    
    if out_frames > 0 then
        local out_t = {{}}
        local start_frame = total_frames - out_frames + 1
        for f = 1, out_frames do
            local gain = (out_frames - f) / out_frames
            local cur_frame = start_frame + f - 1
            local base = (cur_frame - 1) * frame_size + 1
            if channels == 1 then
                local b0, b1 = byte(raw, base, base + 1)
                local s = b0 + b1 * 256
                if s >= 32768 then s = s - 65536 end
                s = floor(s * gain + 0.5)
                if s < -32768 then s = -32768 elseif s > 32767 then s = 32767 end
                if s < 0 then s = s + 65536 end
                out_t[f] = char(s % 256, floor(s / 256) % 256)
            else
                local b0, b1, b2, b3 = byte(raw, base, base + 3)
                local s1 = b0 + b1 * 256
                if s1 >= 32768 then s1 = s1 - 65536 end
                s1 = floor(s1 * gain + 0.5)
                if s1 < -32768 then s1 = -32768 elseif s1 > 32767 then s1 = 32767 end
                if s1 < 0 then s1 = s1 + 65536 end
                
                local s2 = b2 + b3 * 256
                if s2 >= 32768 then s2 = s2 - 65536 end
                s2 = floor(s2 * gain + 0.5)
                if s2 < -32768 then s2 = -32768 elseif s2 > 32767 then s2 = 32767 end
                if s2 < 0 then s2 = s2 + 65536 end
                
                out_t[f] = char(s1 % 256, floor(s1 / 256) % 256, s2 % 256, floor(s2 / 256) % 256)
            end
        end
        part_n = part_n + 1
        out_parts[part_n] = table.concat(out_t)
    end
    
    return table.concat(out_parts)
end

local DEFAULT_WFX_B64 = '{default_fmt_b64}'
local DEFAULT_AUDIO_B64 = 
{b64_literal}

local function parse_wav(path)
    local f = io.open(path, 'rb')
    if not f then return nil, 'cannot open file' end
    local head = f:read(12)
    if not head or #head < 12 or head:sub(1,4) ~= 'RIFF' or head:sub(9,12) ~= 'WAVE' then
        f:close()
        return nil, 'not a valid RIFF/WAVE file'
    end
    local tag, ch, rate, avg, align, bits
    local data_pos, data_size
    local raw_fmt = nil
    while true do
        local chunk = f:read(8)
        if not chunk or #chunk < 8 then break end
        local cid = chunk:sub(1, 4)
        local csize = le32(chunk, 5)
        local pad = csize % 2
        if cid == 'fmt ' then
            local fmt_bytes = f:read(csize)
            if not fmt_bytes or #fmt_bytes < 16 then f:close(); return nil, 'bad fmt chunk' end
            raw_fmt = fmt_bytes
            tag = le16(fmt_bytes, 1)
            ch = le16(fmt_bytes, 3)
            rate = le32(fmt_bytes, 5)
            avg = le32(fmt_bytes, 9)
            align = le16(fmt_bytes, 13)
            bits = le16(fmt_bytes, 15)
            if pad > 0 then f:read(pad) end
        elseif cid == 'data' then
            data_pos = f:seek()
            data_size = csize
            break
        else
            f:seek('cur', csize + pad)
        end
    end
    f:close()
    if not tag or not data_pos or not raw_fmt then return nil, 'missing fmt or data chunk' end
    if tag ~= 1 and tag ~= 2 then
        return nil, string.format('unsupported format tag %d (only 1=PCM, 2=MS-ADPCM supported)', tag)
    end
    if tag == 1 and bits ~= 16 then
        return nil, string.format('PCM must be 16-bit (got %d-bit)', bits)
    end
    if tag == 2 and bits ~= 4 then
        return nil, string.format('MS-ADPCM must be 4-bit (got %d-bit)', bits)
    end

    local wfx_b64
    if tag == 2 then
        -- Preserve authentic 50-byte ADPCMWAVEFORMAT header with cbSize and coefficient table
        wfx_b64 = b64_encode(raw_fmt)
    else
        -- Standard 16-bit PCM: ensure exactly 18-byte WAVEFORMATEX with cbSize=0
        local wfx
        if #raw_fmt >= 18 then
            wfx = raw_fmt:sub(1, 18)
        else
            wfx = raw_fmt:sub(1, 16) .. pack16(0)
        end
        wfx_b64 = b64_encode(wfx)
    end

    local dur = (avg and avg > 0) and (data_size / avg) or 0
    return {{
        path = path,
        tag = tag,
        channels = ch,
        rate = rate,
        avg = avg,
        align = align,
        bits = bits,
        data_pos = data_pos,
        data_size = data_size,
        wfx_b64 = wfx_b64,
        duration = dur,
    }}
end

local function read_wav_slice(info, start_sec, duration_sec, fade_in_sec, fade_out_sec)
    local f = io.open(info.path, 'rb')
    if not f then return nil, 0 end
    local start_byte = math.floor(start_sec * info.avg)
    start_byte = start_byte - (start_byte % info.align)
    if start_byte >= info.data_size then f:close(); return nil, 0 end

    local slice_bytes = math.floor(duration_sec * info.avg)
    slice_bytes = slice_bytes - (slice_bytes % info.align)
    if start_byte + slice_bytes > info.data_size then
        slice_bytes = info.data_size - start_byte
        slice_bytes = slice_bytes - (slice_bytes % info.align)
    end
    if slice_bytes <= 0 then f:close(); return nil, 0 end

    f:seek('set', info.data_pos + start_byte)
    local raw = f:read(slice_bytes)
    f:close()
    if not raw or #raw < slice_bytes then return nil, 0 end
    
    if info.tag == 1 and info.bits == 16 then
        raw = apply_pcm_fade(raw, info.channels, info.rate, fade_in_sec, fade_out_sec)
    end
    
    local actual_duration = slice_bytes / info.avg
    return b64_encode(raw), actual_duration
end

-- ---------------------------------------------------------------- Audio Driver
local ROLE = 'stim'
local NS_RING = {{
    ADDON_ID .. '_a',
    ADDON_ID .. '_b',
    ADDON_ID .. '_c',
    ADDON_ID .. '_d',
}}

local function get_audio_service()
    local mdl3 = rawget(_G, 'MDL3')
    local A = type(mdl3) == 'table' and mdl3.audio or nil
    if type(A) == 'table' and A.api == 1 and type(A.play) == 'function' then
        return A
    end
    return nil
end

local function scan_available_tracks()
    local list = {{}}
    local seen = {{}}
    local function add(name)
        if name and name ~= '' and not seen[name] then
            seen[name] = true
            list[#list + 1] = name
        end
    end
    if CONFIG.track and CONFIG.track ~= '' then
        local base = CONFIG.track:match('([^/\\\\]+%.wav)$') or CONFIG.track
        add(base)
    end
    local known = {{
        'stim_music.wav',
        'stim_music_alt.wav',
        'yu_ai.wav',
        'pao_mo.wav',
        'pi_pa.wav',
        'music.wav',
        'bgm.wav',
        'stim.wav',
        'heal.wav',
    }}
    for _, name in ipairs(known) do
        local found = false
        if log_dir then
            local f = io.open(log_dir .. '/' .. name, 'rb')
            if f then f:close(); found = true end
        end
        if not found then
            for _, d in ipairs(candidates) do
                local f = io.open(d .. '/' .. name, 'rb')
                if f then f:close(); found = true; break end
            end
        end
        if found then
            add(name)
        end
    end
    if #list == 0 then
        list[1] = '[embedded default]'
    end
    return list
end

local function locate_music_file()
    if CONFIG.track and CONFIG.track ~= '' then
        local paths = {{}}
        if log_dir then paths[#paths + 1] = log_dir .. '/' .. CONFIG.track end
        paths[#paths + 1] = CONFIG.track
        for _, p in ipairs(paths) do
            local f = io.open(p, 'rb')
            if f then f:close(); return p end
        end
    end
    for _, d in ipairs(candidates) do
        local p = d .. '/stim_music.wav'
        local f = io.open(p, 'rb')
        if f then f:close(); return p end
    end
    if log_dir then
        local names = {{ 'stim_music.wav', 'stim_music_alt.wav', 'yu_ai.wav', 'pao_mo.wav', 'pi_pa.wav' }}
        for _, n in ipairs(names) do
            local p = log_dir .. '/' .. n
            local f = io.open(p, 'rb')
            if f then f:close(); return p end
        end
    end
    return nil
end

local function probe_audio_api(A, ns)
    if M.audio_api_probed or not A then return end
    M.audio_api_probed = true
    log_fmt('=== MDL3 Audio API Diagnostics ===')
    for k, v in pairs(A) do
        log_fmt('  MDL3.audio.%s = %s (%s)', tostring(k), type(v), tostring(v))
    end
    if type(A.status) == 'function' and ns then
        local ok, st = pcall(A.status, ns)
        if ok and type(st) == 'table' then
            for k, v in pairs(st) do
                log_fmt('  status(%s).%s = %s (%s)', ns, tostring(k), type(v), tostring(v))
            end
        else
            log_fmt('  status(%s) returned: ok=%s, res=%s', ns, tostring(ok), tostring(st))
        end
    end
    log_fmt('==================================')
end

local function prepare_cue_for_pos(target_pos, req_duration, do_fade_in, do_fade_out)
    local A = get_audio_service()
    local ns = M.current_ns
    if not A or not ns then return nil, 0 end

    local stim_sec = req_duration or math.max(1.0, (CONFIG.stim_ms or 6000) / 1000)
    if do_fade_in == nil then do_fade_in = true end
    if do_fade_out == nil then do_fade_out = true end
    
    local in_sec = do_fade_in and math.max(0, (CONFIG.fade_in_ms or 500) / 1000) or 0
    local out_sec = do_fade_out and math.max(0, (CONFIG.fade_out_ms or 1500) / 1000) or 0
    
    if M.using_default or not M.audio_info then
        M.cue_idx = (M.cue_idx or 0) + 1
        local key = 's' .. M.track_gen .. '_' .. M.cue_idx
        A.upload(ns, key, DEFAULT_AUDIO_B64)
        return key, 4.0, ns, 0.0
    end

    local total_dur = M.audio_info.duration
    if total_dur <= 0 then return nil, 0 end

    target_pos = target_pos % total_dur
    if (total_dur - target_pos) < 0.1 then
        target_pos = 0.0
    end

    local slice_dur = math.min(stim_sec, total_dur - target_pos)
    local b64_data, actual_dur = read_wav_slice(M.audio_info, target_pos, slice_dur, in_sec, out_sec)
    if not b64_data or actual_dur <= 0 then
        target_pos = 0.0
        slice_dur = math.min(stim_sec, total_dur)
        b64_data, actual_dur = read_wav_slice(M.audio_info, 0.0, slice_dur, in_sec, out_sec)
    end
    if not b64_data then return nil, 0 end

    M.cue_idx = (M.cue_idx or 0) + 1
    local key = 's' .. M.track_gen .. '_' .. M.cue_idx
    local ok, why = A.upload(ns, key, b64_data)
    if not ok then
        log_fmt('Upload failed for %s on %s: %s', key, ns, tostring(why))
        return nil, 0
    end

    return key, actual_dur, ns, target_pos
end

local function init_audio_track()
    local A = get_audio_service()
    if not A then return false end
    
    -- Stop previous audio and release previous namespace assets
    local old_ns = M.current_ns
    if old_ns then
        pcall(A.stop, old_ns, ROLE)
        if type(A.release) == 'function' then
            pcall(A.release, old_ns)
        end
    end
    
    -- Advance to next rotating namespace to avoid collision with in-progress native release
    M.ns_slot = ((M.ns_slot or 0) % #NS_RING) + 1
    M.current_ns = NS_RING[M.ns_slot]
    local current_ns = M.current_ns
    
    M.track_gen = (M.track_gen or 0) + 1
    M.stim_active = false
    M.stim_extended = false
    M.is_playing = false
    M.track_pos = 0.0
    M.play_start_clock = 0.0
    M.play_start_pos = 0.0
    M.cue_duration = 0.0
    M.cue_idx = 0
    M.current_key = nil
    M.playing_ns = nil
    M.play_retry_key = nil
    M.play_retries = 0
    M.prepared_key = nil
    M.prepared_dur = nil
    M.prepared_ns = nil
    M.prepared_pos = nil
    M.next_prepare_clock = 0
    
    local path = locate_music_file()
    if path then
        local info, err = parse_wav(path)
        if info then
            M.audio_track_path = path
            M.audio_track_fp = get_file_fingerprint(path)
            M.audio_track_filename = path:match('([^/\\\\]+%.wav)$') or path
            M.audio_info = info
            M.using_default = false
            
            local ok_f, why_f = A.define_format(current_ns, info.wfx_b64)
            if not ok_f then log_fmt('define_format failed for %s: %s', current_ns, tostring(why_f)) end
            local ok_p, why_p = A.pool(current_ns, {{ [ROLE] = 2 }})
            if not ok_p then log_fmt('pool failed for %s: %s', current_ns, tostring(why_p)) end
            
            probe_audio_api(A, current_ns)
            
            local fmt_name = (info.tag == 2) and 'MS-ADPCM' or 'PCM-16'
            log_fmt('Audio track loaded: %s on ns=%s (fmt=%s, gen=%d, %.1fs, %d channels, %d Hz)',
                path, current_ns, fmt_name, M.track_gen, info.duration, info.channels, info.rate)
            
            local key, dur, ns, pos = prepare_cue_for_pos(0.0, nil, true, true)
            if key then
                M.prepared_key = key
                M.prepared_dur = dur
                M.prepared_ns = ns
                M.prepared_pos = pos
                log_fmt('Pre-buffered initial cue for %s: %s on %s', M.audio_track_filename, key, ns)
            end
            return true
        else
            log_fmt('WAV parse error (%s): %s', tostring(path), tostring(err))
        end
    end
    
    -- Fall back to embedded default
    M.audio_track_path = nil
    M.audio_track_fp = nil
    M.audio_track_filename = '[embedded default]'
    M.audio_info = nil
    M.using_default = true
    
    A.define_format(current_ns, DEFAULT_WFX_B64)
    A.pool(current_ns, {{ [ROLE] = 2 }})
    probe_audio_api(A, current_ns)
    
    M.cue_idx = 1
    local def_key = 's' .. M.track_gen .. '_1'
    A.upload(current_ns, def_key, DEFAULT_AUDIO_B64)
    M.prepared_key = def_key
    M.prepared_dur = 4.0
    M.prepared_ns = current_ns
    M.prepared_pos = 0.0
    log_fmt('Using embedded default stim audio on ns=%s (key=%s)', current_ns, def_key)
    return true
end

-- ---------------------------------------------------------------- Stim Music Actions
local function start_stim_playback(is_chain)
    if not CONFIG.enabled then return false end
    local A = get_audio_service()
    if not A then return false end
    
    local vol = math.max(0, math.min(100, math.floor((CONFIG.volume or 100) + 0.5)))
    if vol <= 0 then return false end
    
    local key, dur, ns, actual_pos
    if not is_chain and M.prepared_key and M.prepared_ns == M.current_ns and math.abs((M.prepared_pos or 0) - (M.track_pos or 0)) < 0.05 then
        key = M.prepared_key
        dur = M.prepared_dur
        ns = M.prepared_ns
        actual_pos = M.prepared_pos
        M.prepared_key = nil
        M.prepared_dur = nil
        M.prepared_ns = nil
        M.prepared_pos = nil
    else
        local req_dur = nil
        if is_chain and M.stim_end_clock and M.stim_end_clock > M.clock then
            req_dur = math.max(1.0, math.min(10.0, M.stim_end_clock - M.clock))
        end
        local do_in = not is_chain
        key, dur, ns, actual_pos = prepare_cue_for_pos(M.track_pos or 0.0, req_dur, do_in, true)
    end
    
    if not key or not ns then
        log_fmt('Cannot start stim music: cue preparation failed for pos=%.2f', M.track_pos or 0.0)
        return false
    end
    
    local ok, played = pcall(A.play, ns, key, {{ role = ROLE, volume = vol }})
    if ok and played == true then
        M.is_playing = true
        M.play_start_clock = M.clock
        M.play_start_pos = actual_pos or (M.track_pos or 0.0)
        M.cue_duration = dur or 6.0
        M.current_key = key
        M.playing_ns = ns
        M.play_retry_key = nil
        M.play_retries = 0
        M.stims_count = M.stims_count + 1
        local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
        M.last_status_verdict = string.format('PLAYING - at %.1fs / %.1fs (vol=%d%%)', M.play_start_pos, total_dur, vol)
        log_fmt('Stim music started: %s on %s from pos=%.2fs (vol=%d, dur=%.1fs, stim#=%d, chain=%s)',
            key, ns, M.play_start_pos, vol, dur, M.stims_count, tostring(is_chain == true))
        return true
    else
        M.is_playing = false
        local retries = (M.play_retries or 0) + 1
        M.play_retries = retries
        if retries == 1 or retries % 10 == 0 then
            log_fmt('Stim play retry for %s on %s (vol=%d, ok=%s, played=%s, retry #%d)',
                key, ns, vol, tostring(ok), tostring(played), retries)
        end
        M.play_retry_key = key
        M.play_retry_ns = ns
        M.play_retry_dur = dur
        M.play_retry_pos = actual_pos
        M.play_retry_clock = M.clock + 0.1
        return false
    end
end

local function stop_stim_playback(reason)
    if not M.stim_active and not M.is_playing and not M.play_retry_key then return end
    
    local elapsed = 0.0
    if M.is_playing and M.play_start_clock and M.play_start_clock > 0 then
        elapsed = math.max(0.0, M.clock - M.play_start_clock)
        if M.cue_duration and elapsed > M.cue_duration then
            elapsed = M.cue_duration
        end
    end
    
    local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
    if total_dur > 0 then
        M.track_pos = ((M.play_start_pos or 0.0) + elapsed) % total_dur
    else
        M.track_pos = 0.0
    end
    
    M.stim_active = false
    M.stim_extended = false
    M.is_playing = false
    M.play_retry_key = nil
    M.play_retries = 0
    
    local A = get_audio_service()
    local ns = M.playing_ns or M.current_ns
    if A and ns then
        pcall(A.stop, ns, ROLE)
    end
    
    if M.prepared_pos and math.abs(M.prepared_pos - M.track_pos) >= 0.05 then
        M.prepared_key = nil
        M.prepared_dur = nil
        M.prepared_ns = nil
        M.prepared_pos = nil
    end
    
    M.last_status_verdict = string.format('PAUSED - at %.2fs / %.1fs', M.track_pos, total_dur)
    log_fmt('Stim music stopped (%s): paused at %.2fs / %.1fs (played %.2fs)',
        tostring(reason or 'stim_end'), M.track_pos, total_dur, elapsed)
end

-- ---------------------------------------------------------------- Status Snapshot
local function write_status_snapshot()
    if not log_dir then return end
    local p = log_dir .. '/STIM_MUSIC_STATUS.txt'
    local f = io.open(p, 'w')
    if not f then return end
    
    local remaining_ms = M.stim_active and math.floor(math.max(0, M.stim_end_clock - M.clock) * 1000) or -1
    local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
    
    f:write('verdict=', M.last_status_verdict, '\\n')
    f:write('revision=', VERSION, '\\n')
    f:write('enabled=', tostring(CONFIG.enabled), '\\n')
    f:write('stim_ms=', tostring(CONFIG.stim_ms), '\\n')
    f:write('fade_in_ms=', tostring(CONFIG.fade_in_ms), '\\n')
    f:write('fade_out_ms=', tostring(CONFIG.fade_out_ms), '\\n')
    f:write('volume=', tostring(CONFIG.volume), '\\n')
    f:write('min_heal=', tostring(CONFIG.min_heal), '\\n')
    f:write('hot_reload=', tostring(CONFIG.hot_reload), '\\n')
    f:write('folder=', tostring(log_dir), '\\n')
    f:write('namespace=', tostring(M.current_ns or 'none'), '\\n')
    f:write('track=', tostring(M.audio_track_path or '[embedded default]'), '\\n')
    f:write('filename=', tostring(M.audio_track_filename or 'none'), '\\n')
    f:write('using_default=', tostring(M.using_default), '\\n')
    f:write('track_pos_sec=', string.format('%.2f', M.track_pos or 0.0), '\\n')
    f:write('track_duration_sec=', string.format('%.2f', total_dur), '\\n')
    f:write('stim_active=', tostring(M.stim_active), '\\n')
    f:write('is_playing=', tostring(M.is_playing), '\\n')
    f:write('stim_remaining_ms=', tostring(remaining_ms), '\\n')
    f:write('stims_count=', tostring(M.stims_count), '\\n')
    f:write('heals_count=', tostring(M.heals_count), '\\n')
    f:write('hub_state=', tostring(M.hub_state), '\\n')
    f:write('hub_version=', tostring(M.hub_version), '\\n')
    f:close()
end

-- ---------------------------------------------------------------- Mod Options Menu
local function find_options_api()
    local mom = rawget(_G, 'ModOptionsMenu')
    if type(mom) == 'table' and type(mom.register_option) == 'function' then return mom end
    local mdl = rawget(_G, 'MDL3')
    local compat = type(mdl) == 'table' and (mdl.mod_options_menu or mdl.mod_options) or nil
    if type(compat) == 'table' and type(compat.register_option) == 'function' then return compat end
    return nil
end

local function bind_mod_options()
    if M.options_bound then return end
    local MOM = find_options_api()
    if not MOM then return end
    M.options_bound = true

    local function reg(key, spec, apply_fn)
        local id = 'kugua_stim_music.' .. key
        spec.mod_id = ADDON_ID
        spec.mod = L('mod_title')
        local ok = ok_call(MOM.register_option, id, spec)
        if not ok then return end
        if type(MOM.get) == 'function' then
            local saved = ok_call(MOM.get, id)
            if saved ~= nil then apply_fn(saved) end
        end
        if type(MOM.on_change) == 'function' then
            ok_call(MOM.on_change, id, function(val)
                apply_fn(val)
            end)
        end
    end

    reg('enabled', {{
        type = 'toggle', default = CONFIG.enabled,
        label = L('opt_enabled'), description = L('opt_enabled_desc'),
    }}, function(v)
        local val = nil
        if type(v) == 'boolean' then val = v
        elseif type(v) == 'string' then val = (v:lower() == 'true' or v == '1')
        elseif type(v) == 'number' then val = (v ~= 0)
        end
        if val ~= nil and val ~= CONFIG.enabled then
            CONFIG.enabled = val
            log_fmt('Enabled set to %s', tostring(val))
            if not val and (M.stim_active or M.is_playing) then
                stop_stim_playback('disabled')
            end
            write_status_snapshot()
            persist_ini_config()
        end
    end)

    local tracks = scan_available_tracks()
    local default_idx = 1
    local cur_name = M.audio_track_filename or (M.audio_track_path and M.audio_track_path:match('([^/\\\\]+%.wav)$')) or CONFIG.track or 'stim_music.wav'
    for i, name in ipairs(tracks) do
        if name:lower() == cur_name:lower() then
            default_idx = i
            break
        end
    end

    reg('track', {{
        type = 'choice',
        choices = tracks,
        default = default_idx,
        label = L('opt_track'),
        description = L('opt_track_desc'),
    }}, function(v)
        local chosen = nil
        if type(v) == 'number' then
            chosen = tracks[v]
        elseif type(v) == 'string' then
            chosen = v
        end
        if chosen and chosen ~= '' then
            local target = chosen:find('^%[') and '' or chosen
            if target ~= CONFIG.track then
                CONFIG.track = target
                log_fmt('Menu switched track to: %s', chosen)
                init_audio_track()
                write_status_snapshot()
                persist_ini_config()
                M.next_hot_reload_clock = M.clock + 3.0
            end
        end
    end)

    reg('volume', {{
        type = 'slider', min = 0, max = 100, step = 5, default = CONFIG.volume,
        label = L('opt_volume'), description = L('opt_volume_desc'),
    }}, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(0, math.min(100, math.floor(num + 0.5)))
            if num ~= CONFIG.volume then
                CONFIG.volume = num
                log_fmt('Volume set to %d%%', CONFIG.volume)
                if num == 0 and (M.stim_active or M.is_playing) then
                    stop_stim_playback('mute')
                end
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('stim_ms', {{
        type = 'slider', min = 2000, max = 8000, step = 250, default = CONFIG.stim_ms,
        label = L('opt_stim_ms'), description = L('opt_stim_ms_desc'),
    }}, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(1000, math.min(30000, math.floor(num + 0.5)))
            if num ~= CONFIG.stim_ms then
                CONFIG.stim_ms = num
                log_fmt('Stim duration set to %dms', CONFIG.stim_ms)
                if M.stim_active and M.is_playing then
                    local new_dur = num / 1000
                    M.stim_end_clock = (M.play_start_clock or M.clock) + new_dur
                    log_fmt('Live stim end adjusted to clock=%.2f (%.2fs left)',
                        M.stim_end_clock, math.max(0, M.stim_end_clock - M.clock))
                end
                M.prepared_key = nil
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('fade_in_ms', {{
        type = 'slider', min = 0, max = 3000, step = 100, default = CONFIG.fade_in_ms,
        label = L('opt_fade_in'), description = L('opt_fade_in_desc'),
    }}, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(0, math.min(5000, math.floor(num + 0.5)))
            if num ~= CONFIG.fade_in_ms then
                CONFIG.fade_in_ms = num
                log_fmt('Fade-in duration set to %dms', CONFIG.fade_in_ms)
                M.prepared_key = nil
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('fade_out_ms', {{
        type = 'slider', min = 0, max = 4000, step = 100, default = CONFIG.fade_out_ms,
        label = L('opt_fade_out'), description = L('opt_fade_out_desc'),
    }}, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(0, math.min(10000, math.floor(num + 0.5)))
            if num ~= CONFIG.fade_out_ms then
                CONFIG.fade_out_ms = num
                log_fmt('Fade-out duration set to %dms', CONFIG.fade_out_ms)
                M.prepared_key = nil
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('min_heal', {{
        type = 'slider', min = 1, max = 50, step = 1, default = CONFIG.min_heal,
        label = L('opt_min_heal'), description = L('opt_min_heal_desc'),
    }}, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(0, math.min(100, math.floor(num + 0.5)))
            if num ~= CONFIG.min_heal then
                CONFIG.min_heal = num
                log_fmt('Min heal set to %d', CONFIG.min_heal)
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('hot_reload', {{
        type = 'toggle', default = CONFIG.hot_reload,
        label = L('opt_hot_reload'), description = L('opt_hot_reload_desc'),
    }}, function(v)
        local val = nil
        if type(v) == 'boolean' then val = v
        elseif type(v) == 'string' then val = (v:lower() == 'true' or v == '1')
        elseif type(v) == 'number' then val = (v ~= 0)
        end
        if val ~= nil and val ~= CONFIG.hot_reload then
            CONFIG.hot_reload = val
            log_fmt('Hot reload set to %s', tostring(val))
            write_status_snapshot()
            persist_ini_config()
        end
    end)

    log_msg('Mod options bound successfully with ModOptionsMenu.')
end

-- ---------------------------------------------------------------- HD2Data Event Loop
local function unsubscribe_all()
    for name, sub in pairs(M.subs) do
        if type(sub) == 'table' and type(sub.unsubscribe) == 'function' then
            pcall(sub.unsubscribe, sub)
        end
    end
    M.subs = {{}}
end

local function on_mission_started(ev)
    M.last_health = nil
    M.last_stims = nil
    M.stim_active = false
    M.track_pos = 0.0
    M.prepared_key = nil
    log_msg('Mission started: stim music position reset to 0.0s.')
end

local function on_mission_ended(ev)
    stop_stim_playback('mission_ended')
    M.last_health = nil
    M.last_stims = nil
    log_msg('Mission ended: stim playback stopped.')
end

local function on_entity_died(ev)
    if ev and ev.avatar and ev.local_killer then
        stop_stim_playback('entity_died')
    end
end

local EVENT_HANDLERS = {{
    {{ 'mission_started', on_mission_started }},
    {{ 'mission_ended',   on_mission_ended   }},
    {{ 'entity_died',     on_entity_died     }},
}}

local function hub_tick()
    local D = rawget(_G, 'HD2Data')
    if D == nil then
        if M.hub_ref ~= nil then unsubscribe_all() end
        M.hub_state = 'waiting_for_hub'
        return
    end
    if type(D) ~= 'table' or tonumber(D.api) ~= 1 then
        if M.hub_ref ~= nil then unsubscribe_all() end
        M.hub_state = 'bad_api'
        return
    end

    if D ~= M.hub_ref then
        unsubscribe_all()
        M.hub_ref = D
        M.hub_version = tostring(D.version or '?')
        M.hub_state = 'ready'
        log_fmt('HD2Data bound version=%s api=%s', M.hub_version, tostring(D.api))
    end

    for _, pair in ipairs(EVENT_HANDLERS) do
        local name, fn = pair[1], pair[2]
        local sub = M.subs[name]
        local active = (type(sub) == 'table' and type(sub.active) == 'function' and sub:active() == true)
        if not active then
            local s = ok_call(D.on, name, fn, {{ owner = ADDON_ID, id = name, priority = 50 }})
            if s then M.subs[name] = s end
        end
    end
end

-- ---------------------------------------------------------------- Frame Step
local function step(dt)
    dt = tonumber(dt) or 0
    if dt < 0 then dt = 0 elseif dt > 1 then dt = 1 end
    M.clock = M.clock + dt

    if not M.options_bound then
        bind_mod_options()
    end

    hub_tick()

    -- Audio initialization / hot reload
    if not M.audio_format_defined then
        if init_audio_track() then
            M.audio_format_defined = true
        end
    elseif CONFIG.hot_reload and M.clock >= M.next_hot_reload_clock then
        M.next_hot_reload_clock = M.clock + 2.0
        if log_dir then
            local ini_p = log_dir .. '/STIM_MUSIC_CONFIG.ini'
            local fp = get_file_fingerprint(ini_p)
            if fp and fp ~= '' and fp ~= M.config_ini_fp then
                M.config_ini_fp = fp
                load_ini_config()
                log_fmt('Hot reload: INI updated (vol=%d, stim_ms=%d, track=%s)',
                    CONFIG.volume or 100, CONFIG.stim_ms or 6000, tostring(CONFIG.track))
            end
        end
        local current_path = locate_music_file()
        local current_fp = get_file_fingerprint(current_path)
        if current_path ~= M.audio_track_path or current_fp ~= M.audio_track_fp then
            log_fmt('Hot reload trigger: path=%s (fp=%s, prev_fp=%s)',
                tostring(current_path), tostring(current_fp), tostring(M.audio_track_fp))
            init_audio_track()
        end
    end

    -- Step 1: Retry pending play if previous attempt was waiting for voice / buffer
    if M.play_retry_key and M.clock >= (M.play_retry_clock or 0) and M.stim_active then
        if M.clock <= M.stim_end_clock then
            local A = get_audio_service()
            if A then
                local vol = math.max(0, math.min(100, math.floor((CONFIG.volume or 100) + 0.5)))
                local ok, played = pcall(A.play, M.play_retry_ns, M.play_retry_key, {{ role = ROLE, volume = vol }})
                if ok and played == true then
                    M.is_playing = true
                    M.play_start_clock = M.clock
                    M.play_start_pos = M.play_retry_pos or (M.track_pos or 0.0)
                    M.cue_duration = M.play_retry_dur or 6.0
                    M.current_key = M.play_retry_key
                    M.playing_ns = M.play_retry_ns
                    M.play_retry_key = nil
                    M.play_retries = 0
                    M.stims_count = M.stims_count + 1
                    local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
                    M.last_status_verdict = string.format('PLAYING - at %.1fs / %.1fs (vol=%d%%)', M.play_start_pos, total_dur, vol)
                    log_fmt('Stim play retry succeeded for %s on %s', M.current_key, M.playing_ns)
                else
                    M.play_retries = (M.play_retries or 0) + 1
                    M.play_retry_clock = M.clock + 0.05
                end
            end
        else
            log_fmt('Stim window ended before retry succeeded for %s', tostring(M.play_retry_key))
            M.play_retry_key = nil
            M.play_retries = 0
        end
    end

    -- Step 2: Idle pre-upload: prepare next slice buffer while player is running around
    if not M.stim_active and not M.is_playing and M.audio_info and not M.using_default then
        if not M.prepared_key and M.clock >= (M.next_prepare_clock or 0) then
            local key, dur, ns, pos = prepare_cue_for_pos(M.track_pos or 0.0, nil, true, true)
            if key then
                M.prepared_key = key
                M.prepared_dur = dur
                M.prepared_ns = ns
                M.prepared_pos = pos
            end
            M.next_prepare_clock = M.clock + 0.5
        end
    end

    -- Gameplay polling through D.player()
    local D = M.hub_ref
    if D and type(D.player) == 'function' then
        local p = ok_call(D.player)
        if type(p) == 'table' and p.alive ~= false then
            local stim_consumed = (p.stims and M.last_stims and p.stims < M.last_stims)
            local health_gain = (p.health and M.last_health and (p.health - M.last_health) >= (CONFIG.min_heal or 1))
            local stim_triggered = false
            
            if stim_consumed then
                stim_triggered = true
                M.last_stim_consumed_clock = M.clock
                log_fmt('Stim consumed detected: %d -> %d', M.last_stims, p.stims)
            elseif health_gain then
                -- Prevent double-counting the health increase resulting from a consumed stim
                if (M.clock - (M.last_stim_consumed_clock or 0)) > 1.5 then
                    stim_triggered = true
                    M.heals_count = M.heals_count + 1
                    log_fmt('Health gain detected: +%d (%d -> %d)', p.health - M.last_health, M.last_health, p.health)
                end
            end
            
            M.last_stims = p.stims
            M.last_health = p.health
            M.last_alive = true

            if stim_triggered and CONFIG.enabled then
                local stim_duration = math.max(1.0, (CONFIG.stim_ms or 6000) / 1000)
                local fade_out_sec = math.max(0, (CONFIG.fade_out_ms or 1500) / 1000)
                local chain_lead = math.min((M.cue_duration or stim_duration) * 0.4, fade_out_sec) + 0.05
                
                if not M.stim_active then
                    -- Fresh stim trigger: start playing from current track_pos
                    M.stim_active = true
                    M.stim_extended = false
                    M.stim_end_clock = M.clock + stim_duration
                    start_stim_playback(false)
                else
                    -- Consecutive stim: extend overall stim duration without restarting/interrupting audio!
                    local new_end = math.min(M.clock + 30.0, math.max(M.stim_end_clock, M.clock) + stim_duration)
                    M.stim_end_clock = new_end
                    M.stim_extended = true
                    log_fmt('Consecutive stim! Extended window +%.1fs (ends at %.1fs, %.1fs left)',
                        stim_duration, M.stim_end_clock, M.stim_end_clock - M.clock)
                    
                    -- If audio was stopped or not currently playing, kickstart it:
                    if not M.is_playing and not M.play_retry_key then
                        start_stim_playback(false)
                    elseif M.is_playing and M.cue_duration and (M.clock >= (M.play_start_clock + M.cue_duration - chain_lead)) then
                        -- Player stimmed while music is already in fade-out tail: chain immediately to restore volume!
                        local elapsed = math.max(0.0, M.clock - M.play_start_clock)
                        local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
                        if total_dur > 0 then
                            M.track_pos = ((M.play_start_pos or 0.0) + elapsed) % total_dur
                        end
                        M.is_playing = false
                        M.stim_extended = false
                        start_stim_playback(false)
                    end
                end
            end
        elseif type(p) == 'table' and p.alive == false then
            if M.last_alive then
                M.last_alive = false
                stop_stim_playback('player_dead')
            end
        else
            M.last_stims = nil
            M.last_health = nil
        end
    end

    -- Monitor active stim playback & continuous chaining
    if M.stim_active and M.is_playing then
        local fade_out_sec = math.max(0, (CONFIG.fade_out_ms or 1500) / 1000)
        local chain_lead = math.min(M.cue_duration * 0.4, fade_out_sec) + 0.05
        
        if M.clock >= M.stim_end_clock then
            -- Entire stim effect ended
            stop_stim_playback('stim_window_end')
        elseif M.stim_extended and (M.stim_end_clock - M.clock) > 0.1 and (M.clock >= (M.play_start_clock + M.cue_duration - chain_lead)) then
            -- Stim was extended! Chain into next slice before current slice drops into fade-out!
            local elapsed = math.max(0.0, M.clock - M.play_start_clock)
            local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
            if total_dur > 0 then
                M.track_pos = ((M.play_start_pos or 0.0) + elapsed) % total_dur
            else
                M.track_pos = 0.0
            end
            M.is_playing = false
            M.stim_extended = false
            
            log_fmt('Extended stim -> chaining next slice at %.2fs before fade-out (%.1fs left)',
                M.track_pos, M.stim_end_clock - M.clock)
            start_stim_playback(true)
        elseif (M.stim_end_clock - M.clock) > 0.1 and M.clock >= (M.play_start_clock + M.cue_duration - 0.05) then
            -- Normal cue end chaining
            local elapsed = M.cue_duration
            local total_dur = M.audio_info and M.audio_info.duration or (M.using_default and 4.0 or 0.0)
            if total_dur > 0 then
                M.track_pos = ((M.play_start_pos or 0.0) + elapsed) % total_dur
            else
                M.track_pos = 0.0
            end
            M.is_playing = false
            M.stim_extended = false
            
            log_fmt('Audio cue finished, stim active (%.1fs left) -> chaining next slice at %.2fs',
                M.stim_end_clock - M.clock, M.track_pos)
            start_stim_playback(true)
        end
    end

    -- Periodic status file write
    if M.clock >= M.next_status_clock then
        M.next_status_clock = M.clock + 2.0
        write_status_snapshot()
    end
end

-- ---------------------------------------------------------------- Lifecycle Hooks
local prev_update = rawget(_G, 'update')
local prev_shutdown = rawget(_G, 'shutdown')

rawset(_G, 'update', function(dt, ...)
    if type(prev_update) == 'function' then prev_update(dt, ...) end
    local ok, err = pcall(step, dt)
    if not ok then log_fmt('STEP_ERR: %s', tostring(err)) end
end)

rawset(_G, 'shutdown', function(...)
    pcall(function()
        M.active = false
        stop_stim_playback('shutdown')
        local A = get_audio_service()
        if A and type(A.release) == 'function' then
            for _, ns in ipairs(NS_RING) do
                pcall(A.stop, ns, ROLE)
                pcall(A.release, ns)
            end
        end
        unsubscribe_all()
        if log_file then
            log_file:close()
            log_file = nil
        end
        if rawget(_G, KEY) == M then
            rawset(_G, KEY, nil)
        end
    end)
    if type(prev_shutdown) == 'function' then return prev_shutdown(...) end
end)

log_fmt('StimMusic v%s initialized successfully.', VERSION)

return {{
    installed = true,
    name = ZH.mod_title,
    version = VERSION,
    author = 'kugua',
    description = ZH.mod_desc,
}}
'''

# 2. Write source file
src_path = ROOT / 'Source/mods/kugua/stim_music.lua'
src_path.parent.mkdir(parents=True, exist_ok=True)
src_path.write_text(lua_template, encoding='ascii')
print(f"Wrote {src_path} ({len(lua_template)} bytes)")

# 3. Validate syntax with lupa
import lupa
lua = lupa.LuaRuntime(unpack_returned_tuples=False)
try:
    lua.execute(lua_template)
    print("Lua syntax check: PASSED!")
except Exception as e:
    print(f"Lua syntax check: FAILED! {e}")
    sys.exit(1)

# 4. Pack into 9ba626afa44a3aa3.patch_0
lua_bytes = lua_template.encode('ascii')
body = struct.pack('<II', len(lua_bytes), 2) + lua_bytes
archive_bytes = make_archive({resource_hash(RESOURCE): body})

# Write to Addon/ and mod/
addon_patch = ROOT / 'Addon/9ba626afa44a3aa3.patch_0'
mod_patch = ROOT / 'mod/9ba626afa44a3aa3.patch_0'
addon_patch.parent.mkdir(parents=True, exist_ok=True)
mod_patch.parent.mkdir(parents=True, exist_ok=True)
addon_patch.write_bytes(archive_bytes)
mod_patch.write_bytes(archive_bytes)

# Create 0-byte companion files
for base in (addon_patch, mod_patch):
    (base.parent / f"{base.name}.gpu_resources").write_bytes(b'')
    (base.parent / f"{base.name}.stream").write_bytes(b'')

print(f"Built archive: {addon_patch} ({len(archive_bytes)} bytes)")

# 5. Run authentic loader acceptance verification
names, rejected = loader_accept.scan_file(archive_bytes)
print(f"Loader acceptance names: {names}")
print(f"Loader acceptance rejected: {rejected}")
if rejected or RESOURCE not in names:
    print("LOADER ACCEPTANCE FAILED!")
    sys.exit(1)
print("LOADER ACCEPTANCE: 100% PASSED!")

# 6. Update manifest.json
manifest_data = {
    "Version": 1,
    "Guid": "c980dc93-4108-5742-80e4-28f6b06b928a",
    "Name": f"StimMusic v{VERSION} - 打针放音乐",
    "Description": "Requires MDL3 + HD2 Data Hub (0.3.0+). Plays custom music on stim/heal with smooth fade-in/out and dynamic sample resume. / 需要 MDL3 + HD2 Data Hub 前置。打针（回血）触发音乐播放，支持平滑渐入渐出、毫秒级断点接续与音量调节。可在 ESC -> MDL 设置中调节选项。",
    "Options": [
        {
            "Name": "StimMusic (打针放音乐)",
            "Description": "Plays custom music upon stimming / healing. Supports fade in/out, volume control, and custom tracks. / 打针回血播放音乐，支持渐入渐出、音量调节与自定义音乐曲目。",
            "Include": [
                "Addon"
            ]
        }
    ]
}
import json
(ROOT / 'manifest.json').write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding='utf-8')
print("Updated manifest.json")

# 7. Create installable zip in dist/
dist_dir = ROOT / 'dist'
dist_dir.mkdir(parents=True, exist_ok=True)
zip_path = dist_dir / f"StimMusic-{VERSION}.zip"
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(addon_patch, 'Addon/9ba626afa44a3aa3.patch_0')
    zf.write(addon_patch.parent / f"{addon_patch.name}.gpu_resources", 'Addon/9ba626afa44a3aa3.patch_0.gpu_resources')
    zf.write(addon_patch.parent / f"{addon_patch.name}.stream", 'Addon/9ba626afa44a3aa3.patch_0.stream')
    zf.write(ROOT / 'manifest.json', 'manifest.json')
    zf.write(ROOT / 'README.md', 'README.md')
    if (ROOT / 'convert_track.cmd').exists():
        zf.write(ROOT / 'convert_track.cmd', 'convert_track.cmd')
    if (ROOT / 'convert_track.ps1').exists():
        zf.write(ROOT / 'convert_track.ps1', 'convert_track.ps1')
print(f"Packaged distribution zip: {zip_path} ({zip_path.stat().st_size} bytes)")

desktop_repo_dist = Path(r'C:\Users\kugua\Desktop\针剂音效\dist')
if desktop_repo_dist.parent.exists():
    desktop_repo_dist.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, desktop_repo_dist / zip_path.name)
    shutil.copy2(zip_path, Path(r'C:\Users\kugua\Desktop') / zip_path.name)
    print(f"Copied release zip to Desktop and Desktop git repo dist: {zip_path.name}")

# 8. Deploy directly to game directory if present
game_data = Path(r'E:\SteamLibrary\steamapps\common\Helldivers 2\data')
if game_data.exists():
    target_patch = None
    # 1) Check if an existing patch already contains RESOURCE (mods/kugua/stim_music)
    for p_idx in range(16):
        cand = game_data / f"9ba626afa44a3aa3.patch_{p_idx}"
        if cand.is_file():
            try:
                names, _ = loader_accept.scan_file(cand.read_bytes())
                if RESOURCE in names:
                    target_patch = cand
                    print(f"Found existing StimMusic patch slot: {cand}")
                    break
            except Exception:
                pass

    # 2) If not found, find the first available sequential patch slot
    if not target_patch:
        for p_idx in range(16):
            cand = game_data / f"9ba626afa44a3aa3.patch_{p_idx}"
            if not cand.exists():
                target_patch = cand
                print(f"Allocating new sequential patch slot: {cand}")
                break

    if target_patch:
        target_patch.write_bytes(archive_bytes)
        (target_patch.parent / f"{target_patch.name}.gpu_resources").write_bytes(b'')
        (target_patch.parent / f"{target_patch.name}.stream").write_bytes(b'')
        print(f"Directly updated live game patch: {target_patch}")

# 9. Also synchronize HD2 Arsenal mod directories if present
arsenal_parent = Path(r'C:\Users\kugua\AppData\Local\hd2arsenal\mods')
if arsenal_parent.exists():
    for cand in arsenal_parent.glob('StimMusic*'):
        if cand.is_dir() and cand != ROOT:
            addon_dir = cand / 'Addon'
            if addon_dir.exists():
                (addon_dir / '9ba626afa44a3aa3.patch_0').write_bytes(archive_bytes)
                (addon_dir / '9ba626afa44a3aa3.patch_0.gpu_resources').write_bytes(b'')
                (addon_dir / '9ba626afa44a3aa3.patch_0.stream').write_bytes(b'')
                print(f"Synchronized with Arsenal mod directory: {addon_dir}")
            if (ROOT / 'convert_track.cmd').exists():
                (cand / 'convert_track.cmd').write_bytes((ROOT / 'convert_track.cmd').read_bytes())
            if (ROOT / 'convert_track.ps1').exists():
                (cand / 'convert_track.ps1').write_bytes((ROOT / 'convert_track.ps1').read_bytes())
            print(f"Synchronized converter scripts to Arsenal mod directory: {cand}")

# 10. Directly deploy conversion scripts to MDL dedicated directory and legacy directories
deploy_dirs = [
    Path(os.path.expandvars(r'%LOCALAPPDATA%\MDL\Helldivers2\StimMusic')),
    Path(os.path.expandvars(r'%LOCALAPPDATA%\CowboyBingus\Helldivers2\StimMusic')),
]
for target_dir in deploy_dirs:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / 'convert_track.cmd').write_bytes((ROOT / 'convert_track.cmd').read_bytes())
    (target_dir / 'convert_track.ps1').write_bytes((ROOT / 'convert_track.ps1').read_bytes())
    print(f"Directly deployed conversion scripts to: {target_dir}")

print("ALL TASKS COMPLETED SUCCESSFULLY!")
