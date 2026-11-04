-- HD2-Addon: mods/kugua/stim_music
-- StimMusic v2.0.0 for MDL3 (PUC Lua 5.1) + HD2 Data Hub >= 0.3.0 (HD2Data API 1).
-- Plays audio on stim / healing with segment resume and volume controls.
-- Pure Lua 5.1, zero FFI, zero memory writes, 7-bit ASCII only.

local KEY = '__KUGUA_STIM_MUSIC'
if type(rawget(_G, KEY)) == 'table' and rawget(_G, KEY).active == true then
    return rawget(_G, KEY)
end

local ADDON_ID = 'mods/kugua/stim_music'
local VERSION = '2.0.0'

local sr = rawget(_G, 'stingray')
local App = sr and sr.Application
local ok_call = function(fn, ...)
    if type(fn) ~= 'function' then return nil end
    local ok, res = pcall(fn, ...)
    if ok then return res else return nil end
end

-- String table: pure 7-bit ASCII using decimal escapes for Chinese UI labels
local ZH = {
    mod_title = '\230\137\147\233\146\136\230\148\190\233\159\179\228\185\144 (Stim Music)',
    mod_desc = '\233\156\128\232\166\129 MDL3 + HD2 Data Hub (0.3.0+) \229\137\141\231\189\174\227\128\130\230\137\147\233\146\136\239\188\136\229\155\158\232\161\128\239\188\137\232\167\166\229\143\145\233\159\179\228\185\144\230\146\173\230\148\190\239\188\140\230\148\175\230\140\129\228\184\139\230\172\161\231\187\167\231\187\173\230\146\173\230\148\190\228\184\142\233\159\179\233\135\143\232\176\131\232\138\130\227\128\130\229\143\175\229\156\168 ESC -> MDL \232\174\190\231\189\174\228\184\173\232\176\131\232\138\130\233\128\137\233\161\185\227\128\130',
    opt_enabled = '\230\128\187\229\188\128\229\133\179 (Enabled)',
    opt_enabled_desc = '\230\137\147\233\146\136\230\148\190\233\159\179\228\185\144\230\168\161\231\187\132\230\128\187\229\188\128\229\133\179',
    opt_track = '\233\159\179\228\185\144\230\150\135\228\187\182 (Music Track)',
    opt_track_desc = '\229\189\147\229\137\141\231\148\159\230\149\136\231\154\132\233\159\179\228\185\144\230\150\135\228\187\182\229\144\141\227\128\130\229\143\175\229\156\168\230\173\164\229\136\135\230\141\162\239\188\140\230\148\175\230\140\129\231\131\173\230\155\180\230\150\176\227\128\130',
    opt_volume = '\233\159\179\228\185\144\233\159\179\233\135\143 (Volume %)',
    opt_volume_desc = '\233\146\136\229\137\130\233\159\179\228\185\144\230\146\173\230\148\190\233\159\179\233\135\143 (0-100)',
    opt_stim_ms = '\233\146\136\229\137\130\230\151\182\233\149\191 (Stim Length ms)',
    opt_stim_ms_desc = '\228\184\128\230\172\161\233\146\136\229\137\130\231\148\159\230\149\136\230\140\129\231\187\173\230\151\182\233\149\191\228\184\142\233\159\179\228\185\144\230\146\173\230\148\190\231\170\151\229\143\163 (\230\175\171\231\167\146)',
    opt_min_heal = '\230\156\128\229\176\143\229\155\158\232\161\128\233\135\143\229\136\164\229\174\154',
    opt_min_heal_desc = '\229\141\149\230\172\161\229\136\164\229\174\154\233\146\136\229\137\130\231\148\159\230\149\136\231\154\132\230\156\128\229\176\143\229\155\158\232\161\128\230\149\176\229\128\188 (1-50)',
    opt_hot_reload = '\232\135\170\229\138\168\230\163\128\230\181\139\230\155\180\230\150\176 (Hot Reload)',
    opt_hot_reload_desc = '\230\163\128\230\181\139\229\136\176\233\159\179\233\162\145\230\150\135\228\187\182\230\136\150\233\133\141\231\189\174\229\143\152\230\155\180\230\151\182\232\135\170\229\138\168\233\135\141\230\150\176\232\189\189\229\133\165',
}
local EN = {
    mod_title = 'Stim Music',
    mod_desc = 'Plays audio on stim/healing with segment resume. Requires MDL3 + HD2 Data Hub (0.3.0+).',
    opt_enabled = 'Enabled',
    opt_enabled_desc = 'Master toggle for Stim Music mod.',
    opt_track = 'Music Track',
    opt_track_desc = 'Currently active music filename. You can switch tracks here with hot-reload.',
    opt_volume = 'Music Volume (%)',
    opt_volume_desc = 'Playback volume for stim music (0-100).',
    opt_stim_ms = 'Stim Length (ms)',
    opt_stim_ms_desc = 'Stim duration window and playback time per heal (ms).',
    opt_min_heal = 'Minimum Heal Threshold',
    opt_min_heal_desc = 'Minimum health increase to count as stim effect (1-50).',
    opt_hot_reload = 'Hot Reload',
    opt_hot_reload_desc = 'Automatically reloads when music file or config changes.',
}

local function is_chinese_ui()
    local mdl3 = rawget(_G, 'MDL3')
    if type(mdl3) == 'table' and type(mdl3.locale) == 'string' then
        return mdl3.locale:sub(1, 2) == 'zh'
    end
    return true -- default to Chinese UI for Chinese game client
end

local function L(k)
    local t = is_chinese_ui() and ZH or EN
    return t[k] or EN[k] or k
end

-- ---------------------------------------------------------------- Logging & Paths
local log_dir, log_file
local candidates = {}
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
        log_file:write(line, '\n')
        log_file:flush()
    end)
end

local function log_fmt(fmt, ...)
    log_msg(string.format(fmt, ...))
end

log_fmt('=== StimMusic v%s (MDL3 + HD2 Data Hub) outdir=%s ===', VERSION, tostring(log_dir))

-- ---------------------------------------------------------------- Configuration
local CONFIG = {
    enabled = true,
    volume = 100,
    stim_ms = 6000,
    min_heal = 1,
    hot_reload = true,
    track = 'stim_music.wav',
}

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
local M = {
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
    subs = {},
    
    -- Gameplay tracking:
    last_health = nil,
    last_stims = nil,
    last_alive = true,
    last_stim_consumed_clock = 0,
    
    -- Stim effect & playback timing:
    stim_active = false,
    is_playing = false,
    stim_end_clock = 0,
    seg_start_clock = 0,
    seg_end_clock = 0,
    seg_duration = 6.0,
    play_retry_idx = nil,
    play_retry_clock = 0,
    play_retries = 0,
    
    -- Audio system:
    audio_format_defined = false,
    audio_api_probed = false,
    next_upload_clock = 0,
    ns_slot = 0,
    current_ns = nil,
    audio_track_path = nil,
    audio_track_fp = nil,
    audio_track_filename = nil,
    audio_info = nil,
    current_segment = 1,
    total_segments = 1,
    segment_durations = {},
    uploaded_segments = {},
    next_upload_idx = 1,
    using_default = false,
    track_gen = 0,
    
    -- Statistics:
    stims_count = 0,
    heals_count = 0,
    next_status_clock = 0,
    next_hot_reload_clock = 0,
    last_status_verdict = 'INITIALIZING',
}
rawset(_G, KEY, M)

local function load_ini_config()
    if not log_dir then return end
    local p = log_dir .. '/STIM_MUSIC_CONFIG.ini'
    local f = io.open(p, 'r')
    if not f then
        local wf = io.open(p, 'w')
        if wf then
            wf:write('# StimMusic configuration\n')
            wf:write('enabled = 1\n')
            wf:write('volume = 100\n')
            wf:write('stim_ms = 6000\n')
            wf:write('min_heal = 1\n')
            wf:write('hot_reload = 1\n')
            wf:write('track = stim_music.wav\n')
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
            elseif k == 'min_heal' then
                local val = tonumber(v)
                if val then CONFIG.min_heal = math.max(0, math.min(100, math.floor(val + 0.5))) end
            elseif k == 'hot_reload' then CONFIG.hot_reload = (v == '1' or v:lower() == 'true')
            elseif k == 'track' then CONFIG.track = v
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
    f:write('# StimMusic configuration (Auto-saved by MDL menu)\n')
    f:write('enabled = ', CONFIG.enabled and '1' or '0', '\n')
    f:write('volume = ', tostring(math.floor(CONFIG.volume or 100)), '\n')
    f:write('stim_ms = ', tostring(math.floor(CONFIG.stim_ms or 6000)), '\n')
    f:write('min_heal = ', tostring(math.floor(CONFIG.min_heal or 1)), '\n')
    f:write('hot_reload = ', CONFIG.hot_reload and '1' or '0', '\n')
    f:write('track = ', tostring(CONFIG.track or 'stim_music.wav'), '\n')
    f:close()
    M.config_ini_fp = get_file_fingerprint(p)
end

load_ini_config()

-- ---------------------------------------------------------------- Base64 & Audio Utils
local B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local B64_T = {}
for i = 1, #B64 do B64_T[i-1] = B64:sub(i, i) end

local function b64_encode(data)
    local out = {}
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

local B64_REV = {}
for i = 1, #B64 do B64_REV[B64:byte(i)] = i - 1 end

local function b64_decode(data)
    data = data:gsub('[^A-Za-z0-9+/=]', '')
    local out = {}
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

local CONVERTER_CMD_B64 = 'QGVjaG8gb2ZmDQ0KcG93ZXJzaGVsbC5leGUgLU5vUHJvZmlsZSAtRXhlY3V0aW9uUG9saWN5IEJ5cGFzcyAtRmlsZSAiJX5kcDBjb252ZXJ0X3RyYWNrLnBzMSIgJSoNDQo='
local CONVERTER_PS1_B64 = '77u/IyBTdGltTXVzaWMgVWx0cmEtTGlnaHR3ZWlnaHQgQXVkaW8gQ29udmVydGVyIChNUy1BRFBDTSkNCnBhcmFtKA0KICAgIFtQYXJhbWV0ZXIoVmFsdWVGcm9tUmVtYWluaW5nQXJndW1lbnRzID0gJHRydWUpXQ0KICAgIFtzdHJpbmdbXV0kRmlsZXMNCikNCg0KJHNjcmlwdERpciA9IFNwbGl0LVBhdGggLVBhcmVudCAkTXlJbnZvY2F0aW9uLk15Q29tbWFuZC5QYXRoDQppZiAoJHNjcmlwdERpcikgeyBTZXQtTG9jYXRpb24gJHNjcmlwdERpciB9DQoNCiRmZm1wZWcgPSAiRDpcZmZtcGVnLTcuMS4xLWVzc2VudGlhbHNfYnVpbGRcYmluXGZmbXBlZy5leGUiDQppZiAoLW5vdCAoVGVzdC1QYXRoICRmZm1wZWcpKSB7DQogICAgJGZvdW5kID0gR2V0LUNvbW1hbmQgZmZtcGVnIC1FcnJvckFjdGlvbiBTaWxlbnRseUNvbnRpbnVlDQogICAgaWYgKCRmb3VuZCkgew0KICAgICAgICAkZmZtcGVnID0gImZmbXBlZyINCiAgICB9IGVsc2Ugew0KICAgICAgICBXcml0ZS1Ib3N0ICJb6ZSZ6K+vXSDmnKrmib7liLAgZmZtcGVnLmV4Ze+8gSIgLUZvcmVncm91bmRDb2xvciBSZWQNCiAgICAgICAgV3JpdGUtSG9zdCAi6K+356Gu5L+dIEQ6XGZmbXBlZy03LjEuMS1lc3NlbnRpYWxzX2J1aWxkXGJpblxmZm1wZWcuZXhlIOWtmOWcqOaIlumFjee9ruS6huezu+e7nyBQQVRI44CCIg0KICAgICAgICBSZWFkLUhvc3QgIuaMieWbnui9pumUrumAgOWHui4uLiINCiAgICAgICAgZXhpdCAxDQogICAgfQ0KfQ0KDQpXcml0ZS1Ib3N0ICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IiAtRm9yZWdyb3VuZENvbG9yIEN5YW4NCldyaXRlLUhvc3QgIiAgIFN0aW1NdXNpYyDpn7PpopHotoXovbvph4/ovaznoIHlt6XlhbcgKE1TLUFEUENNKSIgLUZvcmVncm91bmRDb2xvciBDeWFuDQpXcml0ZS1Ib3N0ICIgICDlvbvlupXlkYrliKvlh6DljYHlhYbvvIHovbvmnb7lsIbpn7PkuZDljovnvKnoh7MgTVAzIOWkp+WwjyAoM01CfjVNQikiIC1Gb3JlZ3JvdW5kQ29sb3IgQ3lhbg0KV3JpdGUtSG9zdCAiPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PSIgLUZvcmVncm91bmRDb2xvciBDeWFuDQpXcml0ZS1Ib3N0ICLkvb/nlKggZmZtcGVnOiAkZmZtcGVnYG4iDQoNCiRhciA9IDMyMDAwDQokYWMgPSAyDQoNCmlmICgtbm90ICRGaWxlcyAtb3IgJEZpbGVzLkNvdW50IC1lcSAwKSB7DQogICAgV3JpdGUtSG9zdCAi6K+36YCJ5oup5Y6L57yp5L2T56ev6aKE6K6+77yaIiAtRm9yZWdyb3VuZENvbG9yIFllbGxvdw0KICAgIFdyaXRlLUhvc3QgIiAgWzFdIE1QMyDmoIflh4bkvZPnp68gKDMya0h6IOeri+S9k+WjsO+8jDPliIbpkp/nuqYgNS41TULvvIzmjqjojZDvvIEpIg0KICAgIFdyaXRlLUhvc3QgIiAgWzJdIOaegeiHtOWwj+S9k+enryAgICg0NC4xa0h6IOWNleWjsOmBk++8jDPliIbpkp/nuqYgMy44TULvvIzkuI4xOTJrIE1QM+ebuOWQjCkiDQogICAgV3JpdGUtSG9zdCAiICBbM10g6auY5L+d55yf56uL5L2T5aOwICg0OGtIeiDnq4vkvZPlo7DvvIwz5YiG6ZKf57qmIDguNU1C77yM5oiY5ZywNeaWueahiCkiDQogICAgV3JpdGUtSG9zdCAiIg0KICAgICRjaG9pY2UgPSBSZWFkLUhvc3QgIuivt+i+k+WFpemAiemhuSAo55u05o6l5Zue6L2m6buY6K6k6YCJIDEgW01QM+agh+WHhuS9k+enr10pIg0KDQogICAgaWYgKCRjaG9pY2UgLWVxICIyIikgew0KICAgICAgICAkYXIgPSA0NDEwMA0KICAgICAgICAkYWMgPSAxDQogICAgICAgIFdyaXRlLUhvc3QgIuW3sumAieaLqTog5p6B6Ie05bCP5L2T56evICjljZXlo7DpgZMgNDQuMWtIeilgbiIgLUZvcmVncm91bmRDb2xvciBHcmVlbg0KICAgIH0gZWxzZWlmICgkY2hvaWNlIC1lcSAiMyIpIHsNCiAgICAgICAgJGFyID0gNDgwMDANCiAgICAgICAgJGFjID0gMg0KICAgICAgICBXcml0ZS1Ib3N0ICLlt7LpgInmi6k6IOmrmOS/neecn+eri+S9k+WjsCAo56uL5L2T5aOwIDQ4a0h6KWBuIiAtRm9yZWdyb3VuZENvbG9yIEdyZWVuDQogICAgfSBlbHNlIHsNCiAgICAgICAgJGFyID0gMzIwMDANCiAgICAgICAgJGFjID0gMg0KICAgICAgICBXcml0ZS1Ib3N0ICLlt7LpgInmi6k6IE1QMyDmoIflh4bkvZPnp68gKOeri+S9k+WjsCAzMmtIeilgbiIgLUZvcmVncm91bmRDb2xvciBHcmVlbg0KICAgIH0NCg0KICAgICMgU3RlcCAxOiBzY2FuIGNvbXByZXNzZWQgZmlsZXMgKC5tNHMsIC5tcDMsIC5tcDQsIC5mbGFjLCAub2dnKQ0KICAgICRzb3VyY2VGaWxlcyA9IEdldC1DaGlsZEl0ZW0gLUZpbGUgfCBXaGVyZS1PYmplY3QgeyAkXy5FeHRlbnNpb24gLW1hdGNoICdeXC4obXAzfG00c3xtcDR8ZmxhY3xvZ2cpJCcgfQ0KICAgIGZvcmVhY2ggKCRmIGluICRzb3VyY2VGaWxlcykgew0KICAgICAgICAkb3V0TmFtZSA9ICIkKCRmLkJhc2VOYW1lKS53YXYiDQogICAgICAgIFdyaXRlLUhvc3QgIuato+WcqOWOi+e8qei9rOaNojogJCgkZi5OYW1lKSAtPiAkb3V0TmFtZSIgLUZvcmVncm91bmRDb2xvciBZZWxsb3cNCiAgICAgICAgJiAkZmZtcGVnIC15IC12IHdhcm5pbmcgLWkgJGYuRnVsbE5hbWUgLW1hcCAwOmE6MD8gLWFjICRhYyAtYXIgJGFyIC1jOmEgYWRwY21fbXMgLWJsb2NrX3NpemUgMTAyNCAkb3V0TmFtZQ0KICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgew0KICAgICAgICAgICAgJG5ld1NpemVNQiA9IFttYXRoXTo6Um91bmQoKEdldC1JdGVtICRvdXROYW1lKS5MZW5ndGggLyAxTUIsIDIpDQogICAgICAgICAgICBXcml0ZS1Ib3N0ICIgIFvmiJDlip9dICRvdXROYW1lIOW3sueUn+aIkO+8jOS9k+enrzogJG5ld1NpemVNQiBNQiIgLUZvcmVncm91bmRDb2xvciBHcmVlbg0KICAgICAgICB9IGVsc2Ugew0KICAgICAgICAgICAgV3JpdGUtSG9zdCAiICBb5aSx6LSlXSDovazmjaIgJCgkZi5OYW1lKSDlpLHotKUiIC1Gb3JlZ3JvdW5kQ29sb3IgUmVkDQogICAgICAgIH0NCiAgICB9DQoNCiAgICAjIFN0ZXAgMjogc2NhbiBleGlzdGluZyBXQVYgZmlsZXMgYW5kIG9wdGltaXplDQogICAgJHdhdkZpbGVzID0gR2V0LUNoaWxkSXRlbSAtRmlsZSAtRmlsdGVyICIqLndhdiIgfCBXaGVyZS1PYmplY3QgeyAkXy5OYW1lIC1ub3RtYXRjaCAnX2FkcGNtX3RtcFwud2F2JCcgfQ0KICAgIGZvcmVhY2ggKCR3IGluICR3YXZGaWxlcykgew0KICAgICAgICAkb2xkU2l6ZU1CID0gW21hdGhdOjpSb3VuZCgkdy5MZW5ndGggLyAxTUIsIDIpDQogICAgICAgICR0bXBOYW1lID0gIiQoJHcuQmFzZU5hbWUpX2FkcGNtX3RtcC53YXYiDQogICAgICAgIFdyaXRlLUhvc3QgIuato+WcqOS8mOWMluWOi+e8qTogJCgkdy5OYW1lKSAo5b2T5YmN5L2T56evOiAkb2xkU2l6ZU1CIE1CKS4uLiIgLUZvcmVncm91bmRDb2xvciBZZWxsb3cNCiAgICAgICAgJiAkZmZtcGVnIC15IC12IHdhcm5pbmcgLWkgJHcuRnVsbE5hbWUgLW1hcCAwOmE6MD8gLWFjICRhYyAtYXIgJGFyIC1jOmEgYWRwY21fbXMgLWJsb2NrX3NpemUgMTAyNCAkdG1wTmFtZQ0KICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCAtYW5kIChUZXN0LVBhdGggJHRtcE5hbWUpKSB7DQogICAgICAgICAgICAkbmV3U2l6ZU1CID0gW21hdGhdOjpSb3VuZCgoR2V0LUl0ZW0gJHRtcE5hbWUpLkxlbmd0aCAvIDFNQiwgMikNCiAgICAgICAgICAgIE1vdmUtSXRlbSAtUGF0aCAkdG1wTmFtZSAtRGVzdGluYXRpb24gJHcuRnVsbE5hbWUgLUZvcmNlDQogICAgICAgICAgICBXcml0ZS1Ib3N0ICIgIFvlrozmiJBdICQoJHcuTmFtZSkg5bey5LyY5YyW5Li66L276YePIE1TLUFEUENNOiAkb2xkU2l6ZU1CIE1CIC0+ICRuZXdTaXplTUIgTULvvIEiIC1Gb3JlZ3JvdW5kQ29sb3IgR3JlZW4NCiAgICAgICAgfQ0KICAgIH0NCg0KICAgIFdyaXRlLUhvc3QgImBuPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PSIgLUZvcmVncm91bmRDb2xvciBDeWFuDQogICAgV3JpdGUtSG9zdCAi5omA5pyJ6Z+z6aKR5aSE55CG5a6M5oiQ77yB546w5Zyo5omA5pyJ5q2M5puy5Z2H5bey5Y+Y5oiQIE1QMyDlpKflsI/vvIzpm7bljaHpob/mtYHnlYXmkq3mlL7jgIIiIC1Gb3JlZ3JvdW5kQ29sb3IgQ3lhbg0KICAgIFdyaXRlLUhvc3QgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iIC1Gb3JlZ3JvdW5kQ29sb3IgQ3lhbg0KICAgIFJlYWQtSG9zdCAi5oyJ5Zue6L2m6ZSu6YCA5Ye6Li4uIg0KfSBlbHNlIHsNCiAgICBXcml0ZS1Ib3N0ICJb5ouW5ou95qih5byPXSDmraPlnKjku6UgTVAzIOagh+WHhuS9k+enryAoMzJrSHog56uL5L2T5aOwKSDovazmjaLkvKDlhaXnmoTmlofku7YuLi4iIC1Gb3JlZ3JvdW5kQ29sb3IgWWVsbG93DQogICAgZm9yZWFjaCAoJGZpbGUgaW4gJEZpbGVzKSB7DQogICAgICAgIGlmIChUZXN0LVBhdGggJGZpbGUpIHsNCiAgICAgICAgICAgICRpdGVtID0gR2V0LUl0ZW0gJGZpbGUNCiAgICAgICAgICAgICRvdXRQYXRoID0gSm9pbi1QYXRoICRpdGVtLkRpcmVjdG9yeU5hbWUgIiQoJGl0ZW0uQmFzZU5hbWUpLndhdiINCiAgICAgICAgICAgIFdyaXRlLUhvc3QgIuato+WcqOi9rOaNojogJCgkaXRlbS5OYW1lKSAtPiAkKCRpdGVtLkJhc2VOYW1lKS53YXYiIC1Gb3JlZ3JvdW5kQ29sb3IgWWVsbG93DQogICAgICAgICAgICAmICRmZm1wZWcgLXkgLXYgd2FybmluZyAtaSAkaXRlbS5GdWxsTmFtZSAtbWFwIDA6YTowPyAtYWMgJGFjIC1hciAkYXIgLWM6YSBhZHBjbV9tcyAtYmxvY2tfc2l6ZSAxMDI0ICRvdXRQYXRoDQogICAgICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgew0KICAgICAgICAgICAgICAgICRzek1CID0gW21hdGhdOjpSb3VuZCgoR2V0LUl0ZW0gJG91dFBhdGgpLkxlbmd0aCAvIDFNQiwgMikNCiAgICAgICAgICAgICAgICBXcml0ZS1Ib3N0ICIgIFvmiJDlip9dIOW3sueUn+aIkCAkKCRpdGVtLkJhc2VOYW1lKS53YXYgKCRzek1CIE1CKSIgLUZvcmVncm91bmRDb2xvciBHcmVlbg0KICAgICAgICAgICAgfSBlbHNlIHsNCiAgICAgICAgICAgICAgICBXcml0ZS1Ib3N0ICIgIFvlpLHotKVdIOi9rOaNoiAkKCRpdGVtLk5hbWUpIOWksei0pSIgLUZvcmVncm91bmRDb2xvciBSZWQNCiAgICAgICAgICAgIH0NCiAgICAgICAgfQ0KICAgIH0NCiAgICBSZWFkLUhvc3QgIuaMieWbnui9pumUrumAgOWHui4uLiINCn0NCg=='

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

local DEFAULT_WFX_B64 = 'AQABACJWAABErAAAAgAQAAAA'
local DEFAULT_AUDIO_B64 = 
table.concat({
    "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"
})

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
    return {
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
    }
end

local function read_wav_slice(info, start_sec, duration_sec)
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
    local actual_duration = slice_bytes / info.avg
    return b64_encode(raw), actual_duration
end

-- ---------------------------------------------------------------- Audio Driver
local ROLE = 'stim'
local NS_RING = {
    ADDON_ID .. '_a',
    ADDON_ID .. '_b',
    ADDON_ID .. '_c',
    ADDON_ID .. '_d',
}

local function get_audio_service()
    local mdl3 = rawget(_G, 'MDL3')
    local A = type(mdl3) == 'table' and mdl3.audio or nil
    if type(A) == 'table' and A.api == 1 and type(A.play) == 'function' then
        return A
    end
    return nil
end

local function scan_available_tracks()
    local list = {}
    local seen = {}
    local function add(name)
        if name and name ~= '' and not seen[name] then
            seen[name] = true
            list[#list + 1] = name
        end
    end
    if CONFIG.track and CONFIG.track ~= '' then
        local base = CONFIG.track:match('([^/\\]+%.wav)$') or CONFIG.track
        add(base)
    end
    local known = {
        'stim_music.wav',
        'stim_music_alt.wav',
        'yu_ai.wav',
        'pao_mo.wav',
        'pi_pa.wav',
        'music.wav',
        'bgm.wav',
        'stim.wav',
        'heal.wav',
    }
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
        local paths = {}
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
        local names = { 'stim_music.wav', 'stim_music_alt.wav', 'yu_ai.wav', 'pao_mo.wav', 'pi_pa.wav' }
        for _, n in ipairs(names) do
            local p = log_dir .. '/' .. n
            local f = io.open(p, 'rb')
            if f then f:close(); return p end
        end
    end
    return nil
end

local function upload_single_segment(idx)
    local A = get_audio_service()
    local ns = M.current_ns
    if not A or not ns or M.using_default or not M.audio_info then return false end
    if idx < 1 or idx > M.total_segments then return false end
    if M.uploaded_segments[idx] then return true end
    
    local stim_sec = math.max(2.0, (CONFIG.stim_ms or 6000) / 1000)
    local start_sec = (idx - 1) * stim_sec
    local b64_data, actual_duration = read_wav_slice(M.audio_info, start_sec, stim_sec)
    if b64_data then
        local key = 's' .. M.track_gen .. '_' .. idx
        local ok, why = A.upload(ns, key, b64_data)
        if ok then
            M.uploaded_segments[idx] = true
            M.segment_durations[idx] = actual_duration or stim_sec
            log_fmt('Segment %d queued for upload on %s (key=%s, dur=%.1fs)', idx, ns, key, actual_duration or stim_sec)
            return true
        else
            log_fmt('Upload %s refused for ns=%s: %s', key, ns, tostring(why))
            return false
        end
    end
    return false
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
    M.is_playing = false
    M.play_retry_idx = nil
    M.play_retries = 0
    M.segment_durations = {}
    M.uploaded_segments = {}
    M.seg_duration = nil
    M.seg_start_clock = nil
    M.seg_end_clock = nil
    M.next_upload_clock = 0
    
    local path = locate_music_file()
    if path then
        local info, err = parse_wav(path)
        if info then
            M.audio_track_path = path
            M.audio_track_fp = get_file_fingerprint(path)
            M.audio_track_filename = path:match('([^/\\]+%.wav)$') or path
            M.audio_info = info
            M.using_default = false
            local stim_sec = math.max(2.0, (CONFIG.stim_ms or 6000) / 1000)
            local total_segs = math.ceil(info.duration / stim_sec)
            M.total_segments = math.min(100, math.max(1, total_segs))
            M.current_segment = 1
            
            local ok_f, why_f = A.define_format(current_ns, info.wfx_b64)
            if not ok_f then log_fmt('define_format failed for %s: %s', current_ns, tostring(why_f)) end
            local ok_p, why_p = A.pool(current_ns, { [ROLE] = 2 })
            if not ok_p then log_fmt('pool failed for %s: %s', current_ns, tostring(why_p)) end
            
            probe_audio_api(A, current_ns)
            
            -- UI thread: queue segment 1 asynchronously to eliminate menu stutter
            M.next_upload_idx = 1
            
            local fmt_name = (info.tag == 2) and 'MS-ADPCM' or 'PCM-16'
            log_fmt('Audio track loaded: %s on ns=%s (fmt=%s, gen=%d, %.1fs, %d channels, %d Hz, %d segments)',
                path, current_ns, fmt_name, M.track_gen, info.duration, info.channels, info.rate, M.total_segments)
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
    M.total_segments = 1
    M.current_segment = 1
    M.segment_durations[1] = 4.0
    
    A.define_format(current_ns, DEFAULT_WFX_B64)
    A.pool(current_ns, { [ROLE] = 2 })
    probe_audio_api(A, current_ns)
    local def_key = 's' .. M.track_gen .. '_1'
    A.upload(current_ns, def_key, DEFAULT_AUDIO_B64)
    M.uploaded_segments[1] = true
    M.next_upload_idx = 2
    log_fmt('Using embedded default stim audio on ns=%s (key=%s)', current_ns, def_key)
    return true
end

local function step_audio_uploads()
    local A = get_audio_service()
    local ns = M.current_ns
    if not A or not ns or M.using_default or not M.audio_info then return end
    if M.next_upload_idx > M.total_segments then return end
    
    -- Rolling prefetch window: only upload up to (current_segment + 2) segments
    -- Completely prevents consecutive frame freezes and excessive memory consumption
    local prefetch_limit = math.min(M.total_segments, (M.current_segment or 1) + 2)
    if M.next_upload_idx > prefetch_limit then return end
    
    -- Fast forward if segment already uploaded
    if M.uploaded_segments[M.next_upload_idx] then
        M.next_upload_idx = M.next_upload_idx + 1
        return
    end
    
    -- Throttling: minimum 250ms between uploads to spread base64 encoding cost across frames
    if M.clock < (M.next_upload_clock or 0) then return end
    
    -- Native status check: ensure previous upload has completed decoding in XAudio2
    local prev_idx = M.next_upload_idx - 1
    local prev_ready = true
    if prev_idx >= 1 then
        if type(A.status) == 'function' then
            local ok_st, st = pcall(A.status, ns)
            if ok_st and type(st) == 'table' and type(st.ready) == 'number' then
                prev_ready = (st.ready >= prev_idx)
            end
        elseif type(A.ready) == 'function' then
            local prev_key = 's' .. M.track_gen .. '_' .. prev_idx
            local ok_r, is_r = pcall(A.ready, ns, prev_key)
            prev_ready = ok_r and (is_r == true)
        end
    end
    
    if prev_ready then
        local idx = M.next_upload_idx
        if upload_single_segment(idx) then
            M.next_upload_idx = idx + 1
            M.next_upload_clock = M.clock + 0.25
        else
            M.next_upload_clock = M.clock + 0.5
        end
    end
end

-- ---------------------------------------------------------------- Stim Music Actions
local function start_stim_segment(seg_idx)
    if not CONFIG.enabled then return false end
    local A = get_audio_service()
    local ns = M.current_ns
    if not A or not ns then return false end
    
    if not M.using_default then
        if not M.uploaded_segments[seg_idx] then
            upload_single_segment(seg_idx)
        end
    end
    
    local key = M.using_default and ('s' .. M.track_gen .. '_1') or ('s' .. M.track_gen .. '_' .. seg_idx)
    local vol = math.max(0, math.min(100, math.floor((CONFIG.volume or 100) + 0.5)))
    if vol <= 0 then return false end
    
    -- Check if the asset has finished receiving & decoding in the native host
    local ready = false
    if M.using_default then
        ready = true
    elseif type(A.status) == 'function' then
        local ok_st, st = pcall(A.status, ns)
        if ok_st and type(st) == 'table' and type(st.ready) == 'number' then
            ready = (st.ready >= seg_idx)
        else
            ready = (M.uploaded_segments[seg_idx] == true)
        end
    elseif type(A.ready) == 'function' then
        local ok_r, is_r = pcall(A.ready, ns, key)
        ready = ok_r and (is_r == true)
    else
        ready = (M.uploaded_segments[seg_idx] == true)
    end
    
    if not ready then
        local retries = (M.play_retries or 0) + 1
        M.play_retries = retries
        if retries == 1 or retries % 5 == 0 then
            log_fmt('Stim segment %s not ready yet on %s (retrying, attempt #%d)', key, ns, retries)
        end
        M.play_retry_idx = seg_idx
        M.play_retry_clock = M.clock + 0.1
        return false
    end
    
    local ok, played = pcall(A.play, ns, key, { role = ROLE, volume = vol })
    if ok and played == true then
        local stim_sec = math.max(2.0, (CONFIG.stim_ms or 6000) / 1000)
        local dur = (M.segment_durations and M.segment_durations[seg_idx]) or (M.using_default and 4.0) or stim_sec
        M.seg_duration = dur
        M.seg_start_clock = M.clock
        M.seg_end_clock = M.clock + dur
        M.is_playing = true
        M.play_retry_idx = nil
        M.play_retries = 0
        M.stims_count = M.stims_count + 1
        M.last_status_verdict = string.format('PLAYING - segment %d / %d (%.1fs)', seg_idx, M.total_segments, dur)
        log_fmt('Stim music started: %s on %s (vol=%d, dur=%.1fs, stim#=%d)', key, ns, vol, dur, M.stims_count)
        return true
    else
        local retries = (M.play_retries or 0) + 1
        M.play_retries = retries
        if retries == 1 or retries % 5 == 0 then
            log_fmt('Stim play failed for %s on %s (vol=%d, ok=%s, played=%s, retry #%d)',
                key, ns, vol, tostring(ok), tostring(played), retries)
        end
        M.play_retry_idx = seg_idx
        M.play_retry_clock = M.clock + 0.1
        return false
    end
end

local function advance_to_next_segment()
    local prev = M.current_segment
    M.current_segment = M.current_segment + 1
    if M.current_segment > M.total_segments then
        M.current_segment = 1
    end
    return prev, M.current_segment
end

local function stop_stim_playback()
    if not M.stim_active and not M.is_playing then return end
    M.stim_active = false
    M.is_playing = false
    M.play_retry_idx = nil
    M.play_retries = 0
    local A = get_audio_service()
    local ns = M.current_ns
    if A and ns then
        pcall(A.stop, ns, ROLE)
    end
    local prev, nxt = advance_to_next_segment()
    M.last_status_verdict = string.format('PAUSED - played seg %d, next will be %d', prev, nxt)
    log_fmt('Stim music stopped: segment %d finished, next will be %d', prev, nxt)
end

-- ---------------------------------------------------------------- Status Snapshot
local function write_status_snapshot()
    if not log_dir then return end
    local p = log_dir .. '/STIM_MUSIC_STATUS.txt'
    local f = io.open(p, 'w')
    if not f then return end
    
    local stim_dur = math.max(2.0, (CONFIG.stim_ms or 6000) / 1000)
    local remaining_ms = M.stim_active and math.floor(math.max(0, M.stim_end_clock - M.clock) * 1000) or -1
    
    f:write('verdict=', M.last_status_verdict, '\n')
    f:write('revision=', VERSION, '\n')
    f:write('enabled=', tostring(CONFIG.enabled), '\n')
    f:write('stim_ms=', tostring(CONFIG.stim_ms), '\n')
    f:write('volume=', tostring(CONFIG.volume), '\n')
    f:write('min_heal=', tostring(CONFIG.min_heal), '\n')
    f:write('hot_reload=', tostring(CONFIG.hot_reload), '\n')
    f:write('folder=', tostring(log_dir), '\n')
    f:write('namespace=', tostring(M.current_ns or 'none'), '\n')
    f:write('track=', tostring(M.audio_track_path or '[embedded default]'), '\n')
    f:write('filename=', tostring(M.audio_track_filename or 'none'), '\n')
    f:write('using_default=', tostring(M.using_default), '\n')
    f:write('total_segments=', tostring(M.total_segments), '\n')
    f:write('current_segment=', tostring(M.current_segment), '\n')
    f:write('stim_active=', tostring(M.stim_active), '\n')
    f:write('is_playing=', tostring(M.is_playing), '\n')
    f:write('stim_remaining_ms=', tostring(remaining_ms), '\n')
    f:write('stims_count=', tostring(M.stims_count), '\n')
    f:write('heals_count=', tostring(M.heals_count), '\n')
    f:write('hub_state=', tostring(M.hub_state), '\n')
    f:write('hub_version=', tostring(M.hub_version), '\n')
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

    reg('enabled', {
        type = 'toggle', default = CONFIG.enabled,
        label = L('opt_enabled'), description = L('opt_enabled_desc'),
    }, function(v)
        local val = nil
        if type(v) == 'boolean' then val = v
        elseif type(v) == 'string' then val = (v:lower() == 'true' or v == '1')
        elseif type(v) == 'number' then val = (v ~= 0)
        end
        if val ~= nil and val ~= CONFIG.enabled then
            CONFIG.enabled = val
            log_fmt('Enabled set to %s', tostring(val))
            if not val and M.stim_active then
                stop_stim_playback()
            end
            write_status_snapshot()
            persist_ini_config()
        end
    end)

    local tracks = scan_available_tracks()
    local default_idx = 1
    local cur_name = M.audio_track_filename or (M.audio_track_path and M.audio_track_path:match('([^/\\]+%.wav)$')) or CONFIG.track or 'stim_music.wav'
    for i, name in ipairs(tracks) do
        if name:lower() == cur_name:lower() then
            default_idx = i
            break
        end
    end

    reg('track', {
        type = 'choice',
        choices = tracks,
        default = default_idx,
        label = L('opt_track'),
        description = L('opt_track_desc'),
    }, function(v)
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

    reg('volume', {
        type = 'slider', min = 0, max = 100, step = 5, default = CONFIG.volume,
        label = L('opt_volume'), description = L('opt_volume_desc'),
    }, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(0, math.min(100, math.floor(num + 0.5)))
            if num ~= CONFIG.volume then
                CONFIG.volume = num
                log_fmt('Volume set to %d%%', CONFIG.volume)
                if num == 0 and M.stim_active then
                    stop_stim_playback()
                end
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('stim_ms', {
        type = 'slider', min = 2000, max = 8000, step = 250, default = CONFIG.stim_ms,
        label = L('opt_stim_ms'), description = L('opt_stim_ms_desc'),
    }, function(v)
        local num = tonumber(v)
        if num then
            num = math.max(1000, math.min(30000, math.floor(num + 0.5)))
            if num ~= CONFIG.stim_ms then
                CONFIG.stim_ms = num
                log_fmt('Stim duration set to %dms', CONFIG.stim_ms)
                write_status_snapshot()
                persist_ini_config()
            end
        end
    end)

    reg('min_heal', {
        type = 'slider', min = 1, max = 50, step = 1, default = CONFIG.min_heal,
        label = L('opt_min_heal'), description = L('opt_min_heal_desc'),
    }, function(v)
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

    reg('hot_reload', {
        type = 'toggle', default = CONFIG.hot_reload,
        label = L('opt_hot_reload'), description = L('opt_hot_reload_desc'),
    }, function(v)
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
    M.subs = {}
end

local function on_mission_started(ev)
    M.last_health = nil
    M.last_stims = nil
    M.stim_active = false
    M.current_segment = 1
    log_msg('Mission started: stim music position reset to segment 1.')
end

local function on_mission_ended(ev)
    stop_stim_playback()
    M.last_health = nil
    M.last_stims = nil
    log_msg('Mission ended: stim playback stopped.')
end

local function on_entity_died(ev)
    if ev and ev.avatar and ev.local_killer then
        stop_stim_playback()
    end
end

local EVENT_HANDLERS = {
    { 'mission_started', on_mission_started },
    { 'mission_ended',   on_mission_ended   },
    { 'entity_died',     on_entity_died     },
}

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
            local s = ok_call(D.on, name, fn, { owner = ADDON_ID, id = name, priority = 50 })
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

    -- Process progressive audio uploads
    step_audio_uploads()

    -- Retry pending play if previous attempt was waiting for decoder / upload
    if M.play_retry_idx and M.clock >= M.play_retry_clock and M.stim_active then
        if M.clock <= M.stim_end_clock then
            start_stim_segment(M.play_retry_idx)
        else
            log_fmt('Stim window ended before segment %d became ready (retried %d times)',
                M.play_retry_idx, M.play_retries or 0)
            M.play_retry_idx = nil
            M.play_retries = 0
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
                local stim_duration = math.max(2.0, (CONFIG.stim_ms or 6000) / 1000)
                if not M.stim_active then
                    -- Fresh stim trigger: start playing current segment
                    M.stim_active = true
                    M.stim_end_clock = M.clock + stim_duration
                    start_stim_segment(M.current_segment)
                else
                    -- Consecutive stim: extend overall stim duration without restarting/interrupting audio!
                    local new_end = math.min(M.clock + 30.0, math.max(M.stim_end_clock, M.clock) + stim_duration)
                    M.stim_end_clock = new_end
                    log_fmt('Consecutive stim! Extended window +%.1fs (ends at %.1fs, %.1fs left)',
                        stim_duration, M.stim_end_clock, M.stim_end_clock - M.clock)
                    
                    -- If audio was stopped or not currently playing, kickstart it:
                    if not M.is_playing and not M.play_retry_idx then
                        start_stim_segment(M.current_segment)
                    end
                end
            end
        elseif type(p) == 'table' and p.alive == false then
            if M.last_alive then
                M.last_alive = false
                stop_stim_playback()
            end
        else
            M.last_stims = nil
            M.last_health = nil
        end
    end

    -- Monitor active stim playback & continuous segment chaining
    if M.stim_active and M.is_playing then
        if M.clock >= M.stim_end_clock then
            -- Entire stim effect ended
            stop_stim_playback()
        elseif M.clock >= (M.seg_end_clock - 0.02) then
            -- Audio slice finished, but stim effect is still active! Chain into next slice seamlessly!
            local prev, nxt = advance_to_next_segment()
            log_fmt('Segment %d audio finished, stim active (%.1fs left) -> chaining segment %d',
                prev, M.stim_end_clock - M.clock, nxt)
            local expected_start = M.seg_end_clock
            if start_stim_segment(nxt) then
                M.seg_start_clock = expected_start
                M.seg_end_clock = expected_start + M.seg_duration
            end
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
        stop_stim_playback()
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

return {
    installed = true,
    name = ZH.mod_title,
    version = VERSION,
    author = 'kugua',
    description = ZH.mod_desc,
}
