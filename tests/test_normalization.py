"""Unit tests for gateway ID normalization and validation."""

import pytest
from nexora.data_loader import normalize_gateway_id, is_valid_gateway_id


def test_normalize_bare_hex():
    assert normalize_gateway_id("0639ea5602c1") == "0639EA5602C1"
    assert normalize_gateway_id("  0639EA5602C1  ") == "0639EA5602C1"
    assert normalize_gateway_id("001a7d000139") == "001A7D000139"


def test_normalize_colon_hex():
    assert normalize_gateway_id("06:39:EA:56:02:C1") == "0639EA5602C1"
    assert normalize_gateway_id("06:39:ea:56:02:c1") == "0639EA5602C1"
    assert normalize_gateway_id(" 00:1A:7D:00:01:39 ") == "001A7D000139"


def test_invalid_gateway_ids():
    invalid_cases = [
        "",
        "short",
        "0639EA5602C1X",  # 13 chars
        "0639EA5602CG",  # invalid hex 'G'
        "06:39:EA:56:02",  # only 5 octets
        "06:39:EA:56:02:C1:AA",  # 7 octets
        "NOT-A-GATEWAY-ID",
    ]
    for case in invalid_cases:
        with pytest.raises(ValueError):
            normalize_gateway_id(case)
        assert not is_valid_gateway_id(case)
