#!/usr/bin/env python3
"""Triage dashboard.

  uv run dashboard.py            # http://localhost:8000

Reads the lake's state, serves a ranked, filterable queue, and writes triage
decisions (acknowledge / dismiss) back to the lake. Read-only against the
append-only observation logs; only triage state is mutated.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pcrm.config import load_companies
from pcrm.lake import Lake

app = Flask(__name__)
LAKE = Lake("data")


def _companies():
    try:
        return {c.name: c for c in load_companies()}
    except Exception:  # noqa: BLE001
        return {}


@app.route("/")
def index():
    findings = [f for f in LAKE.all_findings() if f["kind"] != "collector_error"]
    findings.sort(key=lambda f: f.get("score", 0), reverse=True)
    companies = _companies()
    sources = sorted({f["source"] for f in findings})
    return render_template(
        "index.html",
        findings=findings,
        companies=sorted(companies),
        sources=sources,
    )


@app.post("/api/triage")
def triage():
    data = request.get_json(force=True)
    ok = LAKE.set_triage(
        data["fingerprint"], data["status"], data.get("note", "")
    )
    return jsonify({"ok": ok})


@app.post("/api/refresh")
def refresh():
    """Re-read state from disk (after a collector run on another process)."""
    global LAKE
    LAKE = Lake("data")
    return jsonify({"ok": True, "count": len(LAKE.all_findings())})


if __name__ == "__main__":
    import os
    # default stays local-only; containers set PCRM_HOST=0.0.0.0
    host = os.environ.get("PCRM_HOST", "127.0.0.1")
    port = int(os.environ.get("PCRM_PORT", "8000"))
    app.run(host=host, port=port, debug=False)
