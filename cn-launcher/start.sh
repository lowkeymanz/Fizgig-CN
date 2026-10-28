#!/usr/bin/env bash
# Fizgig 中文界面桥接启动器（Linux）
set -u
cd "$(dirname "$0")" || exit 1
if [ ! -x "../venv/bin/python" ]; then
    echo "Fizgig 的 Python 环境不存在，请先运行 install_fizgig.py。"
    exit 1
fi
exec "../venv/bin/python" start.py "$@"
