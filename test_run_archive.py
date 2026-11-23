"""Offline tests for v1.1.0 per-run archival output."""
import sys
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shift_corpus_gui import run_folder_name, create_run_directory

CONFIG = {'subreddit':'politics','after':'2022-05-01','before':'2026-11-20','only_period':''}
NOW = datetime(2026,11,22,19,30,0)
assert run_folder_name(CONFIG,NOW)=='politics_20220501-20261120_all_20261122-193000'
assert run_folder_name({**CONFIG,'only_period':'2022-05-01_2022-10-27'},NOW)=='politics_20220501-20221027_single_20261122-193000'
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    first=create_run_directory(root, CONFIG, NOW)
    (first/'data.txt').write_text('preserve')
    second=create_run_directory(root, CONFIG, NOW)
    assert first != second and first.name.endswith('193000') and second.name.endswith('193000_01')
    assert (first/'data.txt').read_text()=='preserve'
    assert second.is_dir()
print('Folder naming, uniqueness, and non-overwrite tests passed')
