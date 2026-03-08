"""Breadcrumb -- Self-healing test framework for Playwright."""

from breadcrumb.playwright.page_wrapper import HealableLocator, HealablePage, heal

#: Alias for ``heal()`` — the primary entry point shown in the README.
crumb = heal

__version__ = "0.1.0a1"

__all__ = [
    "HealableLocator",
    "HealablePage",
    "crumb",
    "heal",
]
