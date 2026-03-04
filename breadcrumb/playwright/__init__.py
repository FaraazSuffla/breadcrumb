"""Playwright integration layer for Breadcrumb self-healing."""

from breadcrumb.playwright.extractor import extract_fingerprint
from breadcrumb.playwright.page_wrapper import HealablePage, heal

__all__ = [
    "HealablePage",
    "extract_fingerprint",
    "heal",
]
