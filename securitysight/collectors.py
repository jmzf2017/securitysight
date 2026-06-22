#!/usr/bin/env python3
"""portco-risk-monitor CLI.

Usage:
  uv run collectors.py --list                 show the collector registry
  uv run collectors.py                         run all ready collectors
  uv run collectors.py --collectors shodan     run collectors matching a substring
  uv run collectors.py --dry-run               run, print the Slack payload, don't post
  uv run collectors.py --no-alert              run without alerting

Then serve the triage dashboard:
  uv run dashboard.py
"""

from __future__ import annotations

import argparse
import sys

from pcrm import registry
from pcrm.pipeline import run


def main() -> int:
    p = argparse.ArgumentParser(
        prog="collectors.py",
        description="Passive portfolio attack-surface & threat monitor.")
    p.add_argument("--list", action="store_true",
                   help="list collectors and exit")
    p.add_argument("--collectors", metavar="SUBSTR", default=None,
                   help="only run collectors whose name contains SUBSTR")
    p.add_argument("--cadence", choices=["daily", "weekly"], default=None,
                   help="only run collectors with this cadence")
    p.add_argument("--no-alert", action="store_true",
                   help="don't send Slack alerts")
    p.add_argument("--dry-run", action="store_true",
                   help="print the Slack payload instead of posting")
    p.add_argument("--companies", default="config/companies.yaml")
    p.add_argument("--data", default="data")
    args = p.parse_args()

    if args.list:
        print(registry.list_table())
        return 0

    print("running collectors…", file=sys.stderr)
    summary = run(
        collector_filter=args.collectors,
        cadence=args.cadence,
        companies_path=args.companies,
        data_root=args.data,
        alert=not args.no_alert,
        dry_run=args.dry_run,
    )
    print(
        f"\ndone: {summary['new']} new, {summary['recurring']} recurring, "
        f"{summary['total_in_lake']} total in lake. "
        f"alert: {summary['alert']}",
        file=sys.stderr,
    )
    if summary["skipped"]:
        print("skipped: " + ", ".join(f"{n} ({w})" for n, w in summary["skipped"]),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
