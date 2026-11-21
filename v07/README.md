# PERF HUNTER V0.7 — zipp glob performance/correctness tradeoff

V0.7 corrects the V0.4 attribution and reproduces the relevant zipp.Path.glob mechanism more directly.

## Upstream history
- [Issue #106](https://github.com/jaraco/zipp/issues/106): Path.glob complexity grew with directory depth.
- [PR #113](https://github.com/jaraco/zipp/pull/113), merge `48b72b8db6ae5f7712323aca6b340744db15f576`: bypassed ZipFile.namelist() by iterating self.root.filelist and changed the upstream depth-complexity test expectation from quadratic to linear.
- [PR #122](https://github.com/jaraco/zipp/pull/122), merge `579be51bb31881a8e04040ff7a7c134053540326`: restored self.root.namelist() while adding directory matching to glob, because the filelist-only path missed implicit directories. This later correctness fix is not itself a fix for issue #106; it restores a code path with the earlier implied-directory enumeration cost.

The benchmark uses installed zipp 4.1.0 as the post-PR-122 baseline and the exact relevant filelist glob core from PR #113 as the comparison. It is a patch-level reproduction of the upstream implementation tradeoff, not a complete checkout/run of the historical commits. zipp.Path.glob is checked at runtime to ensure the installed baseline uses namelist().

## Run

```bash
python -m pip install zipp==4.1.0
python v07/zipp_glob_benchmark.py --output v07/results
python v07/verify.py
(cd v07 && python -m unittest -v test_zipp_glob.py)
```

## Protocol

Three fresh worker processes (seeds 701–703), seven archive depths (16–1024), seven randomized-order paired timing blocks per worker/depth: 147 paired blocks. Each timing call opens a fresh read-only ZIP archive and runs one glob('*.txt'); the archive bytes are prepared outside timing. Each pair uses a common calibrated loop count. Results are medians across paired blocks within each worker, then medians across three workers. This is a single-machine exploratory benchmark, not a confidence interval or formal significance test.

The archive matches the upstream depth fixture: one explicit file at each path d/ repeated i times, for i from 0 to depth−1. CompleteDirs._implied_dirs visits all ancestors of all explicit names, producing exactly depth×(depth−1)/2 parent visits. The filelist path scans only the depth explicit entries.

## Results

| Depth | Implied parent visits | namelist() ms | filelist ms | Speedup |
|---:|---:|---:|---:|---:|
| 16 | 120 | 0.106 | 0.045 | 2.36× |
| 32 | 496 | 0.307 | 0.081 | 3.80× |
| 64 | 2,016 | 1.039 | 0.177 | 5.86× |
| 128 | 8,128 | 3.712 | 0.348 | 10.68× |
| 256 | 32,640 | 15.929 | 0.734 | 21.70× |
| 512 | 130,816 | 69.593 | 1.706 | 40.79× |
| 1024 | 523,776 | 370.841 | 3.993 | 92.87× |

Exploratory log-log timing slopes: 1.96 for namelist() and 1.08 for filelist, consistent with the structural parent-visit counts. At depth 1024, the filelist variant was about 92.9× faster in this environment.

## Correctness tradeoff

For glob('*.txt'), both variants return the same explicit root file. For glob('d'), the post-PR-122 namelist implementation returns the implied directory d/, while the PR-113 filelist-only variant returns nothing. This reproduces why the performance patch could not simply replace namelist() without also preserving implied-directory semantics.

## Limitations

- zipp 4.1.0 baseline plus a transplanted PR #113 glob core, not exact historical package wheels/commits.
- One machine, three worker processes, synthetic depth fixture, no cross-machine replication.
- Runtime includes opening the ZIP and constructing the Path object; archive creation is excluded.
- The PR #113 path is compared using the current Translator; the measured *.txt case is unaffected by the later directory-matching regex change.
- This validates a specific performance/correctness tradeoff, not a general-purpose search algorithm advantage.

Raw worker blocks are in results/workers.json; results/worker_summary.json stores compact per-worker medians for repository-side audit. Aggregates are in results/summary.json and results/summary.csv; results/provenance.json records upstream commit SHAs and the installed source hash.
