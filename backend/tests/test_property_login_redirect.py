"""Property-based test for login redirect detection correctness.

Feature: embedded-vtop-login, Property 5: Login redirect detection correctness

Validates: Requirements 3.5
"""

from hypothesis import given, settings, assume
from hypothesis.strategies import text, composite, sampled_from

from app.connectors.vtop.cookie_interceptor import CookieInterceptor

interceptor = CookieInterceptor()


@composite
def url_with_login_path(draw):
    """Generate URLs that contain /vtop/login."""
    prefix = draw(sampled_from(["https://vtopcc.vit.ac.in", "http://example.com"]))
    suffix = draw(text(alphabet="abcdefghijklmnop?=&", max_size=20))
    return f"{prefix}/vtop/login{suffix}"


@composite
def url_without_login_path(draw):
    """Generate URLs that do NOT contain /vtop/login."""
    prefix = draw(sampled_from([
        "https://vtopcc.vit.ac.in/vtop/content",
        "https://vtopcc.vit.ac.in/vtop/academics",
    ]))
    suffix = draw(text(alphabet="abcdefghijklmnop/", max_size=20))
    url = f"{prefix}{suffix}"
    assume("/vtop/login" not in url)
    return url


@settings(max_examples=100)
@given(url=url_with_login_path())
def test_login_page_url_classified_as_failure(url):
    """For any response URL containing /vtop/login, detect_login_success SHALL return False,
    indicating a failed login (user is still on the login page).

    **Validates: Requirements 3.5**
    """
    assert interceptor.detect_login_success(url, "login") is False


@settings(max_examples=100)
@given(url=url_without_login_path())
def test_non_login_url_classified_as_success(url):
    """For any response URL that does NOT contain /vtop/login, detect_login_success SHALL
    return True, indicating a successful login (user was redirected away from login page).

    **Validates: Requirements 3.5**
    """
    assert interceptor.detect_login_success(url, "login") is True
