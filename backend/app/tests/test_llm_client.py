import pytest
from unittest.mock import MagicMock, patch
from app.agents import llm_client
from app.agents.llm_client import (
    complete,
    complete_vision,
    LLMUnavailableError,
    LLMMalformedResponseError,
    _execute_with_retry,
    _execute_groq_call,
    _key_pool,
    GroqKeyPool
)


def test_complete_text_mode():
    res = complete("Provide business_overview for Kirana shop", response_format="text")
    assert isinstance(res, str)
    assert len(res) > 0


def test_complete_json_mode():
    res = complete("Extract field monthly_turnover 250000", response_format="json")
    assert isinstance(res, dict)
    assert "extracted_fields" in res


def test_complete_vision():
    dummy_bytes = b"fake_jpeg_image_bytes_here"
    res = complete_vision("Inspect machinery", dummy_bytes)
    assert isinstance(res, dict)
    assert "asset_name" in res
    assert "dHash" in res


def test_retry_on_rate_limit_and_raise_llm_unavailable():
    mock_fn = MagicMock(side_effect=Exception("429 Too Many Requests rate limit exceeded"))
    with pytest.raises(LLMUnavailableError):
        _execute_with_retry(mock_fn, max_attempts=2)
    assert mock_fn.call_count == 2


def test_key_pool_round_robin_cycling():
    pool = GroqKeyPool()
    pool._keys = [
        "gsk_test_key_1111111111111111111111111",
        "gsk_test_key_2222222222222222222222222",
        "gsk_test_key_3333333333333333333333333"
    ]
    pool._clients = {k: MagicMock() for k in pool._keys}
    pool._index = 0

    _, k1 = pool.get_client_and_key()
    _, k2 = pool.get_client_and_key()
    _, k3 = pool.get_client_and_key()
    _, k4 = pool.get_client_and_key()

    assert k1 == pool._keys[0]
    assert k2 == pool._keys[1]
    assert k3 == pool._keys[2]
    assert k4 == pool._keys[0]


def test_groq_call_failover_on_429():
    with patch.object(_key_pool, "_keys", ["gsk_key_A1111111111111111111111111", "gsk_key_B2222222222222222222222222"]):
        mock_client_A = MagicMock()
        mock_client_B = MagicMock()
        _key_pool._clients = {
            "gsk_key_A1111111111111111111111111": mock_client_A,
            "gsk_key_B2222222222222222222222222": mock_client_B,
        }
        _key_pool._index = 0

        def fake_call(client):
            if client == mock_client_A:
                raise Exception("429 Too Many Requests: rate_limit_exceeded")
            return "success_from_client_b"

        result = _execute_groq_call(fake_call)
        assert result == "success_from_client_b"
