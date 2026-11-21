# PERF HUNTER

Differential performance testing and counterexample discovery.

## Current status

- **V0.2** — fixed-budget operation-count search baseline.
- **V0.3** — cost-feedback and diversity-search ablations; no stable advantage over uniform mutation.
- **V0.4** — issue-inspired CPython deepcopy and ZIP name-query runtime benchmarks.
- **V0.5** — runtime-guided candidate search with independent-process confirmation and A/A negative controls.
- **V0.6** — anytime-valid adaptive statistical confirmation; 735 paired timing blocks versus 1,200 in the V0.5 fixed protocol on the same 24 finalists.

See [V0.6 report and reproducibility instructions](v06/README.md). Raw per-block timing records and the complete experiment bundle are distributed with the V0.6 artifact; compact process-median sequences and the summary table are tracked in this repository.

The project is experimental. Current runtime cases are issue-inspired adapters, not exact historical upstream before/after builds. Performance claims are machine- and workload-dependent; no cross-machine validation or general false-positive/false-negative estimate has been established.
