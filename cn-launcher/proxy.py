# -*- coding: utf-8 -*-
"""Fizgig 中文界面桥接启动器 —— 反向代理 + 注入层。

- 对绝大多数请求做透明字节级/流式转发到原 Fizgig web server（127.0.0.1:server_port）。
- 对 `/` 与 `/index.html` 注入 translator.js。
- 对 `/__cn__/*` 直接返回本启动器自带的脚本与词典（不转发、不鉴权，登录前即可访问）。

只改这少量路径，其余全部透传，保证登录、上传、训练、下载、日志推送等不受影响。
"""
import http.client
import http.server
import urllib.parse
from pathlib import Path

LAUNCHER_DIR = Path(__file__).resolve().parent

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 8081

INJECT_TAG = b'<script src="/__cn__/translator.js"></script>'

# hop-by-hop 头：逐跳生效，代理不得原样转发到下一跳
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "proxy-connection",
}

_MIME = {
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def _inject(html: bytes) -> bytes:
    """在 </body>（否则 </html>）之前注入翻译脚本。"""
    idx = html.rfind(b"</body>")
    if idx == -1:
        idx = html.rfind(b"</html>")
    if idx == -1:
        return html
    return html[:idx] + INJECT_TAG + html[idx:]


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FizgigCN/1.0"

    def log_message(self, fmt, *args):
        pass  # 安静：控制台留给训练输出

    # ---- 请求头：去掉逐跳头与 Host/Content-Length/Accept-Encoding，强制明文、固定本地 Host ----
    def _fwd_headers(self):
        out = {}
        for k, v in self.headers.items():
            lk = k.lower()
            if lk in HOP_BY_HOP or lk in ("host", "content-length", "accept-encoding"):
                continue
            out[k] = v
        out["Host"] = f"{TARGET_HOST}:{TARGET_PORT}"
        out["Connection"] = "close"
        return out

    # ---- 回传响应头：去逐跳头；按 content_length / chunked 决定传输编码 ----
    def _relay_headers(self, resp, *, sse, content_length):
        for k, v in resp.getheaders():
            lk = k.lower()
            if lk in HOP_BY_HOP or lk in ("content-length", "transfer-encoding", "connection"):
                continue
            self.send_header(k, v)
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        else:
            self.send_header("Transfer-Encoding", "chunked")
        if not sse:
            self.send_header("Connection", "close")

    # ---- /__cn__/*：本启动器自带资源 ----
    def _serve_cn(self, path):
        name = path[len("/__cn__/"):]
        if not name or "/" in name or "\\" in name or name.startswith("."):
            self.send_error(404)
            return
        fp = LAUNCHER_DIR / name
        if not fp.is_file():
            self.send_error(404)
            return
        data = fp.read_bytes()
        ctype = _MIME.get(Path(name).suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass

    # ---- HTML：读全 + 注入 + 重算 Content-Length ----
    def _forward_html(self):
        try:
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=600)
            conn.request("GET", self.path, headers=self._fwd_headers())
            resp = conn.getresponse()
            html = resp.read()
            conn.close()
        except Exception as e:
            self.send_error(502, f"backend unavailable: {e}")
            return
        if "html" in (resp.getheader("Content-Type") or "").lower():
            html = _inject(html)
        self.send_response(resp.status, resp.reason)
        self._relay_headers(resp, sse=False, content_length=len(html))
        self.end_headers()
        try:
            self.wfile.write(html)
        except OSError:
            pass

    # ---- 普通请求：流式转发 ----
    def _forward(self):
        body = None
        if self.command not in ("GET", "HEAD"):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 0:
                body = self.rfile.read(n)
        try:
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=600)
            conn.request(self.command, self.path, body=body, headers=self._fwd_headers())
            resp = conn.getresponse()
        except Exception as e:
            self.send_error(502, f"backend unavailable: {e}")
            return

        sse = (resp.getheader("Content-Type") or "").lower().startswith("text/event-stream")
        cl = resp.getheader("Content-Length")
        self.send_response(resp.status, resp.reason)
        self._relay_headers(resp, sse=sse, content_length=int(cl) if cl is not None else None)
        self.end_headers()

        if self.command == "HEAD":
            conn.close()
            return

        try:
            if cl is not None:
                remaining = int(cl)
                while remaining > 0:
                    chunk = resp.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            else:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except (OSError, http.client.HTTPException):
            # OSError 覆盖 BrokenPipeError / ConnectionResetError / socket.timeout（SSE 长连接空闲超时）
            pass
        finally:
            conn.close()

    # ---- 路由 ----
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/__cn__/"):
            self._serve_cn(path)
        elif path in ("/", "/index.html"):
            self._forward_html()
        else:
            self._forward()

    def do_HEAD(self):
        self._forward()

    def do_POST(self):
        self._forward()

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST


def create_server(proxy_port: int, target_port: int, bind_host: str = "127.0.0.1"):
    global TARGET_PORT
    TARGET_PORT = target_port
    return http.server.ThreadingHTTPServer((bind_host, proxy_port), _Handler)
