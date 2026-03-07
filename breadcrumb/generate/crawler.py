"""Page crawler -- extracts interactive elements from web pages."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

# Tags we consider interactive / extractable
_INTERACTIVE_TAGS = frozenset({"button", "a", "input", "select", "textarea", "form"})


def _best_selector(el: dict) -> str:
    """Build the best CSS selector for an element dict."""
    tag = el.get("tag", "")
    if el.get("data_testid"):
        return f'[data-testid="{el["data_testid"]}"]'
    if el.get("id"):
        return f"#{el['id']}"
    if el.get("name"):
        return f'{tag}[name="{el["name"]}"]'
    if el.get("class"):
        first_cls = el["class"].split()[0]
        return f"{tag}.{first_cls}"
    text = el.get("text")
    if text:
        safe = text.replace('"', '\\"')
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

        let bestSelector = tag;
        if (testid) bestSelector = '[data-testid="' + testid + '"]';
        else if (id) bestSelector = '#' + id;
        else if (name) bestSelector = tag + '[name="' + name + '"]';
        else if (cls && typeof cls === 'string') bestSelector = tag + '.' + cls.split(' ')[0];
        else if (text) bestSelector = tag + ':has-text("' + text.substring(0, 50) + '")';

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
            return page.evaluate(_JS_EXTRACT)

        # Lazy import -- Playwright is optional
        from playwright.sync_api import sync_playwright  # pragma: no cover

        with sync_playwright() as pw:  # pragma: no cover
            browser = pw.chromium.launch()
            ctx = browser.new_context()
            p = ctx.new_page()
            p.goto(url, timeout=self.timeout_ms)
            elements = p.evaluate(_JS_EXTRACT)
            browser.close()
            return elements

    def crawl_static(self, html: str) -> list[dict]:
        """Parse a static HTML string and extract interactive elements.

        Uses Python's stdlib ``html.parser`` -- no Playwright required.
        """
        parser = _StaticHTMLExtractor()
        parser.feed(html)
        return parser.elements
