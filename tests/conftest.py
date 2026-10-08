"""Test-wide setup. Participant pseudonyms need a key (beta.pseudonym; owner decision 2026-10-08): every
test runs with a fixed fixture key, never a production one. Tests of the no-key path clear it themselves."""
import pytest

TEST_FINGERPRINT_KEY = bytes(range(32))


@pytest.fixture(autouse=True)
def _beta_fingerprint_key():
    from beta.pseudonym import install_key
    install_key(TEST_FINGERPRINT_KEY)
    yield
