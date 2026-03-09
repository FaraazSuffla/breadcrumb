# Playwright API

The Playwright layer provides healable wrappers around the Playwright sync API.

---

## crumb / heal

```python
from breadcrumb import crumb

page = crumb(browser.new_page(), test_id="test_login")
```

`crumb` is an alias for `heal`. Both wrap a Playwright `Page` in a `HealablePage`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | `Page` | required | Raw Playwright page object |
| `test_id` | `str` | `"default"` | Identifier used to namespace fingerprints |
| `db_path` | `str` | `".breadcrumb.db"` | Database file path |
| `threshold` | `float` | `0.5` | Minimum confidence to heal (0.0–1.0) |

---

## HealablePage

::: breadcrumb.playwright.page_wrapper.HealablePage

---

## HealableLocator

::: breadcrumb.playwright.page_wrapper.HealableLocator
