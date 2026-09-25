# BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0

Point-in-time schedule of BLS Consumer Price Index news releases (all items, U.S. city average) scheduled from 2020-01-01 through 2024-12-31. The dataset holds **schedule metadata only**: no CPI values, no market data, no event-window returns, and no protected 2025/2026 market values.

## Authority

- **Canonical source.** The first-party BLS page `https://www.bls.gov/schedule/news_release/cpi.htm` ("Schedule of Releases for the Consumer Price Index"). Each release has a Reference Month, a Release Date and a Release Time in Eastern Time.
- **Publication timing.** Dated Internet Archive captures of that same page, fetched as exact archived payloads (`/web/<ts>id_/`). Wayback is used only to date versions of the BLS page. No third-party calendar is used.
- **Timezone and DST.** The official local time is kept. UTC comes from the frozen `STATUTORY_DST_CALENDARS` US transition days in `docs/research/DISCOVERY_SPRINT_04.json`; the file SHA256 is recorded. That result is cross-checked against the Energy Policy Act 2005 rule and against `zoneinfo` America/New_York.
- **Non-authoritative diagnostics.** A live retrieval of the BLS release archive (eventual realized dates) and of the current schedule page. Neither is used to establish safety.

## Point-in-time rule

For a window W of 6h, 12h or 24h, `SAFE_FOR_W` is true only if two conditions hold:

- the latest obtained capture strictly before `T - W` lists the reference month with exactly the final pre-window schedule (date and local time);
- no capture at or after `T - 6h` contradicts that schedule.

The flags are chained by conjunction: W24 implies W12, which implies W6. Only captures whose bytes match Wayback's own CDX SHA-1 digest count as evidence. `EARLIEST_VERIFIED_PUBLICATION` is an upper bound on when the schedule first became public.

## Result

- **Events.** 60 in total, 12 per year for 2020–2024. All 60 are `VERIFIED_PREANNOUNCED` and safe for W6, W12 and W24.
- **Schedule history.** No reschedules and no unresolved events. Every release is at 08:30 ET: 12:30Z in EDT and 13:30Z in EST.
- **Evidence staleness.** The gap between the last pre-cutoff capture and the W24 cutoff has a median of about 177 h. Eleven events have a gap over 30 days, most of them in 2020 when captures were sparse. Each event's `WINDOW_EVIDENCE` records its gap. Post-release captures and the realized-date diagnostic show no schedule change.
- **Out-of-range inventory.** Pre-2020 releases and releases scheduled in 2025 (including reference month 2024-12, released 2025-01-15) are listed only in `OUT_OF_RANGE_INVENTORY.json` (non-canonical).

## Files

| File | Content |
|---|---|
| `EVENTS.json` | Canonical events |
| `OUT_OF_RANGE_INVENTORY.json` | Pre-2020 and 2025 schedule metadata only |
| `SOURCE_AUTHORITY.json` | Authorities, archive method, DST authority, point-in-time rule, legal range, exclusions |
| `SNAPSHOT_LEDGER.json` | All 222 CDX rows plus 2 live pages: role, timestamps, SHA256 of bytes actually obtained, CDX digest match, supported event IDs |
| `MANIFEST.json` | Counts, file digests, raw digests, canonical dataset digest |
| `raw/` | Exact obtained bytes (content-addressed by SHA256), the CDX listing, and `ACQUISITION_LOG.json` |

Captures that Wayback answered with a 302 to a different capture are recorded as not obtained and carry no hash. So is the second row of a duplicate-timestamp pair.

## Reproduce

```bash
python3 -m scripts.research.bls_cpi_schedule_archive_v0 build     # offline, deterministic from raw/
python3 -m scripts.research.bls_cpi_schedule_archive_v0 validate  # offline
python3 -m pytest -q tests/research/test_bls_cpi_schedule_archive_v0.py
```

`acquire` re-runs the network acquisition into `raw/`; it is not needed to rebuild.
