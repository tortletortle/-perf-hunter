"""Verify saved experiments after diagnostic.py has generated results.json."""
import argparse,json,sys
from pathlib import Path
import diagnostic as d
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,default=Path(__file__).resolve().parent.parent/'v02');p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args()
sys.path.insert(0,str(a.baseline.resolve()));import experiment as e
r=json.loads((a.output/'results.json').read_text());assert len(r)==384;assert len({(x['task'],x['method'],x['seed']) for x in r})==384
for x in r:
    h=x['history'];assert len(h)==320 and h==sorted(h) and h[-1]==x['best_ratio'];assert e.evaluate(x['task'],x['best_input'])==(x['best_ratio'],x['tested_ops'],x['reference_ops'])
e.BUDGET=320
for t in e.TASKS:
    for s in (200,201):
        for m,v in [('uniform','uniform'),('generic','archive_uniform')]:
            a=d.run(e,t,m,s);b=e.run(t,v,s);assert a['history']==b['history'] and a['best_input']==b['best_input']
print('384 runs verified; 16 paired baseline replay checks passed')
