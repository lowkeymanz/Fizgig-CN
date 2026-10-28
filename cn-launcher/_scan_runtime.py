# -*- coding: utf-8 -*-
"""运行时抓取 /api/schema，提取后端动态生成的 UI 文本（label/hint/选项等），对照词典输出未翻译项。

来源（设计文档 §2）：表单字段的 label/hint/选项来自 /api/schema，由 families/*.py 动态生成。
静态扫描 .py 会混入 docstring/内部串；运行时抓取的 JSON 就是前端真正渲染的内容，零噪声。

已抓取过则直接读 _schema_dump.json（离线模式），可用 --fetch 强制重新抓取。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

BASE = r"d:/Fizgig-CN"
PY = BASE + r"/venv/Scripts/python.exe"
DICT = BASE + r"/cn-launcher/dict.json"
OUT = BASE + r"/cn-launcher/_untranslated_schema.txt"
DUMP = BASE + r"/cn-launcher/_schema_dump.json"
PORT = 8399

# ---------- 词典加载与匹配（与 translator.js 一致） ----------
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


# ---------- 提取 ----------
UI_KEYS = {"label", "desc", "description", "hint", "help", "title", "tip", "text",
           "caption", "note", "placeholder", "label_done", "info", "message", "warning",
           "download_label", "download_note", "alt_label", "alt_note", "intro",
           "prefs_intro", "prefs_note", "prefs_title", "fetch_note", "block_note",
           "precision_hint", "compile_hint", "edit_note", "sampling_note", "gui_label"}
# 技术字段：值是代码/路径/URL/键名/内部标识，不是 UI
SKIP_KEYS = {"source", "driver", "implementation", "key_template", "alpha_key",
             "url", "href", "link", "file", "path", "key", "id", "value", "default",
             "pref_key", "family", "tab", "type", "kind", "module", "format",
             "trigger", "regex", "pattern", "key_prefix", "prefix"}


def looks_ui_text(s):
    if not s or len(s) < 2:
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    t = s.strip()
    if re.match(r"^[\w./\\-]+$", t):     # key/path/数字样式
        return False
    return True


def run_scan(schema):
    rows = []          # (path, text)

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in SKIP_KEYS:
                    continue
                if isinstance(v, str) and k in UI_KEYS and looks_ui_text(v):
                    rows.append((f"{path}.{k}", v))
                else:
                    walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str) and looks_ui_text(v) and re.search(r"\s", v.strip()):
                    rows.append((f"{path}[{i}]", v))
                else:
                    walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            if looks_ui_text(node) and len(node) > 3 and re.search(r"\s|[A-Z]{2}|[…():,.!?]", node):
                rows.append((path, node))

    walk(schema, "")

    seen = {}
    for path, text in rows:
        t = text.strip()
        if t not in seen:
            seen[t] = path

    untranslated = [(t, p) for t, p in seen.items() if apply(t) is None]
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("TOTAL: %d\n" % len(untranslated))
        f.write("=" * 80 + "\n")
        for t, p in untranslated:
            f.write("[%s] %s\n" % (p, t))
    print("schema strings:", len(seen), "| untranslated:", len(untranslated))


def fetch_schema():
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
            raise SystemExit("server 未在 180 秒内就绪")
        m = re.search(r'name="fizgig-token"\s+content="([^"]+)"', html)
        if not m:
            raise SystemExit("页面中未找到 token")
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/schema",
                                     headers={"X-Fizgig-Token": m.group(1)})
        with urllib.request.urlopen(req, timeout=60) as r:
            schema = json.loads(r.read().decode("utf-8"))
        with io.open(DUMP, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=1)
        print("schema fetched, top-level keys:", list(schema.keys()))
        return schema
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    if os.path.exists(DUMP) and "--fetch" not in sys.argv:
        with io.open(DUMP, encoding="utf-8") as f:
            schema = json.load(f)
    else:
        schema = fetch_schema()
    run_scan(schema)
