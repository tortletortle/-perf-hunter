"""Paired cost-feedback archive ablation, using V0.2 benchmark adapters."""
import argparse,csv,json,math,random,statistics as st,sys,time
from pathlib import Path
METHODS=('uniform','generic','counter','counter_stall')
SEEDS=range(200,224)
BUDGET=320
MARKS=(80,160,320)
def run(e,t,m,seed,budget=BUDGET):
    r=random.Random(seed); best=e.initial(t,r); score,c,d=e.evaluate(t,best)
    def key(x,n,k):
        return e.descriptor(t,x) if m=='generic' else tuple(int(4*math.log2(max(v,1))) for v in (n,k))
    archive={key(best,c,d):(best,score)}; hist=[score]; stale=0; explores=0
    start=time.perf_counter()
    for _ in range(1,budget):
        p=0. if m=='uniform' else (.15 if stale<12 else .65) if m=='counter_stall' else .45
        parent=best
        if p and r.random()<p:
            parent,_=r.choice(tuple(archive.values())); explores+=1
        x=e.mutate(t,parent,r.choice(e.OPS),r); v,n,k=e.evaluate(t,x); b=key(x,n,k)
        if b not in archive or v>archive[b][1]: archive[b]=(x,v)
        if v>score: best,score,c,d=x,v,n,k; stale=0
        else: stale+=1
        hist.append(score)
    return dict(task=t,method=m,seed=seed,history=hist,best_input=list(best),best_ratio=score,tested_ops=c,reference_ops=d,bins=len(archive),explores=explores,seconds=time.perf_counter()-start)
def summarize(rows):
    summary=[]
    for t in sorted({r['task'] for r in rows}):
        for b in MARKS:
            base={r['seed']:r['history'][b-1] for r in rows if r['task']==t and r['method']=='uniform'}
            for m in METHODS:
                g=[r for r in rows if r['task']==t and r['method']==m]; vals=[r['history'][b-1] for r in g]; diff=[v-base[r['seed']] for v,r in zip(vals,g)]
                summary.append(dict(task=t,budget=b,method=m,median=st.median(vals),trajectory=st.median(st.mean(r['history'][:b]) for r in g),wins=sum(x>1e-12 for x in diff),ties=sum(abs(x)<=1e-12 for x in diff),losses=sum(x< -1e-12 for x in diff),seconds=st.median(r['seconds'] for r in g)))
    return summary
def timed(e,t,x):
    v=e.v1
    if t=='sort': a,b=lambda:v.quick(x),lambda:v.merge(x)
    else: a,b=lambda:v.naive(x[:64],x[64:]),lambda:v.kmp(x[:64],x[64:])
    assert a()[0]==b()[0]
    for _ in range(10): a(); b()
    def batch(f):
        start=time.perf_counter_ns()
        for _ in range(100): f()
        return (time.perf_counter_ns()-start)/100
    samples=[]
    for i in range(9):
        if i%2: y=batch(b); z=batch(a)
        else: z=batch(a); y=batch(b)
        samples.append(z/y)
    return dict(runtime_ratio=st.median(samples),min_ratio=min(samples),max_ratio=max(samples))
def main():
    p=argparse.ArgumentParser(); p.add_argument('--baseline',type=Path,default=Path(__file__).resolve().parent.parent/'v02'); p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent); args=p.parse_args()
    sys.path.insert(0,str(args.baseline.resolve())); import experiment as e
    args.output.mkdir(parents=True,exist_ok=True); rows=[]
    for t in e.TASKS:
        for seed in SEEDS:
            order=list(METHODS); random.Random(seed).shuffle(order)
            for m in order: rows.append(run(e,t,m,seed))
        print(t,'complete',flush=True)
    summary=summarize(rows)
    (args.output/'results.json').write_text(json.dumps(rows,separators=(',',':')))
    with (args.output/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    timings=[]
    for t in ('sort','substring'):
        g=[r for r in rows if r['task']==t and r['method']=='uniform']; target=st.median(r['best_ratio'] for r in g); r=min(g,key=lambda z:abs(z['best_ratio']-target)); seed=r['seed']
        for label,x in [('initial',e.initial(t,random.Random(seed))),('searched',tuple(r['best_input']))]:
            timings.append(dict(task=t,seed=seed,case=label,operation_ratio=e.evaluate(t,x)[0],**timed(e,t,x)))
    (args.output/'timings.json').write_text(json.dumps(timings,indent=2)); print('timings',timings,flush=True)
if __name__=='__main__': main()
