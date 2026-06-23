<div align="center">

# securitysight

**Turn a watchlist of companies into a self-updating, prioritized, triageable feed of what you should actually worry about today.**

A free, passive OSINT-derived external attack-surface monitor.

[![tests](https://github.com/jmzf2017/securitysight/actions/workflows/tests.yml/badge.svg)](https://github.com/jmzf2017/securitysight/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![collectors](https://img.shields.io/badge/collectors-10%20live-7ee787)](#whats-collected)
[![mode](https://img.shields.io/badge/mode-passive--only-8b5cf6)](#security--authorization)

<img src="docs/dashboard-preview.svg" width="840" alt="Triage dashboard: a ranked queue of findings, each with a severity score and the reasons it ranks where it does">

</div>

> [!WARNING]
> **This is the open-source project, and it ships with demo data only** — `config/companies.yaml` uses fake `.example` domains.
>
> **Do not run the scheduled workflows against real companies from a public repo (including a public fork).** They persist the findings lake to a branch, and on a public repository that branch — and any workflow artifacts — are **world-readable**. To monitor real assets, run your own instance from a **private** repo, or switch the lake to private storage (see [`deploy/README.md`](deploy/README.md)). Publishing the *code* is fine; publishing a *lake of real findings about real companies* is not.
>
> _The scheduled `daily`/`weekly` workflows are **disabled** in this repo (manual `workflow_dispatch` only)._

> [!NOTE]
> **securitysight is a cross-platform CLI** (Linux / macOS / Windows, Python 3.10+) backed by a local SQLite store. **Reporting is a local web dashboard** you launch with `securitysight serve`; API keys live in your OS keychain. See [**Quickstart**](#quickstart). It runs on your own workstation — nothing is sent anywhere except the passive queries to the intel sources you've keyed.

---

## The problem

Threat intel for a set of companies is scattered across a dozen tools — Shodan, Censys, certificate logs, ransomware leak sites, breach databases, the CISA KEV catalog. Checking each one for each company, every day, and figuring out which of the hundreds of results actually matters, is a full-time job nobody has time for.

**securitysight** runs that sweep for you. It pulls from those sources *passively*, lands everything in a local append-only data lake, **correlates across sources** to score and explain each finding, alerts Slack only on what's genuinely new and serious, and gives you a dashboard to work the queue.

The difference between this and a pile of API scripts is the correlation: a single exposed Postgres is a shrug; an exposed service running a CISA-KEV-listed CVE, at a company that *also* just showed up on a ransomware leak site, is a fire — and this tells the two apart, and tells you why.

## Highlights

- **10 passive collectors** across exposure, ransomware, breach, credential and vulnerability intel — three work with no API key at all.
- **Append-only data lake.** Observations are never mutated, so "what's new today" is a trustworthy diff and you get a full audit trail.
- **Cross-source scoring that explains itself.** Every score carries plain-English reasons; the ranking is auditable, not a black box.
- **Findings point at a system, not just a product.** A product-level hit (e.g. a KEV matched on your tech tags) is correlated to the actual hosts other collectors located — IP, FQDN and port — so you know *where* to look, with an honest "no public host located" note when nothing matches.
- **Signal-only Slack alerts.** Only newly-seen findings at or above your threshold, never a re-alert on something you've seen.
- **A real triage dashboard.** Rank, filter, acknowledge, dismiss — decisions persist back to the lake.
- **Deploy three ways:** systemd timer, Docker Compose, or serverless GitHub Actions.
- **Privacy-aware.** Leaked credentials are stored as masked samples and counts — never raw `email:password` lines.

## Quickstart

Cross-platform CLI (Python 3.10+). Install once, then everything is a
`securitysight` subcommand. From a clone without installing, swap
`securitysight` for `python -m pcrm`.

Try it with sample data — **no API keys needed**:

```bash
pip install -e .                 # or: pip install -r requirements.txt
securitysight init --demo        # set up the data dir + load sample findings
securitysight serve              # triage at http://localhost:8000
```

Point it at the real world:

```bash
securitysight keys set SHODAN_API_KEY    # stored in your OS keychain; repeat per provider
$EDITOR config/companies.yaml            # your watchlist…
securitysight import                     # …loaded into the local store
securitysight companies                  # review it

securitysight run                        # collect (collectors without a key are skipped)
securitysight run --collectors shodan    # or just one
securitysight run --dry-run              # preview the Slack post without sending
securitysight serve                      # open the dashboard to triage
```

The watchlist, settings, API keys and runs are all manageable from the web
dashboard too. Run `securitysight --help` for the full command list; keys can
also be set via environment variables / a `.env` file if you prefer.

> [!NOTE]
> **Headless Linux:** the OS keychain (`keyring`) needs a Secret Service backend
> (GNOME Keyring / KWallet), which a desktop session provides but a bare headless
> server does not. On such hosts, skip `securitysight keys` and supply keys via
> **environment variables** (or a `.env` you `source`) instead — collectors read
> them the same way. macOS (Keychain) and Windows (Credential Manager) work out
> of the box.

## What's collected

Every collector is **passive** — it queries third-party indexes and public feeds and never touches the watched companies' infrastructure.

| Collector | API key | What it surfaces |
|---|:--:|---|
| **Shodan** | `SHODAN_API_KEY` | internet-exposed services + reported CVEs |
| **Censys** | `CENSYS_PAT` | exposed services (second-opinion corroboration) |
| **crt.sh** | — | new hosts/subdomains via Certificate Transparency |
| **RansomLook** | — | ransomware leak-site victim postings |
| **Mallory-Breaches** | `MALLORY_API_KEY` | breach / dump exposure by domain |
| **Mallory-Vulns** | `MALLORY_API_KEY` | vuln intel with exploit-maturity signal |
| **NVD-KEV** | — | CISA Known Exploited Vulnerabilities catalog |
| **HaveIBeenPwned** | `HIBP_API_KEY` | breached employee accounts on a watched domain |
| **VirusTotal** | `VT_API_KEY` | domain reputation verdicts + passive-DNS resolutions |
| **Leak-Lookup** | `LEAKLOOKUP_API_KEY` | leaked credentials by domain, grouped by source (weekly) |

The three keyless feeds work out of the box. The keyed collectors are real implementations written against each provider's documented API shape — verify field mappings against your own tenant on the first live run, since vendor APIs drift.

## How prioritization works

Scoring runs over the **entire lake** on every pass, so it can correlate across sources rather than scoring each finding in isolation. The escalations that turn noise into signal:

- an exposed service running a **KEV** CVE → critical (ransomware-linked KEV → maxed out)
- a **KEV/vuln matched only on a declared tech tag** → scored by evidence: critical if a located host runs it, medium if a candidate host matches, low/medium "patch-awareness" if no host is found (a tag is your assertion you run something, not proof a vulnerable instance exists)
- any finding at a company **currently on a ransomware leak site** → boosted
- a **new certificate host** that a scanner confirms is **live and exposed** → jumps from info to critical
- a host seen by **multiple scanners** → corroboration bump
- **leaked credentials** (HIBP / Leak-Lookup) + an **exposed remote-access service** → boosted
- a domain **flagged malicious** that also exposes services → reads as a likely compromised host
- plus recency (new today) and per-company **criticality** weighting

A worked example, straight from the demo:

```
100  critical  Meridian Health   Shodan   203.0.113.10:3389 (RDP exposed)
       ↳ exposed service runs ransomware-linked KEV CVE (CVE-2024-21887)
       ↳ company is currently on a ransomware leak site
       ↳ new in the last 24h
       ↳ crown-jewel weighting x1.5
```

Four separate signals — an exposed RDP, a known-exploited CVE on it, the company appearing on a leak site, and its crown-jewel weighting — combine into one unambiguous "deal with this now," with the receipts attached.

## Architecture

```mermaid
flowchart LR
  WL["watchlist<br/>companies.yaml"] --> COL["collectors<br/>(10, passive)"]
  SRC["Shodan · Censys · crt.sh · RansomLook · Mallory<br/>CISA KEV · HIBP · VirusTotal · Leak-Lookup"] -.->|passive queries| COL
  COL -->|findings| LAKE["append-only<br/>data lake"]
  LAKE --> SCORE["scoring &<br/>correlation"]
  SCORE -->|new & severe only| SLACK["Slack alerts"]
  SCORE --> DASH["triage<br/>dashboard"]
```

The append-only property is the point: observations are immutable, so diffing any two days is trivial and the "new today" feed is trustworthy.

## Configuration

The watchlist is plain YAML. `tags` double as a product/tech inventory that drives KEV and vuln-intel matching; `criticality` floats a crown-jewel company's findings up.

```yaml
companies:
  - name: Meridian Health
    domains: [meridianhealth.example]
    aliases: ["Meridian", "Meridian Health Systems"]
    tags: [citrix, "windows server"]
    criticality: 1.5        # regulated data — weight findings higher
```

## Deployment

Run the daily sweep with no babysitting. Full setup for each is in **[`deploy/README.md`](deploy/README.md)**.

- **systemd timer** — a oneshot service + daily timer (with catch-up) on any Linux host, plus an optional dashboard service.
- **Docker Compose** — an always-on dashboard and a scheduled collector sharing a data volume.
- **GitHub Actions** — serverless daily + weekly schedulers that persist the shared lake to a branch and post a triage table to each run summary. *(Use a private repo — the lake contains findings about your companies.)*

## Extending

Adding a source is small:

1. Drop a module in `pcrm/collectors/`, subclass `BaseCollector`.
2. Set `NAME`, `KEY_ENV`, `CADENCE`, `STATUS`; implement `collect(self, companies) -> list[Finding]`.
3. Register it in `pcrm/registry.py`.
4. Stay passive, and fail soft (catch errors, return what you have).

A `Finding` is source-agnostic — give it a `kind` and a `detail` dict and the lake, scoring and dashboard handle the rest. To make it correlate, reuse an existing `kind` (e.g. `exposed_service`, `breached_accounts`) or add a rule in `pcrm/scoring.py`.

## Project layout

```
pcrm/
  cli.py             the `securitysight` CLI (run, serve, keys, companies, …)
  __main__.py        `python -m pcrm` entry point
  models.py          Company, Finding (fingerprint, severity)
  store.py           SQLite store — findings, append-only observations, config, runs
  lake.py            Lake facade over the store (ingest / triage / rescore)
  secrets.py         API keys in the OS keychain + run-scoped env injection
  runner.py          background run manager (single-run lock, live status)
  web.py             Flask app factory + REST API — the reporting dashboard
  registry.py        collector registry / --list table
  scoring.py         cross-source correlation & prioritization
  assets.py          locate findings to real hosts (IP/FQDN) + KEV→host link
  pipeline.py        collect → ingest → enrich → score → alert
  collectors/        one module per source
  notify/slack.py    Block Kit alerting
templates/           the web dashboard UI
collectors.py        legacy CLI entry (still works); prefer `securitysight`
dashboard.py         thin Flask entry for Docker/systemd; CLI `serve` is preferred
seed_demo.py         load sample findings to explore offline
config/              watchlist + settings (YAML; imported into the store)
tests/               pytest suite
deploy/              systemd, Docker & GitHub Actions guides + units
.github/workflows/   tests; daily/weekly schedulers (disabled here — manual only)
```

## Security & authorization

> This monitors companies you are **authorized** to monitor — your own organization, portfolio companies, or vendors under agreement.

- **Passive by design.** No scanning, probing, or exploitation of any target. Collectors only read public feeds and third-party indexes.
- **Keys stay in your OS keychain** (`securitysight keys set …`) — or an env var / `.env` if you prefer — and are never committed. Collectors without their key are simply skipped.
- **Credential data is minimized.** Breach/leak findings store counts and masked samples, never plaintext secrets.
- **HIBP** `breacheddomain` lookups only work for domains verified on your own HIBP account — the API enforces the authorization model for you.

## Status

Functional and actively developed (`v0.5`) — a cross-platform CLI with a local web reporting dashboard, an SQLite store, OS-keychain secret storage, cross-source scoring, asset location/correlation, Slack alerting, and all three deployment paths, with a `pytest` suite (129 tests) covering scoring, redaction, asset correlation, the store, secrets, the run manager, the REST API, and the CLI. The keyless collectors are exercised directly; the keyed ones are written to each provider's documented API and worth a field check on first live run. See [`CHANGELOG.md`](CHANGELOG.md) for what's new.

## Contributing

Contributions are welcome — especially new collectors and scoring rules. A few ground rules keep the project coherent:

- **Passive only.** No active scanning, probing, brute-forcing, or exploitation of any target. Collectors read public feeds and third-party indexes; that boundary is non-negotiable and PRs that cross it won't be merged.
- **Minimize sensitive data.** Never store raw secrets or unnecessary PII in the lake — follow the existing pattern of counts and masked samples (see the HIBP and Leak-Lookup collectors).
- **Fail soft.** A single collector or API hiccup must never sink a run; catch, record a `collector_error`, and return what you have.

The fastest way in is to add a collector or a correlation rule. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for dev setup, the collector contract, conventions, and how to report a security issue privately.

```bash
pip install -e . && securitysight init --demo && securitysight serve   # local instance in seconds
```

Run the test suite (covers the scoring correlations and credential redaction):

```bash
pip install -r requirements-dev.txt
pytest
```

## License

[MIT](LICENSE).
