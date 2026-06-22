"""Append-only data lake.

Design:
  data/observations/YYYY-MM-DD.jsonl   immutable run logs. Every finding seen on
                                       every run is appended here, forever. This
                                       is the source of truth and audit trail.
  data/state.json                      derived index, safe to delete & rebuild.
                                       Maps fingerprint -> the merged record with
                                       first_seen / last_seen / current score and
                                       triage state.

Nothing in observations/ is ever edited or deleted. "What changed today" is just
the set of fingerprints whose first_seen == this run. That append-only property
is what makes the feed trustworthy: you can always diff two days.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Iterable

from .models import Finding, utcnow_iso


class Lake:
    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)
        self.obs_dir = self.root / "observations"
        self.state_path = self.root / "state.json"
        self.obs_dir.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, dict] = self._load_state()

    # ---------------------------------------------------------------- state
    def _load_state(self) -> dict[str, dict]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {}

    def _save_state(self) -> None:
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True))
        os.replace(tmp, self.state_path)  # atomic

    # ---------------------------------------------------------------- ingest
    def ingest(self, findings: Iterable[Finding]) -> dict[str, list[Finding]]:
        """Append findings to today's log and merge into state.

        Returns {"new": [...], "recurring": [...]} so the pipeline can alert
        only on genuinely new things.
        """
        run_ts = utcnow_iso()
        log_path = self.obs_dir / f"{date.today().isoformat()}.jsonl"
        new, recurring = [], []

        with log_path.open("a") as log:
            for f in findings:
                fp = f.fingerprint
                prior = self._state.get(fp)
                if prior is None:
                    f.first_seen = run_ts
                    f.last_seen = run_ts
                    self._state[fp] = {
                        **f.to_dict(),
                        "triage": "new",          # new | acknowledged | dismissed
                        "triage_note": "",
                        "triage_at": None,
                    }
                    new.append(f)
                else:
                    f.first_seen = prior["first_seen"]
                    f.last_seen = run_ts
                    # preserve human triage decisions across runs
                    self._state[fp].update(
                        {**f.to_dict(),
                         "triage": prior.get("triage", "new"),
                         "triage_note": prior.get("triage_note", ""),
                         "triage_at": prior.get("triage_at")}
                    )
                    recurring.append(f)

                # immutable append — full record every time
                log.write(json.dumps({"run_ts": run_ts, **f.to_dict()}) + "\n")

        self._save_state()
        return {"new": new, "recurring": recurring}

    # ---------------------------------------------------------------- read
    def all_findings(self) -> list[dict]:
        return list(self._state.values())

    def get(self, fingerprint: str) -> dict | None:
        return self._state.get(fingerprint)

    def set_triage(self, fingerprint: str, status: str, note: str = "") -> bool:
        rec = self._state.get(fingerprint)
        if not rec:
            return False
        rec["triage"] = status
        rec["triage_note"] = note
        rec["triage_at"] = utcnow_iso()
        self._save_state()
        return True

    def rescore(self, scored: list[dict]) -> None:
        """Write recomputed scores back into state (scoring runs over the whole
        lake each run so correlations can use today's full picture)."""
        for rec in scored:
            fp = rec["fingerprint"]
            if fp in self._state:
                self._state[fp]["score"] = rec["score"]
                self._state[fp]["score_reasons"] = rec.get("score_reasons", [])
                self._state[fp]["severity"] = rec["severity"]
        self._save_state()
