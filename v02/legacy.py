"""Exploratory, deterministic operation-count benchmark. Standard library only."""
import random, math, statistics, csv, json
from pathlib import Path

N=64
M=12
BUDGET=160
TRIALS=16

def quick(a):
    if len(a)<2: return list(a),0
    pivot=a[0]; lo=[]; hi=[]
    for x in a[1:]: (lo if x<pivot else hi).append(x)
    l,lc=quick(lo); h,hc=quick(hi)
    return l+[pivot]+h, lc+hc+len(a)-1

def merge(a):
    if len(a)<2: return list(a),0
    l,lc=merge(a[:len(a)//2]); r,rc=merge(a[len(a)//2:]); i=j=c=0; out=[]
    while i<len(l) and j<len(r):
        c+=1
        if l[i]<=r[j]: out.append(l[i]); i+=1
        else: out.append(r[j]); j+=1
    return out+l[i:]+r[j:],lc+rc+c

def naive(t,p):
    c=0
    for i in range(len(t)-len(p)+1):
        for j in range(len(p)):
            c+=1
            if t[i+j]!=p[j]: break
        else: return i,c
    return -1,c

def kmp(t,p):
    c=0; prefix=[0]*len(p); j=0
    for i in range(1,len(p)):
        while True:
            c+=1
            if p[i]==p[j]: j+=1; break
            if not j: break
            j=prefix[j-1]
        prefix[i]=j
    j=0
    for i,x in enumerate(t):
        while True:
            c+=1
            if x==p[j]: j+=1; break
            if not j: break
            j=prefix[j-1]
        if j==len(p): return i-len(p)+1,c
    return -1,c

def initial(task,r):
    if task=='sort': return tuple(r.randrange(N) for _ in range(N))
    return tuple(r.randrange(4) for _ in range(N+M))

def evaluate(task,x):
    if task=='sort':
        a,c=quick(x); b,d=merge(x); assert a==b==sorted(x)
    else:
        t,p=x[:N],x[N:]; a,c=naive(t,p); b,d=kmp(t,p)
        oracle=bytes(t).find(bytes(p)); assert a==b==oracle
    return c/max(d,1),c,d

OPS=('point','swap','reverse','copy_block','fill_block','restart')
def mutate(task,x,op,r):
    if op=='restart': return initial(task,r)
    a=list(x); n=len(a); alphabet=N if task=='sort' else 4
    if op=='point': a[r.randrange(n)]=r.randrange(alphabet)
    elif op=='swap':
        i,j=r.sample(range(n),2); a[i],a[j]=a[j],a[i]
    else:
        i,j=sorted(r.sample(range(n+1),2)); k=j-i
        if op=='reverse': a[i:j]=reversed(a[i:j])
        elif op=='copy_block':
            start=r.randrange(n-k+1); a[i:j]=a[start:start+k]
        elif op=='fill_block': a[i:j]=[r.randrange(alphabet)]*k
    return tuple(a)

def run(task,method,seed):
    r=random.Random(seed); best=initial(task,r); score,c,d=evaluate(task,best); history=[score]
    counts={op:0 for op in OPS}; rewards={op:0.0 for op in OPS}; distinct={best}
    for step in range(1,BUDGET):
        if method=='random': candidate=initial(task,r); op=None
        else:
            if method=='uniform': op=r.choice(OPS)
            elif method=='ucb':
                unused=[op for op in OPS if not counts[op]]
                op=r.choice(unused) if unused else max(OPS,key=lambda o: rewards[o]/counts[o]+0.35*math.sqrt(math.log(step)/counts[o]))
            candidate=mutate(task,best,op,r)
        value,cc,dd=evaluate(task,candidate); distinct.add(candidate)
        if op is not None:
            counts[op]+=1; rewards[op]+=min(1.0,max(0.0,math.log(value/score)))
        if value>score:
            best,score,c,d=candidate,value,cc,dd
        history.append(score)
    return dict(task=task,method=method,seed=seed,best_ratio=score,tested_ops=c,reference_ops=d,unique_inputs=len(distinct),mean_best_so_far=statistics.mean(history),best_input=list(best),operator_counts=counts,history=history)

def main():
    out=Path(__file__).parent
    rows=[run(task,method,seed) for task in ('sort','substring') for method in ('random','uniform','ucb') for seed in range(TRIALS)]
    (out/'raw_results.json').write_text(json.dumps(rows,indent=2))
    fields=['task','method','seed','best_ratio','tested_ops','reference_ops','unique_inputs','mean_best_so_far']
    with (out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    for task in ('sort','substring'):
        for method in ('random','uniform','ucb'):
            g=[x for x in rows if x['task']==task and x['method']==method]
            print(task,method,'median=',round(statistics.median(x['best_ratio'] for x in g),3),'range=',tuple(round(v,3) for v in (min(x['best_ratio'] for x in g),max(x['best_ratio'] for x in g))),'median_auc=',round(statistics.median(x['mean_best_so_far'] for x in g),3))
        paired=[(next(x['best_ratio'] for x in rows if x['task']==task and x['method']=='ucb' and x['seed']==s),next(x['best_ratio'] for x in rows if x['task']==task and x['method']=='uniform' and x['seed']==s)) for s in range(TRIALS)]
        print('paired UCB wins/ties/losses:',sum(a>b for a,b in paired),sum(a==b for a,b in paired),sum(a<b for a,b in paired))
if __name__=='__main__': main()
