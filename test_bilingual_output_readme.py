"""Regression test for English-first bilingual output README."""
import tempfile
from pathlib import Path
from shift_corpus_engine import readme

example = {
    'retrievedAt': '2026-11-22T19:00:00Z',
    'filters': {'subreddits':['politics'],'after':'2022-05-01','before':'2022-10-27',
                'stratifiedSample':True,'samplePerPeriod':180,'seed':1,
                'halfFetch':True, 'includePostsInCorpus':False},
    'result': {'comments':180,'posts':180,'words':6814,'sampleTarget':180,
               'sampleKept':180,'files':[{'name':'pilot.txt','docs':180,'words':6814}],
               'warning':'Archive incomplete'}
}
content = readme(example)
assert content.index('1. About this collection') < content.index('1. 本次采集信息')
assert content.index('Warning: Archive incomplete') < content.index('警告：Archive incomplete')
for phrase in ['Arctic Shift', 'pilot.txt: 180 documents, 6814 words', 'pilot.txt：180 条文本，6814 词',
               'shift_corpus_engine.py --from-json query.json', 'CSV and JSONL', 'CSV 和 JSONL']:
    assert phrase in content, phrase
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'README.txt'
    p.write_text(content, encoding='utf-8-sig')
    assert p.read_text(encoding='utf-8-sig') == content
print('Bilingual output README test passed')
