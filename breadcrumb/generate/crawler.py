"""Page crawler -- extracts interactive elements from web pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, cast

# Tags we consider interactive / extractable
_INTERACTIVE_TAGS = frozenset({"button", "a", "input", "select", "textarea", "form"})

# Allowed characters for CSS identifiers (id, class, name used as ident segments)
_CSS_IDENT_RE = re.compile(r"[^\w-]")


def _sanitize_css_ident(value: str) -> str:
    """Strip characters not safe in a CSS identifier (id, class, name).

    Only word characters (a-z, A-Z, 0-9, _) and hyphens are kept.
    Returns an empty string if nothing survives sanitization.
    """
    return _CSS_IDENT_RE.sub("", value)


def _sanitize_css_string(value: str) -> str:
    """Escape a value for use inside a double-quoted CSS attribute string.

    Escapes backslashes first, then double quotes.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _best_selector(el: dict[str, Any]) -> str:
    """Build the best CSS selector for an element dict."""
    tag: str = el.get("tag", "")
    if el.get("data_testid"):
        safe = _sanitize_css_string(el["data_testid"])
        return f'[data-testid="{safe}"]'
    if el.get("id"):
        safe_id = _sanitize_css_ident(el["id"])
        if safe_id:
            return f"#{safe_id}"
    if el.get("name"):
        safe_name = _sanitize_css_ident(el["name"])
        if safe_name:
            return f'{tag}[name="{safe_name}"]'
    if el.get("class"):
        first_cls = _sanitize_css_ident(el["class"].split()[0])
        if first_cls:
            return f"{tag}.{first_cls}"
    text = el.get("text")
    if text:
        safe = _sanitize_css_string(text)
        return f'{tag}:has-text("{safe}")'
    return tag


class _StaticHTMLExtractor(HTMLParser):
    """stdlib HTMLParser-based extractor for static HTML strings."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict] = []
        self._stack: list[str] = []
        self._current: dict | None = None
        self._text_parts: list[str] = []
        self._hidden = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._stack.append(tag)
        attr_dict = {k: v for k, v in attrs}

        # Check visibility -- skip hidden elements
        style = attr_dict.get("style", "") or ""
        if "display:none" in style.replace(" ", "").lower() or "display: none" in style.lower():
            self._hidden = True
            return

        hidden_attr = attr_dict.get("hidden")
        if hidden_attr is not None:
            self._hidden = True
            return

        # For <a> tags, only capture those with href
        if tag == "a" and "href" not in attr_dict:
            return

        if tag not in _INTERACTIVE_TAGS:
            return

        # If we're already tracking an element (e.g. a <form> container),
        # finalize it before starting to track the new child element.
        if self._current is not None:
            text = " ".join("".join(self._text_parts).split()).strip()
            self._current["text"] = text if text else None
            self._current["selector"] = _best_selector(self._current)
            self.elements.append(self._current)
            self._current = None
            self._text_parts = []

        el: dict = {
            "tag": tag,
            "type": attr_dict.get("type"),
            "id": attr_dict.get("id"),
            "name": attr_dict.get("name"),
            "class": attr_dict.get("class"),
            "text": None,
            "href": attr_dict.get("href"),
            "placeholder": attr_dict.get("placeholder"),
            "aria_label": attr_dict.get("aria-label"),
            "data_testid": attr_dict.get("data-testid"),
            "value": attr_dict.get("value"),
            "role": attr_dict.get("role"),
            "selector": "",
        }
        self._current = el
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._hidden and tag in self._stack:
            self._hidden = False

        if self._stack:
            self._stack.pop()

        if self._current is not None and self._current["tag"] == tag:
            text = " ".join("".join(self._text_parts).split()).strip()
            self._current["text"] = text if text else None
            self._current["selector"] = _best_selector(self._current)
            self.elements.append(self._current)
            self._current = None
            self._text_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle self-closing tags like <input />."""
        tag = tag.lower()
        if tag not in _INTERACTIVE_TAGS:
            return
        attr_dict = {k: v for k, v in attrs}

        style = attr_dict.get("style", "") or ""
        if "display:none" in style.replace(" ", "").lower() or "display: none" in style.lower():
            return

        el: dict = {
            "tag": tag,
            "type": attr_dict.get("type"),
            "id": attr_dict.get("id"),
            "name": attr_dict.get("name"),
            "class": attr_dict.get("class"),
            "text": None,
            "href": attr_dict.get("href"),
            "placeholder": attr_dict.get("placeholder"),
            "aria_label": attr_dict.get("aria-label"),
            "data_testid": attr_dict.get("data-testid"),
            "value": attr_dict.get("value"),
            "role": attr_dict.get("role"),
            "selector": "",
        }
        el["selector"] = _best_selector(el)
        self.elements.append(el)


# JavaScript snippet used by the Playwright crawl() method
_JS_EXTRACT = """
() => {
    const TAGS = ['button', 'a[href]', 'input', 'select', 'textarea', 'form'];
    const selector = TAGS.join(', ');
    const nodes = document.querySelectorAll(selector);
    const results = [];
    for (const el of nodes) {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || el.hidden) continue;

        const tag = el.tagName.toLowerCase();
        const testid = el.getAttribute('data-testid');
        const id = el.id || null;
        const name = el.getAttribute('name') || null;
        const cls = el.className || null;
        const text = (el.textContent || '').trim().substring(0, 200) || null;

        const escAttr = (v) => v.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        const escIdent = (v) => v.replace(/[^\\w-]/g, '');
        let bestSelector = tag;
        if (testid) bestSelector = '[data-testid="' + escAttr(testid) + '"]';
        else if (id) { const sid = escIdent(id); if (sid) bestSelector = '#' + sid; }
        else if (name) bestSelector = tag + '[name="' + escAttr(name) + '"]';
        else if (cls && typeof cls === 'string') {
            const sc = escIdent(cls.split(' ')[0]); if (sc) bestSelector = tag + '.' + sc;
        }
        else if (text) bestSelector = tag + ':has-text("' + escAttr(text.substring(0, 50)) + '")';

        results.push({
            tag,
            type: el.getAttribute('type') || null,
            id,
            name,
            class: typeof cls === 'string' ? cls : null,
            text,
            href: el.getAttribute('href') || null,
            placeholder: el.getAttribute('placeholder') || null,
            aria_label: el.getAttribute('aria-label') || null,
            data_testid: testid || null,
            value: el.value || null,
            role: el.getAttribute('role') || null,
            selector: bestSelector,
        });
    }
    return results;
}
"""


class PageCrawler:
    """Crawls a web page and extracts interactive elements."""

    def __init__(self, timeout_ms: int = 5000) -> None:
        self.timeout_ms = timeout_ms

    def crawl(self, url: str, page: Any | None = None) -> list[dict]:
        """Extract interactive elements from a live page via Playwright.

        If *page* is provided (a Playwright Page object), it will be used
        directly.  Otherwise a new browser context is created (and closed
        after extraction).
        """
        if page is not None:
            page.goto(url, timeout=self.timeout_ms)
            return cast(list[dict[Any, Any]], page.evaluate(_JS_EXTRACT))

        # Lazy import -- Playwright is optional
        from playwright.sync_api import sync_playwright  # pragma: no cover

        with sync_playwright() as pw:  # pragma: no cover
            browser = pw.chromium.launch()
            ctx = browser.new_context()
            p = ctx.new_page()
            p.goto(url, timeout=self.timeout_ms)
            elements = p.evaluate(_JS_EXTRACT)
            browser.close()
            return cast(list[dict[Any, Any]], elements)

    def crawl_static(self, html: str) -> list[dict]:
        """Parse a static HTML string and extract interactive elements.

        Uses Python's stdlib ``html.parser`` -- no Playwright required.
        """
        parser = _StaticHTMLExtractor()
        parser.feed(html)
        return parser.elements
