# CORE_BTC_BINANCE_V0 quality report (generated)

snapshot_id: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
source objects planned: 104
source objects verified: 104
checksum failures: 0
first observed: 1577836800000
last observed: 1787702340000
expected 1m minutes: 3497760
observed unique: 3497760
missing minutes: 0
duplicate extra rows: 0
conflicting duplicates: 0
rejected schema rows: 0
rejected invariant rows: 0
HTF incomplete buckets: {"15m": 0, "1h": 0, "4h": 0, "5m": 0}
raw bytes: 149695931
canonical bytes: 275417429
extracted CSV leftovers: []

Price/volume columns are NUMERIC DECIMAL VALUES STORED AS CANONICAL DECIMAL STRINGS. Research code MUST parse/cast them numerically before comparison, sorting, arithmetic, or aggregation. Never compare them lexicographically. Normalization is format(Decimal(value), 'f'). Decimal('1.0') and Decimal('1.00') are distinct canonical text.

SNAPSHOT_CANDIDATE_READY is not ACCEPTED_FOR_DISCOVERY.
The repository planning manifest remains unpromoted.

