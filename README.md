# 塔塔寻宝助手

> 仅供个人学习与非商业技术研究。禁止商业使用、售卖、收费服务及二次牟利。
> 使用、修改和免费分享必须遵守 [LICENSE](LICENSE) 和 [使用声明](NOTICE.md)。
> 本项目采用自定义非商业源码许可，不属于 OSI 开源许可。

独立桌面项目，使用 Python 标准库 Tkinter。双击 `塔塔寻宝助手.exe`，进入游戏寻宝地图，点击“读取 / 刷新地图”。模拟器地址和 ADB 路径可在界面修改。

黄色格子显示客户端模型记录的宝藏占地，其他格子暂显示“待判定”，不代表安全空地。支持每 10 秒刷新及 JSON 导出。不自动点击或挖掘，不修改游戏内存。

## 当前限制

- 需要模拟器 root，读取游戏进程 `/proc/PID/mem`。
- 当前为已验证会话版本，绑定 PID 3148 和当前 Lua 全局表位置。换地图可重新读取；重启游戏/模拟器后需要重新定位，尚未实现通用自动定位。
- 读取失败会清空地图，防止使用旧数据。
- 第一关一次宝藏预测已实际验证；第七关读取到完整 49 格及 5 件宝藏，但未逐格验证。炸弹位置尚未判定。

## 源码

`app.py` 为 UI，`reader.py` 为只读内存及 Lua 5.4 表解析。安装 Python 后可运行 `python app.py`，无需第三方运行时依赖。Windows 打包使用 PyInstaller。

```powershell
python app.py
```

自行打包：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name 塔塔寻宝助手 app.py
```

仓库仅提供源码，不包含游戏文件、调试转储或旧版本启动器。

