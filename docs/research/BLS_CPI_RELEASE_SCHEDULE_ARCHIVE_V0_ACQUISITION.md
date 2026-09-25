# BLS CPI release-schedule archive V0 — acquisition record

`VERDICT = BLS_CPI_CALENDAR_V0_DURABLY_PINNED`
`KIND = DATA_PROVENANCE_ONLY`
`NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER`

This unit is the calendar-acquisition/provenance half of `GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN`. Its only output is the point-in-time CPI release schedule for 2020–2024.

Out of scope, and not done: C012 was not designed or preregistered; C004's event set was not chosen; no power was computed; no hypothesis was executed. No CPI values, BTC data or event-window returns were read or computed. Protected 2025/2026 market values were not opened, no execution permit was created, Generator V0 memory was not modified, and no LLM or provider was called.

Machine-readable twin: `BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0_ACQUISITION.json`. Dataset: `docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/`. Script: `scripts/research/bls_cpi_schedule_archive_v0.py`.

## What was acquired

- **CDX listing.** The Wayback CDX listing of `bls.gov/schedule/news_release/cpi.htm`, 2019–2024: 222 rows with status 200.
- **Wayback captures.** 190 archived payloads, fetched exactly (`id_`). Of these, 189 match Wayback's own CDX SHA-1 digest. The one mismatching capture (2019-01-18, pre-range) is retained but not used as evidence.
- **Not obtained.** 31 captures redirected to a different capture. One row of a duplicate-timestamp pair was also not served. None of these carry a hash.
- **Live first-party pages, retrieved on 2026-09-25.** The current schedule page and the BLS CPI release archive. These are diagnostics only and are never point-in-time authority.
- **Retention.** All obtained bytes are retained under `raw/`, content-addressed by SHA256, following the D11_FOMC_OFFICIAL_V0 and MARKET-06 `durable_raw` precedent. That is 109 distinct Wayback payloads, about 5 MB.

## Result

- **Events.** 60 in total, 12 per year for 2020–2024, covering reference months 2019-12 through 2024-11.
- **Status and safety.** All 60 are `VERIFIED_PREANNOUNCED`. The safe counts are W6 = 60, W12 = 60 and W24 = 60.
- **Schedule history.** No reschedules were observed in any capture, and no event is unresolved.
- **Release time and UTC.** Every release is at 08:30 America/New_York, which is 12:30Z during EDT and 13:30Z during EST. The DST verification passed for all 60 events: the frozen `STATUTORY_DST_CALENDARS` table, the EPAct 2005 rule and zoneinfo all agree.
- **Earliest publication.** The earliest verified publication precedes release by 29 to 425 days.
- **Evidence staleness.** The gap from the latest pre-cutoff capture to the W24 cutoff is 2 h at minimum, about 177 h at the median and 2770 h at most. Eleven events have a gap over 30 days, mainly in 2020 when captures were sparse. The gap is recorded per event in `WINDOW_EVIDENCE`, so downstream designs can apply a staleness bound without redefining the dataset.
- **Diagnostics.** Post-release captures and the realized-date archive show no change, but they are not used for the safety flags.
- **Excluded from the canonical set.** Reference month 2024-12 (released 2025-01-15) and the other 2025 releases, plus pre-2020 releases, appear only as metadata in `OUT_OF_RANGE_INVENTORY.json`.

Dataset digest: `760ed2c5d18b03b7a41c25e6bab157ebde476977fdc3e5f7a3462aa376f4154f`.

## Downstream status

This dataset resolves the CPI calendar observable. C012 and C004 may reference it later. It changes no candidate status beyond removing that one data blocker.

## Validation run

- `python3 -m scripts.research.bls_cpi_schedule_archive_v0 validate` returns `VALID`. It rebuilds the dataset byte-exact from `raw/` and checks all ten required invariants.
- `python3 -m compileall -q scripts/research`: pass.
- `tests/research/test_bls_cpi_schedule_archive_v0.py`: 24 passed.
- Discovery Sprint 03/04 D11/D12 calendar tests: 90 passed.
- `git diff --check`: clean.
