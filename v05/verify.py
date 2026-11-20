"""Verify recorded V0.5 artifacts without rerunning noisy timing tests."""
import json, math, statistics as st
from pathlib import Path
import search as s

def main():
    root=Path(__file__).parent
    def read(name): return json.loads((root/name).read_text())
    a,b=read('search.json'),read('validation.json')
    f,z=read('finalists.json'),read('summary.json')
    rr=[r for w in a for r in w['rows']]; vv=[r for w in b for r in w['rows']]
    assert len(rr)==384 and len(vv)==240 and len(f)==len(z)==24
    assert len({(r['case'],r['method'],r['seed'],r['step']) for r in rr})==384
    assert len({(r['id'],r['worker']) for r in vv})==240
    assert len({w['source_sha'] for w in a+b})==1
    for r in rr+vv:
        assert r['ratio']==st.median(x['ratio'] for x in r['blocks'])
        assert all(math.isclose(x['a_ns']/x['b_ns'],x['ratio'],rel_tol=1e-12) for x in r['blocks'])
    for x,y in zip(f,z):
        assert all(y[k]==v for k,v in x.items())
        g=[r for r in rr if (r['case'],r['method'],r['seed'])==(x['case'],x['method'],x['seed'])]
        assert len(g)==s.BUDGET
        best=max(g,key=lambda r:r['ratio'])
        assert best['x']==x['x'] and best['ratio']==x['search_ratio']
        vals=[r['ratio'] for r in vv if r['id']==x['id']]
        assert len(vals)==s.WORKERS
        assert all(y[k]==v for k,v in s.verdict(vals,len(f)).items())
    print('PASS: 384 search candidates, 240 process-level medians, 24 verdicts')
if __name__=='__main__': main()
