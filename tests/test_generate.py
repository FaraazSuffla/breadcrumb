"""Tests for breadcrumb.generate -- crawler, classifier, and codegen."""

from __future__ import annotations

import pathlib

import pytest

from breadcrumb.generate.classifier import ElementClassifier
from breadcrumb.generate.codegen import TestCodeGenerator
from breadcrumb.generate.crawler import PageCrawler

_DEMO_DIR = pathlib.Path(__file__).parent / "demo_app"
_V1_HTML = (_DEMO_DIR / "v1.html").read_text(encoding="utf-8")
_V2_HTML = (_DEMO_DIR / "v2.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def crawler() -> PageCrawler:
    return PageCrawler()


@pytest.fixture()
def v1_elements(crawler: PageCrawler) -> list[dict]:
    return crawler.crawl_static(_V1_HTML)


@pytest.fixture()
def v2_elements(crawler: PageCrawler) -> list[dict]:
    return crawler.crawl_static(_V2_HTML)


@pytest.fixture()
def classifier() -> ElementClassifier:
    return ElementClassifier()


@pytest.fixture()
def codegen() -> TestCodeGenerator:
    return TestCodeGenerator()


# ---------------------------------------------------------------------------
# Crawler tests
# ---------------------------------------------------------------------------


class TestCrawlStatic:
    """Tests for PageCrawler.crawl_static()."""

    def test_crawl_static_finds_buttons(self, v1_elements: list[dict]) -> None:
        buttons = [e for e in v1_elements if e["tag"] == "button"]
        # v1.html has: login-btn, add-to-cart-1, add-to-cart-2, search-btn, subscribe-btn
        assert len(buttons) >= 4
        button_ids = {b.get("id") for b in buttons}
        assert "login-btn" in button_ids
        assert "search-btn" in button_ids

    def test_crawl_static_finds_inputs(self, v1_elements: list[dict]) -> None:
        inputs = [e for e in v1_elements if e["tag"] == "input"]
        # v1.html: email-input, password-input, search-input, subscribe-email, subscribe-terms
        assert len(inputs) >= 4
        types_found = {i.get("type") for i in inputs}
        assert "email" in types_found
        assert "password" in types_found

    def test_crawl_static_finds_links(self, v1_elements: list[dict]) -> None:
        links = [e for e in v1_elements if e["tag"] == "a"]
        # nav: 3 links, footer: 2 links
        assert len(links) >= 5

    def test_crawl_static_finds_forms(self, v1_elements: list[dict]) -> None:
        forms = [e for e in v1_elements if e["tag"] == "form"]
        assert len(forms) >= 1
        assert any(f.get("id") == "login-form" for f in forms)

    def test_crawl_static_selector_prefers_testid(self, v1_elements: list[dict]) -> None:
        email = [e for e in v1_elements if e.get("data_testid") == "email-field"]
        assert len(email) == 1
        assert email[0]["selector"] == '[data-testid="email-field"]'

    def test_crawl_static_selector_uses_id(self, v1_elements: list[dict]) -> None:
        login_btn = [e for e in v1_elements if e.get("id") == "login-btn"]
        assert len(login_btn) == 1
        # login-btn also has data-testid, so testid wins
        assert login_btn[0]["selector"] == '[data-testid="login-submit"]'

    def test_crawl_static_v2(self, v2_elements: list[dict]) -> None:
        buttons = [e for e in v2_elements if e["tag"] == "button"]
        assert len(buttons) >= 4
        button_ids = {b.get("id") for b in buttons}
        assert "auth-button" in button_ids

    def test_crawl_static_captures_text(self, v1_elements: list[dict]) -> None:
        login_btn = [e for e in v1_elements if e.get("id") == "login-btn"]
        assert login_btn
        assert login_btn[0]["text"] is not None
        assert "Sign In" in login_btn[0]["text"]

    def test_crawl_static_element_fields(self, v1_elements: list[dict]) -> None:
        """Every element dict has the required keys."""
        required_keys = {
            "tag",
            "type",
            "id",
            "name",
            "class",
            "text",
            "href",
            "placeholder",
            "aria_label",
            "data_testid",
            "value",
            "role",
            "selector",
        }
        for el in v1_elements:
            assert required_keys.issubset(el.keys()), f"Missing keys in {el}"

    def test_crawl_static_empty_html(self, crawler: PageCrawler) -> None:
        result = crawler.crawl_static("<html><body><p>No interactive elements</p></body></html>")
        assert result == []

    def test_crawl_static_hidden_elements(self, crawler: PageCrawler) -> None:
        html = '<button style="display:none">Hidden</button><button id="vis">Visible</button>'
        result = crawler.crawl_static(html)
        assert len(result) == 1
        assert result[0]["id"] == "vis"


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifier:
    """Tests for ElementClassifier."""

    def test_classify_login_elements(
        self,
        classifier: ElementClassifier,
        v1_elements: list[dict],
    ) -> None:
        classified = classifier.classify_page(v1_elements)
        login_btn = [e for e in classified if e.get("id") == "login-btn"]
        assert login_btn
        assert login_btn[0]["role"] == "login_form"

    def test_classify_email_input(
        self,
        classifier: ElementClassifier,
        v1_elements: list[dict],
    ) -> None:
        classified = classifier.classify_page(v1_elements)
        email = [e for e in classified if e.get("data_testid") == "email-field"]
        assert email
        assert email[0]["role"] == "email_input"

    def test_classify_password_input(
        self,
        classifier: ElementClassifier,
        v1_elements: list[dict],
    ) -> None:
        classified = classifier.classify_page(v1_elements)
        pw = [e for e in classified if e.get("data_testid") == "password-field"]
        assert pw
        assert pw[0]["role"] == "password_input"

    def test_classify_search_elements(
        self,
        classifier: ElementClassifier,
        v1_elements: list[dict],
    ) -> None:
        classified = classifier.classify_page(v1_elements)
        search_input = [e for e in classified if e.get("data_testid") == "search-box"]
        assert search_input
        assert search_input[0]["role"] == "search"

        search_btn = [e for e in classified if e.get("id") == "search-btn"]
        assert search_btn
        assert search_btn[0]["role"] == "search"

    def test_classify_navigation_links(
        self,
        classifier: ElementClassifier,
        v1_elements: list[dict],
    ) -> None:
        classified = classifier.classify_page(v1_elements)
        nav_links = [e for e in classified if e.get("id") == "nav-home"]
        assert nav_links
        assert nav_links[0]["role"] == "navigation"

    def test_classify_generic_button(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "button", "text": "Add to Cart", "id": "add-to-cart-1"}
        assert classifier.classify(el) == "button"

    def test_classify_submit_button(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "button", "text": "Submit", "type": "submit"}
        assert classifier.classify(el) == "submit"

    def test_classify_dropdown(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "select", "id": "country"}
        assert classifier.classify(el) == "dropdown"

    def test_classify_form(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "form", "id": "contact-form"}
        assert classifier.classify(el) == "form"

    def test_classify_text_input(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "input", "type": "text", "id": "username"}
        assert classifier.classify(el) == "text_input"

    def test_classify_textarea(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "textarea", "id": "comments"}
        assert classifier.classify(el) == "text_input"

    def test_classify_unknown(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "div", "id": "mystery"}
        assert classifier.classify(el) == "unknown"

    def test_classify_page_returns_copies(
        self,
        classifier: ElementClassifier,
    ) -> None:
        elements = [{"tag": "button", "text": "OK"}]
        classified = classifier.classify_page(elements)
        assert classified[0] is not elements[0]
        assert "role" in classified[0]

    def test_classify_checkbox(
        self,
        classifier: ElementClassifier,
    ) -> None:
        el = {"tag": "input", "type": "checkbox", "id": "agree"}
        assert classifier.classify(el) == "button"


# ---------------------------------------------------------------------------
# Codegen tests
# ---------------------------------------------------------------------------


class TestCodegen:
    """Tests for TestCodeGenerator."""

    def test_generate_page_object(self, codegen: TestCodeGenerator) -> None:
        elements = [
            {
                "tag": "input",
                "type": "email",
                "id": "email",
                "data_testid": "email",
                "selector": '[data-testid="email"]',
                "role": "email_input",
                "name": None,
                "class": None,
                "text": None,
                "href": None,
                "placeholder": "Email",
                "aria_label": None,
                "value": None,
            },
            {
                "tag": "button",
                "type": "submit",
                "id": "login-btn",
                "data_testid": "login-submit",
                "selector": '[data-testid="login-submit"]',
                "role": "login_form",
                "name": None,
                "class": "btn",
                "text": "Sign In",
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "value": None,
            },
        ]
        code = codegen.generate_page_object("login", elements)
        assert "class LoginPage:" in code
        assert "def __init__(self, page):" in code
        assert "self.page = page" in code
        assert "page.locator(" in code
        assert "def fill_" in code or "def click_" in code

    def test_generate_page_object_class_name(self, codegen: TestCodeGenerator) -> None:
        elements = [
            {
                "tag": "button",
                "id": "ok",
                "selector": "#ok",
                "text": "OK",
                "type": None,
                "name": None,
                "class": None,
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "data_testid": None,
                "value": None,
                "role": "button",
            },
        ]
        code = codegen.generate_page_object("user_settings", elements)
        assert "class UserSettingsPage:" in code

    def test_generate_test_file(self, codegen: TestCodeGenerator) -> None:
        elements = [
            {
                "tag": "input",
                "type": "email",
                "id": "email",
                "data_testid": "email",
                "selector": '[data-testid="email"]',
                "role": "email_input",
                "name": None,
                "class": None,
                "text": None,
                "href": None,
                "placeholder": "Email",
                "aria_label": None,
                "value": None,
            },
            {
                "tag": "button",
                "type": "submit",
                "id": "submit",
                "data_testid": None,
                "selector": "#submit",
                "role": "submit",
                "name": None,
                "class": None,
                "text": "Submit",
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "value": None,
            },
        ]
        code = codegen.generate_test_file("login", elements, page_url="http://localhost/login")
        assert "def test_" in code
        assert "import pytest" in code
        assert "class TestLoginPage:" in code
        assert "http://localhost/login" in code

    def test_generate_test_file_has_fill_test(self, codegen: TestCodeGenerator) -> None:
        elements = [
            {
                "tag": "input",
                "type": "text",
                "id": "username",
                "selector": "#username",
                "role": "text_input",
                "name": None,
                "class": None,
                "text": None,
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "data_testid": None,
                "value": None,
            },
        ]
        code = codegen.generate_test_file("registration", elements, page_url="http://example.com")
        assert "test_fill_inputs" in code

    def test_generate_test_file_no_url(self, codegen: TestCodeGenerator) -> None:
        elements = [
            {
                "tag": "button",
                "id": "ok",
                "selector": "#ok",
                "text": "OK",
                "type": None,
                "name": None,
                "class": None,
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "data_testid": None,
                "value": None,
                "role": "button",
            },
        ]
        code = codegen.generate_test_file("misc", elements)
        assert 'URL = ""' in code

    def test_codegen_ollama_fallback(self) -> None:
        """When ollama_model is set but ollama is not installed, it falls back silently."""
        gen = TestCodeGenerator(ollama_model="llama3")
        elements = [
            {
                "tag": "button",
                "id": "ok",
                "selector": "#ok",
                "text": "OK",
                "type": None,
                "name": None,
                "class": None,
                "href": None,
                "placeholder": None,
                "aria_label": None,
                "data_testid": None,
                "value": None,
                "role": "button",
            },
        ]
        # Should not raise even if ollama is not installed
        code = gen.generate_test_file("test_page", elements)
        assert "def test_" in code


# ---------------------------------------------------------------------------
# Integration: crawl_static -> classify -> codegen
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Integration test: crawl v1.html -> classify -> generate code."""

    def test_full_pipeline(
        self,
        crawler: PageCrawler,
        classifier: ElementClassifier,
        codegen: TestCodeGenerator,
    ) -> None:
        elements = crawler.crawl_static(_V1_HTML)
        classified = classifier.classify_page(elements)
        pom = codegen.generate_page_object("demo", classified)
        test_code = codegen.generate_test_file("demo", classified, page_url="http://localhost:8080")

        assert "class DemoPage:" in pom
        assert "def __init__(self, page):" in pom
        assert "class TestDemoPage:" in test_code
        assert "def test_" in test_code
        assert "http://localhost:8080" in test_code
