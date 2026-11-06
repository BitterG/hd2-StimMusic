"""Assemble and build 9ba626afa44a3aa3.patch_0 from Source/mods/kugua/stim_music.lua."""
from __future__ import annotations

import json
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
src_path = ROOT / 'Source/mods/kugua/stim_music.lua'
if not src_path.is_file():
    print(f"Error: {src_path} not found!")
    sys.exit(1)

lua_code = src_path.read_text(encoding='ascii')
m_ver = re.search(r"local VERSION = '([^']+)'", lua_code)
VERSION = m_ver.group(1) if m_ver else '2.3.0'

print(f"Building {RESOURCE} v{VERSION} from {src_path}...")

# 1. Validate syntax with lupa
import lupa
lua = lupa.LuaRuntime(unpack_returned_tuples=False)
try:
    lua.execute(lua_code)
    print("Lua syntax check: PASSED!")
except Exception as e:
    print(f"Lua syntax check: FAILED! {e}")
    sys.exit(1)

# 2. Pack into 9ba626afa44a3aa3.patch_0
lua_bytes = lua_code.encode('ascii')
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

# 3. Run authentic loader acceptance verification
names, rejected = loader_accept.scan_file(archive_bytes)
print(f"Loader acceptance names: {names}")
print(f"Loader acceptance rejected: {rejected}")
if rejected or RESOURCE not in names:
    print("LOADER ACCEPTANCE FAILED!")
    sys.exit(1)
print("LOADER ACCEPTANCE: 100% PASSED!")

# 4. Update manifest.json
manifest_data = {
    "Version": 1,
    "Guid": "c980dc93-4108-5742-80e4-28f6b06b928a",
    "Name": f"StimMusic v{VERSION} - 打针放音乐",
    "Description": "Requires MDL3 + HD2 Data Hub (0.3.0+). Plays custom music on stim/heal with smooth fade-in/out and dynamic sample resume. / 需要 MDL3 + HD2 Data Hub 前置。打针（回血）播放音乐，支持渐入渐出与毫秒级断点接续。可在 ESC -> MDL 设置中调节选项。",
    "Options": [
        {
            "Name": "StimMusic (打针放音乐)",
            "Description": "Plays custom music upon stimming / healing. Supports fade in/out, volume control, and custom tracks. / 打针回血播放音乐，支持渐入渐出与自定义曲目",
            "Include": [
                "Addon"
            ]
        }
    ]
}
(ROOT / 'manifest.json').write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding='utf-8')
print("Updated manifest.json")

# 5. Create installable zip in dist/
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

# 6. Deploy directly to game directory if present
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

# 7. Also synchronize HD2 Arsenal mod directories if present
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

# 8. Directly deploy conversion scripts to MDL dedicated directory and legacy directories
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
