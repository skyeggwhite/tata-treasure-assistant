import subprocess, struct, time

PACKAGE = 'com.lilithgame.pgame.android.cn'
ADB = r'C:\Program Files\NetEase\MuMu Player 12\shell\adb.exe'
# Verified session locator. Rebinding after process restart is not implemented yet.
SESSION_PID = '3148'
ED_TABLE = 0x79a39199be80
CONTROLLER = 0x79a392abf9f0

class Reader:
    def __init__(self, adb=ADB, serial='127.0.0.1:16384'):
        self.base = [adb, '-s', serial]
        self.cache = {}
        self.calls = 0

    def prefetch(self, addresses):
        pages = sorted({a & ~65535 for a in addresses if 0x10000 < a < 0x800000000000} - self.cache.keys())
        # One root/ADB process per batch, instead of per memory block.
        for start in range(0, len(pages), 24):
            batch = pages[start:start+24]
            commands = [f'dd if=/proc/{self.pid}/mem bs=4096 skip={p//4096} count=16 2>/dev/null' for p in batch]
            data = self.command(['exec-out', 'su -c "' + '; '.join(commands) + '"'])
            if len(data) != len(batch)*65536:
                raise RuntimeError('批量内存读取不完整，请重新刷新')
            for i, page in enumerate(batch):
                self.cache[page] = data[i*65536:(i+1)*65536]

    def command(self, args):
        self.calls += 1
        result = subprocess.run(self.base + args, capture_output=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace').strip() or '模拟器连接失败')
        return result.stdout

    def mem(self, address, length):
        if not 0x10000 < address < 0x800000000000 or not 0 < length <= 1048576:
            raise RuntimeError('内存地址或长度校验失败')
        result = bytearray()
        while length:
            page = address & ~65535
            offset = address - page
            count = min(length, 65536 - offset)
            if page not in self.cache:
                self.cache[page] = self.command(['exec-out', f'su -c "dd if=/proc/{self.pid}/mem bs=4096 skip={page//4096} count=16 2>/dev/null"'])
            part = self.cache[page][offset:offset+count]
            if len(part) != count:
                raise RuntimeError('内存读取不完整，请检查 root 或游戏状态')
            result.extend(part)
            address += count
            length -= count
        return bytes(result)

    def u64(self, address):
        return struct.unpack('<Q', self.mem(address, 8))[0]

    def string(self, address):
        header = self.mem(address, 24)
        if header[8] not in (4, 20):
            raise ValueError('字符串类型不匹配')
        size = header[11] if header[8] == 4 else self.u64(address+16)
        if size > 300:
            raise ValueError('字符串过长')
        return self.mem(address+24, size).decode('utf-8', errors='replace') if size else ''

    def table(self, address):
        header = self.mem(address, 56)
        if header[8] != 5 or header[11] > 15:
            raise RuntimeError('Lua 表校验失败，当前会话地址可能已失效')
        count = 1 << header[11]
        data = self.mem(self.u64(address+24), count*24)
        self.prefetch([struct.unpack_from('<Q',data,i+16)[0] for i in range(0,len(data),24)
                       if data[i+8] and data[i+9]&15==4])
        result = {}
        for i in range(count):
            offset = i*24
            tag, keytag = data[offset+8], data[offset+9]
            if tag == 0:
                continue
            value = struct.unpack_from('<Q', data, offset)[0]
            key = struct.unpack_from('<Q', data, offset+16)[0]
            if keytag & 15 == 4:
                try:
                    key = self.string(key)
                except (ValueError, RuntimeError):
                    continue
            elif keytag != 3:
                continue
            result[key] = (value, tag)
        size = struct.unpack_from('<I', header, 12)[0]
        array = self.u64(address+16)
        if size > 32768:
            raise RuntimeError('Lua 数组长度异常')
        if array and size:
            data = self.mem(array, size*16)
            for i in range(size):
                tag = data[i*16+8]
                if tag:
                    result[i+1] = (struct.unpack_from('<Q', data, i*16)[0], tag)
        return result

    def read(self):
        started = time.perf_counter()
        self.calls = 0
        self.cache.clear()
        self.pid = self.command(['shell', 'pidof', PACKAGE]).decode().strip()
        if self.pid != SESSION_PID:
            raise RuntimeError('游戏进程已变化。本版绑定已验证会话，重启后需要重新定位；请勿使用旧地图。')
        if 'uid=0' not in self.command(['shell', 'su -c "id"']).decode():
            raise RuntimeError('请开启模拟器 root 权限')
        # Validated session instance: avoid decoding all 2660 unrelated ed entries.
        controller = self.table(CONTROLLER)
        if 'huntModel' not in controller or 'HuntNet' not in controller:
            raise RuntimeError('活动实例校验失败，需要重新定位')
        model = self.table(controller['huntModel'][0])
        board = self.table(model['boardData'][0])
        width, height = board['width'][0], board['height'][0]
        if not 1 <= width <= 20 or not 1 <= height <= 20:
            raise RuntimeError('地图尺寸异常')
        tiles = []
        tile_refs = self.table(board['tiles'][0])
        addresses = [address for address,tag in tile_refs.values() if tag == 69]
        self.prefetch(addresses)
        node_ranges = []
        for address in addresses:
            header = self.mem(address,56)
            if header[8] != 5 or header[11] > 15:
                raise RuntimeError('地块对象校验失败')
            node = struct.unpack_from('<Q',header,24)[0]
            length = (1 << header[11])*24
            node_ranges.extend(range(node & ~65535, ((node+length-1)&~65535)+1,65536))
        self.prefetch(node_ranges)
        keys = []
        for address in addresses:
            header = self.mem(address,56)
            nodes = self.mem(self.u64(address+24),(1<<header[11])*24)
            keys.extend(struct.unpack_from('<Q',nodes,i+16)[0] for i in range(0,len(nodes),24) if nodes[i+9]&15==4)
        self.prefetch(keys)
        for _, (address, tag) in tile_refs.items():
            if tag != 69:
                continue
            field = self.table(address)
            if not all(k in field for k in ('x', 'y', 'tileTid', 'treasureID', 'isFlipped')):
                continue
            tiles.append(dict(x=field['x'][0], y=field['y'][0], treasure=field['treasureID'][0],
                              tile_type=field['tileTid'][0], flipped=field['isFlipped'][1] == 17))
        if len(tiles) != width*height or len({(t['x'],t['y']) for t in tiles}) != len(tiles):
            raise RuntimeError('地图数据不完整，请进入挖宝地图后刷新')
        if any(not 1 <= t['x'] <= width or not 1 <= t['y'] <= height for t in tiles):
            raise RuntimeError('地块坐标异常')
        return dict(board=board['boardID'][0], width=width, height=height, tiles=tiles,
                    pid=self.pid, treasure_count=len({t['treasure'] for t in tiles if t['treasure']}),
                    read_seconds=round(time.perf_counter()-started,2), adb_calls=self.calls)
