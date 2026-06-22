"""The daily pipeline: collect -> ingest -> score -> alert.

Kept separate from the CLI so it can also be driven from cron, a notebook, or
tests. Returns a summary dict.
"""

from __future__ import annotations

import sys
import time

from .config import load_companies, load_settings
from .lake import Lake
from .registry import select
from .scoring import score_all
from .assets import enrich_assets
from .notify import slack


def run(collector_filter: str | None = None, *,
        cadence: str | None = None,
        companies_path: str = "config/companies.yaml",
        data_root: str = "data",
        alert: bool = True,
        dry_run: bool = False) -> dict:
    settings = load_settings()
    companies = load_companies(companies_path)
    company_map = {c.name: c for c in companies}
    lake = Lake(data_root)

    collectors = select(collector_filter, cadence)
    ran, skipped, all_findings = [], [], []

    for cls in collectors:
        c = cls()
        if not c.ready:
            why = "stub" if c.STATUS == "stub" else f"missing {c.KEY_ENV}"
            skipped.append((c.NAME, why))
            print(f"  skip  {c.NAME:<16} ({why})", file=sys.stderr)
            continue
        t0 = time.time()
        try:
            found = c.collect(companies)
        except Exception as e:  # noqa: BLE001 - one collector can't sink the run
            print(f"  FAIL  {c.NAME:<16} {e}", file=sys.stderr)
            skipped.append((c.NAME, f"error: {e}"))
            continue
        all_findings.extend(found)
        ran.append(c.NAME)
        print(f"  ok    {c.NAME:<16} {len(found):>4} findings "
              f"({time.time()-t0:.1f}s)", file=sys.stderr)

    # ingest (diff new vs recurring), then score the whole lake, then alert new
    result = lake.ingest(all_findings)
    scored = score_all(lake.all_findings(), company_map)
    enrich_assets(lake.all_findings())   # attach location + affected_assets in place
    lake.rescore(scored)                 # persists state (same dict objects)

    # re-read new findings with their freshly-computed scores
    new_scored = [lake.get(f.fingerprint) for f in result["new"]]
    new_scored = [f for f in new_scored if f]

    alert_result = {"sent": 0, "reason": "alerting disabled"}
    if alert:
        alert_result = slack.post_new_findings(
            new_scored,
            min_severity=settings.get("alert_min_severity", "high"),
            dashboard_url=settings.get("dashboard_url", "http://localhost:8000"),
            dry_run=dry_run,
        )

    return {
        "ran": ran,
        "skipped": skipped,
        "new": len(result["new"]),
        "recurring": len(result["recurring"]),
        "total_in_lake": len(lake.all_findings()),
        "alert": alert_result,
    }
