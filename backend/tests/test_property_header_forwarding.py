"""Property-based test for request header forwarding logic.

Feature: embedded-vtop-login, Property 3: Request header forwarding preserves all headers except Host

Validates: Requirements 1.4
"""

from hypothesis import given, settings
from hypothesis.strategies import dictionaries, text

from app.connectors.vtop.proxy_utils import prepare_upstream_headers

VTOP_HOST = "vtopcc.vit.ac.in"


@settings(max_examples=100)
@given(headers=dictionaries(text(min_size=1, max_size=30), text(max_size=100)))
def test_prepare_upstream_headers_sets_host(headers):
    """For any set of incoming request headers, prepare_upstream_headers SHALL
    set the Host header to the VTOP server hostname.

    **Validates: Requirements 1.4**
    """
    result = prepare_upstream_headers(headers, VTOP_HOST)
    assert result["Host"] == VTOP_HOST, (
        f"Host header should be '{VTOP_HOST}', got '{result.get('Host')}'"
    )


@settings(max_examples=100)
@given(headers=dictionaries(text(min_size=1, max_size=30), text(max_size=100)))
def test_prepare_upstream_headers_preserves_non_host(headers):
    """For any set of incoming request headers, prepare_upstream_headers SHALL
    preserve all other headers (cookies, referer, origin, custom headers)
    with original names and values.

    **Validates: Requirements 1.4**
    """
    result = prepare_upstream_headers(headers, VTOP_HOST)

    # All non-Host headers preserved unchanged
    for key, value in headers.items():
        if key.lower() != "host":
            assert key in result, f"Non-host header '{key}' was removed"
            assert result[key] == value, (
                f"Header '{key}' value changed: expected '{value}', got '{result[key]}'"
            )


@settings(max_examples=100)
@given(headers=dictionaries(text(min_size=1, max_size=30), text(max_size=100)))
def test_prepare_upstream_headers_no_extra_headers(headers):
    """For any set of incoming request headers, prepare_upstream_headers SHALL NOT
    introduce any headers beyond Host that were not in the original set.

    **Validates: Requirements 1.4**
    """
    result = prepare_upstream_headers(headers, VTOP_HOST)

    # No extra headers beyond Host and the original set
    for key in result:
        if key == "Host":
            continue
        assert key in headers, f"Unexpected header '{key}' appeared in result"
