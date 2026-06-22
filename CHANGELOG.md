# Changelog

All notable changes to securitysight are documented here.

## 0.3.1

### Added
- **`./runssp update --dry-run`** (and `update_repos.sh --dry-run`) — shows, per
  repo, the exact overlay diff (added / changed / deleted), the **exclude list
  actually applied** to each side (resolved from the real flags, so an inverted
  flag shows up), and each clone's resolved **path + `origin` remote**. Runs the
  invariant checks and exits **0 without writing, committing, or pushing
  anything** — the safe way to eyeball a push before authorizing it.
- **Fail-loud invariant guards** on *every* `update` (dry-run and real), each
  aborting with a nonzero exit and a message naming the invariant:
  - **A** — the public overlay must not carry `context.md` (it names the org).
  - **B** — the public overlay must not carry a *real* watchlist; only demo
    `.example` `config/companies.yaml` may go public.
  - **C** — the private overlay must not add/overwrite/delete anything under
    `config/`, `.env` or `data/`.
  - **D** — *remote identity (the keystone):* each clone's `git remote get-url
    origin` must match the repo its path claims to be (the private path's origin
    must be the `-private` repo, the public path's must not). A swapped or
    misconfigured `.ssp.env` aborts here, before a single file is copied.
  Guards run **before** any mutating step; on a real run they gate the push.
- `SSP_PRIVATE_REPO_PATTERN` (optional, in `.ssp.env`) overrides the substring
  that distinguishes the private repo for Invariant D (default: `private`).
- `tests/test_update_guards.py` — happy-path + one deliberate-violation test per
  invariant (A–D) against local throwaway remotes, plus a dry-run
  no-filesystem-mutation test.

## 0.3.0

### Added
- **`runssp`** — a single macOS entry point. `./runssp` runs a collection
  (no alerts) then opens the dashboard; subcommands: `run`, `dashboard`,
  `reset`, `update`, `test`, `setup`.
- **Reset / start-fresh** — `./runssp reset` (and `collectors.py --reset`).
  Archives the local `data/` lake to `data.bak.<timestamp>` by default
  (`--purge` to hard-delete), with a confirmation prompt (`--yes` to skip).
  With `--remote` (or on confirmation) it also deletes the cloud `risk-lake`
  branch on securitysight-private so Actions re-baselines from empty.
- **`update_repos.sh`** (`./runssp update`) — pushes the current build to both
  GitHub repos: full overlay to public (keeps demo config), code-only overlay to
  private (preserves your real `config/`, `.env` and `data/`). Public first;
  shows a diff and asks before each push; git handles credential prompts.
- Clone paths read from a gitignored `.ssp.env` (see `.ssp.env.example`) so home
  paths never reach the public repo.
- `tests/test_lake.py` — reset behavior (archive / purge / no-op).

## 0.2.1

### Changed
- **Product/inventory findings (CISA KEV & vuln-intel matched on `tags`) are now
  scored by evidence, not by the bare tag match.** A tag is your *assertion* that
  you run something, not proof a vulnerable instance exists. So: a match backed by
  an internet-exposed host stays critical; a candidate (cert-only) host is medium;
  a tag-only match with no host located is now low/medium "patch-awareness" rather
  than critical. This stops the critical queue from filling with un-actionable
  product matches. Accurate `tags` still matter — list what you actually run.
- Pipeline/seed now enrich (locate hosts) **before** scoring, so the score can see
  whether a real host backs a product match.

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
