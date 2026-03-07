"""AI test generation -- crawling, classification, and code generation."""

from breadcrumb.generate.classifier import ElementClassifier
from breadcrumb.generate.codegen import TestCodeGenerator
from breadcrumb.generate.crawler import PageCrawler

__all__ = [
    "ElementClassifier",
    "PageCrawler",
    "TestCodeGenerator",
]
