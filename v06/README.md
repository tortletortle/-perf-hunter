# PERF HUNTER V0.6 — Adaptive Statistical Confirmation

V0.6 replaces the fixed 10-worker/5-block validation protocol with sequential, process-level evidence accumulation. It reuses the 24 finalists selected by V0.5; it does **not** rerun or change the search phase.

## Run
From the repository root:

```bash
python v06/adaptive.py --output v06/results
python v06/verify.py
```

Requires CPython 3.13.5 and the standard library. Assertions must remain enabled. The source expects the V0.2, V0.4 and V0.5 files in their repository paths.

## Statistical rule
A fresh subprocess contributes one Bernoulli observation per active finalist: success iff the median of three randomized-order paired timing blocks has baseline/adapted ratio > 1.10. Blocks within a process are summarized into one observation; they are not treated as independent replicates. Each round randomizes finalist order.

There are 24 finalists and two possible inferential claims per finalist. Bonferroni allocates alpha = 0.05 / (24 × 2) = 0.00104167 to each claim, so the e-value boundary is 960.

- Confirmation e-process: mixture likelihood ratio with alternative q uniformly distributed on [0.5, 1], against null success probability p ≤ 0.5. Crossing 960 supports a median process-level ratio > 1.10.
- Futility e-process: mixture likelihood ratio with alternative q uniformly distributed on [0, 0.9], against null p ≥ 0.9. Crossing 960 supports that fewer than 90% of fresh process medians exceed 1.10. This is **not** evidence that the optimization has zero effect; it means the improvement is not sufficiently reproducible at the chosen 90% standard.
- If neither boundary is crossed by 20 workers, status is inconclusive.

Both are nonnegative mixture likelihood-ratio supermartingales under their respective composite nulls. Ville's inequality plus Bonferroni controls the familywise error across both claim types, assuming independent fresh-process observations for each finalist and a stable measurement protocol. Cross-finalist dependence does not invalidate Bonferroni. Host-level temporal dependence can still compromise the independence assumption; process isolation and randomized order mitigate but do not eliminate it.

The finite-horizon exact crossing probabilities under the boundary nulls are calculated by dynamic programming in `adaptive.py`; they are 0.00017166 for confirmation at p=0.5 and 0.00028163 for futility at p=0.9, both below 0.00104167.

## Observed results
- 24 finalists: 16 issue-inspired positive controls and 8 identical-implementation A/A negative controls.
- 245 independent worker-process samples; each process uses 3 paired timing blocks.
- 735 paired timing blocks versus 1,200 in V0.5's fixed protocol: 465 fewer, a 38.75% reduction.
- All 16 positive-control finalists reached confirmation. Fifteen stopped after 13 workers; one required 18 workers because one worker median fell below threshold.
- All 8 A/A finalists stopped for futility after 4 workers (0/4 successes).

This is a controlled result on the existing two issue-inspired adapters and an A/A control, not a general benchmark-wide sensitivity/specificity estimate. The V0.4 ZIP case is only a mechanism-level proxy for zipp #106; V0.7 separately reproduces the upstream `filelist` optimization and later directory-correctness revert. It does not establish algorithmic novelty or cross-machine robustness. The old and new protocols use different numbers of blocks per worker (5 vs 3), so the comparison is in paired timing blocks, not wall-clock time or total process-launch cost.

## Files
- `adaptive.py`: sequential mixture-e testing and process orchestration.
- `test_adaptive.py`: unit tests for e-values, stopping rules and finite-horizon error bounds.
- `verify.py`: checks raw or compact worker records, or falls back to summary-level verification when raw records are not present.
- `reference/finalists.json`: frozen V0.5 finalist set used for this validation.
- `results/rounds.json`: full raw per-round worker records and paired blocks (included in the downloadable bundle).
- `results/observations.json`: compact per-candidate process-median sequences for GitHub-side audit.
- `results/summary.csv`: finalist-level table committed to the repository.
- `results/summary.json`: full JSON summary included in the downloadable bundle.
- `results/protocol_stats.json`, `manifest.json`: budget, null-bound calculations and file hashes.
