"""Proxy utility functions for the VTOP reverse proxy.

Provides header stripping, URL rewriting, and request header preparation
to enable the VTOP login page to render inside an iframe.
"""

import re

# The VTOP domain that proxy traffic originates from
VTOP_DOMAIN = "vtopcc.vit.ac.in"

# Headers that block iframe embedding (matched case-insensitively)
_BLOCKED_HEADERS = {"x-frame-options", "content-security-policy"}


def strip_frame_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove X-Frame-Options and Content-Security-Policy headers (case-insensitive).

    Preserves all other headers with their original names and values unchanged.

    Args:
        headers: Dictionary of HTTP response headers.

    Returns:
        A new dictionary with frame-blocking headers removed.
    """
    return {
        name: value
        for name, value in headers.items()
        if name.lower() not in _BLOCKED_HEADERS
    }


def rewrite_urls(content: str, proxy_base: str) -> str:
    """Rewrite VTOP domain URLs to route through the proxy.

    Replaces all references to vtopcc.vit.ac.in with the proxy base URL
    in HTML and JavaScript content. Handles:
    - Full URLs with protocol (https://vtopcc.vit.ac.in/vtop/...)
    - Protocol-relative URLs (//vtopcc.vit.ac.in/vtop/...)
    - src, href, action attributes and URLs in inline scripts

    Args:
        content: HTML or JavaScript string content from VTOP.
        proxy_base: The proxy base URL path (e.g., "/api/vtop/proxy").

    Returns:
        Content with all VTOP domain URLs rewritten to proxy URLs.
    """
    # Normalize proxy_base — strip trailing slash
    proxy_base = proxy_base.rstrip("/")

    # Replace full URLs: https://vtopcc.vit.ac.in/vtop/path -> /api/vtop/proxy/path
    # Also handle http:// variant
    content = re.sub(
        r"https?://" + re.escape(VTOP_DOMAIN) + r"/vtop(/[^\s\"'<>)*]*|(?=[\"'<>\s)])|(?=$))",
        lambda m: proxy_base + (m.group(1) if m.group(1) else ""),
        content,
    )

    # Replace protocol-relative URLs: //vtopcc.vit.ac.in/vtop/path -> /api/vtop/proxy/path
    content = re.sub(
        r"//" + re.escape(VTOP_DOMAIN) + r"/vtop(/[^\s\"'<>)*]*|(?=[\"'<>\s)])|(?=$))",
        lambda m: proxy_base + (m.group(1) if m.group(1) else ""),
        content,
    )

    # Replace any remaining domain references without /vtop prefix
    # e.g., https://vtopcc.vit.ac.in/assets/... -> /api/vtop/proxy/assets/...
    # but only full URLs (not already handled above)
    content = re.sub(
        r"https?://" + re.escape(VTOP_DOMAIN) + r"(/[^\s\"'<>)*]*|(?=[\"'<>\s)])|(?=$))",
        lambda m: proxy_base + (m.group(1) if m.group(1) else ""),
        content,
    )

    content = re.sub(
        r"//" + re.escape(VTOP_DOMAIN) + r"(/[^\s\"'<>)*]*|(?=[\"'<>\s)])|(?=$))",
        lambda m: proxy_base + (m.group(1) if m.group(1) else ""),
        content,
    )

    # Replace relative /vtop/... paths in attributes (src, href, action)
    # e.g., /vtop/assets/img/logo.png -> /api/vtop/proxy/assets/img/logo.png
    # Only match paths inside quotes (attribute values) to avoid false positives
    content = re.sub(
        r'((?:src|href|action)\s*=\s*["\'])/vtop/([^\s"\'<>]*)',
        lambda m: m.group(1) + proxy_base + "/" + m.group(2),
        content,
        flags=re.IGNORECASE,
    )

    # Also handle /vtop/ paths in JavaScript string literals
    content = re.sub(
        r"""(['"])/vtop/([^\s"'<>]*)""",
        lambda m: m.group(1) + proxy_base + "/" + m.group(2),
        content,
    )

    return content


def prepare_upstream_headers(request_headers: dict, vtop_host: str) -> dict:
    """Forward request headers, replacing Host with VTOP hostname.

    Preserves cookies, referer, origin, and all custom headers.
    Only the Host header is replaced to maintain a valid browsing context
    with the upstream VTOP server.

    Args:
        request_headers: Dictionary of incoming request headers.
        vtop_host: The VTOP server hostname (e.g., "vtopcc.vit.ac.in").

    Returns:
        A new dictionary with Host set to vtop_host and all other headers preserved.
    """
    # Build a new dict preserving all headers except Host (case-insensitive)
    forwarded = {
        name: value
        for name, value in request_headers.items()
        if name.lower() != "host"
    }

    # Set the Host header to the VTOP hostname
    forwarded["Host"] = vtop_host

    return forwarded
