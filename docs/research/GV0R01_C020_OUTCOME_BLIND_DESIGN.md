# GV0R01-C020 outcome-blind design

Official regional holidays remove the corresponding participant block, which displaces the BTCUSDT perpetual intraday volume profile away from that region's session. The lead contrast is the mean log US-session share displacement on NYSE weekday closures versus matched same-weekday non-holiday days.

Gate: `EXECUTION_INFORMATIONALLY_WEAK`.
Covered NYSE full weekday closures: 47.
US session: 09:30 America/New_York inclusive on the closure's calendar date to 16:00 America/New_York exclusive on the closure's calendar date.
Endpoint: mean over covered NYSE full weekday closures of that log ratio.
Alpha attainable: True. Minimum exact p: 1.6473952425747334e-59.
Execution bar, frozen before power: -0.10536051565782628 LOG_US_SESSION_SHARE_DISPLACEMENT.
Power performed: True.
MDE at 80 percent: {'BASE': -0.10777346075740324, 'STRESS': -0.21981884443629107}.
Null rejection, base: 0.055.
No BTC price or volume value was opened.
