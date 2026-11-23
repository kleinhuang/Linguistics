#!/bin/bash
set -e
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 shift_corpus_gui.py
else
  echo "Python 3 not found. Install Python 3.10+ from python.org."
  read -r -p "Press Enter to close..." _
  exit 1
fi
