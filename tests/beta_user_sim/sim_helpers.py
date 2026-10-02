"""Shared fixtures for the synthetic beta user tests (no network, no database)."""
import copy
import functools
import json

from beta.config import BetaConfig
from tools.beta_user_sim.bundle import bundle_from_dict
from tools.beta_user_sim.llm import ROLE_USER, build_models
from tools.beta_user_sim.replay import ReplayConfig, ReplayEngine
from tools.beta_user_sim.synthetic import make_synthetic_bundle

CFG = BetaConfig.load()


@functools.lru_cache(maxsize=None)
def _raw() -> str:
    return json.dumps(make_synthetic_bundle(CFG))


def raw_bundle() -> dict:
    return json.loads(_raw())


def bundle(mutate=None):
    raw = raw_bundle()
    if mutate is not None:
        mutate(raw)
    return bundle_from_dict(raw)


class ScriptedUser:
    """Role A stand-in driven by a function of the turn JSON. Records every prompt."""

    model_id = "scripted-user"

    def __init__(self, decide):
        self._decide = decide
        self.prompts = []

    def settings(self):
        return {"deterministic": True, "network": False}

    def complete(self, messages, *, role):
        assert role == ROLE_USER
        self.prompts.append(copy.deepcopy(list(messages)))
        turn = json.loads(messages[-1]["content"])
        return json.dumps(self._decide(turn))


def models(user=None):
    m = build_models("fake")
    if user is not None:
        m[ROLE_USER] = user
    return m


def engine(user=None, *, raw=None, **rcfg):
    b = bundle_from_dict(raw) if raw is not None else bundle()
    return ReplayEngine(b, CFG, models(user), ReplayConfig(**rcfg))


def run(user=None, **rcfg):
    e = engine(user, **rcfg)
    return e, e.run()
