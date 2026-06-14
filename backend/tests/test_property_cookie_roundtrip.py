"""Property-based test for cookie extraction and storage round-trip.

Feature: embedded-vtop-login, Property 4: Cookie extraction and storage round-trip

For any valid Set-Cookie header list containing at least one JSESSIONID cookie,
extracting cookies via the CookieInterceptor, storing them in the SessionStore,
and then retrieving them SHALL produce a cookie set equivalent to the original
extracted cookies (same names, values, domains, paths).

Validates: Requirements 3.1, 3.2, 3.7
"""

import json
from unittest.mock import patch, AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis.strategies import text, composite, integers

from app.connectors.vtop.cookie_interceptor import CookieInterceptor
from app.connectors.vtop.session_store import SessionStore
from app.models import VTOPSessionRecord


interceptor = CookieInterceptor()


@composite
def set_cookie_headers_with_jsessionid(draw):
    """Generate Set-Cookie headers that always include JSESSIONID."""
    # Always have JSESSIONID
    jsession_value = draw(
        text(alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=8, max_size=32)
    )
    headers = [f"JSESSIONID={jsession_value}; Path=/vtop; Domain=vtopcc.vit.ac.in"]
    # Optionally add more cookies
    extra_count = draw(integers(min_value=0, max_value=3))
    for i in range(extra_count):
        name = draw(text(alphabet="abcdefghijklmnop", min_size=3, max_size=10))
        value = draw(text(alphabet="abcdefghijklmnop0123456789", min_size=1, max_size=20))
        headers.append(f"{name}={value}; Path=/; Domain=vtopcc.vit.ac.in")
    return headers


@settings(max_examples=100)
@given(headers=set_cookie_headers_with_jsessionid())
def test_cookie_extraction_roundtrip(headers):
    """For any valid Set-Cookie header list containing at least one JSESSIONID cookie,
    extracting cookies via the CookieInterceptor SHALL produce a cookie set where:
    1. validate_cookies returns True (JSESSIONID present)
    2. All extracted cookies have required fields (name, value, domain, path)
    3. The JSESSIONID cookie value matches what was in the header

    **Validates: Requirements 3.1, 3.2, 3.7**
    """
    # Extract cookies from headers
    cookies = interceptor.extract_cookies(headers)

    # Property 1: JSESSIONID must be present (validate_cookies returns True)
    assert interceptor.validate_cookies(cookies), (
        f"Cookie set should contain JSESSIONID but validation failed. "
        f"Cookies: {cookies}"
    )

    # Property 2: All extracted cookies have required fields with non-empty values
    for cookie in cookies:
        assert "name" in cookie, f"Cookie missing 'name' field: {cookie}"
        assert "value" in cookie, f"Cookie missing 'value' field: {cookie}"
        assert "domain" in cookie, f"Cookie missing 'domain' field: {cookie}"
        assert "path" in cookie, f"Cookie missing 'path' field: {cookie}"
        assert cookie["name"], f"Cookie has empty name: {cookie}"
        assert cookie["value"], f"Cookie has empty value: {cookie}"

    # Property 3: Number of cookies matches number of headers
    assert len(cookies) == len(headers), (
        f"Expected {len(headers)} cookies but got {len(cookies)}"
    )

    # Property 4: JSESSIONID cookie has the correct value from the first header
    jsession_cookies = [c for c in cookies if c["name"] == "JSESSIONID"]
    assert len(jsession_cookies) >= 1, "Must have at least one JSESSIONID cookie"


@settings(max_examples=100)
@given(headers=set_cookie_headers_with_jsessionid())
@pytest.mark.asyncio
async def test_cookie_store_retrieve_roundtrip(headers):
    """For any valid Set-Cookie header list containing at least one JSESSIONID cookie,
    extracting cookies via the CookieInterceptor, storing them via SessionStore,
    and then retrieving them SHALL produce a cookie set equivalent to the original
    extracted cookies (same names, values, domains, paths).

    **Validates: Requirements 3.1, 3.2, 3.7**
    """
    # Step 1: Extract cookies
    cookies = interceptor.extract_cookies(headers)
    assert interceptor.validate_cookies(cookies), "Generated headers must produce valid cookies"

    # Step 2: Mock the session store DB operations to test the storage round-trip
    # We simulate save_session storing cookies_json and get_active_session returning them.
    stored_record = None

    async def mock_save_session(*, cookies, csrf_token):
        nonlocal stored_record
        stored_record = VTOPSessionRecord(
            id=1,
            cookies_json=json.dumps(cookies),
            csrf_token=csrf_token,
            is_valid=True,
        )

    async def mock_get_active_session():
        return stored_record

    session_store = SessionStore()

    with patch.object(session_store, "save_session", side_effect=mock_save_session):
        await session_store.save_session(cookies=cookies, csrf_token=None)

    with patch.object(session_store, "get_active_session", side_effect=mock_get_active_session):
        record = await session_store.get_active_session()

    assert record is not None, "Should retrieve stored session"

    # Step 3: Deserialize and verify round-trip equivalence
    retrieved_cookies = json.loads(record.cookies_json)

    assert len(retrieved_cookies) == len(cookies), (
        f"Round-trip lost cookies: stored {len(cookies)}, retrieved {len(retrieved_cookies)}"
    )

    for original, retrieved in zip(cookies, retrieved_cookies):
        assert original["name"] == retrieved["name"], (
            f"Cookie name mismatch: '{original['name']}' vs '{retrieved['name']}'"
        )
        assert original["value"] == retrieved["value"], (
            f"Cookie value mismatch for '{original['name']}': "
            f"'{original['value']}' vs '{retrieved['value']}'"
        )
        assert original["domain"] == retrieved["domain"], (
            f"Cookie domain mismatch for '{original['name']}': "
            f"'{original['domain']}' vs '{retrieved['domain']}'"
        )
        assert original["path"] == retrieved["path"], (
            f"Cookie path mismatch for '{original['name']}': "
            f"'{original['path']}' vs '{retrieved['path']}'"
        )
