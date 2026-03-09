"""Breadcrumb -- Self-healing test framework for Playwright."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.1.0a1"

__all__ = [
    "HealableLocator",
    "HealablePage",
    "crumb",
    "heal",
]

if TYPE_CHECKING:
    from breadcrumb.playwright.page_wrapper import HealableLocator, HealablePage, heal

    crumb = heal


def __getattr__(name: str) -> object:
    if name in ("HealableLocator", "HealablePage", "heal", "crumb"):
        from breadcrumb.playwright.page_wrapper import HealableLocator, HealablePage, heal

        globals()["HealableLocator"] = HealableLocator
        globals()["HealablePage"] = HealablePage
        globals()["heal"] = heal
        globals()["crumb"] = heal
        return globals()[name]
    raise AttributeError(f"module 'breadcrumb' has no attribute {name!r}")
