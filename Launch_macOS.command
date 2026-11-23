#!/bin/zsh
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 shift_corpus_gui.py
else
  echo '未找到 Python 3，请安装 Python 3 后重试。'
  read '?按回车键关闭…'
fi
