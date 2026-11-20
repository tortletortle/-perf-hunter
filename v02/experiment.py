"""Fixed-budget operation-count experiment, Python standard library only."""
import csv,json,math,random,statistics as st,bisect
from collections import deque
from pathlib import Path
import legacy as v1
TASKS=('sort','substring','graph','bounds')
METHODS=('random','uniform','ucb','archive_uniform','window_greedy','window_archive')
BUDGET=160
SEEDS=range(100,124)
OPS=v1.OPS
SPECS={'sort':(64,64),'substring':(76,4),'graph':(80,16),'bounds':(96,64)}
def initial(t,r):
    n,k=SPECS[t]; return tuple(r.randrange(k) for _ in range(n))
def mutate(t,x,op,r):
    if t in ('sort','substring'): return v1.mutate(t,x,op,r)
    if op=='restart': return initial(t,r)
    a=list(x); n,k=SPECS[t]
    if op=='point': a[r.randrange(n)]=r.randrange(k)
    elif op=='swap':
        i,j=r.sample(range(n),2); a[i],a[j]=a[j],a[i]
    else:
        i,j=sorted(r.sample(range(n+1),2)); m=j-i
        if op=='reverse': a[i:j]=reversed(a[i:j])
        elif op=='copy_block':
            p=r.randrange(n-m+1); a[i:j]=a[p:p+m]
        elif op=='fill_block': a[i:j]=[r.randrange(k)]*m
    return tuple(a)
def sort_eval(x):
    a,c=v1.quick(x); b,d=v1.merge(x); assert a==b==sorted(x)
    return c/max(d,1),c,d
def substring_eval(t,p):
    a,c=v1.naive(t,p); b,d=v1.kmp(t,p); assert a==b==bytes(t).find(bytes(p))
    return c/max(d,1),c,d
def graph_eval(x):
    edges=list(zip(x[::2],x[1::2])); seen={0}; q=deque([0]); c=0
    while q:
        u=q.popleft()
        for a,b in edges:
            c+=1
            if a==u and b not in seen: seen.add(b); q.append(b)
    adj=[[] for _ in range(16)]; d=0
    for a,b in edges: adj[a].append(b); d+=1
    seen2={0}; q=deque([0])
    while q:
        for b in adj[q.popleft()]:
            d+=1
            if b not in seen2: seen2.add(b); q.append(b)
    closure={0}
    while True:
        nxt=closure|{b for a,b in edges if a in closure}
        if nxt==closure: break
        closure=nxt
    assert seen==seen2==closure
    return c/max(d,1),c,d
def bounds_eval(x):
    keys=sorted(x[:64]); queries=x[64:]; c=d=0
    for q in queries:
        i=0
        while i<len(keys):
            c+=1
            if keys[i]>=q: break
            i+=1
        lo,hi=0,len(keys)
        while lo<hi:
            mid=(lo+hi)//2; d+=1
            if keys[mid]<q: lo=mid+1
            else: hi=mid
        assert i==lo==bisect.bisect_left(keys,q)
    return c/max(d,1),c,d
def evaluate(t,x):
    if t=='sort': return sort_eval(x)
    if t=='substring': return substring_eval(x[:64],x[64:])
    if t=='graph': return graph_eval(x)
    return bounds_eval(x)
def descriptor(t,x):
    n,k=SPECS[t]
    vals=(sum(a==b for a,b in zip(x,x[1:]))/(n-1),len(set(x))/min(n,k),sum(a<b for a,b in zip(x,x[1:]))/(n-1))
    return tuple(min(3,int(v*4)) for v in vals)
def run(t,m,seed):
    r=random.Random(seed); best=initial(t,r); score,c,d=evaluate(t,best)
    archive={descriptor(t,best):(best,score)}; hist=[score]; unique={best}; counts=dict.fromkeys(OPS,0); sums=dict.fromkeys(OPS,0.); window=deque(maxlen=40)
    for step in range(1,BUDGET):
        parent,ps=best,score
        if m in ('archive_uniform','window_archive') and r.random()<.45: parent,ps=r.choice(tuple(archive.values()))
        if m=='random': child=initial(t,r); op=None
        else:
            if m in ('uniform','archive_uniform'): op=r.choice(OPS)
            else:
                wc,wr,steps=counts,sums,step
                if m.startswith('window'):
                    wc=dict.fromkeys(OPS,0); wr=dict.fromkeys(OPS,0.); steps=len(window)
                    for o,v in window: wc[o]+=1; wr[o]+=v
                unused=[o for o in OPS if not wc[o]]
                op=r.choice(unused) if unused else max(OPS,key=lambda o:wr[o]/wc[o]+.35*math.sqrt(math.log(steps)/wc[o]))
            child=mutate(t,parent,op,r)
        val,cc,dd=evaluate(t,child); unique.add(child); key=descriptor(t,child); novel=key not in archive
        if novel or val>archive[key][1]: archive[key]=(child,val)
        if op is not None:
            gain=min(1.,max(0.,math.log(max(val,1e-12)/max(ps,1e-12))))
            counts[op]+=1; sums[op]+=gain; window.append((op,.8*gain+.2*int(novel)))
        if val>score: best,score,c,d=child,val,cc,dd
        hist.append(score)
    return dict(task=t,method=m,seed=seed,best_ratio=score,tested_ops=c,reference_ops=d,unique_inputs=len(unique),bins=len(archive),mean_best_so_far=st.mean(hist),best_input=list(best),operator_counts=counts,history=hist)
def minimize(t,x):
    parts=[tuple(x)] if t=='sort' else [tuple(x[:64]),tuple(x[64:])]; fn=sort_eval if t=='sort' else substring_eval
    orig=fn(*parts); calls=0; changed=True
    while changed and calls<500:
        changed=False
        for p in range(len(parts)):
            n=len(parts[p]); minimum=2 if t=='sort' else 1
            for size in sorted({max(1,n//2),max(1,n//4),1},reverse=True):
                if n-size<minimum: continue
                for i in range(n-size+1):
                    cand=parts.copy(); cand[p]=parts[p][:i]+parts[p][i+size:]
                    if t=='substring' and len(cand[0])<len(cand[1]): continue
                    if calls>=500: break
                    val=fn(*cand); calls+=1
                    if val[0]>=.95*orig[0] and val[1]>=.70*orig[1]: parts=cand; changed=True; break
                if changed or calls>=500: break
            if changed or calls>=500: break
    return dict(task=t,before=list(x),after=[list(p) for p in parts],original_metrics=orig,final_metrics=fn(*parts),evaluations=calls,original_size=len(x),final_size=sum(map(len,parts)))
def main():
    out=Path(__file__).parent; rows=[]
    for t in TASKS:
        for m in METHODS: rows.extend(run(t,m,s) for s in SEEDS)
        print(t,'completed',flush=True)
    fields=['task','method','seed','best_ratio','tested_ops','reference_ops','unique_inputs','bins','mean_best_so_far']
    with (out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    (out/'raw_results.json').write_text(json.dumps(rows,separators=(',',':')))
    summary=[]; shrinks=[]
    for t in TASKS:
        base={x['seed']:x for x in rows if x['task']==t and x['method']=='uniform'}
        for m in METHODS:
            g=[x for x in rows if x['task']==t and x['method']==m]; diffs=[x['best_ratio']-base[x['seed']]['best_ratio'] for x in g]
            summary.append(dict(task=t,method=m,median=st.median(x['best_ratio'] for x in g),median_auc=st.median(x['mean_best_so_far'] for x in g),median_bins=st.median(x['bins'] for x in g),wins=sum(x>1e-12 for x in diffs),ties=sum(abs(x)<=1e-12 for x in diffs),losses=sum(x< -1e-12 for x in diffs)))
            print(t,m,summary[-1],flush=True)
        if t in ('sort','substring'):
            g=[x for x in rows if x['task']==t and x['method']=='window_archive']; middle=st.median(x['best_ratio'] for x in g); row=min(g,key=lambda x:abs(x['best_ratio']-middle)); shrink=minimize(t,row['best_input']); shrink['seed']=row['seed']; shrinks.append(shrink)
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    (out/'shrinks.json').write_text(json.dumps(shrinks,indent=2)); print('shrink',[(s['task'],s['original_size'],s['final_size'],s['original_metrics'],s['final_metrics']) for s in shrinks])
if __name__=='__main__': main()
