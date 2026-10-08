# LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. This note does not change the product.

## Provenance

Design SHA `59361e92bf2e2e49507ae59e4d34b41801ff6739`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

## Partition

Selected K = 3. Training rows 1688.
Routing `NO_INCREMENTAL_JOINT_STATE_STRUCTURE`. SUCCESSOR_CANDIDATE = `NONE`.
PRODUCT_INTEGRATION_CANDIDATE = False.

## Centroids

- STATE_1: (-2.2407, -1.4104, +0.5276, -0.2530, +2.1374). above-average OI contraction; OI change decelerating; aggressive flow toward the level; near-average flow shift; above-average price progress toward the level
- STATE_2: (-0.0362, -0.0768, -0.1266, +0.1510, -0.2318). near-average OI change; near-average OI acceleration; near-average aggressive flow; near-average flow shift; near-average price progress
- STATE_3: (+1.8216, +1.4016, +0.2815, -0.3184, +1.4715). above-average OI expansion; OI change accelerating; near-average aggressive flow; near-average flow shift; above-average price progress toward the level

## RESOLVE_4H

- STATE_1 → RESOLVE_4H: +3.32 pp (95% -1.18 pp .. +7.53 pp), p=0.11808217575286639, q=0.3542465272585992, N=1679, n_state=186, clusters=227, bootstrap_valid=2000
- STATE_2 → RESOLVE_4H: -0.90 pp (95% -4.27 pp .. +2.71 pp), p=0.6187533461445851, q=0.6187533461445851, N=1679, n_state=1174, clusters=227, bootstrap_valid=2000
- STATE_3 → RESOLVE_4H: -1.15 pp (95% -4.99 pp .. +2.50 pp), p=0.5454992872160949, q=0.6187533461445851, N=1679, n_state=319, clusters=227, bootstrap_valid=2000

## BREAK_GIVEN_RESOLVED

- STATE_1 → BREAK_GIVEN_RESOLVED: -2.72 pp (95% -11.91 pp .. +5.71 pp), p=0.5533341084194663, q=0.6187533461445851, N=1513, n_state=175, clusters=227, bootstrap_valid=2000
- STATE_2 → BREAK_GIVEN_RESOLVED: -3.13 pp (95% -9.43 pp .. +3.20 pp), p=0.3299955142962456, q=0.6187533461445851, N=1513, n_state=1046, clusters=227, bootstrap_valid=2000
- STATE_3 → BREAK_GIVEN_RESOLVED: +5.37 pp (95% -1.08 pp .. +11.93 pp), p=0.11035651177161351, q=0.3542465272585992, N=1513, n_state=292, clusters=227, bootstrap_valid=2000

## Three-way map

- STATE_1: N=186, BREAK=0.4032258064516129, REJECT=0.5376344086021505, NEITHER=0.05913978494623656, RESOLVE=0.9408602150537635, BREAK|RESOLVED=0.42857142857142855
- STATE_2: N=1174, BREAK=0.38841567291311757, REJECT=0.5025553662691652, NEITHER=0.10902896081771721, RESOLVE=0.8909710391822828, BREAK|RESOLVED=0.4359464627151052
- STATE_3: N=319, BREAK=0.4702194357366771, REJECT=0.445141065830721, NEITHER=0.08463949843260188, RESOLVE=0.9153605015673981, BREAK|RESOLVED=0.5136986301369864

## Specificity

- STATE_1 → RESOLVE_4H: delta -2.95 pp (95% -8.91 pp .. +2.71 pp), beta_real +1.61 pp, beta_pseudo +4.55 pp, N=2118
- STATE_1 → BREAK_GIVEN_RESOLVED: delta -17.60 pp (95% -31.94 pp .. -2.97 pp), beta_real -1.88 pp, beta_pseudo +15.72 pp, N=1622
- STATE_2 → RESOLVE_4H: delta +6.99 pp (95% +2.08 pp .. +12.11 pp), beta_real +1.66 pp, beta_pseudo -5.33 pp, N=2118
- STATE_2 → BREAK_GIVEN_RESOLVED: delta +3.99 pp (95% -5.94 pp .. +13.62 pp), beta_real -3.36 pp, beta_pseudo -7.35 pp, N=1622
- STATE_3 → RESOLVE_4H: delta -7.24 pp (95% -12.96 pp .. -1.49 pp), beta_real -3.65 pp, beta_pseudo +3.59 pp, N=2118
- STATE_3 → BREAK_GIVEN_RESOLVED: delta +7.88 pp (95% -3.91 pp .. +20.12 pp), beta_real +4.29 pp, beta_pseudo -3.58 pp, N=1622

## Decisions

- STATE_1 → RESOLVE_4H: NONE, conjunction False, failed ['fdr', 'interval']
- STATE_1 → BREAK_GIVEN_RESOLVED: NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs']
- STATE_2 → RESOLVE_4H: NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo']
- STATE_2 → BREAK_GIVEN_RESOLVED: NONE, conjunction False, failed ['fdr', 'interval', 'epochs']
- STATE_3 → RESOLVE_4H: NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo']
- STATE_3 → BREAK_GIVEN_RESOLVED: NONE, conjunction False, failed ['fdr', 'interval', 'epochs']

## Claim

Claim ceiling L2. A selected state is a historical association in this cohort, not a current probability.
Centroid words describe robust-z coordinates. They are not a participant identity and not a cause.

## Reporting note

The three-way `n_ambiguous` field is 0 because ambiguous rows were removed before the counter. The RESOLVE estimation sample has 1679 rows against 1688 predictor-complete training rows, so 9 rows are outside that sample. The BREAK / REJECT / NEITHER rates use the labeled rows only. Coefficients were not recomputed. `bootstrap_valid` is the finite-draw count of the coefficient that the cell reports, and it is 2000 on every primary and specificity cell.
