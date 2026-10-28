# 中文界面如何启动

按仓库根目录的 [README.md](README.md) 完成安装之后（Windows 双击 `install_fizgig.bat`，Linux 执行 `python install_fizgig.py`），
用下面的方式启动**中文界面**。中文层不需要安装任何额外依赖，也不改动 Fizgig 的源码。

## Windows

双击 **`cn-launcher\start.bat`**。

它会：

1. 用 `venv\Scripts\python.exe` 在后台启动原版 Fizgig 服务（`fizgig.py --web`，默认端口 8081）；
2. 在同进程起一个本地反代（默认端口 **8090**），向页面注入中文翻译脚本；
3. 自动打开浏览器访问 <http://127.0.0.1:8090/>。

之后照常登录使用即可。要退出，在 `start.bat` 的窗口里按 **Ctrl+C**（原服务和代理会一起关闭）。

## Linux

```bash
cd cn-launcher
./start.sh
```

## 端口与可选参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--proxy-port` | 8090 | 中文界面的访问端口（浏览器用这个） |
| `--server-port` | 8081 | 原版 Fizgig 服务端口，被占用时自动顺延 |
| `--host` | 127.0.0.1 | 代理绑定地址，仅本机访问时用默认值 |
| `--no-browser` | — | 不自动打开浏览器 |

例：想用 9000 端口且不弹浏览器

```bash
venv\Scripts\python.exe cn-launcher\start.py --proxy-port 9000 --no-browser
```

## 常见问题

- **提示 venv 不存在**：先按 README.md 跑一次安装脚本。
- **页面仍是英文**：改过词典后请按 **Ctrl+F5** 强刷一次。
- **想用英文原版**：照 README.md 用 `Launch Fizgig.bat`（或 `./launch_fizgig.sh`），走 8081 端口，与中文启动器互不影响。
