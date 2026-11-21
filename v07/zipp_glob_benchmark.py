"""Reproduce zipp #106 / PR #113 and the later directory-correctness revert #122.

The performance variant is the exact relevant PR #113 strategy: iterate
ZipFile.filelist rather than calling CompleteDirs.namelist(). The baseline is
the currently installed zipp.Path.glob implementation, which uses namelist().
"""
from __future__ import annotations
import argparse
import csv
import importlib.metadata
import inspect
import io
import json
import math
import os
import random
import re
import statistics as st
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import zipp

DEPTHS = (16, 32, 64, 128, 256, 512, 1024)
SEEDS = (701, 702, 703)
PAIRS = 7
TARGET_NS = 2_000_000
MAX_LOOPS = 24
PATTERN = '*.txt'


def glob_filelist(path: zipp.Path, pattern: str):
    """PR #113's filelist-based glob core, using the installed Translator."""
    if not pattern:
        raise ValueError(f'Unacceptable pattern: {pattern!r}')
    prefix = re.escape(path.at)
    tr = zipp.Translator(seps='/')
    matches = re.compile(prefix + tr.translate(pattern)).fullmatch
    names = (data.filename for data in path.root.filelist)
    return map(path._next, filter(matches, names))


def build_archive(depth: int) -> bytes:
    """Match the upstream complexity fixture: one file at every directory depth."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_STORED) as zf:
        for i in range(depth):
            path = 'd/' * i
            zf.writestr(f'{path}a.txt', b'x')
    return buf.getvalue()


def run_glob(blob: bytes, variant: str, pattern: str = PATTERN):
    with zipfile.ZipFile(io.BytesIO(blob), 'r') as zf:
        root = zipp.Path(zf)
        if variant == 'namelist':
            return tuple(p.at for p in root.glob(pattern))
        if variant == 'filelist':
            return tuple(p.at for p in glob_filelist(root, pattern))
        raise ValueError(variant)


def batch(fn, loops: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(loops):
        fn()
    return time.perf_counter_ns() - start


def measure(blob: bytes, rng: random.Random):
    baseline = lambda: run_glob(blob, 'namelist')
    optimized = lambda: run_glob(blob, 'filelist')
    assert baseline() == optimized()
    # Calibrate a shared loop count so each timed side is roughly a few ms.
    probe = max(1, batch(baseline, 1), batch(optimized, 1))
    loops = max(1, min(MAX_LOOPS, TARGET_NS // probe))
    rows = []
    for block in range(PAIRS):
        reverse = rng.randrange(2)
        if reverse:
            fast_ns = batch(optimized, loops)
            base_ns = batch(baseline, loops)
        else:
            base_ns = batch(baseline, loops)
            fast_ns = batch(optimized, loops)
        base_ns /= loops
        fast_ns /= loops
        rows.append(dict(block=block, reverse=reverse, loops=loops,
                         namelist_ns=base_ns, filelist_ns=fast_ns,
                         speedup=base_ns / fast_ns))
    return rows


def structural_work(depth: int):
    # CompleteDirs._implied_dirs walks every ancestor of every explicit filename.
    # With names d^i/a.txt for i=0..depth-1, the parent visits are sum(i).
    return dict(depth=depth, explicit_file_entries=depth,
                implied_parent_visits=depth * (depth - 1) // 2)


def worker(seed: int):
    rng = random.Random(seed)
    results = []
    for depth in DEPTHS:
        blob = build_archive(depth)
        blocks = measure(blob, rng)
        results.append(dict(seed=seed, depth=depth, archive_bytes=len(blob),
                            structural_work=structural_work(depth), blocks=blocks,
                            median_speedup=st.median(x['speedup'] for x in blocks),
                            median_namelist_ns=st.median(x['namelist_ns'] for x in blocks),
                            median_filelist_ns=st.median(x['filelist_ns'] for x in blocks)))
    # The PR #113 optimization must retain file matches but omits implied directories.
    blob = build_archive(4)
    file_base = run_glob(blob, 'namelist', '*.txt')
    file_fast = run_glob(blob, 'filelist', '*.txt')
    dir_base = run_glob(blob, 'namelist', 'd')
    dir_fast = run_glob(blob, 'filelist', 'd')
    return dict(seed=seed, zipp_version=importlib.metadata.version('zipp'),
                glob_source_sha=source_sha(inspect.getsource(zipp.Path.glob)),
                results=results, semantic_probe=dict(file_pattern_baseline=file_base,
                    file_pattern_filelist=file_fast, directory_pattern_namelist=dir_base,
                    directory_pattern_filelist=dir_fast))


def source_sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def log_slope(xs, ys):
    lx=[math.log(x) for x in xs]; ly=[math.log(y) for y in ys]
    mx=st.mean(lx); my=st.mean(ly)
    return sum((x-mx)*(y-my) for x,y in zip(lx,ly))/sum((x-mx)**2 for x in lx)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--seed', type=int, default=SEEDS[0])
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent/'results')
    args=parser.parse_args()
    if args.worker:
        source=inspect.getsource(zipp.Path.glob)
        if 'self.root.namelist()' not in source:
            raise RuntimeError('Installed zipp.Path.glob is not the expected namelist baseline')
        print(json.dumps(worker(args.seed)))
        return
    args.output.mkdir(parents=True,exist_ok=True)
    workers=[]
    for seed in SEEDS:
        raw=subprocess.check_output([sys.executable,str(Path(__file__).resolve()),'--worker','--seed',str(seed)],
                                    text=True,env={**os.environ,'PYTHONHASHSEED':str(seed)})
        workers.append(json.loads(raw))
    rows=[]
    for depth in DEPTHS:
        group=[next(r for r in w['results'] if r['depth']==depth) for w in workers]
        base=st.median(x['median_namelist_ns'] for x in group)
        fast=st.median(x['median_filelist_ns'] for x in group)
        rows.append(dict(depth=depth,median_namelist_ns=base,median_filelist_ns=fast,
                         speedup=base/fast,explicit_file_entries=depth,
                         implied_parent_visits=depth*(depth-1)//2,
                         namelist_worker_wins=sum(x['median_namelist_ns']>x['median_filelist_ns'] for x in group)))
    slopes=dict(namelist=log_slope(DEPTHS,[r['median_namelist_ns'] for r in rows]),
                filelist=log_slope(DEPTHS,[r['median_filelist_ns'] for r in rows]))
    semantic=workers[0]['semantic_probe']
    assert semantic['file_pattern_baseline']==semantic['file_pattern_filelist']
    assert semantic['directory_pattern_namelist']==['d/']
    assert semantic['directory_pattern_filelist']==[]
    summary=dict(zipp_version=workers[0]['zipp_version'],seeds=list(SEEDS),depths=list(DEPTHS),
                 paired_blocks_per_worker=PAIRS,workers=len(SEEDS),
                 total_paired_blocks=len(SEEDS)*len(DEPTHS)*PAIRS,
                 rows=rows,log_log_slopes=slopes,semantic_probe=semantic,
                 upstream=dict(issue='jaraco/zipp#106',performance_pr='jaraco/zipp#113',
                    performance_merge='48b72b8db6ae5f7712323aca6b340744db15f576',
                    directory_correctness_pr='jaraco/zipp#122',
                    directory_correctness_merge='579be51bb31881a8e04040ff7a7c134053540326'))
    (args.output/'workers.json').write_text(json.dumps(workers,separators=(',',':')))
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    with (args.output/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
