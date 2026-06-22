# Changelog

All notable changes to securitysight are documented here.

## 0.2.0

### Added
- **Asset location & correlation** (`pcrm/assets.py`). Every finding now carries a
  normalized `location` (IP, port, FQDNs), and product/inventory findings — a
  CISA KEV or vuln-intel hit matched on your tech tags — are correlated to the
  actual hosts other collectors located. These appear as `affected_assets`
  (e.g. an Exchange KEV resolving to `mail.example.com (198.51.100.9:443)` from
  Shodan, plus `autodiscover.example.com` from crt.sh), with an explicit
  "no public host located — check internal inventory" note when nothing matches.
- Dashboard **"where"** line and **affected-assets** block on each finding.
- Slack alerts now include a location line per finding.
- `tests/test_assets.py` — 13 tests for the locator and correlation logic.

### Changed
- The CISA KEV collector records which tags matched (`matched_tags`), which
  drives the new correlation.
- Pipeline now runs an enrichment pass: `collect → ingest → score → enrich → alert`.

## 0.1.0

- Initial release: 10 passive collectors (Shodan, Censys, crt.sh, RansomLook,
  Mallory ×2, CISA KEV, HaveIBeenPwned, VirusTotal, Leak-Lookup), an append-only
  JSONL data lake, cross-source scoring with plain-English reasons, Slack
  alerting, a Flask triage dashboard, systemd / Docker / GitHub Actions
  deployment, and a pytest suite covering scoring and credential redaction.
