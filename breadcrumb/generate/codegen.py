"""Test code generator -- produces Page Object Models and pytest stubs."""

from __future__ import annotations

import re


def _sanitize_name(raw: str) -> str:
    """Turn an arbitrary string into a valid Python identifier."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", raw)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if not name or name[0].isdigit():
        name = "el_" + name
    return name


def _element_var_name(el: dict) -> str:
    """Derive a descriptive variable name for an element."""
    role = el.get("role", "unknown")
    tag = el.get("tag", "element")

    # Use data-testid if available
    testid = el.get("data_testid")
    if testid:
        return _sanitize_name(testid)

    # Use id
    el_id = el.get("id")
    if el_id:
        return _sanitize_name(el_id)

    # Use text content
    text = el.get("text")
    if text:
        short = text[:30]
        return _sanitize_name(f"{tag}_{short}")

    # Use name
    name = el.get("name")
    if name:
        return _sanitize_name(name)

    # Fallback
    return _sanitize_name(f"{role}_{tag}")


def _method_name(el: dict) -> str:
    """Generate a method name for interacting with the element."""
    tag = el.get("tag", "")
    role = el.get("role", "unknown")
    var = _element_var_name(el)

    if tag == "input" or tag == "textarea" or role in ("email_input", "password_input", "text_input", "search"):
        return f"fill_{var}"
    if tag == "select" or role == "dropdown":
        return f"select_{var}"
    return f"click_{var}"


def _method_body(el: dict, var_name: str) -> str:
    """Generate a method body for interacting with the element."""
    tag = el.get("tag", "")
    role = el.get("role", "unknown")

    if tag == "input" or tag == "textarea" or role in ("email_input", "password_input", "text_input", "search"):
        return f"self.{var_name}.fill(value)"
    if tag == "select" or role == "dropdown":
        return f"self.{var_name}.select_option(value)"
    return f"self.{var_name}.click()"


def _method_params(el: dict) -> str:
    """Return extra parameter string for element interaction methods."""
    tag = el.get("tag", "")
    role = el.get("role", "unknown")

    if tag in ("input", "textarea", "select") or role in (
        "email_input", "password_input", "text_input", "search", "dropdown",
    ):
        return ", value: str"
    return ""


def _to_class_name(page_name: str) -> str:
    """Convert a page name to PascalCase class name."""
    # Already PascalCase?
    if page_name[0].isupper() and "_" not in page_name and " " not in page_name:
        if not page_name.endswith("Page"):
            return page_name + "Page"
        return page_name

    parts = re.split(r"[_\s-]+", page_name)
    name = "".join(p.capitalize() for p in parts if p)
    if not name.endswith("Page"):
        name += "Page"
    return name


def _try_ollama_enrich(model: str, page_name: str, elements: list[dict]) -> dict | None:
    """Attempt to get richer test names from Ollama. Returns None on failure."""
    try:
        import ollama as ollama_lib

        tag_summary = ", ".join(
            f"{e.get('tag')}({e.get('role', 'unknown')})" for e in elements[:20]
        )
        prompt = (
            f"Given a page called '{page_name}' with these elements: {tag_summary}. "
            f"Suggest a one-line docstring for a smoke test of this page. "
            f"Reply with ONLY the docstring text, no quotes."
        )
        response = ollama_lib.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response["message"]["content"].strip()
        if text:
            return {"test_docstring": text}
    except Exception:
        pass
    return None


class TestCodeGenerator:
    """Generates Page Object Model classes and pytest test stubs."""

    def __init__(self, ollama_model: str | None = None) -> None:
        self._ollama_model = ollama_model

    def generate_page_object(self, page_name: str, elements: list[dict]) -> str:
        """Generate a Page Object Model class as a Python string."""
        cls_name = _to_class_name(page_name)

        # Filter to interactive elements only (skip forms, they are containers)
        interactive = [
            e for e in elements
            if e.get("tag") in ("button", "input", "select", "textarea", "a")
        ]

        lines = [
            f"class {cls_name}:",
            f'    """Page object for the {page_name} page."""',
            "",
            "    def __init__(self, page):",
            "        self.page = page",
        ]

        seen_vars: set[str] = set()
        var_map: list[tuple[str, dict]] = []

        for el in interactive:
            var = _element_var_name(el)
            if var in seen_vars:
                var = var + "_" + (el.get("tag") or "el")
            seen_vars.add(var)
            selector = el.get("selector", el.get("tag", ""))
            lines.append(f"        self.{var} = page.locator('{selector}')")
            var_map.append((var, el))

        if not interactive:
            lines.append("        pass")

        # Generate interaction methods
        for var, el in var_map:
            method = _method_name(el)
            # Avoid duplicate method names by using var-based name
            method = method.split("_", 1)
            method = method[0] + "_" + var
            params = _method_params(el)
            body = _method_body(el, var)

            lines.append("")
            lines.append(f"    def {method}(self{params}) -> None:")
            lines.append(f"        {body}")

        return "\n".join(lines) + "\n"

    def generate_test_file(self, page_name: str, elements: list[dict], page_url: str = "") -> str:
        """Generate a pytest test file with basic test stubs."""
        cls_name = _to_class_name(page_name)

        # Try to get enriched docstring from Ollama
        enrichment = None
        if self._ollama_model:
            enrichment = _try_ollama_enrich(self._ollama_model, page_name, elements)

        test_docstring = "Smoke test: verify key elements are visible."
        if enrichment and enrichment.get("test_docstring"):
            test_docstring = enrichment["test_docstring"]

        url_line = f'    URL = "{page_url}"' if page_url else '    URL = ""'

        lines = [
            f'"""Auto-generated tests for the {page_name} page."""',
            "",
            "import pytest",
            "from playwright.sync_api import Page, expect",
            "",
            "",
        ]

        # Generate a smoke test that checks visibility of key elements
        interactive = [
            e for e in elements
            if e.get("tag") in ("button", "input", "select", "textarea", "a")
        ]

        lines.append(f"class Test{cls_name}:")
        lines.append(f'    """{test_docstring}"""')
        lines.append("")
        lines.append(url_line)
        lines.append("")

        # Test: page loads
        lines.append("    def test_page_loads(self, page: Page) -> None:")
        lines.append('        """Verify the page loads successfully."""')
        if page_url:
            lines.append("        page.goto(self.URL)")
        else:
            lines.append("        pass  # TODO: set URL")
        lines.append("")

        # Per-element tests
        seen_tests: set[str] = set()
        for el in interactive:
            var = _element_var_name(el)
            tag = el.get("tag", "")
            selector = el.get("selector", tag)
            test_name = f"test_{var}_is_visible"
            if test_name in seen_tests:
                test_name = test_name + "_" + tag
            seen_tests.add(test_name)

            lines.append(f"    def {test_name}(self, page: Page) -> None:")
            lines.append(f'        """Verify {var} element is visible."""')
            if page_url:
                lines.append("        page.goto(self.URL)")
            lines.append(f"        expect(page.locator('{selector}')).to_be_visible()")
            lines.append("")

        # If there are fillable elements, add a fill test
        fillable = [e for e in interactive if e.get("tag") in ("input", "textarea")]
        if fillable:
            lines.append("    def test_fill_inputs(self, page: Page) -> None:")
            lines.append('        """Verify inputs can be filled."""')
            if page_url:
                lines.append("        page.goto(self.URL)")
            for el in fillable[:5]:  # Limit to first 5
                selector = el.get("selector", "")
                input_type = (el.get("type") or "text").lower()
                if input_type == "email":
                    val = "test@example.com"
                elif input_type == "password":
                    val = "password123"
                elif input_type == "checkbox":
                    continue
                else:
                    val = "test value"
                lines.append(f"        page.locator('{selector}').fill('{val}')")
            lines.append("")

        return "\n".join(lines)
