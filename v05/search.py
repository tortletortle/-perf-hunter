"""Runtime-guided search against issue-inspired V0.4 adapters."""
import argparse, csv, gc, io, json, math, os, random, statistics as st, subprocess, sys, zipfile
from pathlib import Path

CASES = ('deepcopy', 'zip', 'aa')
METHODS = ('random', 'mutate')
SEEDS = (501, 502, 503, 504)
BUDGET = 16
WORKERS = 10
N = 256
THRESHOLD = 1.10


def factory(case, x, old, fast, z):
    if case in ('deepcopy', 'aa'):
        data = [i if i % 100 < x[0] else [i] if x[1] == 1 else [[i]] for i in range(N)]
        a = lambda: old(data)
        b = (lambda: old(data)) if case == 'aa' else (lambda: fast(data))
        assert a() == b() == data
    else:
        prefixes = tuple(f'p{(x[1]+i)%16:02d}/' for i in range(x[0]))
        def a():
            return tuple(sum(n.startswith(p) for n in z.namelist()) for p in prefixes)
        def b():
            names = z.namelist()
            return tuple(sum(n.startswith(p) for n in names) for p in prefixes)
        assert a() == b() == (N//16,)*len(prefixes)
    return a,b


def sample(case, rng):
    return (rng.randint(1,32),rng.randrange(16)) if case == 'zip' else (rng.randrange(101),rng.randint(1,2))


def mutate(case, x, rng):
    if rng.random()<.2: return sample(case,rng)
    if case == 'zip': return (max(1,min(32,x[0]+rng.choice((-8,-2,2,8)))),rng.randrange(16))
    return (max(0,min(100,x[0]+rng.choice((-25,-5,5,25)))),rng.choice((1,2)))


def measure(v4, a, b, rng, blocks):
    a(); b()
    loops=max(1,min(128,200_000//max(1,v4.batch(a,1),v4.batch(b,1))))
    rows=[]; enabled=gc.isenabled(); gc.disable()
    try:
        for _ in range(blocks):
            rev=rng.randrange(2)
            if rev: y=v4.batch(b,loops); x=v4.batch(a,loops)
            else: x=v4.batch(a,loops); y=v4.batch(b,loops)
            rows.append(dict(a_ns=x/loops,b_ns=y/loops,ratio=x/y,loops=loops,reverse=rev))
    finally:
        if enabled: gc.enable()
    return rows


def worker(v4, mode, seed, finalists=None):
    old,fast,source_sha=v4.clone_copy()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for i in range(N): z.writestr(f'p{i%16:02d}/f{i:05d}',b'')
    result=[]
    with zipfile.ZipFile(buf) as z:
        if mode=='search':
            order=[(c,m) for c in CASES for m in METHODS]; random.Random(seed).shuffle(order)
            for case,method in order:
                rng=random.Random(seed); noise=random.Random(seed+10000); best=None; score=-1
                for step in range(BUDGET):
                    x=sample(case,rng) if best is None or method=='random' else mutate(case,best,rng)
                    rows=measure(v4,*factory(case,x,old,fast,z),noise,3)
                    v=st.median(r['ratio'] for r in rows)
                    result.append(dict(case=case,method=method,seed=seed,step=step,x=x,ratio=v,blocks=rows))
                    if v>score: score=v; best=x
        else:
            rng=random.Random(seed); order=list(finalists); rng.shuffle(order)
            for f in order:
                rows=measure(v4,*factory(f['case'],f['x'],old,fast,z),rng,5)
                result.append(dict(id=f['id'],worker=seed,ratio=st.median(r['ratio'] for r in rows),blocks=rows))
    return dict(source_sha=source_sha,rows=result)


def verdict(values, family):
    n=len(values); k=sum(v>THRESHOLD for v in values)
    p=sum(math.comb(n,j) for j in range(k,n+1))/2**n
    return dict(validation_median=st.median(values),min_worker=min(values),above_threshold=k,p=p,adjusted_p=min(1,p*family),confirmed=p*family<=.05)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--baseline',type=Path,default=Path(__file__).parent.parent/'perf_hunter_v04'); p.add_argument('--output',type=Path,default=Path(__file__).parent); p.add_argument('--worker',choices=('search','validate')); p.add_argument('--seed',type=int); p.add_argument('--finalists',type=Path); a=p.parse_args()
    sys.path.insert(0,str(a.baseline.resolve())); import benchmark as v4
    if a.worker:
        print(json.dumps(worker(v4,a.worker,a.seed,json.loads(a.finalists.read_text()) if a.finalists else None))); return
    a.output.mkdir(parents=True,exist_ok=True)
    def spawn(mode,seed,extra=()):
        cmd=[sys.executable,__file__,'--baseline',str(a.baseline.resolve()),'--worker',mode,'--seed',str(seed),*extra]
        return json.loads(subprocess.check_output(cmd,text=True,env={**os.environ,'PYTHONHASHSEED':str(seed)}))
    search=[spawn('search',s) for s in SEEDS]; rows=[r for w in search for r in w['rows']]
    finalists=[]
    for c in CASES:
        for m in METHODS:
            for s in SEEDS:
                r=max((r for r in rows if (r['case'],r['method'],r['seed'])==(c,m,s)),key=lambda r:r['ratio'])
                finalists.append(dict(id=f'{c}:{m}:{s}',case=c,method=m,seed=s,x=r['x'],search_ratio=r['ratio']))
    fp=a.output/'finalists.json'; fp.write_text(json.dumps(finalists,indent=2))
    validated=[spawn('validate',900+i,('--finalists',str(fp.resolve()))) for i in range(WORKERS)]
    checks=[r for w in validated for r in w['rows']]; summary=[]
    for f in finalists:
        vals=[r['ratio'] for r in checks if r['id']==f['id']]
        assert len(vals)==WORKERS
        summary.append(dict(**f,**verdict(vals,len(finalists))))
    for name,data in [('search.json',search),('validation.json',validated),('summary.json',summary)]: (a.output/name).write_text(json.dumps(data))
    with (a.output/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    for c in CASES:
        for m in METHODS:
            g=[r for r in summary if (r['case'],r['method'])==(c,m)]
            print(c,m,'search',round(st.median(r['search_ratio'] for r in g),3),'validation',round(st.median(r['validation_median'] for r in g),3),'confirmed',sum(r['confirmed'] for r in g),'/',len(g))
    print('evaluations',len(rows),'validation blocks',sum(len(r['blocks']) for r in checks))

if __name__=='__main__': main()
