"""Read-only locator for the currently validated game build / Lua 5.4 layout."""
import struct

def locate(reader, target='hunt'):
    if target not in ('hunt','globals'):
        raise ValueError('未知定位目标')
    maps = reader.command(['exec-out', 'su -c "cat /proc/'+reader.pid+'/maps"']).decode()
    regions = []
    for line in maps.splitlines():
        parts = line.split()
        start, end = [int(v,16) for v in parts[0].split('-')]
        if parts[1] == 'rw-p' and len(parts) == 5 and 65536 <= end-start <= 8*1048576:
            regions.append((start,end))
    # Unity runtime allocation arenas are aligned to 16 MiB. Scanning arbitrary
    # large anonymous blocks first exhausted the budget after a long session.
    regions.sort(key=lambda r:(r[0] % (16*1048576) != 0, -(r[1]-r[0])))
    budget = 256*1048576
    scanned = 0
    errors = []
    for start,end in regions:
        if scanned+end-start > budget:
            continue
        data = reader.command(['exec-out',f'su -c "dd if=/proc/{reader.pid}/mem bs=4096 skip={start//4096} count={(end-start)//4096} 2>/dev/null"'])
        scanned += len(data)
        pos = data.find(b'LuaClient\0')
        while pos >= 16:
            try:
                # Runtime name copies are adjacent to links into method/class structures.
                link = struct.unpack_from('<Q',data,pos-16)[0]
                klass = reader.u64(link)
                name = reader.u64(klass+16)
                if reader.mem(name,10) != b'LuaClient\0' or reader.u64(klass+64) != klass:
                    raise ValueError('class mismatch')
                fields = reader.u64(klass+128)
                field = reader.mem(fields,32)
                field_name = struct.unpack_from('<Q',field)[0]
                if not reader.mem(field_name,30).startswith(b'<Instance>k__BackingField\0'):
                    raise ValueError('singleton mismatch')
                instance = reader.u64(reader.u64(klass+184))
                actual_class = reader.u64(instance)
                if actual_class != klass and reader.u64(actual_class+88) != klass:
                    raise ValueError('inheritance mismatch')
                state = reader.u64(instance+32)
                state_class = reader.u64(state)
                if reader.mem(reader.u64(state_class+16),9) != b'LuaState\0':
                    raise ValueError('state mismatch')
                native = reader.u64(state+16)
                if reader.mem(native+8,1) != b'\x08':
                    raise ValueError('thread mismatch')
                g = reader.u64(native+24)
                registry = reader.u64(g+64)
                if reader.mem(registry+8,1) != b'\x05':
                    raise ValueError('registry mismatch')
                array = reader.u64(registry+16)
                if reader.u64(array) != native:
                    raise ValueError('main thread mismatch')
                globals_address = reader.u64(array+16)
                if target == 'globals':
                    globals_table = reader.table(globals_address)
                    if 'ed' not in globals_table or 'package' not in globals_table:
                        raise ValueError('globals mismatch')
                    return globals_address
                ed = reader.table(globals_address)['ed']
                controller = reader.table(ed[0])['HuntController']
                if controller[1] != 69 or 'huntModel' not in reader.table(controller[0]):
                    raise ValueError('controller mismatch')
                return controller[0]
            except (RuntimeError,ValueError,KeyError,struct.error) as exc:
                errors.append(str(exc))
            pos = data.find(b'LuaClient\0',pos+10)
    reader.locator_errors = errors
    raise RuntimeError('未找到兼容的 Lua 状态。请进入寻宝地图；当前仅支持已验证游戏版本的 MuMu。')
