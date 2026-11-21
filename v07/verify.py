"""Verify saved V0.7 zipp benchmark records and semantic probes."""
import json
import math
import statistics as st
from pathlib import Path
import zipp_glob_benchmark as b


def slope(xs, ys):
    lx=[math.log(x) for x in xs]; ly=[math.log(y) for y in ys]
    mx=st.mean(lx); my=st.mean(ly)
    return sum((x-mx)*(y-my) for x,y in zip(lx,ly))/sum((x-mx)**2 for x in lx)


def main():
    root=Path(__file__).resolve().parent
    out=root/'results'
    full=(out/'workers.json').exists()
    compact=(not full) and (out/'worker_summary.json').exists()
    workers=json.loads((out/('workers.json' if full else 'worker_summary.json')).read_text()) if (full or compact) else None
    summary=json.loads((out/'summary.json').read_text())
    assert summary['zipp_version']=='4.1.0'
    assert len(summary['rows'])==len(b.DEPTHS)
    if workers is not None:
        assert len(workers)==3 and len({w['seed'] for w in workers})==3
        assert all(w['zipp_version']=='4.1.0' for w in workers)
        assert len({w['glob_source_sha'] for w in workers})==1
        assert all(len(w['results'])==len(b.DEPTHS) for w in workers)
        for w in workers:
            for row in w['results']:
                assert row['structural_work']==b.structural_work(row['depth'])
                if full:
                    assert len(row['blocks'])==b.PAIRS
                    assert math.isclose(row['median_speedup'],st.median(x['speedup'] for x in row['blocks']),rel_tol=1e-12)
                    assert math.isclose(row['median_namelist_ns'],st.median(x['namelist_ns'] for x in row['blocks']),rel_tol=1e-12)
                    assert math.isclose(row['median_filelist_ns'],st.median(x['filelist_ns'] for x in row['blocks']),rel_tol=1e-12)
        for row in summary['rows']:
            depth=row['depth']; group=[next(x for x in w['results'] if x['depth']==depth) for w in workers]
            base=st.median(x['median_namelist_ns'] for x in group)
            fast=st.median(x['median_filelist_ns'] for x in group)
            assert math.isclose(row['median_namelist_ns'],base,rel_tol=1e-12)
            assert math.isclose(row['median_filelist_ns'],fast,rel_tol=1e-12)
            assert math.isclose(row['speedup'],base/fast,rel_tol=1e-12)
    assert summary['total_paired_blocks']==3*7*7==147
    semantic=summary['semantic_probe']
    assert semantic['file_pattern_baseline']==semantic['file_pattern_filelist']==['a.txt']
    assert semantic['directory_pattern_namelist']==['d/']
    assert semantic['directory_pattern_filelist']==[]
    xs=[r['depth'] for r in summary['rows']]
    ys1=[r['median_namelist_ns'] for r in summary['rows']]
    ys2=[r['median_filelist_ns'] for r in summary['rows']]
    assert math.isclose(summary['log_log_slopes']['namelist'],slope(xs,ys1),rel_tol=1e-12)
    assert math.isclose(summary['log_log_slopes']['filelist'],slope(xs,ys2),rel_tol=1e-12)
    print('PASS: 3 workers × 7 depths × 7 paired blocks = 147 paired blocks' + (' (full raw blocks)' if full else ' (compact worker medians)' if compact else ' (summary audit)'))
    print('PASS: timing aggregates, structural work counts and semantic regression checks')

if __name__=='__main__': main()
