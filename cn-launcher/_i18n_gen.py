# -*- coding: utf-8 -*-
"""从批次"find/zh"文件生成标准词典条目：按前缀在扫描结果中提取完整原文作 en 键，
保证与页面渲染文本逐字节一致（空白折叠后）。

用法: python _i18n_gen.py <find_batch.json> <out_batch.json>
find_batch 元素:
  {"find": "原文前缀(折叠空白后, >=15字)", "zh": "译文"}            -> {"en": 完整原文, "zh": ...}
  {"find": "模板骨架前缀", "re": "^...$", "zh": "...$1..."}        -> 正则条目（find 仅校验存在）
  {"raw_en": "完整原文", "zh": ...}                               -> 直接透传（用于拼接句等非扫描行文本）
未命中或多义的 find 会报错并跳过。
"""
import io
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent                # <repo>/cn-launcher
SCAN_FILES = ["_untranslated_all.txt", "_untranslated_schema.txt", "_untranslated_apis.txt"]

RE_ALL = re.compile(r"^\[[a-z.]+:\d+\] \[(?:text|title|placeholder|js|tpl)\] (.*)$")
RE_PATH = re.compile(r"^\[((?:[^\[\]]|\[[0-9]+\])+)\] (.*)$")


def collapse(s):
    return re.sub(r"\s+", " ", s).strip()


def load_entries():
    texts = []
    for name in SCAN_FILES:
        with io.open(BASE / name, encoding="utf-8") as f:
            cur = None
            for line in f:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("TOTAL") or line.startswith("=="):
                    continue
                m = RE_ALL.match(line) or RE_PATH.match(line)
                if m:
                    tail = m.group(m.lastindex)
                    cur = [tail.strip()]
                    texts.append(cur)
                elif cur is not None:
                    cur.append(line.strip())
    return [" ".join(" ".join(t).split()) for t in texts]


def main(batch_path, out_path):
    texts = load_entries()
    with io.open(batch_path, encoding="utf-8") as f:
        items = json.load(f)
    out, problems = [], []
    for it in items:
        if "raw_en" in it:
            out.append({"en": it["raw_en"], "zh": it["zh"]})
            continue
        if "re" in it and not it.get("find"):
            out.append({"re": it["re"], "zh": it["zh"]})
            continue
        find = collapse(it["find"])
        hits = [t for t in texts if t.startswith(find)]
        if not hits:
            problems.append("未命中: %s" % find[:60])
            continue
        if len(set(hits)) > 1 and "re" not in it:
            problems.append("多义(%d种): %s -> %s" % (
                len(set(hits)), find[:40], " | ".join(sorted({h[:60] for h in hits}))))
            continue
        if "re" in it:
            if not hits:
                problems.append("正则无目标: %s" % find[:60])
                continue
            out.append({"re": it["re"], "zh": it["zh"]})
        else:
            out.append({"en": hits[0], "zh": it["zh"]})
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("generated:", len(out), "| problems:", len(problems))
    for p in problems:
        print("  " + p)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
