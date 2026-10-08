"""Test-wide settings. The keyed fingerprint (beta.admin.fingerprint) needs its secret; tests use a fixed one."""
import os

os.environ.setdefault("BETA_FINGERPRINT_KEY", "test-fingerprint-key-0123456789abcdef0123456789")
