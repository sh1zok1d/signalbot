# Validation compute plan

**Status:** development benchmark only. Official validation was not started.

**Command:**

```bash
PYTHONPATH=/workspace python3.11 -m scripts.research.self_referential_contrast_v1.benchmark --workers N --output /opt/cursor/artifacts/validation_benchmark.json
```

`--workers` is an execution parameter. The measured reference below uses one process for the per-world timings. The speedup probe uses workers `1`, `2`, and `4` on four generic worlds at `T = 16384`, `R = 999`. Chunk sizes `1`, `2`, and `4` were timed on a four-world probe and produced identical seed digests and rejection decisions.

No operational budget is authorized in the amendment. The projections below are the stopping evidence. The official 1600-world screens were not run.

## Measured throughput

Single process, `R = 999`, development purpose, synthetic fixtures.

| case | T | B_T | wall seconds | draws/second | CPU / wall | VmRSS KiB | VmHWM KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 256 | 7 | 0.0254 | 39353 | 1.00 | 40876 | 40876 |
| medium | 2048 | 13 | 0.0907 | 11010 | 1.00 | 41224 | 50200 |
| large generic | 16384 | 26 | 0.5489 | 1820 | 1.00 | 42192 | 91244 |
| maximum generic | 65536 | 41 | 2.2800 | 438 | 1.00 | 78312 | 244988 |
| admission length, mechanical floor | 30354 | 721 | 0.8216 | 1216 | 1.00 | 44296 | 244988 |

`B_T = 721` on the admission-length case is the bandwidth rule's output at that adapter floor, not a constant inside the generic estimator. Peak high-water mark on this process was about 245 MiB, reached on the `T = 65536` case.

## Speedup probe

Four worlds, `T = 16384`, `R = 999`, process pool, chunk size 1.

| workers | wall seconds | speedup vs 1 | efficiency |
| ---: | ---: | ---: | ---: |
| 1 | 1.607 | 1.00 | 1.00 |
| 2 | 1.312 | 1.22 | 0.61 |
| 4 | 0.788 | 2.04 | 0.51 |

This probe is only a few seconds, so process startup is visible in the efficiency. It is not a claim that a 25-minute job keeps efficiency 0.51. The workers=1 projections below do not depend on that efficiency.

## Workers=1 projections from measured draws/second

Generic screen mix produced by the frozen allocation: `544` worlds at `T = 2048`, `544` at `T = 16384`, `512` at `T = 65536`.

| suite | projection at workers = 1 |
| --- | ---: |
| 1600 generic worlds, `R = 999` | 1515 seconds |
| 1600 exact-geometry worlds at the admission length, `R = 999` | 1315 seconds |
| 200 high-R diagnostic worlds, `R = 9999`, generic length mix | 1914 seconds |

Sequential total of those three suites is about 4744 seconds, about 79 minutes, on this machine at one worker. Four worker processes would reduce the compute portion, with a one-time pool start that is small relative to that total, and with memory on the order of one 245 MiB high-water mark per worker on the longest generic worlds.

## Gate

`operational_budget_authorized = false`

`official_validation_executed = false`

Official validation stays stopped until a budget is authorized. `N` and `R` were not reduced after seeing results, because there are no official results.
