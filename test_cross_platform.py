"""Offline cross-platform smoke tests; no GUI display or network required."""
from pathlib import Path
import sys
from shift_corpus_gui import user_output_dir, command_preview, make_command, I18N
from shift_corpus_engine import parse_args, UA as ENGINE_UA
assert 'ShiftCorpus_Output' == user_output_dir().name
assert set(I18N['zh']) == set(I18N['en'])
assert ENGINE_UA == 'ShiftCorpus-Research/1.0 (academic corpus collection)'
assert (Path(__file__).resolve().parent / 'Launch_Windows.bat').is_file()
assert (Path(__file__).resolve().parent / 'Launch_Linux.sh').is_file()
assert (Path(__file__).resolve().parent / 'Launch_macOS.command').is_file()
v = dict(subreddit='politics',after='2022-05-01',before='2026-11-20',period_days='180',sample_per_period='180',seed='1',min_words='5',partial_policy='proportional',only_period='',out=str(user_output_dir()),english=True,exclude_bots=True,exclude_nsfw=True,near_dup=True,with_posts=True)
cmd = make_command(v)
args = parse_args(cmd[3:])
assert args.partial_policy=='proportional' and args.half and args.stratified_sample
assert isinstance(command_preview(cmd), str)
assert 'shift_corpus_engine.py' in command_preview(cmd)
print('Cross-platform offline smoke checks passed')
