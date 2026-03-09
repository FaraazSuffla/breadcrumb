# Troubleshooting

Common problems and how to fix them.

---

## Healing isn't working

**Symptom:** Tests still fail on locator changes even after running them once.

**Causes & fixes:**

1. **`test_id` is not stable** — If you use the standalone wrapper without an explicit `test_id`, breadcrumb infers one from the call stack. Renaming the calling file or function changes the inferred ID, breaking fingerprint lookup.

   Fix: always pass an explicit, stable `test_id`:
   ```python
   page = crumb(browser.new_page(), test_id="test_login")
   ```

2. **Database is in the wrong place** — `.breadcrumb.db` is created in the directory you run Python or pytest from. If you run from different directories, multiple databases are created and fingerprints are not shared.

   Fix: pin the database path:
   ```python
   page = crumb(browser.new_page(), test_id="test_login", db_path="./tests/.breadcrumb.db")
   ```
   Or in `pytest.ini`:
   ```ini
   [pytest]
   addopts = --breadcrumb --breadcrumb-db ./tests/.breadcrumb.db
   ```

3. **Confidence threshold too high** — The default is `0.5`. If your app has large DOM changes between versions (many classes and IDs renamed at once), the best candidate might score below `0.5`.

   Fix: lower the threshold:
   ```python
   page = crumb(browser.new_page(), test_id="test_login", threshold=0.4)
   ```
   Do not go below `0.3` — false positives become likely.

4. **First run didn't fingerprint** — Breadcrumb only saves fingerprints when a locator action succeeds. If the first run also failed (e.g. the page wasn't loaded), no fingerprint was stored.

   Fix: run the test against the working version of the app first, then introduce the locator change.

---

## Confidence scores are always low

**Symptom:** `breadcrumb doctor` or `breadcrumb report` shows healing events with confidence around 0.3–0.4.

**Causes & fixes:**

- **Too many DOM changes at once** — breadcrumb scores 7 signals. If most signals changed simultaneously, the overall score is naturally lower. Lower the threshold slightly or consider whether the page changed so dramatically that re-fingerprinting makes more sense.

- **Text content locale/dynamic changes** — if element text is dynamic (e.g. "Welcome, Alice" vs "Welcome, Bob"), the text signal contributes noise. Use `data-testid` attributes on stable elements for more reliable healing.

---

## `breadcrumb report` shows no data

**Symptom:** `breadcrumb report` prints zeroes or "No healing events recorded."

**Causes & fixes:**

- Tests weren't run with `--breadcrumb`. Breadcrumb only records data when the plugin is active.
- Database is in a different directory than where you're running the CLI. Use `--db` to point to the right file:
  ```bash
  breadcrumb report --db ./tests/.breadcrumb.db
  ```

---

## Tests are quarantined unexpectedly

**Symptom:** Tests skip automatically with a quarantine notice.

**Explanation:** Breadcrumb quarantines tests whose flip rate (pass/fail alternation) exceeds 20% over the last 10 runs. This is intentional to prevent flaky tests from blocking CI.

**Fix:**
- Check `breadcrumb doctor` to see how many tests are quarantined.
- Stabilize the underlying test, then clear quarantine by deleting the `quarantined_tests` rows from `.breadcrumb.db` or re-running the test suite enough times to establish a stable pass/fail pattern.

---

## `breadcrumb generate` fails

**Symptom:** `Error: AI test generation requires additional dependencies.`

**Fix:**
```bash
pip install pytest-breadcrumb[playwright,ai]
playwright install chromium
```

---

## `breadcrumb mcp` fails

**Symptom:** `Error: MCP server requires the 'mcp' extra.`

**Fix:**
```bash
pip install pytest-breadcrumb[mcp]
```

---

## Integration tests fail or are skipped

Integration tests (in `tests/test_integration.py`) require a real Chromium browser and must be opted into explicitly:

```bash
playwright install chromium
pytest --integration
```

Without `--integration`, the tests are silently skipped (not failed).
