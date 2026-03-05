"""Breadcrumb -- Self-healing test framework for Playwright."""

from breadcrumb.playwright.page_wrapper import HealablePage, HealableLocator, heal

#: Alias for ``heal()`` — the primary entry point shown in the README.
crumb = heal

__version__ = "0.1.0-dev"

__all__ = [
    "HealablePage",
    "HealableLocator",
    "crumb",
    "heal",
]
