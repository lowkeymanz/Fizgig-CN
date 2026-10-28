# -*- coding: utf-8 -*-
"""抓取其余返回 UI 文本的 GET API，对照词典输出未翻译项（补第 4 类汉化点）。"""
import io
import json
import os
import re
import subprocess
import time
import urllib.request

BASE = r"d:/Fizgig-CN"
PY = BASE + r"/venv/Scripts/python.exe"
DICT = BASE + r"/cn-launcher/dict.json"
OUT = BASE + r"/cn-launcher/_untranslated_apis.txt"
PORT = 8398

APIS = [
    "/api/prefs",
    "/api/state",
    "/api/captions/options",
    "/api/refmod/info",
    "/api/extract/info",
    "/api/royale/info",
    "/api/profile/info",
    "/api/studio/families",
    "/api/studio/layout",
    "/api/fetch",
    "/api/helpers",
]

with io.open(DICT, encoding="utf-8") as f:
    phrases = json.load(f)["phrases"]
exact, regexes = {}, []
for p in phrases:
    if p.get("re"):
        try:
            regexes.append([re.compile(p["re"]), p["zh"]])
        except re.error:
            pass
    elif p.get("en"):
        exact[p["en"]] = p["zh"]


def apply(text):
    s = str(text)
    if s in exact:
        return exact[s]
    t = s.strip()
    if t and t != s and t in exact:
        return s.replace(t, exact[t])
    if not t:
        return None
    m = re.search(r"[:：]\s*$", t)
    if m:
        nc = t[:m.start()]
        if nc != t and nc in exact:
            return s.replace(t, exact[nc] + t[m.start():])
    for rx, zh in regexes:
        mm = rx.search(t)
        if mm:
            return s.replace(t, re.sub(r"\$(\d+)", lambda g: mm.group(int(g.group(1))) or "", zh))
    return None


SKIP_KEYS = {"source", "driver", "implementation", "key_template", "alpha_key", "url", "href",
             "link", "file", "path", "key", "id", "value", "default", "pref_key", "family",
             "tab", "type", "kind", "module", "format", "trigger", "regex", "pattern",
             "key_prefix", "prefix", "token", "sha", "hash", "folder", "output_dir"}


def looks_ui_text(s):
    if not s or len(s) < 2 or not re.search(r"[A-Za-z]", s):
        return False
    t = s.strip()
    if re.match(r"^[\w./\\-]+$", t):
        return False
    return True


def collect(node, path, rows):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            collect(v, f"{path}.{k}", rows)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, f"{path}[{i}]", rows)
    elif isinstance(node, str):
        if looks_ui_text(node) and len(node) > 3 and re.search(r"\s|[A-Z]{2}|[…():,.!?]", node):
            rows.append((path, node))


kw = {}
if os.name == "nt":
    kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
proc = subprocess.Popen([PY, "fizgig.py", "--web", "--port", str(PORT)], cwd=BASE,
                        env=dict(os.environ, PYTHONIOENCODING="utf-8"), **kw)
try:
    html = None
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2) as r:
                if r.status == 200:
                    html = r.read().decode("utf-8", "replace")
                    break
        except Exception:
            time.sleep(0.5)
    if html is None:
        raise SystemExit("server 未就绪")
    m = re.search(r'name="fizgig-token"\s+content="([^"]+)"', html)
    token = m.group(1)

    all_rows = []
    for api in APIS:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}{api}",
                                         headers={"X-Fizgig-Token": token})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            before = len(all_rows)
            collect(data, api, all_rows)
            print(f"{api}: +{len(all_rows)-before} strings")
        except Exception as e:
            print(f"{api}: 跳过 ({type(e).__name__})")

    seen = {}
    for path, text in all_rows:
        t = text.strip()
        if t not in seen:
            seen[t] = path
    untranslated = [(t, p) for t, p in seen.items() if apply(t) is None]
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("TOTAL: %d\n" % len(untranslated))
        f.write("=" * 80 + "\n")
        for t, p in untranslated:
            f.write("[%s] %s\n" % (p, t))
    print("unique strings:", len(seen), "| untranslated:", len(untranslated))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
