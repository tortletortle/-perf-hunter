"""Issue-inspired benchmarks, standard library only; not exact upstream revisions."""
import argparse, copy, csv, gc, hashlib, inspect, io, json, os, platform
import random, statistics as st, subprocess, sys, time, zipfile
from pathlib import Path

SIZES = (128, 512, 2048)
SEEDS = (410, 411, 412)
BLOCKS = 9
TARGET_NS = 1_000_000


def clone_copy():
    source = inspect.getsource(copy)
    needle = '    d = id(x)\n'
    # Fail closed if the historical layout is not present (e.g. newer CPython).
    start = source.index('def deepcopy(')
    stop = source.index('\n_deepcopy_dispatch', start)
    if source[start:stop].count(needle) != 1:
        raise RuntimeError('Unsupported copy.deepcopy layout')
    a, b = {}, {}
    exec(compile(source, '<baseline copy>', 'exec'), a)
    if '_atomic_types' in a:
        raise RuntimeError('Expected pre-fast-path copy module')
    atomic = {t for t, f in a['_deepcopy_dispatch'].items() if f is a['_deepcopy_atomic']}
    modified = source[:start] + source[start:stop].replace(
        needle, '    if type(x) in _ph_atomic:\n        return x\n' + needle, 1) + source[stop:]
    exec(compile(modified, '<adapted copy>', 'exec'), b)
    b['_ph_atomic'] = frozenset(atomic)
    return a['deepcopy'], b['deepcopy'], hashlib.sha256(source.encode()).hexdigest()


def batch(fn, loops):
    start = time.perf_counter_ns()
    for _ in range(loops):
        fn()
    return time.perf_counter_ns() - start


def measure(a, b, rng):
    assert a() == b()
    a(); b()
    loops = max(1, min(4096, TARGET_NS // max(1, batch(a, 1), batch(b, 1))))
    rows = []
    enabled = gc.isenabled()
    gc.disable()
    try:
        for block in range(BLOCKS):
            reverse = rng.randrange(2)
            if reverse:
                y = batch(b, loops); x = batch(a, loops)
            else:
                x = batch(a, loops); y = batch(b, loops)
            rows.append(dict(block=block, reverse=reverse, loops=loops,
                             a_ns=x/loops, b_ns=y/loops, ratio=x/y))
    finally:
        if enabled: gc.enable()
    return rows


def worker(seed):
    rng = random.Random(seed)
    old, fast, source_sha = clone_copy()
    rows = []
    def add(case, size, workload, a, b):
        for r in measure(a, b, rng):
            rows.append(dict(seed=seed, case=case, size=size, workload=workload, **r))
    for n in SIZES:
        for mode in ('atomic', 'mixed', 'nested'):
            data = [rng.randrange(100000) for _ in range(n)]
            data = [v if mode == 'atomic' or (mode == 'mixed' and i % 2 == 0)
                    else [v] for i, v in enumerate(data)]
            original = copy.deepcopy(data)
            for fn in (old, fast):
                result = fn(data)
                assert result == original and result is not data
                assert all(not isinstance(x,list) or x is not y for x,y in zip(data,result))
            add('deepcopy', n, mode, lambda: old(data), lambda: fast(data))
        shared = [1]; cycle = [shared, shared]; cycle.append(cycle)
        for fn in (old, fast):
            out = fn(cycle)
            assert out is out[2] and out[0] is out[1] and out[0] is not shared
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for i in range(n): z.writestr(f'p{i % 16:02d}/f{i:05d}', b'')
        with zipfile.ZipFile(buf) as z:
            for q in (1,16,64):
                prefixes = tuple(f'p{rng.randrange(16):02d}/' for _ in range(q))
                # Each timed call includes all list constructions, including cache setup.
                def repeated():
                    return tuple(sum(name.startswith(p) for name in z.namelist()) for p in prefixes)
                def cached():
                    names = z.namelist()
                    return tuple(sum(name.startswith(p) for name in names) for p in prefixes)
                assert repeated() == cached() == (n//16,)*q
                add('zip_names', n, f'q{q}', repeated, cached)
        if n == 512:
            data = list(range(n))
            add('aa_control', n, 'identical', lambda: old(data), lambda: old(data))
    return dict(seed=seed, python=sys.version, platform=platform.platform(), source_sha=source_sha, rows=rows)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--worker',type=int); p.add_argument('--output',type=Path,default=Path(__file__).parent); a=p.parse_args()
    if a.worker is not None:
        print(json.dumps(worker(a.worker))); return
    a.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for seed in SEEDS:
        raw=subprocess.check_output([sys.executable,__file__,'--worker',str(seed)],text=True,env={**os.environ,'PYTHONHASHSEED':str(seed)})
        results.append(json.loads(raw)); print('worker',seed,'complete',flush=True)
    rows=[r for result in results for r in result['rows']]
    summary=[]
    for case,size,workload in sorted({(r['case'],r['size'],r['workload']) for r in rows}):
        vals=[st.median(r['ratio'] for r in rows if (r['case'],r['size'],r['workload'],r['seed'])==(case,size,workload,s)) for s in SEEDS]
        summary.append(dict(case=case,size=size,workload=workload,median_ratio=st.median(vals),min_worker=min(vals),max_worker=max(vals),workers_above_1=sum(v>1 for v in vals)))
    for name,data in [('raw.csv',rows),('summary.csv',summary)]:
        with (a.output/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    (a.output/'environment.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='rows'} for r in results],indent=2))
    print('paired blocks',len(rows),'conditions',len(summary))

if __name__=='__main__': main()
