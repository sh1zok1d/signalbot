"""Operational runtime boundary for deliberate, bounded manual commands.

This package hosts the operational shadow CLI (one-shot / dry-run / status). It
is the layer allowed to read the wall clock, load configs, resolve the code
version, open network sessions, and perform Database I/O — the pure analytics
packages never do any of that. It adds no continuous loop, scheduler, timer,
recovery, or discovery logic.
"""
