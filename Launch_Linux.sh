#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install python3 and python3-tk."
  exit 1
fi
python3 shift_corpus_gui.py
