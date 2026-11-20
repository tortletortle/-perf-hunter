# PERF HUNTER V0.3

From the repository root, run `python v03/diagnostic.py`. Uses the unchanged V0.2 adapters and Python standard library. Local bundle users can pass `--baseline ../perf_hunter_v02` while running in the experiment directory.

## Protocol
Four original synthetic tasks, four strategies, 24 paired seeds (200–223), 320 evaluations per run including initialization (384 runs; 122,880 evaluations). Checkpoints: 80, 160, 320. Uniform uses the global best; generic archive uses V0.2 input descriptors and probability 0.45; counter archive uses quarter-log2 bins of the two measured operation counts and probability 0.45; counter_stall changes probability to 0.15 before 12 stagnant iterations and 0.65 afterward. All use uniform mutation and the same oracle. These are cost counters, not path-level traces. Same seed IDs align initial inputs, not subsequent random streams. No training/tuning, formal significance claims or new external benchmarks.

## Results (median best ratio at 320)
| Task | Uniform | Generic | Counter | Counter-stall |
|---|---:|---:|---:|---:|
| Sort | 10.50 | 10.50 | 10.50 | 10.50 |
| Substring | 4.61 | 4.48 | 4.38 | 4.37 |
| Graph | 9.09 | 8.47 | 8.35 | 8.81 |
| Bounds | 10.66 | 10.60 | 10.54 | 10.61 |

Neither archive variant beats uniform on median. The cost-feedback archive does not establish an improvement over generic features; insufficient evidence to rule out other forms of feedback. Sorting has a ceiling effect. The design uses equal evaluation budgets, not equal wall-clock budgets.

## Runtime sanity check
Two representative uniform trials closest to the median, both seed 200. Compare initial and searched input; existing counted Python implementations, 10 warm-up calls each and nine alternating batches of 100 calls per implementation. Median paired time ratios (tested/reference): sort 0.465 to 1.712; substring 0.886 to 3.773. Runtime not a search objective and not generalizable to production; timings noisy and machine-specific. Full generated results.json, summary.csv, timings.json and run.log included in the local bundle, reproducible from source; timing values will vary.

## Validation
384 saved runs checked for unique task/method/seed, monotone histories and oracle-verified final inputs/metrics. Sixteen replay comparisons of uniform and generic across the four tasks and seeds 200 and 201 match V0.2 at a 320-evaluation budget.
