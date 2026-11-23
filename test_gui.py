"""Simple offline smoke checks; does not require a display or internet access."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shift_corpus_gui import make_command, estimate_windows
from shift_corpus_engine import parse_args, period_windows

v=dict(subreddit='politics',after='2022-05-01',before='2026-11-20',period_days='180',sample_per_period='180',seed='1',min_words='5',partial_policy='proportional',only_period='',out='./corpus_output',english=True,exclude_bots=True,exclude_nsfw=True,near_dup=True,with_posts=True)
cmd=make_command(v)
args=parse_args(cmd[3:])
assert args.half and args.stratified_sample and args.with_posts
assert args.partial_policy=='proportional' and args.exclude_nsfw and args.near_dup
assert estimate_windows('2022-05-01','2026-11-20',180,180,'proportional')==(10,1665,1665)
assert len(period_windows('2022-05-01','2026-11-20',180))==10
v['only_period']='2022-05-01_2022-10-27'
assert '--only-period' in make_command(v)
for after,before in [('2026-11-22','2026-01-01'),('bad','2026-10-01')]:
    v.update(after=after,before=before)
    try: make_command(v)
    except ValueError: pass
    else: raise AssertionError('invalid date accepted')
print('All offline smoke checks passed')
