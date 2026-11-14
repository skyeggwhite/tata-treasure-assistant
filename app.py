import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
import threading, queue, json, time
from pathlib import Path
from datetime import datetime
import traceback, subprocess, base64, math, sys
from reader import Reader, ADB
from radish_reader import RadishReader
from radish_runner import RadishRunner

class App:
    def __init__(self, root):
        self.root = root
        root.title('塔塔寻宝助手')
        self.ui_scale=min(float(root.tk.call('tk','scaling'))/(96/72),(root.winfo_screenwidth()-80)/1320,(root.winfo_screenheight()-100)/1020)
        scale=self.ui_scale
        root.tk.call('tk','scaling',(96/72)*scale)
        root.geometry(f'{round(1320*scale)}x{round(1020*scale)}+30+20')
        root.minsize(round(1200*scale),round(960*scale))
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
        self.connected=False;self.connecting=False;self.connection_config=None;self.closing=False
        self.ui_events=queue.Queue();self.preview_busy=False;self.preview_raw=None;self.preview_image=None
        self.connection_status=tk.StringVar(value='未连接')
        self.device=tk.StringVar(value='按连接地址连接');self.device_map={}
        self.preview_status=tk.StringVar(value='连接后显示模拟器当前画面')
        self.action_hint=tk.StringVar(value='请先连接模拟器，再选择功能并进入对应游戏页面。')
        self.read_settings()
        header=tk.Frame(root,bg='#eef2f7');header.pack(fill='x',padx=28,pady=(22,16))
        tk.Label(header,text='塔塔寻宝助手',bg='#eef2f7',fg='#17243a',font=('Microsoft YaHei UI',30,'bold')).pack(side='left')
        tk.Label(header,textvariable=self.connection_status,bg='#dbeafe',fg='#1d4ed8',font=('Microsoft YaHei UI',14),padx=14,pady=7).pack(side='right')
        body=tk.Frame(root,bg='#eef2f7');body.pack(fill='both',expand=True,padx=28,pady=(0,18))
        left=tk.Frame(body,bg='#eef2f7');left.pack(side='left',fill='both',expand=True,padx=(0,18))
        right=tk.Frame(body,bg='white',width=round(380*scale),padx=16,pady=16);right.pack(side='right',fill='both');right.pack_propagate(False)
        panel=tk.Frame(left,bg='white',padx=20,pady=16);panel.pack(fill='x',pady=(0,12))
        tk.Label(panel,text='01  连接模拟器',bg='white',fg='#17243a',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w',pady=(0,8))
        row=tk.Frame(panel,bg='white');row.pack(fill='x')
        self.devices=ttk.Combobox(row,textvariable=self.device,state='readonly');self.devices.pack(side='left',fill='x',expand=True)
        self.devices.bind('<<ComboboxSelected>>',self.select_device)
        self.discover_button=ttk.Button(row,text='刷新',command=self.discover);self.discover_button.pack(side='left',padx=8)
        self.connect_button=ttk.Button(row,text='连接',command=self.connect);self.connect_button.pack(side='left')
        row=tk.Frame(panel,bg='white');row.pack(fill='x',pady=(10,0))
        tk.Label(row,text='连接地址',bg='white',fg='#263449').pack(side='left',padx=(0,10))
        self.serial_entry=ttk.Entry(row,textvariable=self.serial);self.serial_entry.pack(side='left',fill='x',expand=True)
        self.advanced_button=ttk.Button(row,text='高级设置 ▸',command=self.toggle_connection_options);self.advanced_button.pack(side='left',padx=(8,0))
        self.connection_options=tk.Frame(panel,bg='white')
        tk.Label(self.connection_options,text='ADB 路径',bg='white',fg='#64748b').pack(side='left')
        self.adb_entry=ttk.Entry(self.connection_options,textvariable=self.adb);self.adb_entry.pack(side='left',fill='x',expand=True,padx=10)
        ttk.Button(self.connection_options,text='浏览',command=self.browse).pack(side='left')
        panel=tk.Frame(left,bg='white',padx=20,pady=16);panel.pack(fill='x',pady=(0,12))
        tk.Label(panel,text='02  功能与操作',bg='white',fg='#17243a',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w',pady=(0,8))
        row=tk.Frame(panel,bg='white');row.pack(fill='x')
        tk.Label(row,text='选择功能',bg='white',fg='#263449').pack(side='left',padx=(0,10))
        self.feature_box=ttk.Combobox(row,textvariable=self.feature,values=['营地寻宝','挖萝卜'],state='readonly');self.feature_box.pack(side='left',fill='x',expand=True)
        self.feature_box.bind('<<ComboboxSelected>>',self.change_feature)
        tk.Label(panel,textvariable=self.guide,bg='#eff6ff',fg='#476182',font=('Microsoft YaHei UI',13),justify='left',anchor='w',padx=12,pady=10,wraplength=round(710*scale)).pack(fill='x',pady=(10,0))
        tk.Label(panel,textvariable=self.action_hint,bg='white',fg='#476182',font=('Microsoft YaHei UI',12),anchor='w',justify='left',wraplength=round(710*scale)).pack(fill='x',pady=(10,6))
        self.main_actions=tk.Frame(panel,bg='white');self.main_actions.pack(fill='x')
        self.secondary_actions=tk.Frame(panel,bg='white');self.secondary_actions.pack(fill='x',pady=(8,0))
        self.refresh=ttk.Button(self.main_actions,text='读取 / 刷新地图',style='Primary.TButton',command=self.load)
        self.radish_controls=self.main_actions
        self.probe_button=ttk.Button(self.main_actions,text='开始自动探测',style='Primary.TButton',command=self.start_probe)
        self.stop_button=ttk.Button(self.main_actions,text='停止  F9',command=self.stop_probe,state='disabled')
        self.read_position=ttk.Button(self.secondary_actions,text='只读取位置',command=self.load)
        self.auto_box=ttk.Checkbutton(self.secondary_actions,text='每 10 秒刷新地图',variable=self.auto)
        tk.Label(left,textvariable=self.status,anchor='w',justify='left',wraplength=round(740*scale),bg='#dbeafe',fg='#1d4ed8',padx=14,pady=10,font=('Microsoft YaHei UI',13)).pack(fill='x',pady=(0,12))
        board=tk.Frame(left,bg='white',padx=16,pady=12);board.pack(fill='both',expand=True)
        tk.Label(board,textvariable=self.legend,bg='white',fg='#475569',anchor='w',font=('Microsoft YaHei UI',13),wraplength=round(710*scale),justify='left').pack(fill='x',pady=(0,8))
        self.canvas=tk.Canvas(board,bg='#f8fafc',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw());self.canvas.bind('<Motion>',self.hover)
        bottom=tk.Frame(board,bg='white');bottom.pack(fill='x',pady=(8,0))
        ttk.Button(bottom,text='导出结果',command=self.export).pack(side='right')
        tk.Label(bottom,textvariable=self.detail,bg='white',fg='#476182',anchor='w',justify='left',font=('Microsoft YaHei UI',12),wraplength=round(560*scale)).pack(side='left',fill='x',expand=True)
        tk.Label(right,text='当前模拟器画面',bg='white',fg='#17243a',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        self.preview=tk.Canvas(right,bg='#0f172a',highlightthickness=0);self.preview.pack(fill='both',expand=True,pady=(12,8))
        self.preview.bind('<Configure>',lambda e:self.render_preview())
        tk.Label(right,textvariable=self.preview_status,bg='white',fg='#64748b',font=('Microsoft YaHei UI',12),wraplength=round(345*scale),justify='left').pack(fill='x')
        tk.Label(right,text='需要 root · 不修改游戏内存\n自动探测运行中请勿操作地图；F9 可停止。',bg='#eff6ff',fg='#476182',font=('Microsoft YaHei UI',12),justify='left',padx=10,pady=12,wraplength=round(325*scale)).pack(fill='x',pady=(12,0))
        self.adb.trace_add('write',lambda *a:self.connection_changed());self.serial.trace_add('write',lambda *a:self.connection_changed())
        root.bind('<F9>',lambda e:self.stop_probe());root.protocol('WM_DELETE_WINDOW',self.close)
        self.change_feature();root.after(100,self.poll);root.after(10000,self.tick)
        root.after(150,self.discover);root.after(300,self.preview_tick)

    def browse(self):
        if self.busy or self.connecting:return
        path = filedialog.askopenfilename(filetypes=[('ADB','adb.exe')])
        if path:self.adb.set(path)

    def settings_path(self):
        return (Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent)/'settings.json'

    def read_settings(self):
        try:
            d=json.loads(self.settings_path().read_text(encoding='utf-8'))
            for key in ('adb','serial','feature'):
                if key in d:getattr(self,key).set(d[key])
            if self.feature.get() not in ('营地寻宝','挖萝卜'):self.feature.set('营地寻宝')
        except (OSError,ValueError):pass

    def save_settings(self):
        try:self.settings_path().write_text(json.dumps({k:getattr(self,k).get() for k in ('adb','serial','feature')},ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:pass

    @staticmethod
    def adb_command(adb,*args):
        p=subprocess.run([adb,*args],capture_output=True,timeout=12,creationflags=0x08000000)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace').strip() or '模拟器通信失败')
        return p.stdout

    def discover(self):
        if self.busy or self.connecting or getattr(self,'discovering',False):return
        self.discovering=True;self.discover_button.state(['disabled']);adb=self.adb.get().strip()
        def work():
            try:
                devices={}
                manager=Path(adb).parent.parent/'nx_main'/'MuMuManager.exe'
                if manager.exists():
                    p=subprocess.run([str(manager),'info','-v','all'],capture_output=True,timeout=12,creationflags=0x08000000)
                    for key,v in json.loads(p.stdout).items():
                        if v.get('is_android_started') and v.get('adb_port'):
                            devices[f'{v.get("name","MuMu")} · 实例 {key}']=f'{v.get("adb_host_ip","127.0.0.1")}:{v["adb_port"]}'
                if not devices:
                    for line in self.adb_command(adb,'devices').decode().splitlines()[1:]:
                        columns=line.split()
                        if len(columns)>=2 and columns[1]=='device':devices[columns[0]]=columns[0]
                self.ui_events.put(('devices',devices))
            except Exception as exc:self.ui_events.put(('devices_error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def select_device(self,event=None):
        if self.busy or self.connecting:return
        if self.device.get() in self.device_map:self.serial.set(self.device_map[self.device.get()])

    def toggle_connection_options(self):
        if self.connection_options.winfo_manager():
            self.connection_options.pack_forget();self.advanced_button.configure(text='高级设置 ▸')
        else:
            self.connection_options.pack(fill='x',pady=(10,0));self.advanced_button.configure(text='高级设置 ▾')

    def connection_changed(self):
        if self.connection_config!=(self.adb.get().strip(),self.serial.get().strip()):
            self.connected=False;self.connection_config=None;self.reader=None;self.reader_config=None
            self.data=None;self.preview_raw=None;self.stop_event.set()
            self.connection_status.set('未连接 · 请重新连接');self.draw();self.render_preview()
        self.update_controls()

    def update_controls(self):
        locked=self.busy or self.connecting
        enabled=self.connected and not locked
        for w in (self.refresh,self.read_position,self.probe_button):w.configure(state='normal' if enabled else 'disabled')
        self.probe_button.configure(text='自动探测中' if self.busy else '开始自动探测' if self.connected else '请先连接模拟器')
        self.refresh.configure(text='读取 / 刷新地图' if self.connected else '请先连接模拟器')
        self.feature_box.configure(state='disabled' if locked else 'readonly')
        self.devices.configure(state='disabled' if locked else 'readonly')
        for w in (self.serial_entry,self.adb_entry,self.connect_button):w.configure(state='disabled' if locked else 'normal')
        self.discover_button.configure(state='disabled' if locked or getattr(self,'discovering',False) else 'normal')
        self.stop_button.configure(state='normal' if self.busy and getattr(self,'probing',False) else 'disabled')
        self.auto_box.configure(state='normal' if enabled else 'disabled')
        self.action_hint.set('请先在上方连接模拟器，连接成功后才能操作。' if not self.connected else '运行中，请勿手动操作地图；点击停止或按 F9 结束。' if self.busy else '已连接。进入挖萝卜页面后直接开始自动探测，无需先读取。' if self.feature.get()=='挖萝卜' else '已连接。进入营地寻宝地图后点击读取 / 刷新地图。')

    def connect(self):
        if self.busy or self.connecting:return
        signature=(self.adb.get().strip(),self.serial.get().strip())
        adb,serial=signature
        if not Path(adb).is_file() or not serial:
            self.status.set('请填写正确的 ADB 路径和连接地址，可在高级设置中修改。');return
        self.connected=False;self.connecting=True;self.update_controls();self.connection_status.set('正在连接…')
        def work():
            try:
                if ':' in serial:self.adb_command(adb,'connect',serial)
                if self.adb_command(adb,'-s',serial,'get-state').decode().strip()!='device':raise RuntimeError('模拟器未就绪')
                raw=self.adb_command(adb,'-s',serial,'exec-out','screencap','-p')
                if not raw.startswith(b'\x89PNG'):raise RuntimeError('无法读取模拟器画面')
                if 'uid=0' not in self.adb_command(adb,'-s',serial,'shell','su -c "id"').decode():raise RuntimeError('请开启模拟器 root 后重新连接')
                self.ui_events.put(('connected',(signature,raw)))
            except Exception as exc:self.ui_events.put(('connect_error',(signature,str(exc))))
        threading.Thread(target=work,daemon=True).start()

    def preview_tick(self):
        if self.closing:return
        if self.connected and not self.preview_busy:
            self.preview_busy=True;signature=self.connection_config
            def work():
                try:
                    raw=self.adb_command(signature[0],'-s',signature[1],'exec-out','screencap','-p')
                    if not raw.startswith(b'\x89PNG'):raise RuntimeError('截图数据无效')
                    self.ui_events.put(('preview',(signature,True,raw)))
                except Exception as exc:self.ui_events.put(('preview',(signature,False,str(exc))))
            threading.Thread(target=work,daemon=True).start()
        self.root.after(2500,self.preview_tick)

    def render_preview(self):
        self.preview.delete('all')
        if not self.preview_raw:
            self.preview.create_text(self.preview.winfo_width()/2,self.preview.winfo_height()/2,text='连接后显示当前画面',fill='#94a3b8',font=('Microsoft YaHei UI',14));return
        try:
            full=tk.PhotoImage(data=base64.b64encode(self.preview_raw).decode('ascii'),format='png')
            scale=max(1,math.ceil(max(full.width()/max(1,self.preview.winfo_width()-8),full.height()/max(1,self.preview.winfo_height()-8))))
            self.preview_image=full.subsample(scale,scale)
            self.preview.create_image(self.preview.winfo_width()/2,self.preview.winfo_height()/2,image=self.preview_image,anchor='center')
        except tk.TclError:self.preview_status.set('画面解码失败，请重新连接')

    def process_ui_events(self):
        while True:
            try:kind,data=self.ui_events.get_nowait()
            except queue.Empty:return
            if kind in ('devices','devices_error'):
                self.discovering=False;self.discover_button.state(['!disabled'])
                if kind=='devices':
                    self.device_map=data;self.devices.configure(values=list(data))
                    selected=next((k for k,v in data.items() if v==self.serial.get()),next(iter(data),''))
                    self.device.set(selected)
                    if selected and not self.connected:self.serial.set(data[selected])
                else:self.status.set('查找模拟器失败：'+data+'；也可手动填写连接地址。')
            elif kind in ('connected','connect_error'):
                signature,payload=data;self.connecting=False
                if signature!=(self.adb.get().strip(),self.serial.get().strip()):self.update_controls();continue
                self.connected=kind=='connected'
                if self.connected:
                    self.connection_config=signature;self.preview_raw=payload;self.render_preview();self.save_settings()
                    self.connection_status.set('已连接 · root 可用');self.preview_status.set('当前画面 · 每约 2.5 秒刷新');self.status.set('连接成功，请进入对应游戏页面后操作。')
                else:
                    self.connection_config=None;self.preview_raw=None;self.render_preview()
                    self.connection_status.set('连接失败');self.status.set('连接失败：'+payload)
                self.update_controls()
            elif kind=='preview':
                signature,ok,payload=data;self.preview_busy=False
                if signature!=self.connection_config:continue
                if ok:
                    self.preview_raw=payload;self.render_preview();self.preview_status.set('当前画面 · 更新于 '+time.strftime('%H:%M:%S'))
                else:
                    self.preview_raw=None;self.render_preview();self.preview_status.set('画面刷新失败，请检查模拟器连接。')

    def stop_probe(self):
        self.stop_event.set()
        if self.busy and getattr(self,'probing',False):self.status.set('正在停止，等待当前读取或点击结束…')

    def load(self):
        if self.busy or not self.connected or self.connecting:return
        self.probing=False
        self.stop_event.clear()
        self.busy = True
        self.update_controls()
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
        self.process_ui_events()
        try:
            request_id, ok, result = self.events.get_nowait()
            if request_id != self.request_id:
                self.root.after(100,self.poll)
                return
            if ok is None:
                self.data=result;self.describe(result);self.draw()
                self.root.after(100,self.poll);return
            self.busy = False
            self.probing=False;self.update_controls()
            if ok:
                self.data = result
                self.describe(result)
            else:self.data=None;self.status.set('读取 / 探测失败：'+result)
            self.draw()
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def tick(self):
        if self.auto.get() and self.feature.get()=='营地寻宝':self.load()
        self.root.after(10000,self.tick)

    def timeout(self, request_id):
        if self.busy and request_id == self.request_id:
            self.request_id += 1
            self.busy = False
            self.reader = None
            self.reader_config = None
            self.stop_event.set();self.probing=False;self.update_controls()
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
        for w in (self.refresh,self.probe_button,self.stop_button,self.read_position,self.auto_box):w.pack_forget()
        if self.feature.get()=='挖萝卜':
            self.probe_button.pack(side='left',fill='x',expand=True)
            self.stop_button.pack(side='left',padx=(10,0))
            self.read_position.pack(side='left')
            self.guide.set('① 连接模拟器，并开启 root。\n② 进入挖萝卜页面，直接点击“开始自动探测”。\n③ 自动读取目标、移动地图并按 GO；F9 停止。')
            self.legend.set('挖萝卜：只显示当前目标，找到后随机生成下一个；不修改游戏内存。')
        else:
            self.refresh.pack(side='left',fill='x',expand=True)
            self.auto_box.pack(side='left')
            self.guide.set('① 连接模拟器，并开启 root。\n② 进入营地寻宝地图，点击“读取 / 刷新地图”。\n③ 换地图或挖掘后再次刷新；本功能不自动挖掘。')
            self.legend.set('地图预览    ● 黄色：宝藏    ● 灰色：待判定    ✓ 已翻开')
        self.status.set('进入挖萝卜页面后可直接开始自动探测。' if self.connected and self.feature.get()=='挖萝卜' else '进入寻宝地图后点击读取 / 刷新。' if self.connected else '请先连接模拟器，再进入对应游戏页面。');self.draw()
        self.update_controls()
        if self.connected:self.save_settings()

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
        if self.busy or not self.connected or self.connecting or self.feature.get()!='挖萝卜':return
        self.probing=True
        self.stop_event.clear();self.busy=True;self.request_id+=1;request=self.request_id
        self.update_controls()
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
        self.closing=True;self.stop_event.set();self.root.destroy()

if __name__=='__main__':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:pass
    root=tk.Tk()
    App(root)
    root.mainloop()
