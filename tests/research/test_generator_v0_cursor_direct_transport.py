"""Transport-only coverage for explicit DIRECT mode on the V03 ladder campaign.

No provider call is made in this module.
"""
import pytest

from scripts.research.generator_v0.__main__ import main
from scripts.research.generator_v0.context import ContractError, Contexts
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.cloud_openai_transport import CloudProxyOpenAITransport
from scripts.research.generator_v0 import routing


def _capture_mode(monkeypatch):
    seen = {}

    def stop_before_provider_calls(contexts, cap, environ, openai_network_mode='DIRECT', routes=None):
        seen['mode'] = openai_network_mode
        seen['routes'] = routes
        raise ContractError('transport-test-stop')

    monkeypatch.setattr(
        'scripts.research.generator_v0.routed_provider.live_routed_provider',
        stop_before_provider_calls,
    )
    return seen


def test_ladder_explicit_direct_is_respected(monkeypatch, tmp_path):
    seen = _capture_mode(monkeypatch)
    with pytest.raises(ContractError, match='transport-test-stop'):
        main([
            'ladder-40-card',
            '--allow-real-llm',
            '--budget-usd', '1',
            '--openai-network-mode', 'DIRECT',
            '--run-dir', str(tmp_path / 'direct'),
        ])
    assert seen['mode'] == 'DIRECT'
    assert seen['routes'] is routing.LADDER_ROUTES      # V03: the batch GENERATOR route


def test_ladder_without_flag_keeps_cloud_proxy_default(monkeypatch, tmp_path):
    seen = _capture_mode(monkeypatch)
    with pytest.raises(ContractError, match='transport-test-stop'):
        main([
            'ladder-40-card',
            '--allow-real-llm',
            '--budget-usd', '1',
            '--run-dir', str(tmp_path / 'cloud-default'),
        ])
    assert seen['mode'] == 'CLOUD_PROXY'


def test_first_30_still_forces_cloud_proxy(monkeypatch, tmp_path):
    seen = _capture_mode(monkeypatch)
    with pytest.raises(ContractError, match='transport-test-stop'):
        main([
            'first-30-card',
            '--allow-real-llm',
            '--budget-usd', '1',
            '--openai-network-mode', 'DIRECT',
            '--run-dir', str(tmp_path / 'first30'),
        ])
    assert seen['mode'] == 'CLOUD_PROXY'
    assert seen['routes'] is routing.ROUTES             # V02 keeps the synchronous route


def test_transport_identity_records_direct_and_cloud_modes():
    c = Contexts()
    direct = OpenAIProvider(
        'test-key',
        allow_real=True,
        budget_micro_usd=1_000_000,
        contexts=c,
        routes=routing.ROUTES,
        network_mode='DIRECT',
        transport=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('network forbidden')),
    )
    cloud = OpenAIProvider(
        None,
        allow_real=True,
        budget_micro_usd=1_000_000,
        contexts=c,
        routes=routing.ROUTES,
        network_mode='CLOUD_PROXY',
        transport=CloudProxyOpenAITransport(),
    )
    di = direct.transport_identity()
    ci = cloud.transport_identity()
    assert di['OPENAI_NETWORK_MODE'] == 'DIRECT'
    assert di['OPENAI_API_KEY_REQUIRED'] is True
    assert di['DIRECT_API_HOST'] is True
    assert ci['OPENAI_NETWORK_MODE'] == 'CLOUD_PROXY'
    assert ci['OPENAI_API_KEY_REQUIRED'] is False
    assert ci['DIRECT_API_HOST'] is False
    assert direct.routing_digest != cloud.routing_digest
