#!/usr/bin/env bash
# Fizgig 中文界面桥接启动器（Linux）
set -u
cd "$(dirname "$0")" || exit 1
if [ ! -x "../venv/bin/python" ]; then
    echo "Fizgig 的 Python 环境不存在，请先运行 install_fizgig.py。"
    exit 1
fi

# 屏蔽第三方库（如 einops）在 Python 3.13 下的 SyntaxWarning 噪音；用户自定义则保留
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::SyntaxWarning}"

exec "../venv/bin/python" start.py "$@"
