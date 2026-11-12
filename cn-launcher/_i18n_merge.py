# -*- coding: utf-8 -*-
"""把批次词典文件合并进 dict.json（保持原格式：每条一行、LF、UTF-8）。

用法: python _i18n_merge.py <batch.json> [batch2.json ...]
批次文件为 JSON 数组，元素形如 {"en": ..., "zh": ...} 或 {"re": ..., "zh": ...}。
按 (en|re, zh) 去重；重复运行安全。
"""
import io
import json
import sys
from pathlib import Path

DICT = Path(__file__).resolve().parent / "dict.json"


def key(p):
    return ("re:" + p["re"]) if "re" in p else ("en:" + p["en"])


def main(paths):
    with io.open(DICT, encoding="utf-8") as f:
        phrases = json.load(f)["phrases"]
    have = {key(p) for p in phrases}
    added, dup = 0, 0
    for path in paths:
        with io.open(path, encoding="utf-8") as f:
            batch = json.load(f)
        for p in batch:
            k = key(p)
            if k in have:
                dup += 1
                continue
            have.add(k)
            phrases.append(p)
            added += 1
    # 与 dict.json 既有格式保持一致：indent=2 的美观排版，每个词条独立多行
    with io.open(DICT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"phrases": phrases}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("added:", added, "| skipped dup:", dup, "| total:", len(phrases))


if __name__ == "__main__":
    main(sys.argv[1:])
