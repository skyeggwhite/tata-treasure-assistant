"""Read current radish target and camera; never write game memory."""
import struct
import time
from reader import Reader, PACKAGE
from locator import locate


class RadishReader(Reader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.globals_address = None
        self.live_tables = set()

    def table(self, address):
        result = super().table(address)
        self.live_tables.add(address)
        return result

    def refresh_tables(self):
        pages = set()
        for address in self.live_tables:
            header = self.mem(address, 56)
            if header[8] != 5 or header[11] > 15:
                continue
            ranges = [(address, 56), (self.u64(address+24), (1 << header[11])*24)]
            count = struct.unpack_from('<I', header, 12)[0]
            if count:
                ranges.append((self.u64(address+16), count*16))
            for start, length in ranges:
                if start and length:
                    pages.update(range(start & ~65535, (start+length-1 & ~65535)+65536, 65536))
        for page in pages:
            self.cache.pop(page, None)
        self.prefetch(pages)
        self.live_tables.clear()

    @staticmethod
    def number(ref):
        value, tag = ref
        if tag == 3:
            return struct.unpack('<q', struct.pack('<Q', value))[0]
        if tag == 19:
            return struct.unpack('<d', struct.pack('<Q', value))[0]
        raise RuntimeError('活动坐标数值类型不匹配')

    def read(self):
        started = time.perf_counter()
        self.calls = 0
        self.pid = self.command(['shell', 'pidof', PACKAGE]).decode().strip()
        if not self.pid.isdigit():
            raise RuntimeError('请先启动游戏并进入挖萝卜活动')
        stat = self.command(['exec-out', f'su -c "cat /proc/{self.pid}/stat"']).decode()
        session = (self.pid, stat.rsplit(')', 1)[1].split()[19])
        if session != self.session:
            self.globals_address = None
            self.session = session
            self.cache.clear()
            self.live_tables.clear()
        elif self.live_tables:
            self.refresh_tables()
        if self.globals_address is None:
            self.globals_address = locate(self, target='globals')
        try:
            ed = self.table(self.table(self.globals_address)['ed'][0])
        except (RuntimeError, KeyError, struct.error):
            self.cache.clear()
            self.globals_address = locate(self, target='globals')
            ed = self.table(self.table(self.globals_address)['ed'][0])
        try:
            controller = self.table(ed['CityDetectController'][0])
            view = self.table(controller['_mainView'][0])
            if view.get('isShow', (0, 1))[1] != 17:
                raise RuntimeError('请进入挖萝卜地图后再读取')
            module_address = view['_detectModule'][0]
            module = self.table(module_address)
            model = self.table(controller['homesteadOtherPModel'][0])
            manager = self.table(self.table(ed['HomesteadGPManager'][0])['_instance'][0])
            homestead = self.table(manager['Homestead'][0])
            camera = self.table(homestead['HomesteadSceneCamera'][0])
            define = self.table(ed['HomesteadDefine'][0])
            x, y = (self.number(module[k]) for k in ('_targetGridX', '_targetGridY'))
            width, height = (self.number(model[k]) for k in ('MapWidth', 'MapHeight'))
            if not (0 <= x < width and 0 <= y < height):
                raise RuntimeError('萝卜目标坐标无效')
            cell, ratio = (self.number(define[k]) for k in ('CellSize', 'HeightRatio'))
            cx, cy = (self.number(camera[k]) for k in ('_cachePositionX', '_cachePositionY'))
            size, aspect = (self.number(camera[k]) for k in ('_cacheCameraSize', '_cameraAspect'))
            if not (cell > 0 and ratio > 0 and size > 0 and aspect > 0):
                raise RuntimeError('相机换算参数无效')
            target_world = ((x+y)*cell, (y-x)*cell*ratio)
            # Inverse of the game's GridToWorldPos, rounding is performed at aim time.
            aim_y = (cx/cell + cy/(cell*ratio))/2
            aim_x = cx/cell-aim_y
            return dict(kind='radish', target_x=x, target_y=y, width=width, height=height,
                        energy=self.number(module['_energy']), found=self.number(module['_foundCount']),
                        camera_x=cx, camera_y=cy, camera_size=size, aspect=aspect,
                        target_world_x=target_world[0], target_world_y=target_world[1],
                        aim_x=aim_x, aim_y=aim_y, moving=camera.get('_isCameraMoving',(0,1))[1]==17,
                        game_over=module.get('_isGameOver',(0,1))[1]==17,
                        can_probe=view.get('_forceDisableBtnGo',(0,1))[1]!=17,
                        board=module.get('__instanceId',(module_address,3))[0],
                        read_seconds=round(time.perf_counter()-started,2), adb_calls=self.calls)
        except KeyError as exc:
            raise RuntimeError('未找到挖萝卜活动数据，请进入地图后读取') from exc
