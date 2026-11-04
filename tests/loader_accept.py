"""Validate an addon archive against MDL3 / Shared Loader discovery rules.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from archive import resource_hash

FAMILY = '9ba626afa44a3aa3'
LUA_TYPE_BYTES = bytes((226, 23, 209, 44, 250, 141, 78, 161))
MAGIC = 0xF0000011
DECLARATION = re.compile(rb'^-- HD2-Addon: (mods/[A-Za-z0-9_]+/[A-Za-z0-9_/]+)\r?\n')


def u32(b, off):
    return struct.unpack_from('<I', b, off)[0]


def offset64(b, off):
    high = u32(b, off + 4)
    if high > 2097151:
        return None
    return u32(b, off) + high * 4294967296


def declaration(prefix):
    m = DECLARATION.match(prefix)
    if not m:
        return None
    name = m.group(1).decode('ascii')
    if '//' in name or name.endswith('/') or name == 'mods/codex/loader':
        return None
    return name


def key_bytes(name):
    return resource_hash(name).to_bytes(8, 'little')


def scan_file(data: bytes):
    names, rejected = [], []
    size = len(data)
    if size < 72:
        return names, ['truncated header']
    if u32(data, 0) != MAGIC:
        return names, [f'invalid archive magic {u32(data, 0):#x}']
    types, count = u32(data, 4), u32(data, 8)
    table_start = 72 + 32 * types
    table_end = table_start + 80 * count
    if not (types > 0 and table_end <= size):
        return names, ['truncated archive tables']

    seen = set()
    for index in range(count):
        row = data[table_start + index * 80: table_start + index * 80 + 80]
        if len(row) < 80:
            rejected.append(f'row {index} truncated')
            continue
        if row[8:16] != LUA_TYPE_BYTES:
            continue
        key = row[0:8]
        offset, length = offset64(row, 16), u32(row, 56)
        if key in seen:
            continue
        if offset is None or offset < table_end or length < 8:
            rejected.append(f'row {index}: offset/length unusable')
            continue
        if offset > size or length > size - offset:
            rejected.append(f'row {index}: resource outside the archive')
            continue
        envelope = data[offset:offset + 8]
        body_length = u32(envelope, 0)
        if u32(envelope, 4) != 2 or body_length > length - 8:
            rejected.append(f'row {index}: bad envelope')
            continue
        seen.add(key)
        prefix = data[offset + 8: offset + 8 + min(body_length, 256)]
        name = declaration(prefix)
        if not name:
            rejected.append(f'row {index}: no valid declaration')
            continue
        want_key = key_bytes(name)
        if key != want_key:
            rejected.append(f'row {index}: key {key.hex()} != MurmurHash64A({name!r}) == {want_key.hex()}')
            continue
        names.append(name)
    return names, rejected


if __name__ == '__main__':
    target = ROOT / 'Addon/9ba626afa44a3aa3.patch_0'
    if not target.is_file():
        target = ROOT / 'mod/9ba626afa44a3aa3.patch_0'
    if not target.is_file():
        print('No patch archive found to validate')
        sys.exit(1)
    data = target.read_bytes()
    names, rejected = scan_file(data)
    print(f'Archive: {target.name} ({len(data)} bytes)')
    print(f'Discovered names: {names}')
    print(f'Rejected reasons: {rejected}')
    if rejected or not names:
        print('VALIDATION FAILED')
        sys.exit(1)
    print('VALIDATION SUCCESSFUL: 100% compliant with MDL3 discovery rules!')
