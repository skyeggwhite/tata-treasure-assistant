"""Align the camera using read-only feedback, then send ordinary ADB input."""
import re
import time


class RadishRunner:
    def __init__(self, reader, stop, event):
        self.reader, self.stop, self.event = reader, stop, event
        self.board = None
        self.width, self.height = 1080, 1920

    def read(self):
        d = self.reader.read()
        if self.board is None:
            self.board = d['board']
        if d['board'] != self.board:
            raise RuntimeError('活动已切换，停止自动探测，请重新读取')
        self.event(d)
        return d

    def input(self, *args):
        if not self.stop.is_set():
            self.reader.command(['shell', 'input', *map(str,args)])

    @staticmethod
    def aligned(d):
        return (not d['moving'] and round(d['aim_x']) == d['target_x']
                and round(d['aim_y']) == d['target_y']
                and max(abs(d['aim_x']-d['target_x']),abs(d['aim_y']-d['target_y'])) < .45)

    def run(self):
        size = self.reader.command(['shell','wm','size']).decode()
        sizes = re.findall(r'(\d+)x(\d+)',size)
        if sizes:
            self.width,self.height = map(int,sizes[-1])
        if abs(self.width/self.height-9/16) > .03:
            raise RuntimeError('自动探测仅适配已验证的 9:16 竖屏，请调整模拟器分辨率')
        probes = 0
        d = self.read()
        while not self.stop.is_set() and probes < 6:
            d = self.read()
            if d['game_over'] or d['energy'] <= 0:
                return d
            before = d
            target = (d['target_x'],d['target_y'])
            for _ in range(12):
                if self.stop.is_set():return d
                if (d['energy'],d['found']) != (before['energy'],before['found']):
                    raise RuntimeError('探测数据在瞄准期间变化，已停止，避免与手动操作冲突')
                if (d['target_x'],d['target_y']) != target:
                    raise RuntimeError('目标在瞄准期间变化，已停止')
                if self.aligned(d):
                    self.stop.wait(.8)
                    d = self.read()
                    if self.aligned(d) and d['can_probe']:break
                    continue
                dx = -(d['target_world_x']-d['camera_x'])*self.height/(2*d['camera_size'])
                dy = (d['target_world_y']-d['camera_y'])*self.height/(2*d['camera_size'])
                limit = self.width*.32
                factor = min(1,limit/max(1,abs(dx),abs(dy)))
                x,y = self.width*.5,self.height*(850/1920)
                self.input('swipe',round(x),round(y),round(x+dx*factor),round(y+dy*factor),600)
                self.stop.wait(1)
                d = self.read()
            else:
                raise RuntimeError('瞄准未收敛，未按 GO。请停止拖动地图并重新读取')
            if self.stop.is_set():return d
            if not self.aligned(d) or not d['can_probe']:
                raise RuntimeError('瞄准或按钮状态未就绪，未按 GO')
            if ((d['energy'],d['found']) != (before['energy'],before['found'])
                    or (d['target_x'],d['target_y']) != target):
                raise RuntimeError('探测数据已变化，未按 GO')
            self.input('tap',round(self.width*925/1080),round(self.height*1775/1920))
            probes += 1
            started = time.monotonic()
            while not self.stop.is_set():
                self.stop.wait(1)
                d = self.read()
                if d['found'] > before['found']:
                    # Allow the dog/celebration animation to finish before another input.
                    self.stop.wait(4)
                    break
                if d['game_over']:
                    return d
                if time.monotonic()-started > 30:
                    raise RuntimeError('本次 GO 未确认命中，已停止，不重复消耗次数')
        return d
