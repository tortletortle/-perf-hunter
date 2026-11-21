# PERF HUNTER V0.4

Issue-inspired runtime benchmark, standard library only. Run `python benchmark.py` with CPython 3.13.5 (the deepcopy adapter rejects an unsupported layout). Do not disable assertions. Run from the repository with `python v04/benchmark.py --output results-v04`.

## Cases and provenance
- CPython issue #114264 / merged PR #114266 (https://github.com/python/cpython/pull/114266): compare two isolated copies of the locally installed copy module, with one extra early return for types using its atomic dispatcher. This is a controlled adaptation, not an exact checkout of the upstream patch. Tests cover plain lists, nested lists, aliasing and cycles, not custom memo semantics or the entire upstream suite.
- zipp issue #106 is specifically about `Path.glob` complexity growing with directory depth. PR #113 (https://github.com/jaraco/zipp/pull/113) bypassed `ZipFile.namelist()` by iterating `filelist`; PR #122 (https://github.com/jaraco/zipp/pull/122) later restored `namelist()` while fixing implicit-directory matching. The V0.4 ZIP test only compared repeated name-list construction with a per-call snapshot. It is a mechanism-level proxy, **not** a reproduction of `zipp.Path.glob` or either upstream patch. V0.7 adds the more direct PR-level reproduction.

## Protocol
Three subprocesses with seeds 410–412, 19 conditions each, nine randomized-order paired measurement blocks per condition, 513 blocks total. Calibrate common loop count; GC disabled only during measured blocks. Each result is median of three worker medians; no confidence interval or significance claim. A/A control uses the identical implementation. Results are machine-specific and are not search-engine results.

## Observations
At size 2048: deepcopy atomic 2.592x, mixed 1.343x, nested 1.142x; zip queries q1 0.991x, q16 1.417x, q64 1.422x. A/A median 1.000, worker medians 0.937–1.024. All three workers exceed 1 for all deepcopy conditions and q16/q64 ZIP conditions. ZIP q1 is a negative control. Raw CSV contains times and ratios, summary CSV aggregates, environment JSON records the local copy source hash. Both correctness assertions and saved-data aggregation checks passed locally.

## Limitations
Only two issue-inspired adapters, synthetic inputs, no pinned historical upstream before/after builds, no CPU pinning or independent machine replication, no novel search algorithm or automated discovery validation. Next: add exact historical commit pairs and budgeted search with independent finalist reruns and false-positive controls.
