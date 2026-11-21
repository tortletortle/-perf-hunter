"""Anytime-valid adaptive confirmation for PERF HUNTER V0.5 finalists.

Uses process-level Bernoulli outcomes: a fresh worker contributes one success
iff the median of its paired timing blocks exceeds the practical ratio threshold.
The confirmation and futility e-processes are mixture likelihood ratios.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import random
import statistics as st
import subprocess
import sys
import zipfile
import io
import gc
from pathlib import Path

THRESHOLD = 1.10
FUTILITY_TARGET = 0.90
FAMILY_ALPHA = 0.05
MAX_WORKERS = 20
BLOCKS_PER_WORKER = 3


def e_confirm(n: int, k: int) -> float:
    """Mixture e-value: q~Uniform[0.5,1], null Bernoulli p<=0.5."""
    if n < 0 or not 0 <= k <= n:
        raise ValueError((n, k))
    return sum(math.comb(n + 1, j) for j in range(k + 1)) / ((n + 1) * math.comb(n, k))


def e_futility(n: int, k: int, target: float = FUTILITY_TARGET) -> float:
    """Mixture e-value: q~Uniform[0,target], null Bernoulli p>=target."""
    if n < 0 or not 0 <= k <= n or not 0 < target < 1:
        raise ValueError((n, k, target))
    # Integral of the beta-binomial likelihood ratio, evaluated via a binomial tail.
    tail = sum(
        math.comb(n + 1, j) * target**j * (1 - target) ** (n + 1 - j)
        for j in range(k + 1, n + 2)
    )
    beta = 1.0 / ((n + 1) * math.comb(n, k))
    return beta * tail / (target ** (k + 1) * (1 - target) ** (n - k))


def thresholds(finalist_count: int) -> tuple[float, float]:
    # Two claims per finalist (confirmation and futility), Bonferroni family control.
    alpha_each = FAMILY_ALPHA / (2 * finalist_count)
    return 1 / alpha_each, alpha_each


def classify(observations: list[float], finalist_count: int, max_workers: int = MAX_WORKERS):
    n = len(observations)
    k = sum(x > THRESHOLD for x in observations)
    boundary, alpha_each = thresholds(finalist_count)
    ec = e_confirm(n, k) if n else 1.0
    ef = e_futility(n, k) if n else 1.0
    if ec >= boundary:
        status = "confirmed_median_ratio_above_threshold"
    elif ef >= boundary:
        status = "futility_evidence_below_90pct_reproducibility"
    elif n >= max_workers:
        status = "inconclusive_at_worker_cap"
    else:
        status = "continue_sampling"
    return dict(n_workers=n, successes=k, failures=n-k, success_fraction=(k/n if n else None),
                e_confirm=ec, e_futility=ef, e_boundary=boundary, alpha_each=alpha_each,
                status=status)


def factory(v5, case, x, old, fast, z):
    return v5.factory(case, x, old, fast, z)


def worker(v4, v5, seed: int, finalists: list[dict]):
    """One fresh process supplies one independent process-level observation per active finalist."""
    old, fast, source_sha = v4.clone_copy()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for i in range(v5.N):
            zf.writestr(f'p{i % 16:02d}/f{i:05d}', b'')
    rng = random.Random(seed)
    order = list(finalists)
    rng.shuffle(order)
    rows = []
    with zipfile.ZipFile(buf) as zf:
        for f in order:
            a, b = factory(v5, f['case'], f['x'], old, fast, zf)
            blocks = v5.measure(v4, a, b, rng, BLOCKS_PER_WORKER)
            ratios = [r['ratio'] for r in blocks]
            rows.append(dict(id=f['id'], worker_seed=seed, ratio=st.median(ratios),
                             success=st.median(ratios) > THRESHOLD, blocks=blocks))
    return dict(seed=seed, source_sha=source_sha, rows=rows)


def exact_crossing_probability(p: float, which: str, finalist_count: int, max_workers: int = MAX_WORKERS):
    """Exact finite-horizon probability of crossing one e-boundary under Bernoulli(p)."""
    boundary, _ = thresholds(finalist_count)
    states = {0: 1.0}
    crossing = 0.0
    for n in range(1, max_workers + 1):
        nxt = {}
        for k0, mass in states.items():
            for bit, probability in ((0, 1-p), (1, p)):
                k = k0 + bit
                ev = e_confirm(n, k) if which == 'confirm' else e_futility(n, k)
                if ev >= boundary:
                    crossing += mass * probability
                elif n < max_workers:
                    nxt[k] = nxt.get(k, 0.0) + mass * probability
        states = nxt
    return crossing


def run_main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    finalists = json.loads(args.finalists.read_text())
    if len(finalists) != 24:
        raise ValueError(f"Expected 24 V0.5 finalists, got {len(finalists)}")
    ids = [f['id'] for f in finalists]
    if len(set(ids)) != len(ids):
        raise ValueError("Finalist IDs must be unique")
    # Each candidate is evaluated in a fresh process at each round; already stopped candidates are removed.
    states = {f['id']: {'finalist': f, 'observations': [], 'worker_records': [], 'status': 'continue_sampling'} for f in finalists}
    rounds = []
    for round_index in range(1, MAX_WORKERS + 1):
        active = [s['finalist'] for s in states.values() if s['status'] == 'continue_sampling']
        if not active:
            break
        seed = 61000 + round_index
        cmd = [sys.executable, str(Path(__file__).resolve()), '--baseline', str(args.baseline.resolve()),
               '--reference-search', str(args.reference_search.resolve()), '--legacy-dir', str(args.legacy_dir.resolve()), '--worker', '--seed', str(seed),
               '--active-file', str(args.output / f'active_round_{round_index:02d}.json')]
        (args.output / f'active_round_{round_index:02d}.json').write_text(json.dumps(active))
        raw = subprocess.check_output(cmd, text=True, env={**os.environ, 'PYTHONHASHSEED': str(seed)})
        batch = json.loads(raw)
        rounds.append(batch)
        for row in batch['rows']:
            state = states[row['id']]
            state['observations'].append(row['ratio'])
            state['worker_records'].append(row)
            verdict = classify(state['observations'], len(finalists))
            state['status'] = verdict['status']
        counts = {s: sum(v['status'] == s for v in states.values()) for s in sorted({v['status'] for v in states.values()})}
        print(f"round {round_index}: active={len(active)} status={counts}", flush=True)
    summary = []
    for f in finalists:
        state = states[f['id']]
        verdict = classify(state['observations'], len(finalists))
        summary.append(dict(**f, **verdict, workers_used=len(state['observations']), paired_blocks=len(state['observations']) * BLOCKS_PER_WORKER))
    total_blocks = sum(s['paired_blocks'] for s in summary)
    fixed_blocks = len(finalists) * 10 * 5
    stats = dict(finalist_count=len(finalists), max_workers=MAX_WORKERS, blocks_per_worker=BLOCKS_PER_WORKER,
                 adaptive_worker_samples=sum(s['workers_used'] for s in summary), adaptive_paired_blocks=total_blocks,
                 fixed_v05_paired_blocks=fixed_blocks, paired_blocks_saved=fixed_blocks-total_blocks,
                 paired_block_reduction=1-total_blocks/fixed_blocks,
                 confirm_null_crossing_probability=exact_crossing_probability(0.5, 'confirm', len(finalists)),
                 futility_null_crossing_probability=exact_crossing_probability(FUTILITY_TARGET, 'futility', len(finalists)))
    (args.output / 'rounds.json').write_text(json.dumps(rounds))
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    (args.output / 'protocol_stats.json').write_text(json.dumps(stats, indent=2))
    import csv
    with (args.output / 'summary.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    print(json.dumps(stats, indent=2))
    for case in ('deepcopy', 'zip', 'aa'):
        for method in ('random', 'mutate'):
            group = [s for s in summary if s['case'] == case and s['method'] == method]
            print(case, method, 'statuses=', {k: sum(x['status'] == k for x in group) for k in sorted({x['status'] for x in group})},
                  'median_workers=', st.median(x['workers_used'] for x in group))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', type=Path, default=Path(__file__).resolve().parent.parent / 'v04')
    p.add_argument('--reference-search', type=Path, default=Path(__file__).resolve().parent.parent / 'v05' / 'search.py')
    p.add_argument('--finalists', type=Path, default=Path(__file__).resolve().parent / 'reference' / 'finalists.json')
    p.add_argument('--legacy-dir', type=Path, default=Path(__file__).resolve().parent.parent / 'v02')
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'results')
    p.add_argument('--worker', action='store_true')
    p.add_argument('--seed', type=int, default=61001)
    p.add_argument('--active-file', type=Path)
    args = p.parse_args()
    if args.worker:
        sys.path.insert(0, str(args.baseline.resolve()))
        import benchmark as v4
        sys.path.insert(0, str(args.legacy_dir.resolve()))
        sys.path.insert(0, str(args.reference_search.resolve().parent))
        import search as v5
        active = json.loads(args.active_file.read_text())
        print(json.dumps(worker(v4, v5, args.seed, active)))
        return
    run_main(args)

if __name__ == '__main__':
    main()
