"""Element classifier -- assigns semantic roles to page elements."""

from __future__ import annotations

import re

# Keyword patterns for each semantic role (compiled once)
_LOGIN_RE = re.compile(r"login|log.in|signin|sign.in|auth", re.IGNORECASE)
_SEARCH_RE = re.compile(r"search|query|find|\bq\b", re.IGNORECASE)
_SUBMIT_RE = re.compile(r"submit|save|confirm|\bok\b|\byes\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"email|e.mail", re.IGNORECASE)


def _text_fields(el: dict) -> str:
    """Concatenate all text-like fields of an element for keyword matching."""
    parts = []
    for key in ("text", "id", "name", "placeholder", "aria_label", "data_testid", "class"):
        val = el.get(key)
        if val:
            parts.append(val)
    return " ".join(parts)


class ElementClassifier:
    """Heuristic-based classifier that assigns semantic roles to elements."""

    def classify(self, element: dict) -> str:
        """Return a semantic role string for *element*."""
        tag = (element.get("tag") or "").lower()
        input_type = (element.get("type") or "").lower()
        haystack = _text_fields(element)

        # Password input -- check before login so password_input wins
        if tag == "input" and input_type == "password":
            return "password_input"

        # Email input
        if tag == "input" and (input_type == "email" or _EMAIL_RE.search(haystack)):
            return "email_input"

        # Login-related
        if _LOGIN_RE.search(haystack):
            if tag == "form":
                return "login_form"
            if tag == "button" or (tag == "input" and input_type == "submit"):
                return "login_form"
            if tag == "input":
                return "text_input"
            return "login_form"

        # Search
        if _SEARCH_RE.search(haystack):
            if tag == "input":
                return "search"
            if tag == "button":
                return "search"
            return "search"

        # Submit buttons
        if tag == "button" or (tag == "input" and input_type == "submit"):
            if _SUBMIT_RE.search(haystack):
                return "submit"
            if input_type == "submit":
                return "submit"
            return "button"

        # Select / dropdown
        if tag == "select":
            return "dropdown"

        # Textarea
        if tag == "textarea":
            return "text_input"

        # Other inputs
        if tag == "input":
            if input_type in ("text", "", "tel", "url", "number"):
                return "text_input"
            if input_type == "checkbox":
                return "button"
            if input_type == "radio":
                return "button"
            return "text_input"

        # Form
        if tag == "form":
            return "form"

        # Links
        if tag == "a":
            return "navigation"

        return "unknown"

    def classify_page(self, elements: list[dict]) -> list[dict]:
        """Return a copy of *elements* with the ``role`` field set."""
        result = []
        for el in elements:
            classified = dict(el)
            classified["role"] = self.classify(el)
            result.append(classified)
        return result
