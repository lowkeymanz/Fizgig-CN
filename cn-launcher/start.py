# -*- coding: utf-8 -*-
"""Fizgig 中文界面桥接启动器入口。

流程：定位 venv Python → 启动原 Fizgig server（子进程）→ 同进程起反向代理 → 打开浏览器 → 阻塞直到退出。
不 import、不修改 Fizgig 的任何源码；只以子进程方式启动 `fizgig.py --web`。
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LAUNCHER_DIR = Path(__file__).resolve().parent


def find_python() -> Path:
    if os.name == "nt":
        p = BASE_DIR / "venv" / "Scripts" / "python.exe"
    else:
        p = BASE_DIR / "venv" / "bin" / "python"
    return p if p.is_file() else Path(sys.executable)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def free_port(start: int) -> int:
    for p in range(start, min(65536, start + 200)):
        if port_free(p):
            return p
    raise SystemExit(f"从 {start} 起找不到可用端口。")


def server_ready(port: int, timeout: float = 120.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Fizgig 中文界面桥接启动器")
    ap.add_argument("--server-port", type=int, default=8081, help="原 Fizgig 服务端口（默认 8081）")
    ap.add_argument("--proxy-port", type=int, default=8090, help="代理端口（默认 8090）")
    ap.add_argument("--host", default="127.0.0.1", help="代理绑定地址（默认 127.0.0.1；0.0.0.0 供外网访问）")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()

    py = find_python()
    if not py.is_file():
        print("未找到 Fizgig 的 Python 环境，请先运行 install_fizgig.bat（或 install_fizgig.py）。")
        return 1

    server_port = args.server_port if port_free(args.server_port) else free_port(args.server_port + 1)
    proxy_port = args.proxy_port if port_free(args.proxy_port) else free_port(args.proxy_port + 1)

    # 启动原 Fizgig server
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            [str(py), "fizgig.py", "--web", "--port", str(server_port)],
            cwd=str(BASE_DIR), env=env, **kw
        )
    except OSError as e:
        print(f"无法启动 Fizgig：{e}")
        return 1

    if not server_ready(server_port):
        try:
            proc.terminate()
        except Exception:
            pass
        print("Fizgig 的 Web UI 未能启动。请先运行 install_fizgig，或手动执行 `python fizgig.py --web` 查看原因。")
        return 1

    # 同进程起代理
    sys.path.insert(0, str(LAUNCHER_DIR))
    from proxy import create_server
    httpd = create_server(proxy_port, server_port, args.host)

    local_host = args.host in ("127.0.0.1", "localhost", "::1")
    if not args.no_browser and local_host:
        webbrowser.open(f"http://127.0.0.1:{proxy_port}/")

    print(f"Fizgig 中文界面已就绪：http://127.0.0.1:{proxy_port}/")
    print(f"（代理端口 {proxy_port}，原服务端口 {server_port}，绑定 {args.host}）")
    print("按 Ctrl+C 退出。")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
