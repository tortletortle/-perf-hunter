# PERF HUNTER V0.2

Exploratory differential operation-count search. Python 3, standard library only.

```
python experiment.py
python -m unittest -v test_experiment.py
```

## Protocol
4 tasks, 6 methods, 24 paired seed IDs (100–123), 160 evaluations per run including the initial input. 576 runs and 92,160 search evaluations. Same initial input per task/seed, subsequent streams may diverge. Duplicate evaluations count. The sorting/substring tasks reuse V0.1 code in legacy.py; graph and bounds are new exploratory tasks, not externally curated validation. Settings were chosen before this run, not optimized afterward. Oracle assertions must remain enabled (do not run Python -O).

- sort: first-pivot quicksort vs mergesort, 64 elements, key comparisons.
- substring: naive vs KMP, 64-symbol text and 12-symbol pattern, symbol comparisons including KMP preprocessing.
- graph: BFS scanning all edges vs indexed adjacency BFS, 16 vertices and 40 directed edges, duplicates/self-loops allowed, start 0; counts edge examinations including adjacency construction.
- bounds: linear vs binary lower-bound search, 64 sorted keys and 32 queries, key comparisons; sorting is common input preparation and excluded.

All report numerator/reference operation counts (not speedup in seconds). Each candidate is checked against Python sorted, bytes.find, independent fixed-point reachability or bisect_left respectively. Methods use identical mutation functions. Uniform and UCB match V0.1 on original tasks; UCB uses lifetime clipped positive log gains. Archive search selects a random occupied bin with probability 0.45, otherwise global best. Bins use adjacent equality, distinct fraction, ascending adjacency fraction; four levels each. Window variants use last 40 operations, reward 0.8*clipped positive log gain relative to parent + 0.2*new-bin indicator. UCB exploration constant 0.35. All methods track archive occupancy for comparison; only archive variants sample it. Each variant has identical evaluation count, not equal CPU time. No inference of statistical significance; two additional synthetic tasks do not constitute strong external generalization evidence.

## Results
See summary.csv for median best ratio, median trajectory mean, median bin count, paired win/tie/loss vs uniform. Combined variant loses on median on all four tasks vs uniform. Archive improves median occupied-bin count on 3 of 4 tasks but not median maximum score. Window-greedy improves graph median only, ties sort. Sorting exhibits ceiling effects, graph also has a limited score range. Archive descriptors are generic and may be poorly aligned to the actual objective. These are hypotheses, not verified causal explanations.

## Shrinking
Search is followed by a separate deletion-only minimizer for sort/substring. Select the combined variant's trial closest to median best score per task (first if tied). Up to 500 additional deletion evaluations, excluding initial and final measurement. Keep >=95% original ratio and >=70% original numerator. This is threshold-preserving, not globally minimal; no graph or bounds shrink adapter yet. See shrinks.json.

## Reproduction and limitations
results.csv: trial metrics; raw_results.json: histories and best inputs; summary.csv: aggregates; run.log: execution log; tests.log: verification log. No real runtime benchmarking, external fuzzer comparison, production target integration, UI, or claim of novel research. PerfFuzz, MAP-Elites and MOPT are research references, not imported dependencies.
