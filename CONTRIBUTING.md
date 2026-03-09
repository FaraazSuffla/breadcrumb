# Breadcrumb — Development Guide

## How to Contribute

Thank you for considering contributing to Breadcrumb! Here's how to get started.

### Development Setup

```bash
git clone https://github.com/FaraazSuffla/breadcrumb.git
cd breadcrumb

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e ".[dev,docs]"
playwright install chromium
pre-commit install
```

### Running Tests

```bash
pytest                          # Run all tests
pytest --cov                    # Run with coverage
pytest -x                       # Stop on first failure
pytest --integration            # Run integration tests (require real Chromium browser)
```

> **Note:** Integration tests in `tests/test_integration.py` are skipped by default. They require `playwright install chromium` and the `--integration` flag to run.

### Code Quality

```bash
ruff check .                    # Lint
ruff format .                   # Format
pyright                         # Type check
mypy breadcrumb/                # Type check (mypy)
```

### Branch Strategy (GitHub Flow)

1. `main` is always deployable
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make small, focused commits with clear messages
4. Open a Pull Request when ready
5. CI must pass before merge
6. Squash merge into `main`

### Commit Messages

```
<type>: <short description>

Types: feat, fix, docs, test, refactor, ci, chore
```

### Code Standards

- 100% type hint coverage (pyright strict + mypy strict)
- 90%+ test coverage
- All code formatted with ruff
- All public APIs documented with docstrings

## Code of Conduct

Be respectful, inclusive, and constructive. We're building something to help everyone.
