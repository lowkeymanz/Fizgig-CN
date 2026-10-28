# -*- coding: utf-8 -*-
"""聚焦扫描 Web UI 文本（HTML 文本节点/属性 + app.js 字符串），对照词典输出未翻译项。"""
import io
import json
import re
from html.parser import HTMLParser

DICT = r"d:/Fizgig-CN/cn-launcher/dict.json"
OUT = r"d:/Fizgig-CN/cn-launcher/_untranslated_all.txt"
INDEX_HTML = r"d:/Fizgig-CN/src/fizgig/web/static/index.html"
APP_JS = r"d:/Fizgig-CN/src/fizgig/web/static/app.js"

# ---------- 词典加载与匹配（与 translator.js 保持一致） ----------
with io.open(DICT, encoding="utf-8") as f:
    phrases = json.load(f)["phrases"]

exact = {}
regexes = []
for p in phrases:
    if p.get("re"):
        try:
            partial = not p["re"].startswith("^")
            regexes.append([re.compile(p["re"]), p["zh"], partial])
        except re.error:
            pass
    elif p.get("en"):
        exact[p["en"]] = p["zh"]


def apply(text):
    s = str(text)
    if s in exact:
        return exact[s]
    trimmed = s.strip()
    if not trimmed:
        return None
    if trimmed != s and trimmed in exact:
        return s.replace(trimmed, exact[trimmed])
    t = re.sub(r"\s+", " ", trimmed)
    if t in exact:
        return s.replace(trimmed, exact[t])
    m = re.search(r"[:：]\s*$", t)
    if m:
        nc = t[:m.start()]
        if nc != t and nc in exact:
            return s.replace(trimmed, exact[nc] + t[m.start():])
    for rx, zh, partial in regexes:
        if partial:
            continue
        mm = rx.search(t)
        if mm:
            return s.replace(trimmed, re.sub(r"\$(\d+)", lambda g: mm.group(int(g.group(1))) or "", zh))

    # 片段级替换（未锚定的正则）
    res, hit = s, False
    for rx, zh, partial in regexes:
        if not partial or not rx.search(res):
            continue
        res = rx.sub(lambda m, z=zh: re.sub(r"\$(\d+)", lambda g: m.group(int(g.group(1))) or "", z), res, count=1)
        hit = True
    return res if hit and res != s else None


# HTML 标签名 / 属性 / CSS 值 / JS 事件名等常见的非 UI 词汇
NON_UI_WORDS = {
    "span", "button", "label", "input", "select", "option", "textarea", "div",
    "p", "a", "img", "i", "ul", "li", "nav", "main", "header", "footer",
    "section", "article", "table", "tr", "td", "th", "form", "field", "note",
    "hint", "row", "card", "title", "text", "class", "type", "name", "value",
    "id", "key", "data", "list", "item", "group", "menu", "link", "radio",
    "checkbox", "summary", "details", "toggle", "click", "change", "keydown",
    "input", "output", "submit", "reset", "focus", "blur", "error", "login",
    "retry", "none", "done", "shown", "wide", "check", "choice", "option",
    "smooth", "start", "stop", "open", "close", "save", "load", "send", "get",
    "post", "put", "delete", "fetch", "await", "true", "false", "null",
    "undefined", "strict", "use", "new", "var", "let", "const", "return",
    "if", "else", "for", "while", "function", "async", "of", "in", "to",
}


# JS 代码特征（这些一定不是 UI 文本）
CODE_HINTS = (
    "$(", "${", ".value", ".trim", ".checked", ".split", ".startsWith", ".replace",
    "encodeURIComponent", "getElementById", "querySelector", "replaceChildren",
    "Number(", "String(", ".children", ".length", ".pop(", ".join(", ".push(",
    ".classList", ".style", ".dataset", ".addEventListener", "setAttribute",
)


def looks_ui(s, kind="text"):
    """判断字符串是否可能是面向用户的 UI 文本。"""
    # 含变量的模板骨架：保留"文字类"句子，排除 HTML/代码结构
    if kind == "tpl":
        j = s.replace("\x00", " x ")
        if re.search(r"[<>{}]", j):
            return False
        if re.search(r"\w\s*=\s*[\"']", j) or re.search(r"\b(class|style|href|src|id|data-\w+)\s*:", j):
            return False
        # 函数调用/单位片段（var( x )、rgba( , )、width:%）
        if re.search(r"\b(var|rgba|rgb|url|calc|hsl|https?|api)\b", j, re.I):
            return False
        if re.search(r"\w+\([^)]{0,3}\)", j):
            return False
        alpha_words = [w for w in j.split() if re.search(r"[A-Za-z]{2,}", w)]
        if len(alpha_words) < 2:
            return False
        if not any(len(w.strip(".,:;!?()[]\"'")) >= 4 for w in alpha_words):
            return False
        return True

    if not re.search(r"[A-Za-z]", s):
        return False
    t = s.strip()
    if not t or len(t) < 2:
        return False
    # 纯代码符号 / 路径 / URL
    if re.match(r"^[/#.]", t):
        return False
    if re.match(r"^[\w.-]+://", t):
        return False
    if re.search(r"[{};=<>]", t):
        return False

    # JS 代码片段（模板拼接、方法调用）
    if "$" in t:
        return False
    if any(h in t for h in CODE_HINTS):
        return False
    if re.match(r"^[,)+?=]", t) or re.search(r"[,+(]$", t):
        return False
    # 纯 CSS 值（如 display:none）
    if re.match(r"^[a-z-]+:[a-z-]+$", t):
        return False

    # 单个词：几乎都是标签名 / id / class / 值，直接排除（UI 单词标签已在词典或 HTML 中覆盖）
    if not re.search(r"\s", t):
        if re.search(r"[…›✓→:!?。！？]", t):
            return True
        return False

    # 含空格：过滤 class/id 串（全小写字母数字连字符下划线点）
    words = t.split()
    if all(re.match(r"^[a-z0-9\-_.]+$", w) for w in words):
        return False
    # 全是常见非 UI 词
    if all(w.lower() in NON_UI_WORDS for w in words):
        return False
    # 至少有一个较长的英文单词，或含 UI 标点
    has_long = any(re.match(r"^[A-Za-z]{3,}", w) for w in words)
    has_punct = bool(re.search(r"[…›✓→:!?。！？]", t))
    if not has_long and not has_punct:
        return False
    return True


# ---------- HTML 文本节点 / 属性提取 ----------
SKIP_TAGS = {"script", "style", "noscript", "textarea", "code", "pre", "iframe"}
ATTRS = {"title", "placeholder", "aria-label"}


class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []          # (line, kind, text)
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        for k, v in attrs:
            if k in ATTRS and v and v.strip():
                self.rows.append((self.getpos()[0], k, v.strip()))

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        t = data.strip()
        if t:
            self.rows.append((self.getpos()[0], "text", t))


def collect_html(path):
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
    c = TextCollector()
    c.feed(src)
    return c.rows


# ---------- JS 字符串提取 ----------
JS_RE = re.compile(
    r'"(?P<d>(?:\\.|[^"\\])*)"|'
    r"'(?P<s>(?:\\.|[^'\\])*)'|"
    r'`(?P<t>(?:\\.|[^`\\])*)`'
)


def strip_comments_js(src):
    # 去除块注释与行注释（近似，避免匹配注释里的英文）
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def unescape_js(s):
    return (s.replace("\\n", " ").replace("\\t", " ")
             .replace('\\"', '"').replace("\\'", "'")
             .replace("\\\\", "\\"))


TPL_EXPR_RE = re.compile(r"\$\{[^{}]*\}")
PH = "\x00"          # 模板插值占位符

LIT = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)'
# 相邻字符串字面量的拼接（"a" + "b" + `c${x}`），先合并成完整句子
CONCAT_RE = re.compile(r"(" + LIT + r"(?:\s*\+\s*" + LIT + r")+)")


def _lit_inner(lit):
    inner = lit[1:-1]
    if lit[0] == "`":
        inner = TPL_EXPR_RE.sub(PH, inner)
    return inner


def collect_js(path):
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
    src = strip_comments_js(src)
    rows = []
    spans = []

    # 1) 先合并拼接表达式
    for m in CONCAT_RE.finditer(src):
        text = m.group(1)
        joined = unescape_js("".join(_lit_inner(lm.group(0)) for lm in re.finditer(LIT, text)))
        line = src.count("\n", 0, m.start()) + 1
        rows.append((line, "tpl" if PH in joined else "js", joined))
        spans.append((m.start(1), m.end(1)))

    def inside(pos):
        return any(a <= pos < b for a, b in spans)

    # 2) 再取未并入拼接的单个字面量
    for m in JS_RE.finditer(src):
        if inside(m.start()):
            continue
        raw = m.group("d") or m.group("s") or m.group("t")
        if raw is None:
            continue
        line = src.count("\n", 0, m.start()) + 1
        if m.group("t") is not None:
            skel = TPL_EXPR_RE.sub(PH, raw)
            if PH in skel:
                rows.append((line, "tpl", unescape_js(skel)))
                continue
            if "\n" in raw:
                continue
        rows.append((line, "js", unescape_js(raw)))
    return rows


def main():
    rows = []

    for line, kind, text in collect_html(INDEX_HTML):
        if looks_ui(text, kind) and apply(text) is None:
            rows.append(("index.html", line, kind, text))

    for line, kind, text in collect_js(APP_JS):
        if not looks_ui(text, kind):
            continue
        # 含变量骨架：用占位值探测，才能命中按同一骨架生成的正则
        probe = text.replace("\x00", "s") if kind == "tpl" else text
        if apply(probe) is None:
            rows.append(("app.js", line, kind, text))

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("TOTAL: %d\n" % len(rows))
        f.write("=" * 80 + "\n")
        for path, line, kind, text in rows:
            f.write("[%s:%d] [%s] %s\n" % (path, line, kind, text.replace("\x00", "⟦v⟧")))

    print("done, total =", len(rows))


if __name__ == "__main__":
    main()
