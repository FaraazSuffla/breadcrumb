"""Auto-quarantine logic for flaky tests.

Flaky/Chronic tests are auto-quarantined: they still run but their failures
do not block the CI pipeline. Tests that become Stable/Intermittent again
are automatically released from quarantine.
"""

from __future__ import annotations

import time

from breadcrumb.core.storage import FingerprintStore
from breadcrumb.flaky.analyzer import TestAnalyzer


class QuarantineManager:
    """Manages the quarantine list for flaky tests.

    Quarantined tests:
        - Are still executed so data keeps accumulating.
        - Their failures should not block CI (callers are responsible for
          enforcing this; the manager only tracks quarantine state).
        - Are automatically released when their classification improves to
          Stable or Intermittent.

    Usage::

        manager = QuarantineManager(store, analyzer)
        manager.quarantine("test_checkout", "auto: Chronic fliprate 0.7")
        if manager.is_quarantined("test_checkout"):
            ...
        report = manager.auto_update()
    """

    def __init__(
        self,
        store: FingerprintStore,
        analyzer: TestAnalyzer,
        fliprate_threshold: float = 0.3,
    ) -> None:
        self._store = store
        self._analyzer = analyzer
        self._threshold = fliprate_threshold

    def is_quarantined(self, test_id: str) -> bool:
        """Return True if the test is currently quarantined."""
        conn = self._store._get_conn()
        row = conn.execute(
            "SELECT 1 FROM quarantine WHERE test_id = ?",
            (test_id,),
        ).fetchone()
        return row is not None

    def quarantine(self, test_id: str, reason: str) -> None:
        """Add a test to the quarantine list."""
        conn = self._store._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO quarantine (test_id, reason, quarantined_at, auto_unquarantine) "
            "VALUES (?, ?, ?, 1)",
            (test_id, reason, time.time()),
        )
        conn.commit()

    def unquarantine(self, test_id: str) -> None:
        """Remove a test from the quarantine list."""
        conn = self._store._get_conn()
        conn.execute("DELETE FROM quarantine WHERE test_id = ?", (test_id,))
        conn.commit()

    def auto_update(self) -> dict[str, list[str]]:
        """Auto-quarantine Flaky/Chronic tests; release Stable/Intermittent ones.

        Only tests with auto_unquarantine=1 are candidates for automatic release.

        Returns:
            {"quarantined": [list of newly quarantined test_ids],
             "unquarantined": [list of released test_ids]}
        """
        classifications = self._analyzer.get_all_classifications()
        newly_quarantined: list[str] = []
        newly_unquarantined: list[str] = []

        for test_id, classification in classifications.items():
            currently = self.is_quarantined(test_id)

            if classification in ("Flaky", "Chronic") and not currently:
                reason = f"auto: {classification} (fliprate threshold {self._threshold:.2f})"
                self.quarantine(test_id, reason)
                newly_quarantined.append(test_id)

            elif classification in ("Stable", "Intermittent") and currently:
                # Only auto-release if marked for auto-unquarantine
                conn = self._store._get_conn()
                row = conn.execute(
                    "SELECT auto_unquarantine FROM quarantine WHERE test_id = ?",
                    (test_id,),
                ).fetchone()
                if row and row[0]:
                    self.unquarantine(test_id)
                    newly_unquarantined.append(test_id)

        return {"quarantined": newly_quarantined, "unquarantined": newly_unquarantined}

    def get_all_quarantined(self) -> list[str]:
        """Return the list of all currently quarantined test_ids."""
        conn = self._store._get_conn()
        rows = conn.execute(
            "SELECT test_id FROM quarantine ORDER BY quarantined_at DESC",
        ).fetchall()
        return [r[0] for r in rows]
