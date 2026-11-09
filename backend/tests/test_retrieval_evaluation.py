import json
from pathlib import Path


def test_synthetic_evaluation_split_and_references_are_consistent():
    root = Path(__file__).resolve().parents[2]
    dataset = json.loads((root / 'evals' / 'retrieval-cases-v1.json').read_text(encoding='utf-8'))
    sources = json.loads((root / 'data' / 'knowledge' / 'synthetic-v1.json').read_text(encoding='utf-8'))
    keys = {source['key'] for source in sources}
    cases = dataset['cases']
    assert len(cases) == 30 and len({case['id'] for case in cases}) == 30
    assert len({case['query'] for case in cases}) == 30
    assert all(case['key'] in keys and case['query'].strip() for case in cases)
    dev = [case for case in cases if case['split'] == 'dev']
    holdout = [case for case in cases if case['split'] == 'holdout']
    assert len(dev) == 20 and len(holdout) == 10
    assert {case['key'] for case in dev}.isdisjoint({case['key'] for case in holdout})
