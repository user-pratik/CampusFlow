"""Property-based test for header stripping logic.

Feature: embedded-vtop-login, Property 1: Response header stripping preserves non-target headers

Validates: Requirements 1.1
"""

from hypothesis import given, settings
from hypothesis.strategies import dictionaries, text

from app.connectors.vtop.proxy_utils import strip_frame_headers


@settings(max_examples=100)
@given(headers=dictionaries(text(min_size=1, max_size=50), text(max_size=200)))
def test_strip_frame_headers_preserves_non_target(headers):
    """For any set of HTTP response headers, strip_frame_headers SHALL:
    1. Remove all headers named X-Frame-Options or Content-Security-Policy (case-insensitive)
    2. Preserve every other header name and value unchanged

    **Validates: Requirements 1.1**
    """
    result = strip_frame_headers(headers)

    # 1. No X-Frame-Options or Content-Security-Policy in result (case-insensitive)
    for key in result:
        assert key.lower() not in ("x-frame-options", "content-security-policy"), (
            f"Blocked header '{key}' was not stripped from result"
        )

    # 2. All non-target headers preserved unchanged
    for key, value in headers.items():
        if key.lower() not in ("x-frame-options", "content-security-policy"):
            assert key in result, f"Non-target header '{key}' was removed"
            assert result[key] == value, (
                f"Header '{key}' value changed: expected '{value}', got '{result[key]}'"
            )

    # 3. No extra headers introduced
    for key in result:
        assert key in headers, f"Unexpected header '{key}' appeared in result"
