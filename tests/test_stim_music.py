"""Comprehensive automated test suite for StimMusic 2.0.0.
Verifies loader acceptance, static security rules, and simulates gameplay events with mocks.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from archive import resource_hash
import loader_accept
import lupa


class TestLoaderAcceptance(unittest.TestCase):
    def test_addon_patch(self):
        patch_file = ROOT / 'Addon/9ba626afa44a3aa3.patch_0'
        self.assertTrue(patch_file.is_file(), "Addon patch file must exist")
        data = patch_file.read_bytes()
        names, rejected = loader_accept.scan_file(data)
        self.assertEqual(rejected, [], f"Rejected: {rejected}")
        self.assertIn('mods/kugua/stim_music', names)

    def test_mod_patch(self):
        patch_file = ROOT / 'mod/9ba626afa44a3aa3.patch_0'
        self.assertTrue(patch_file.is_file(), "mod patch file must exist")
        data = patch_file.read_bytes()
        names, rejected = loader_accept.scan_file(data)
        self.assertEqual(rejected, [], f"Rejected: {rejected}")
        self.assertIn('mods/kugua/stim_music', names)


class TestStaticSecurity(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')

    def test_pure_ascii(self):
        for idx, char in enumerate(self.src):
            self.assertLess(ord(char), 128, f"Non-ASCII char at offset {idx}: {repr(char)}")

    def test_no_ffi(self):
        self.assertNotIn("require('ffi')", self.src)
        self.assertNotIn('require("ffi")', self.src)
        self.assertNotIn('ffi.cdef', self.src)
        self.assertNotIn('winmm', self.src)
        self.assertNotIn('kernel32', self.src)

    def test_no_memory_writes_or_reads(self):
        forbidden = [
            'WriteProcessMemory',
            'ReadProcessMemory',
            'VirtualProtect',
            'GetModuleHandle',
        ]
        for term in forbidden:
            self.assertNotIn(term, self.src)

    def test_first_line_declaration(self):
        first_line = self.src.splitlines()[0]
        self.assertEqual(first_line, '-- HD2-Addon: mods/kugua/stim_music')


class TestLuaRuntimeSimulation(unittest.TestCase):
    def test_mock_simulation(self):
        lua = lupa.LuaRuntime(unpack_returned_tuples=False)

        # Mock game VM environment
        env_setup = """
        local calls = {
            audio_plays = {},
            audio_stops = {},
            audio_uploads = {},
            format = nil,
            pool = nil,
            options = {},
            subscribers = {},
        }

        local mock_player_data = {
            health = 80,
            health_max = 100,
            stims = 4,
            alive = true,
        }

        -- Mock MDL3
        _G.MDL3 = {
            audio = {
                api = 1,
                define_format = function(ns, fmt)
                    calls.format = { ns = ns, fmt = fmt }
                    return true
                end,
                pool = function(ns, roles)
                    calls.pool = { ns = ns, roles = roles }
                    return true
                end,
                upload = function(ns, key, b64)
                    calls.audio_uploads[#calls.audio_uploads + 1] = { ns = ns, key = key, len = #b64 }
                    return true
                end,
                status = function(ns)
                    return { ready = 0, pool = 2 }
                end,
                play = function(ns, key, opts)
                    calls.audio_plays[#calls.audio_plays + 1] = { ns = ns, key = key, opts = opts }
                    return true
                end,
                stop = function(ns, role)
                    calls.audio_stops[#calls.audio_stops + 1] = { ns = ns, role = role }
                    return true
                end,
            },
            mod_options_menu = {
                register_option = function(id, spec)
                    calls.options[id] = spec
                    return true
                end,
                get = function(id) return nil end,
                on_change = function(id, cb) end,
            },
            locale = 'zh_CN',
        }

        -- Mock HD2Data
        _G.HD2Data = {
            api = 1,
            version = '0.3.0',
            player = function()
                return mock_player_data
            end,
            on = function(name, cb, opts)
                calls.subscribers[name] = cb
                return {
                    active = function() return true end,
                    unsubscribe = function() calls.subscribers[name] = nil end,
                }
            end,
        }

        _G.MOCK_CALLS = calls
        _G.MOCK_PLAYER = mock_player_data
        """
        lua.execute(env_setup)

        src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
        mod = lua.execute(src)
        self.assertIsNotNone(mod)

        calls = lua.globals().MOCK_CALLS
        player = lua.globals().MOCK_PLAYER
        step_fn = lua.globals().update

        # Initial step to trigger first-frame initialization
        step_fn(0.0)

        # Verify initial registration
        self.assertIsNotNone(calls.format)
        self.assertTrue(calls.format.ns.startswith('mods/kugua/stim_music'))
        self.assertIsNotNone(calls.pool)
        self.assertEqual(calls.pool.roles.stim, 2)

        # Verify options registration, including music track display
        self.assertIn('kugua_stim_music.enabled', calls.options)
        self.assertIn('kugua_stim_music.track', calls.options)
        track_opt = calls.options['kugua_stim_music.track']
        self.assertEqual(track_opt.type, 'choice')
        self.assertGreaterEqual(len(track_opt.choices), 1)

        # 1. First tick with normal health - no stim triggered
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 0)

        # 2. Player uses a stim: stims drops from 4 to 3
        player.stims = 3
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 1)
        self.assertTrue(calls.audio_plays[1].key.startswith('s'))
        self.assertEqual(calls.audio_plays[1].opts.role, 'stim')

        # 3. Next tick inside stim window: still playing, does not trigger a duplicate play
        step_fn(1.0)
        self.assertEqual(len(calls.audio_plays), 1)

        # 4. Stim window finishes (default 6 seconds): step multiple frames
        for _ in range(7):
            step_fn(1.0)
        self.assertEqual(len(calls.audio_stops), 1)
        self.assertEqual(calls.audio_stops[1].role, 'stim')

        # 5. Player stims a second time: stims drops from 3 to 2
        player.stims = 2
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 2)
        # Verify segment progression
        play_key_2 = calls.audio_plays[2].key
        self.assertTrue(play_key_2.startswith('s'))

        # 6. Player takes fatal damage: player.alive = False
        player.alive = False
        step_fn(0.1)
        # Audio should stop immediately
        self.assertGreaterEqual(len(calls.audio_stops), 2)

    def test_consecutive_stims_continuous_chain(self):
        lua = lupa.LuaRuntime(unpack_returned_tuples=False)
        env_setup = """
        local calls = {
            audio_plays = {},
            audio_stops = {},
            audio_releases = {},
            audio_uploads = {},
            format = nil,
            pool = nil,
            options = {},
            subscribers = {},
        }
        local mock_player_data = {
            health = 80,
            health_max = 100,
            stims = 4,
            alive = true,
        }
        os.getenv = function(name) return nil end
        _G.MDL3 = {
            audio = {
                api = 1,
                define_format = function(ns, fmt)
                    calls.format = { ns = ns, fmt = fmt }
                    return true
                end,
                pool = function(ns, roles)
                    calls.pool = { ns = ns, roles = roles }
                    return true
                end,
                upload = function(ns, key, b64)
                    calls.audio_uploads[#calls.audio_uploads + 1] = { ns = ns, key = key }
                    return true
                end,
                status = function(ns)
                    return { ready = 0, pool = 2 }
                end,
                play = function(ns, key, opts)
                    calls.audio_plays[#calls.audio_plays + 1] = { ns = ns, key = key, opts = opts }
                    return true
                end,
                stop = function(ns, role)
                    calls.audio_stops[#calls.audio_stops + 1] = { ns = ns, role = role }
                    return true
                end,
                release = function(ns)
                    calls.audio_releases[#calls.audio_releases + 1] = ns
                    return true
                end,
            },
            mod_options_menu = {
                register_option = function(id, spec)
                    calls.options[id] = spec
                    return true
                end,
                get = function(id) return nil end,
                on_change = function(id, cb)
                    if calls.options[id] then
                        calls.options[id].cb = cb
                    end
                end,
            },
            locale = 'zh_CN',
        }
        _G.HD2Data = {
            api = 1,
            version = '0.3.0',
            player = function() return mock_player_data end,
            on = function(name, cb, opts)
                calls.subscribers[name] = cb
                return {
                    active = function() return true end,
                    unsubscribe = function() calls.subscribers[name] = nil end,
                }
            end,
        }
        _G.MOCK_CALLS = calls
        _G.MOCK_PLAYER = mock_player_data
        """
        lua.execute(env_setup)
        src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
        lua.execute(src)

        calls = lua.globals().MOCK_CALLS
        player = lua.globals().MOCK_PLAYER
        step_fn = lua.globals().update

        step_fn(0.0)

        # Stim 1: player stims (4 -> 3)
        player.stims = 3
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 1)

        # 3 seconds later, player consecutive-stims (3 -> 2)
        for _ in range(30):
            step_fn(0.1)
        player.stims = 2
        step_fn(0.1)

        # Advance past 6.0s (first segment duration): should seamlessly chain into segment 2!
        for _ in range(35):
            step_fn(0.1)

        # Now calls.audio_plays should have chained into segment 2!
        self.assertGreaterEqual(len(calls.audio_plays), 2)
        # Total audio stops should be 0 because music has NOT stopped yet (continuous play)
        self.assertEqual(len(calls.audio_stops), 0)

        # Now advance until the full combined stim duration expires
        for _ in range(70):
            step_fn(0.1)

        # Now it should have stopped once after the entire sequence finished
        self.assertGreaterEqual(len(calls.audio_stops), 1)

    def test_menu_track_switch_reloads_cleanly(self):
        lua = lupa.LuaRuntime(unpack_returned_tuples=False)
        env_setup = """
        local calls = {
            audio_plays = {},
            audio_stops = {},
            audio_releases = {},
            audio_uploads = {},
            format = nil,
            pool = nil,
            options = {},
            subscribers = {},
        }
        local mock_player_data = {
            health = 80,
            health_max = 100,
            stims = 4,
            alive = true,
        }
        os.getenv = function(name) return nil end
        _G.MDL3 = {
            audio = {
                api = 1,
                define_format = function(ns, fmt)
                    calls.format = { ns = ns, fmt = fmt }
                    return true
                end,
                pool = function(ns, roles)
                    calls.pool = { ns = ns, roles = roles }
                    return true
                end,
                upload = function(ns, key, b64)
                    calls.audio_uploads[#calls.audio_uploads + 1] = { ns = ns, key = key }
                    return true
                end,
                status = function(ns)
                    return { ready = 0, pool = 2 }
                end,
                play = function(ns, key, opts)
                    calls.audio_plays[#calls.audio_plays + 1] = { ns = ns, key = key, opts = opts }
                    return true
                end,
                stop = function(ns, role)
                    calls.audio_stops[#calls.audio_stops + 1] = { ns = ns, role = role }
                    return true
                end,
                release = function(ns)
                    calls.audio_releases[#calls.audio_releases + 1] = ns
                    return true
                end,
            },
            mod_options_menu = {
                register_option = function(id, spec)
                    calls.options[id] = spec
                    return true
                end,
                get = function(id) return nil end,
                on_change = function(id, cb)
                    if calls.options[id] then
                        calls.options[id].cb = cb
                    end
                end,
            },
            locale = 'zh_CN',
        }
        _G.HD2Data = {
            api = 1,
            version = '0.3.0',
            player = function() return mock_player_data end,
            on = function(name, cb, opts)
                calls.subscribers[name] = cb
                return {
                    active = function() return true end,
                    unsubscribe = function() calls.subscribers[name] = nil end,
                }
            end,
        }
        _G.MOCK_CALLS = calls
        _G.MOCK_PLAYER = mock_player_data
        """
        lua.execute(env_setup)
        src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
        lua.execute(src)

        calls = lua.globals().MOCK_CALLS
        player = lua.globals().MOCK_PLAYER
        step_fn = lua.globals().update

        step_fn(0.0)

        # First stim
        player.stims = 3
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 1)

        # Trigger track switch via menu callback with a distinct new track name
        track_opt = calls.options['kugua_stim_music.track']
        self.assertIsNotNone(track_opt.cb)
        track_opt.cb('track_switch_test_alt.wav')

        # Verify previous audio stopped and namespace released
        self.assertGreaterEqual(len(calls.audio_stops), 1)
        self.assertGreaterEqual(len(calls.audio_releases), 1)
        self.assertTrue(calls.audio_releases[len(calls.audio_releases)].startswith('mods/kugua/stim_music'))

        # Next stim with new track
        player.stims = 2
        step_fn(0.1)
        # Should start new track's segment 1
        self.assertGreaterEqual(len(calls.audio_plays), 2)
        new_play = calls.audio_plays[len(calls.audio_plays)]
        self.assertTrue(new_play.key.startswith('s2_'))

    def test_volume_slider_scaling_and_persistence(self):
        lua = lupa.LuaRuntime(unpack_returned_tuples=False)
        env_setup = """
        local calls = {
            audio_plays = {},
            audio_stops = {},
            audio_releases = {},
            audio_uploads = {},
            format = nil,
            pool = nil,
            options = {},
            subscribers = {},
        }
        local mock_player_data = {
            health = 80,
            health_max = 100,
            stims = 4,
            alive = true,
        }
        os.getenv = function(name) return nil end
        _G.MDL3 = {
            audio = {
                api = 1,
                define_format = function(ns, fmt)
                    calls.format = { ns = ns, fmt = fmt }
                    return true
                end,
                pool = function(ns, roles)
                    calls.pool = { ns = ns, roles = roles }
                    return true
                end,
                upload = function(ns, key, b64)
                    calls.audio_uploads[#calls.audio_uploads + 1] = { ns = ns, key = key }
                    return true
                end,
                status = function(ns)
                    return { ready = 0, pool = 2 }
                end,
                play = function(ns, key, opts)
                    calls.audio_plays[#calls.audio_plays + 1] = { ns = ns, key = key, opts = opts }
                    return true
                end,
                stop = function(ns, role)
                    calls.audio_stops[#calls.audio_stops + 1] = { ns = ns, role = role }
                    return true
                end,
                release = function(ns)
                    calls.audio_releases[#calls.audio_releases + 1] = ns
                    return true
                end,
            },
            mod_options_menu = {
                register_option = function(id, spec)
                    calls.options[id] = spec
                    return true
                end,
                get = function(id) return nil end,
                on_change = function(id, cb)
                    if calls.options[id] then
                        calls.options[id].cb = cb
                    end
                end,
            },
            locale = 'zh_CN',
        }
        _G.HD2Data = {
            api = 1,
            version = '0.3.0',
            player = function() return mock_player_data end,
            on = function(name, cb, opts)
                calls.subscribers[name] = cb
                return {
                    active = function() return true end,
                    unsubscribe = function() calls.subscribers[name] = nil end,
                }
            end,
        }
        _G.MOCK_CALLS = calls
        _G.MOCK_PLAYER = mock_player_data
        """
        lua.execute(env_setup)
        src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
        lua.execute(src)

        calls = lua.globals().MOCK_CALLS
        player = lua.globals().MOCK_PLAYER
        step_fn = lua.globals().update

        step_fn(0.0)

        # 1. Default volume play:
        player.stims = 3
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), 1)
        self.assertEqual(calls.audio_plays[1].opts.volume, 100)

        # 2. Adjust volume slider to 10 via menu callback:
        vol_opt = calls.options['kugua_stim_music.volume']
        self.assertIsNotNone(vol_opt.cb)
        vol_opt.cb(10)

        # Advance past first stim duration (6.0s) so first stim completes:
        for _ in range(8):
            step_fn(1.0)
        player.stims = 2
        step_fn(0.1)

        self.assertGreaterEqual(len(calls.audio_plays), 2)
        self.assertEqual(calls.audio_plays[len(calls.audio_plays)].opts.volume, 10)

        # 3. String numeric parsing from ModOptionsMenu.values text format ('25'):
        vol_opt.cb('25')
        for _ in range(8):
            step_fn(1.0)
        player.stims = 1
        step_fn(0.1)
        self.assertEqual(calls.audio_plays[len(calls.audio_plays)].opts.volume, 25)

        # 4. Mute volume (0) should stop current playback and prevent playing:
        vol_opt.cb(0)
        self.assertGreaterEqual(len(calls.audio_stops), 1)
        prev_play_count = len(calls.audio_plays)
        player.stims = 0
        step_fn(0.1)
        self.assertEqual(len(calls.audio_plays), prev_play_count)

    def test_ms_adpcm_and_rolling_prefetch_window(self):
        # Alias for backward-compatible test runner: tests dynamic sample-accurate resume and stim_ms adjustment
        self.test_dynamic_sample_accurate_resume_and_stim_ms_adjustment()

    def test_dynamic_sample_accurate_resume_and_stim_ms_adjustment(self):
        import subprocess
        # Generate 30s MS-ADPCM wav file
        test_wav = ROOT / 'test_adpcm_resume.wav'
        ffmpeg_bin = r'D:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe'
        cmd = [
            ffmpeg_bin,
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30',
            '-ac', '2', '-ar', '48000', '-c:a', 'adpcm_ms', '-block_size', '1024',
            '-y', str(test_wav)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"ffmpeg failure: {res.stderr.decode('utf-8', errors='ignore')}")

        try:
            lua = lupa.LuaRuntime(unpack_returned_tuples=False)
            env_setup = """
            local calls = {
                audio_plays = {},
                audio_stops = {},
                audio_releases = {},
                audio_uploads = {},
                format = nil,
                pool = nil,
                options = {},
                subscribers = {},
            }
            local mock_player_data = {
                health = 80,
                health_max = 100,
                stims = 4,
                alive = true,
            }
            os.getenv = function(name) return nil end
            _G.MDL3 = {
                audio = {
                    api = 1,
                    define_format = function(ns, fmt)
                        calls.format = { ns = ns, fmt = fmt }
                        return true
                    end,
                    pool = function(ns, roles)
                        calls.pool = { ns = ns, roles = roles }
                        return true
                    end,
                    upload = function(ns, key, b64)
                        calls.audio_uploads[#calls.audio_uploads + 1] = { ns = ns, key = key, len = #b64 }
                        return true
                    end,
                    status = function(ns)
                        return { ready = 0, pool = 2 }
                    end,
                    play = function(ns, key, opts)
                        calls.audio_plays[#calls.audio_plays + 1] = { ns = ns, key = key, opts = opts }
                        return true
                    end,
                    stop = function(ns, role)
                        calls.audio_stops[#calls.audio_stops + 1] = { ns = ns, role = role }
                        return true
                    end,
                    release = function(ns)
                        calls.audio_releases[#calls.audio_releases + 1] = ns
                        return true
                    end,
                },
                mod_options_menu = {
                    register_option = function(id, spec)
                        calls.options[id] = spec
                        return true
                    end,
                    get = function(id) return nil end,
                    on_change = function(id, cb)
                        if calls.options[id] then
                            calls.options[id].cb = cb
                        end
                    end,
                },
                locale = 'zh_CN',
            }
            _G.HD2Data = {
                api = 1,
                version = '0.3.0',
                player = function() return mock_player_data end,
                on = function(name, cb, opts)
                    calls.subscribers[name] = cb
                    return {
                        active = function() return true end,
                        unsubscribe = function() calls.subscribers[name] = nil end,
                    }
                end,
            }
            _G.MOCK_CALLS = calls
            _G.MOCK_PLAYER = mock_player_data
            """
            lua.execute(env_setup)
            src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
            lua.execute(src)

            calls = lua.globals().MOCK_CALLS
            player = lua.globals().MOCK_PLAYER
            step_fn = lua.globals().update
            M = lua.globals()['__KUGUA_STIM_MUSIC']

            # Step frame 0: mod options binding
            step_fn(0.0)

            # Switch to test WAV track via menu choice
            track_opt = calls.options['kugua_stim_music.track']
            self.assertIsNotNone(track_opt.cb)
            track_opt.cb(str(test_wav).replace('\\', '/'))

            # Idle step pre-buffers first slice (s2_1)
            step_fn(0.1)
            self.assertEqual(len(calls.audio_uploads), 2)
            self.assertEqual(calls.audio_uploads[2].key, 's2_1')
            self.assertLess(calls.audio_uploads[2].len, 200000)

            # 1. First stim: stims 4 -> 3
            player.stims = 3
            step_fn(0.1)
            self.assertEqual(len(calls.audio_plays), 1)
            self.assertEqual(calls.audio_plays[1].key, 's2_1')

            # Let stim play for 3.0 seconds (30 ticks of 0.1s)
            for _ in range(30):
                step_fn(0.1)

            # Player takes fatal damage: stops playback at ~3.0s
            player.alive = False
            step_fn(0.1)
            self.assertGreaterEqual(len(calls.audio_stops), 1)

            # Verify M.track_pos is sample-accurate around 3.0s (NOT 0.0, NOT 6.0)!
            self.assertAlmostEqual(M.track_pos, 3.0, delta=0.2)

            # 2. Player respawns and dynamically adjusts stim_ms in menu (e.g. from 6000ms to 4500ms)
            player.alive = True
            player.stims = 4
            step_fn(0.1)

            stim_opt = calls.options['kugua_stim_music.stim_ms']
            self.assertIsNotNone(stim_opt.cb)
            stim_opt.cb(4500)

            # Verify that adjusting stim_ms preserved track_pos EXACTLY!
            self.assertAlmostEqual(M.track_pos, 3.0, delta=0.2)

            # Player stims again: stims 4 -> 3
            player.stims = 3
            step_fn(0.1)
            self.assertEqual(len(calls.audio_plays), 2)
            self.assertTrue(calls.audio_plays[2].key.startswith('s2_'))
            self.assertAlmostEqual(M.play_start_pos, 3.0, delta=0.2)

            # Advance 4.5 seconds (the new stim_ms duration):
            for _ in range(45):
                step_fn(0.1)
            # Advance past stim end window:
            step_fn(0.1)

            # Verify track_pos paused at 3.0 + 4.5 = 7.5s!
            self.assertAlmostEqual(M.track_pos, 7.5, delta=0.25)

            # 3. Player adjusts stim_ms again to 8000ms
            stim_opt.cb(8000)
            self.assertAlmostEqual(M.track_pos, 7.5, delta=0.25)

            # Next stim resumes from 7.5s
            player.stims = 2
            step_fn(0.1)
            self.assertEqual(len(calls.audio_plays), 3)
            self.assertAlmostEqual(M.play_start_pos, 7.5, delta=0.25)

        finally:
            if test_wav.exists():
                test_wav.unlink()

    def test_auto_deploy_converter_scripts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            clean_tmp = str(tmp_path).replace('\\', '/')
            lua = lupa.LuaRuntime(unpack_returned_tuples=False)
            env_setup = f"""
            local calls = {{
                audio_plays = {{}},
                audio_stops = {{}},
                audio_uploads = {{}},
            }}
            os.getenv = function(name)
                if name == 'LOCALAPPDATA' then return '{clean_tmp}' end
                return nil
            end
            _G.MDL3 = {{
                audio = {{
                    api = 1,
                    define_format = function() return true end,
                    pool = function() return true end,
                    upload = function() return true end,
                    status = function() return {{ ready = 1, pool = 2 }} end,
                    play = function() return true end,
                    stop = function() return true end,
                }},
                mod_options_menu = {{
                    register_option = function() return true end,
                }},
                locale = 'zh_CN',
            }}
            _G.HD2Data = {{
                api = 1,
                version = '0.3.0',
                player = function() return {{ health = 100, stims = 4, alive = true }} end,
                on = function() return {{ active = function() return true end }} end,
            }}
            """
            # Create the candidate music folder so log_dir binds to it
            music_sub = tmp_path / 'CowboyBingus/Helldivers2/StimMusic'
            music_sub.mkdir(parents=True, exist_ok=True)
            (music_sub / 'stim_music.log').write_text('')

            lua.execute(env_setup)
            src = (ROOT / 'Source/mods/kugua/stim_music.lua').read_text(encoding='ascii')
            lua.execute(src)

            # Verification: the mod must have automatically created both scripts!
            cmd_file = music_sub / 'convert_track.cmd'
            ps1_file = music_sub / 'convert_track.ps1'
            self.assertTrue(cmd_file.is_file(), "convert_track.cmd must be auto-deployed")
            self.assertTrue(ps1_file.is_file(), "convert_track.ps1 must be auto-deployed")
            self.assertGreater(ps1_file.stat().st_size, 1000)

            # Close log file handle to allow directory cleanup on Windows
            shutdown_fn = lua.globals().shutdown
            if shutdown_fn:
                shutdown_fn()


if __name__ == '__main__':
    unittest.main()
