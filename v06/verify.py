"""Structural and statistical-protocol checks for saved V0.6 output."""
import json
import math
import statistics as st
from pathlib import Path
import adaptive as a


def main():
    root = Path(__file__).resolve().parent
    out = root / 'results'
    detailed = (out / 'rounds.json').exists()
    rounds = json.loads((out / ('rounds.json' if detailed else 'worker_outcomes.json')).read_text())
    summary = json.loads((out / 'summary.json').read_text())
    stats = json.loads((out / 'protocol_stats.json').read_text())
    finalists = json.loads((root / 'reference' / 'finalists.json').read_text())
    assert len(finalists) == len(summary) == 24
    assert len({x['id'] for x in finalists}) == 24
    states = {x['id']: [] for x in finalists}
    stopped = set()
    all_seeds = []
    for round_no, batch in enumerate(rounds, 1):
        expected_active = {fid for fid, observations in states.items()
                           if not observations or a.classify(observations, 24)['status'] == 'continue_sampling'}
        rows = batch['rows']
        if rows and isinstance(rows[0], list):
            rows = [dict(id=r[0], ratio=r[1], success=bool(r[2])) for r in rows]
        assert {r['id'] for r in rows} == expected_active
        assert batch['seed'] not in all_seeds
        all_seeds.append(batch['seed'])
        assert len({r['id'] for r in rows}) == len(rows)
        assert batch['source_sha']
        for row in rows:
            assert row['id'] in states and row['id'] not in stopped
            assert row['success'] == (row['ratio'] > a.THRESHOLD)
            if detailed:
                assert len(row['blocks']) == a.BLOCKS_PER_WORKER
                ratios = [b['ratio'] for b in row['blocks']]
                assert math.isclose(row['ratio'], st.median(ratios), rel_tol=1e-12)
                for b in row['blocks']:
                    assert math.isclose(b['a_ns'] / b['b_ns'], b['ratio'], rel_tol=1e-12)
            states[row['id']].append(row['ratio'])
        # A finalist that met a stopping boundary in this round must never appear again.
        for fid, observations in states.items():
            if observations and a.classify(observations, 24)['status'] != 'continue_sampling':
                stopped.add(fid)
    assert len(all_seeds) == len(rounds) == 18
    assert not any(a.classify(obs, 24)['status'] == 'continue_sampling' for obs in states.values())
    assert len({x['source_sha'] for x in rounds}) == 1
    for item in summary:
        obs = states[item['id']]
        v = a.classify(obs, 24)
        assert item['workers_used'] == len(obs)
        assert item['paired_blocks'] == len(obs) * a.BLOCKS_PER_WORKER
        for key, value in v.items():
            assert item[key] == value, (item['id'], key, item[key], value)
        assert len(obs) <= a.MAX_WORKERS
    positive = [x for x in summary if x['case'] != 'aa']
    negative = [x for x in summary if x['case'] == 'aa']
    assert len(positive) == 16 and len(negative) == 8
    assert all(x['status'] == 'confirmed_median_ratio_above_threshold' for x in positive)
    assert all(x['status'] == 'futility_evidence_below_90pct_reproducibility' for x in negative)
    _, alpha = a.thresholds(24)
    assert stats['adaptive_worker_samples'] == sum(len(x) for x in states.values()) == 245
    assert stats['adaptive_paired_blocks'] == sum(x['paired_blocks'] for x in summary) == 735
    assert stats['fixed_v05_paired_blocks'] == 24 * 10 * 5 == 1200
    assert math.isclose(stats['paired_block_reduction'], 0.3875, abs_tol=1e-12)
    assert stats['confirm_null_crossing_probability'] <= alpha
    assert stats['futility_null_crossing_probability'] <= alpha
    assert a.exact_crossing_probability(.5, 'confirm', 24) == stats['confirm_null_crossing_probability']
    assert a.exact_crossing_probability(.9, 'futility', 24) == stats['futility_null_crossing_probability']
    print('PASS: 24 finalists, adaptive stopping chronology, 245 process samples, 735 paired blocks' + (' (full block records)' if detailed else ' (compact worker outcomes)'))
    print('PASS: 16 positive controls confirmed; 8 A/A controls stopped for futility')
    print('PASS: finite-horizon null crossing bounds are below per-claim alpha')

if __name__ == '__main__':
    main()
