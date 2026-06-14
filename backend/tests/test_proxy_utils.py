"""Unit tests for proxy_utils module."""

import pytest

from app.connectors.vtop.proxy_utils import (
    prepare_upstream_headers,
    rewrite_urls,
    strip_frame_headers,
)


class TestStripFrameHeaders:
    """Tests for strip_frame_headers()."""

    def test_removes_x_frame_options(self):
        headers = {"X-Frame-Options": "DENY", "Content-Type": "text/html"}
        result = strip_frame_headers(headers)
        assert "X-Frame-Options" not in result
        assert result["Content-Type"] == "text/html"

    def test_removes_content_security_policy(self):
        headers = {"Content-Security-Policy": "frame-ancestors 'none'", "Server": "nginx"}
        result = strip_frame_headers(headers)
        assert "Content-Security-Policy" not in result
        assert result["Server"] == "nginx"

    def test_case_insensitive_removal(self):
        headers = {
            "x-frame-options": "SAMEORIGIN",
            "CONTENT-SECURITY-POLICY": "default-src 'self'",
            "content-type": "text/html",
        }
        result = strip_frame_headers(headers)
        assert len(result) == 1
        assert result["content-type"] == "text/html"

    def test_preserves_all_non_target_headers(self):
        headers = {
            "Content-Type": "text/html",
            "Cache-Control": "no-cache",
            "Set-Cookie": "session=abc",
            "X-Custom-Header": "value",
        }
        result = strip_frame_headers(headers)
        assert result == headers

    def test_empty_headers(self):
        assert strip_frame_headers({}) == {}

    def test_removes_both_target_headers_together(self):
        headers = {
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "frame-ancestors 'none'",
            "Content-Type": "text/html",
        }
        result = strip_frame_headers(headers)
        assert len(result) == 1
        assert result["Content-Type"] == "text/html"


class TestRewriteUrls:
    """Tests for rewrite_urls()."""

    def test_rewrites_full_https_url(self):
        content = '<script src="https://vtopcc.vit.ac.in/vtop/assets/main.js"></script>'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<script src="/api/vtop/proxy/assets/main.js"></script>'

    def test_rewrites_href_attribute(self):
        content = '<a href="https://vtopcc.vit.ac.in/vtop/login">Login</a>'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<a href="/api/vtop/proxy/login">Login</a>'

    def test_rewrites_action_attribute(self):
        content = '<form action="https://vtopcc.vit.ac.in/vtop/doLogin">'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<form action="/api/vtop/proxy/doLogin">'

    def test_rewrites_protocol_relative_url(self):
        content = '<img src="//vtopcc.vit.ac.in/vtop/images/logo.png">'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<img src="/api/vtop/proxy/images/logo.png">'

    def test_rewrites_inline_script_url(self):
        content = "var url = 'https://vtopcc.vit.ac.in/vtop/ajax/getData';"
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == "var url = '/api/vtop/proxy/ajax/getData';"

    def test_leaves_non_vtop_urls_unchanged(self):
        content = '<a href="https://google.com/search">Google</a>'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<a href="https://google.com/search">Google</a>'

    def test_handles_multiple_urls(self):
        content = (
            '<link href="https://vtopcc.vit.ac.in/vtop/css/style.css">\n'
            '<script src="https://vtopcc.vit.ac.in/vtop/js/app.js"></script>'
        )
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert "/api/vtop/proxy/css/style.css" in result
        assert "/api/vtop/proxy/js/app.js" in result
        assert "vtopcc.vit.ac.in" not in result

    def test_strips_trailing_slash_from_proxy_base(self):
        content = '<a href="https://vtopcc.vit.ac.in/vtop/login">Login</a>'
        result = rewrite_urls(content, "/api/vtop/proxy/")
        assert result == '<a href="/api/vtop/proxy/login">Login</a>'

    def test_rewrites_domain_without_vtop_prefix(self):
        content = '<img src="https://vtopcc.vit.ac.in/static/img.png">'
        result = rewrite_urls(content, "/api/vtop/proxy")
        assert result == '<img src="/api/vtop/proxy/static/img.png">'

    def test_empty_content(self):
        assert rewrite_urls("", "/api/vtop/proxy") == ""


class TestPrepareUpstreamHeaders:
    """Tests for prepare_upstream_headers()."""

    def test_replaces_host_header(self):
        headers = {"Host": "localhost:8000", "Cookie": "session=abc"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Host"] == "vtopcc.vit.ac.in"
        assert result["Cookie"] == "session=abc"

    def test_case_insensitive_host_replacement(self):
        headers = {"host": "localhost:8000", "Content-Type": "application/json"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Host"] == "vtopcc.vit.ac.in"
        assert "host" not in result
        assert result["Content-Type"] == "application/json"

    def test_preserves_cookies(self):
        headers = {"Host": "localhost", "Cookie": "JSESSIONID=abc123; other=val"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Cookie"] == "JSESSIONID=abc123; other=val"

    def test_preserves_referer(self):
        headers = {"Host": "localhost", "Referer": "http://localhost/page"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Referer"] == "http://localhost/page"

    def test_preserves_origin(self):
        headers = {"Host": "localhost", "Origin": "http://localhost"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Origin"] == "http://localhost"

    def test_preserves_custom_headers(self):
        headers = {"Host": "localhost", "X-Custom": "value", "Authorization": "Bearer token"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["X-Custom"] == "value"
        assert result["Authorization"] == "Bearer token"

    def test_adds_host_when_not_present(self):
        headers = {"Cookie": "session=abc", "Accept": "text/html"}
        result = prepare_upstream_headers(headers, "vtopcc.vit.ac.in")
        assert result["Host"] == "vtopcc.vit.ac.in"
        assert result["Cookie"] == "session=abc"
        assert result["Accept"] == "text/html"

    def test_empty_headers(self):
        result = prepare_upstream_headers({}, "vtopcc.vit.ac.in")
        assert result == {"Host": "vtopcc.vit.ac.in"}
