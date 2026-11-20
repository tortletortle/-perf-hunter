import unittest,random,json
from pathlib import Path
import experiment as e
import legacy
class Tests(unittest.TestCase):
    def test_oracles_and_mutation_domains(self):
        for t in e.TASKS:
            r=random.Random(123); x=e.initial(t,r); n,k=e.SPECS[t]
            for _ in range(20):
                for op in e.OPS:
                    x=e.mutate(t,x,op,r)
                    self.assertEqual(len(x),n); self.assertTrue(all(0<=a<k for a in x)); self.assertGreaterEqual(e.evaluate(t,x)[0],0)
    def test_legacy_baselines(self):
        for t in ('sort','substring'):
            for m in ('random','uniform','ucb'):
                for seed in (100,101):
                    a=e.run(t,m,seed); b=legacy.run(t,m,seed)
                    self.assertEqual(a['history'],b['history']); self.assertEqual(a['best_input'],b['best_input'])
    def test_saved_experiment(self):
        rows=json.loads(Path(__file__).with_name('raw_results.json').read_text())
        self.assertEqual(len(rows),576)
        self.assertEqual(len({(r['task'],r['method'],r['seed']) for r in rows}),576)
        for r in rows:
            h=r['history']; self.assertEqual(len(h),160); self.assertEqual(h[-1],r['best_ratio']); self.assertEqual(h,sorted(h)); self.assertEqual(e.evaluate(r['task'],r['best_input']),(r['best_ratio'],r['tested_ops'],r['reference_ops']))
    def test_shrink(self):
        rows=json.loads(Path(__file__).with_name('shrinks.json').read_text())
        for r in rows:
            fn=e.sort_eval if r['task']=='sort' else e.substring_eval
            val=fn(*r['after']); self.assertEqual(tuple(r['final_metrics']),val); self.assertGreaterEqual(val[0],.95*r['original_metrics'][0]); self.assertGreaterEqual(val[1],.70*r['original_metrics'][1]); self.assertLessEqual(r['final_size'],r['original_size'])
if __name__=='__main__': unittest.main()
