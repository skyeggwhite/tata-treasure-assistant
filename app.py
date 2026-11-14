import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
import threading, queue, json, time
from pathlib import Path
from datetime import datetime
import traceback
from reader import Reader, ADB
from radish_reader import RadishReader
from radish_runner import RadishRunner

class App:
    def __init__(self, root):
        self.root = root
        root.title('塔塔寻宝助手')
        root.geometry('1180x940')
        root.minsize(960, 800)
        root.configure(bg='#eef2f7')
        root.option_add('*Font', ('Microsoft YaHei UI', 14))
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI',14), background='white', foreground='#263449')
        style.configure('TEntry', padding=7, fieldbackground='white')
        style.configure('TButton', padding=(12,8), background='#e9eef6', borderwidth=0)
        style.map('TButton', background=[('active','#dbe5f5')])
        style.configure('Primary.TButton', background='#2563eb', foreground='white', font=('Microsoft YaHei UI',15,'bold'))
        style.map('Primary.TButton', background=[('disabled','#cbd5e1'),('active','#1d4ed8')], foreground=[('disabled','#64748b')])
        self.events = queue.Queue()
        self.busy = False
        self.request_id = 0
        self.data = None
        self.reader = None
        self.reader_config = None
        self.serial = tk.StringVar(value='127.0.0.1:16384')
        self.adb = tk.StringVar(value=ADB)
        self.auto = tk.BooleanVar()
        self.feature = tk.StringVar(value='营地寻宝')
        self.stop_event = threading.Event()
        self.guide=tk.StringVar(value='① 开启模拟器 root，进入游戏的寻宝地图。\n② 点击“读取 / 刷新地图”，下方显示当前地图的宝藏位置。\n③ 换地图或挖掘后，再次点击刷新；也可勾选自动刷新。')
        self.legend=tk.StringVar(value='地图预览    ● 黄色：宝藏    ● 灰色：待判定    ✓ 已翻开')
        self.status = tk.StringVar(value='等待读取')
        self.detail = tk.StringVar(value='把鼠标移到地块上，可查看坐标和状态。')
        header=tk.Frame(root,bg='#eef2f7')
        header.pack(fill='x',padx=28,pady=(22,16))
        tk.Label(header,text='塔塔寻宝助手',bg='#eef2f7',fg='#17243a',font=('Microsoft YaHei UI',30,'bold')).pack(side='left')
        tk.Label(header,text='塔塔冒险队 · MuMu',bg='#eef2f7',fg='#64748b',font=('Microsoft YaHei UI',15)).pack(side='left',padx=18)
        panel=tk.Frame(root,bg='white',padx=20,pady=16)
        panel.pack(fill='x',padx=28)
        tk.Label(panel,text='使用流程',bg='white',fg='#17243a',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        tk.Label(panel,textvariable=self.guide,bg='#eff6ff',fg='#476182',font=('Microsoft YaHei UI',14),justify='left',anchor='w',padx=12,pady=10).pack(fill='x',pady=(10,12))
        row=tk.Frame(panel,bg='white');row.pack(fill='x')
        feature_row=tk.Frame(panel,bg='white');feature_row.pack(fill='x',before=row,pady=(0,10))
        tk.Label(feature_row,text='选择功能',bg='white',fg='#263449').pack(side='left',padx=(0,10))
        self.feature_box=ttk.Combobox(feature_row,textvariable=self.feature,values=['营地寻宝','挖萝卜'],state='readonly',width=12)
        self.feature_box.pack(side='left',padx=(0,10));self.feature_box.bind('<<ComboboxSelected>>',self.change_feature)
        tk.Label(row,text='模拟器地址',bg='white',fg='#263449').pack(side='left')
        ttk.Entry(row,textvariable=self.serial,width=20).pack(side='left',padx=10)
        self.refresh=ttk.Button(row,text='读取 / 刷新地图',style='Primary.TButton',command=self.load)
        self.refresh.pack(side='left',padx=5)
        ttk.Button(row,text='导出 JSON',command=self.export).pack(side='left',padx=5)
        ttk.Checkbutton(row,text='每 10 秒刷新',variable=self.auto).pack(side='left',padx=10)
        self.radish_controls=tk.Frame(panel,bg='white')
        self.probe_button=ttk.Button(self.radish_controls,text='开始自动探测',style='Primary.TButton',command=self.start_probe)
        self.probe_button.pack(side='left')
        self.stop_button=ttk.Button(self.radish_controls,text='停止  F9',command=lambda:self.stop_event.set(),state='disabled');self.stop_button.pack(side='left',padx=10)
        tk.Label(self.radish_controls,text='找到后随机生成下一个目标，每次先读坐标再瞄准；运行中请勿操作地图。',bg='white',fg='#476182',font=('Microsoft YaHei UI',12),wraplength=600).pack(side='left')
        root.bind('<F9>',lambda e:self.stop_event.set())
        path=tk.Frame(panel,bg='white');path.pack(fill='x',pady=(12,0))
        tk.Label(path,text='ADB 路径',bg='white',fg='#64748b').pack(side='left')
        ttk.Entry(path,textvariable=self.adb).pack(side='left',fill='x',expand=True,padx=10)
        ttk.Button(path,text='选择',command=self.browse).pack(side='left')
        tk.Label(root,textvariable=self.status,anchor='w',justify='left',wraplength=1080,bg='#dbeafe',fg='#1d4ed8',padx=14,pady=10).pack(fill='x',padx=28,pady=12)
        board=tk.Frame(root,bg='white',padx=16,pady=12);board.pack(fill='both',expand=True,padx=28)
        tk.Label(board,textvariable=self.legend,bg='white',fg='#475569',anchor='w',font=('Microsoft YaHei UI',14)).pack(fill='x',pady=(0,8))
        self.canvas=tk.Canvas(board,bg='#f8fafc',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<Motion>',self.hover)
        tk.Label(board,textvariable=self.detail,bg='white',fg='#476182',anchor='w').pack(fill='x',pady=(8,0))
        tk.Label(root,text='需要 root · 不修改游戏内存 · 营地寻宝仅预览，挖萝卜可单独启动自动探测\n首次读取较慢；换活动后请重新读取。仅适配当前已验证游戏版本和竖屏。',bg='#eef2f7',fg='#64748b',justify='left',anchor='w',font=('Microsoft YaHei UI',12)).pack(fill='x',padx=28,pady=(12,18))
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)
        root.after(10000,self.tick)

    def browse(self):
        path = filedialog.askopenfilename(filetypes=[('ADB','adb.exe')])
        if path:self.adb.set(path)

    def load(self):
        if self.busy:return
        self.stop_event.clear()
        self.busy = True
        self.request_id += 1
        request_id = self.request_id
        self.root.after(180000, lambda:self.timeout(request_id))
        self.data = None
        self.draw()
        self.refresh.state(['disabled'])
        self.feature_box.configure(state='disabled')
        self.status.set('正在检查模拟器、root 和地图数据…')
        adb, serial = self.adb.get(), self.serial.get()
        if self.reader_config != (adb,serial,self.feature.get()):
            self.reader = (RadishReader if self.feature.get()=='挖萝卜' else Reader)(adb,serial)
            self.reader_config = (adb,serial,self.feature.get())
        reader = self.reader
        def work():
            try:self.events.put((request_id, True, reader.read()))
            except Exception as exc:self.events.put((request_id, False,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            request_id, ok, result = self.events.get_nowait()
            if request_id != self.request_id:
                self.root.after(100,self.poll)
                return
            if ok is None:
                self.data=result;self.describe(result);self.draw()
                self.root.after(100,self.poll);return
            self.busy = False
            self.refresh.state(['!disabled'])
            self.feature_box.configure(state='readonly');self.probe_button.state(['!disabled']);self.stop_button.state(['disabled'])
            if ok:
                self.data = result
                self.describe(result)
            else:self.data=None;self.status.set('读取 / 探测失败：'+result)
            self.draw()
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def tick(self):
        if self.auto.get():self.load()
        self.root.after(10000,self.tick)

    def timeout(self, request_id):
        if self.busy and request_id == self.request_id:
            self.request_id += 1
            self.busy = False
            self.reader = None
            self.reader_config = None
            self.refresh.state(['!disabled'])
            self.stop_event.set();self.feature_box.configure(state='readonly');self.probe_button.state(['!disabled']);self.stop_button.state(['disabled'])
            self.status.set('读取超时，可再次点击刷新。请检查模拟器连接和 root 状态。')

    def draw(self):
        c=self.canvas
        c.delete('all')
        if not self.data:
            c.create_text(c.winfo_width()/2,c.winfo_height()/2,text='进入对应游戏页面后，点击上方读取按钮',fill='#64748b',font=('Microsoft YaHei UI',16))
            return
        d=self.data
        if d.get('kind')=='radish':
            self.draw_radish(d);return
        size=max(1,min((c.winfo_width()-60)/d['width'],(c.winfo_height()-48)/d['height']))
        left=(c.winfo_width()-size*d['width'])/2
        top=(c.winfo_height()-size*d['height'])/2+8
        self.board_geometry=(left,top,size)
        for x in range(d['width']):
            c.create_text(left+(x+.5)*size,top-15,text=str(x+1),fill='#64748b',font=('Microsoft YaHei UI',11))
        for y in range(d['height']):
            c.create_text(left-18,top+(y+.5)*size,text=str(y+1),fill='#64748b',font=('Microsoft YaHei UI',11))
        for t in d['tiles']:
            x=left+(t['x']-1)*size;y=top+(t['y']-1)*size
            treasure=t['treasure'];color='#fef3c7' if treasure else '#e2e8f0'
            c.create_rectangle(x+3,y+3,x+size-3,y+size-3,fill=color,outline='#d4a72c' if treasure else '#cbd5e1',width=2)
            # One short label per cell. Coordinates and state live outside the grid.
            text=str(treasure) if treasure else '·'
            # Negative font sizes use pixels, independent of Windows DPI scaling.
            font=tkfont.Font(family='Microsoft YaHei UI',size=-max(1,int(size*.36)),weight='bold')
            limit=max(1,size*.48)
            while (font.measure(text)>limit or font.metrics('linespace')>size*.55) and abs(font.cget('size'))>1:
                font.configure(size=font.cget('size')+1)
            c.create_text(x+size/2,y+size/2,text=text,fill='#92400e' if treasure else '#64748b',font=font)
            if t['flipped']:
                # Draw the state mark in its own inset corner; no glyph overflow.
                inset=max(5,size*.10);mark=size*.18
                mx=x+size-inset-mark;my=y+inset
                c.create_line(mx,my+mark*.55,mx+mark*.35,my+mark,mx+mark,my,
                              fill='#15803d',width=max(1,size*.035),capstyle='round',joinstyle='round')

    def hover(self,event):
        if not self.data or not hasattr(self,'board_geometry'):return
        if self.data.get('kind')=='radish':return
        left,top,size=self.board_geometry
        x=int((event.x-left)//size)+1;y=int((event.y-top)//size)+1
        t=next((t for t in self.data['tiles'] if t['x']==x and t['y']==y),None)
        if t:
            content=f'宝藏 {t["treasure"]}' if t['treasure'] else '无宝藏编号，炸弹 / 空地待判定'
            self.detail.set(f'第 {y} 行 · 第 {x} 列    {content}    {"已翻开" if t["flipped"] else "未翻开"}')

    def export(self):
        if not self.data:
            self.status.set('请先成功读取地图再导出。')
            return
        name='挖萝卜当前目标.json' if self.data.get('kind')=='radish' else f'寻宝第{self.data["board"]}关.json'
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile=name,filetypes=[('JSON','*.json')])
        if path:
            with open(path,'w',encoding='utf-8') as f:json.dump(self.data,f,ensure_ascii=False,indent=2)

    def describe(self,d):
        if d.get('kind')=='radish':
            if d['game_over']:
                self.status.set(f'挖萝卜结束 · 已找到 {d["found"]} 个 · 剩余 {d["energy"]} 次')
                self.detail.set('本次活动已结束。下一次进入挖萝卜页面后，请重新读取。')
                return
            self.status.set(f'当前目标 ({d["target_x"]}, {d["target_y"]}) · 已找到 {d["found"]} · 剩余 {d["energy"]} 次 · 读取 {d["read_seconds"]} 秒'+(' · 已停止' if self.stop_event.is_set() else ' · 活动结束' if d['game_over'] else ''))
            self.detail.set(f'瞄准坐标 ({d["aim_x"]:.2f}, {d["aim_y"]:.2f})。示意图使用游戏内部坐标，找到后目标会更新。')
        else:
            self.status.set(f'第 {d["board"]} 关 · {d["width"]}×{d["height"]} · {d["treasure_count"]} 件宝藏 · 耗时 {d.get("read_seconds",0)} 秒 · 更新于 {time.strftime("%H:%M:%S")}')

    def change_feature(self,event=None):
        if self.busy:return
        self.data=None;self.reader=None;self.reader_config=None
        if self.feature.get()=='挖萝卜':
            self.radish_controls.pack(fill='x',pady=(12,0))
            self.guide.set('① 开启 root，进入挖萝卜页面，暂不点击 GO。\n② 点击“读取 / 刷新地图”，显示当前目标与瞄准点。\n③ 点击“开始自动探测”，助手移动地图并按 GO；F9 停止。')
            self.legend.set('挖萝卜：只显示当前目标，找到后随机生成下一个；不修改游戏内存。')
        else:
            self.radish_controls.pack_forget()
            self.guide.set('① 开启 root，进入营地寻宝地图。\n② 点击“读取 / 刷新地图”，显示当前宝藏位置。\n③ 换地图或挖掘后再次刷新；本功能不自动挖掘。')
            self.legend.set('地图预览    ● 黄色：宝藏    ● 灰色：待判定    ✓ 已翻开')
        self.status.set('请选择对应游戏页面，然后点击读取 / 刷新');self.draw()

    def draw_radish(self,d):
        c=self.canvas;w,h=c.winfo_width(),c.winfo_height()
        if d['game_over']:
            c.create_text(w/2,h/2,text=f'本次已结束\n找到 {d["found"]} 个萝卜',fill='#2563eb',font=('Microsoft YaHei UI',24,'bold'),justify='center')
            return
        size=max(1,min((w-140)/d['width'],(h-100)/d['height']))
        left=(w-size*d['width'])/2;top=(h-size*d['height'])/2
        c.create_rectangle(left,top,left+size*d['width'],top+size*d['height'],fill='#eff6ff',outline='#cbd5e1')
        for n in range(0,121,20):
            c.create_line(left+n*size,top,left+n*size,top+size*d['height'],fill='#dbeafe')
            c.create_line(left,top+n*size,left+size*d['width'],top+n*size,fill='#dbeafe')
        for x,y,color in [(d['target_x'],d['target_y'],'#d97706'),(d['aim_x'],d['aim_y'],'#2563eb')]:
            px,py=left+x*size,top+(d['height']-y)*size
            c.create_oval(px-7,py-7,px+7,py+7,fill=color,outline='white',width=2)
        c.create_text(w/2,22,text='营地坐标示意：橙色为当前萝卜，蓝色为瞄准点',fill='#475569',font=('Microsoft YaHei UI',14))
        c.create_text(w/2,h-20,text=f'目标 X={d["target_x"]}   Y={d["target_y"]}    每次命中后重新读取下一个目标',fill='#92400e',font=('Microsoft YaHei UI',15,'bold'))

    def start_probe(self):
        if self.busy:return
        self.stop_event.clear();self.busy=True;self.request_id+=1;request=self.request_id
        adb,serial=self.adb.get(),self.serial.get()
        if self.reader_config!=(adb,serial,'挖萝卜'):
            self.reader=RadishReader(adb,serial);self.reader_config=(adb,serial,'挖萝卜')
        reader=self.reader
        self.refresh.state(['disabled']);self.probe_button.state(['disabled']);self.stop_button.state(['!disabled']);self.feature_box.configure(state='disabled')
        self.status.set('自动探测：读取目标后瞄准，再点击 GO…')
        def work():
            try:
                data=RadishRunner(reader,self.stop_event,lambda d:self.events.put((request,None,d))).run()
                self.events.put((request,True,data))
            except Exception as exc:
                message=str(exc)
                try:
                    folder=Path(__file__).resolve().parent if not getattr(__import__('sys'),'frozen',False) else Path(__import__('sys').executable).resolve().parent
                    folder=folder/'diagnostics'/datetime.now().strftime('%Y%m%d_%H%M%S_%f');folder.mkdir(parents=True)
                    (folder/'error.json').write_text(json.dumps({'error':message,'traceback':traceback.format_exc()},ensure_ascii=False,indent=2),encoding='utf-8')
                    try:(folder/'screen.png').write_bytes(reader.command(['exec-out','screencap','-p']))
                    except Exception:pass
                    message+='；诊断信息已保存：'+str(folder)
                except Exception:pass
                self.events.put((request,False,message))
        threading.Thread(target=work,daemon=True).start()

    def close(self):
        self.stop_event.set();self.root.destroy()

if __name__=='__main__':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:pass
    root=tk.Tk()
    App(root)
    root.mainloop()
