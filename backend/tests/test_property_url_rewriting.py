"""Property-based test for URL rewriting logic.

Feature: embedded-vtop-login, Property 2: URL rewriting transforms all VTOP domain URLs to proxy URLs

Validates: Requirements 1.3
"""

from hypothesis import given, settings, assume
from hypothesis.strategies import text, sampled_from, composite, lists

from app.connectors.vtop.proxy_utils import rewrite_urls

VTOP_DOMAIN = "vtopcc.vit.ac.in"
PROXY_BASE = "/api/vtop/proxy"


@composite
def html_with_vtop_urls(draw):
    """Generate HTML content that includes VTOP domain URLs."""
    paths = draw(
        lists(
            text(alphabet="abcdefghijklmnop/", min_size=1, max_size=20),
            min_size=1,
            max_size=5,
        )
    )
    prefix = draw(sampled_from(["https://", "http://", "//"]))
    html_parts = []
    for path in paths:
        url = f'{prefix}{VTOP_DOMAIN}/vtop/{path}'
        html_parts.append(f'<a href="{url}">link</a>')
    return "\n".join(html_parts)


@settings(max_examples=100)
@given(content=html_with_vtop_urls())
def test_rewrite_urls_removes_all_vtop_domain_references(content):
    """For any HTML/JS string containing URLs with the VTOP domain,
    applying rewrite_urls() SHALL replace all VTOP domain references
    with the proxy base URL.

    **Validates: Requirements 1.3**
    """
    result = rewrite_urls(content, PROXY_BASE)
    assert VTOP_DOMAIN not in result, (
        f"VTOP domain '{VTOP_DOMAIN}' still present in rewritten content:\n{result}"
    )


@settings(max_examples=100)
@given(content=text(min_size=1, max_size=200))
def test_rewrite_urls_leaves_non_vtop_unchanged(content):
    """For any string that does NOT contain the VTOP domain,
    applying rewrite_urls() SHALL return the content unchanged.

    **Validates: Requirements 1.3**
    """
    assume(VTOP_DOMAIN not in content)
    result = rewrite_urls(content, PROXY_BASE)
    assert result == content, (
        f"Non-VTOP content was modified:\nInput:  {content!r}\nOutput: {result!r}"
    )
