"""Participant pseudonyms (owner decision 2026-10-08): `u_` + HMAC-SHA-256(key, str(telegram_user_id))[:12], the key
from BETA_FINGERPRINT_KEY. Deterministic with a key, different with another key, refused without one; the
key never appears in an error, a log line or a report."""
import base64
import hashlib
import hmac
import logging
import re
from pathlib import Path

import pytest

import main
from beta import pseudonym as ps
from beta.admin import classify_fingerprint, fingerprint
from beta_fakes import run
from runtime.beta_cli import run_beta_cli_command

REPO = Path(__file__).resolve().parents[2]
KEY_A, KEY_B = bytes(range(32)), bytes(range(1, 33))


def test_deterministic_with_the_key_and_different_with_another():
    ps.install_key(KEY_A)
    a = fingerprint(900000000123)
    assert a == fingerprint(900000000123) and re.fullmatch(r"u_[0-9a-f]{12}", a)
    assert a == "u_" + hmac.new(KEY_A, b"900000000123", hashlib.sha256).hexdigest()[:12]
    assert a != fingerprint(900000000124)
    assert a != "u_" + hashlib.sha256(b"signalbot-beta-v0:900000000123").hexdigest()[:12]   # the old unkeyed form
    ps.install_key(KEY_B)
    assert fingerprint(900000000123) != a
    assert fingerprint(None) == "none"


def test_admin_reply_matching_uses_the_same_keyed_function():
    ps.install_key(KEY_A)
    rows = [{"telegram_user_id": 900000000123}, {"telegram_user_id": 900000000124}]
    assert classify_fingerprint(rows, fingerprint(900000000123)) == ("OK", [rows[0]])
    ps.install_key(KEY_B)                                   # a fingerprint printed under the old key no longer matches
    assert classify_fingerprint(rows, "u_" + hmac.new(KEY_A, b"900000000123", hashlib.sha256).hexdigest()[:12])[0] \
        == "UNKNOWN"


@pytest.mark.parametrize("raw", [KEY_A.hex(), KEY_A.hex().upper(), base64.b64encode(KEY_A).decode(),
                                 bytes(range(48)).hex()])
def test_hex_or_base64_of_at_least_32_bytes_is_accepted(raw):
    assert ps.parse_key(raw) in (KEY_A, bytes(range(48)))


@pytest.mark.parametrize("raw", ["", "   ", None, bytes(range(31)).hex(), base64.b64encode(bytes(31)).decode(),
                                 "not a key at all !!", "abc"])
def test_a_missing_or_short_key_is_refused_without_echoing_it(raw):
    with pytest.raises(ps.FingerprintKeyError) as e:
        ps.parse_key(raw)
    assert "BETA_FINGERPRINT_KEY" in str(e.value)
    if raw and raw.strip():
        assert raw.strip() not in str(e.value)


def test_no_key_no_fingerprint():
    ps.clear_key()
    with pytest.raises(ps.FingerprintKeyError):
        fingerprint(900000000123)


def test_the_cli_refuses_to_start_without_a_key(capsys):
    ps.clear_key()

    class NoDb:                                             # nothing may be touched before the key check
        def __getattr__(self, name):
            raise AssertionError(f"DB touched: {name}")
    for flag in ("--beta-notify-once", "--beta-once", "--beta-health"):
        with pytest.raises(SystemExit) as e:
            run(run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=NoDb(), env={}))
        assert e.value.code == 2
        out = capsys.readouterr().out
        assert "CONFIG_ERROR" in out and "BETA_FINGERPRINT_KEY is not set" in out
    bad = "ab" * 10                                         # 10 bytes: refused, and never echoed
    with pytest.raises(SystemExit):
        run(run_beta_cli_command(main.parse_args(["--beta-notify-once", "--beta-json"]), db=NoDb(),
                                 env={"BETA_FINGERPRINT_KEY": bad}))
    assert bad not in capsys.readouterr().out


def test_the_bot_refuses_to_start_without_a_key(monkeypatch):
    ps.clear_key()
    import runtime.beta_bot as bot
    from beta.config import BetaSecrets
    monkeypatch.setenv("BETA_ENABLED", "1")
    monkeypatch.setenv("BETA_TELEGRAM_ENABLED", "1")
    monkeypatch.setenv("BETA_TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.delenv("BETA_FINGERPRINT_KEY", raising=False)
    monkeypatch.setattr(bot, "setup_logging", lambda *_a, **_k: None)
    monkeypatch.setattr(BetaSecrets, "from_env", classmethod(lambda cls, env=None: cls(bot_token="123:abc",
                                                                                        owner_user_id=None)))
    monkeypatch.setattr(bot.asyncio, "run", lambda *_a, **_k: pytest.fail("the bot started without a key"))
    with pytest.raises(SystemExit) as e:
        bot.main()
    assert "BETA_FINGERPRINT_KEY" in str(e.value.code)


def test_the_key_is_never_logged_and_read_in_one_place(caplog):
    caplog.set_level(logging.DEBUG)
    ps.install_key_from_env({"BETA_FINGERPRINT_KEY": KEY_B.hex()})
    fingerprint(900000000123)
    assert KEY_B.hex() not in caplog.text
    reads = re.compile(r"KEY_ENV|pseudonym\._KEY|import _KEY|get\(\s*[\"']BETA_FINGERPRINT_KEY|\[[\"']BETA_FINGERPRINT_KEY")
    readers = [p.relative_to(REPO).as_posix() for p in list((REPO / "beta").glob("*.py")) +
               list((REPO / "runtime").glob("*.py")) + list((REPO / "tools").rglob("*.py"))
               + [REPO / "main.py"] if reads.search(p.read_text())]
    assert readers == ["beta/pseudonym.py"]                 # nothing else reads the env var or the held key
    assert not [n for n in dir(ps) if n.lower() in ("get_key", "key", "current_key")]
