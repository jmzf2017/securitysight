"""securitysight — cross-platform command-line interface.

Run as `securitysight <command>` (after `pip install -e .`) or, from a clone,
`python -m pcrm <command>`. Reporting is served by a local web server:

  securitysight init [--demo]          set up the data dir (optionally seed demo)
  securitysight keys list|set|validate|delete NAME   manage API keys (OS keychain)
  securitysight companies              show the watchlist
  securitysight import|export          watchlist/settings <-> YAML
  securitysight run [opts]             run a collection
  securitysight serve [--host --port]  start the local web reporting dashboard
  securitysight reset [--purge --yes]  clear the lake
  securitysight version

The data lake + settings live in the per-user data dir by default
(override with --data or $PCRM_DATA); API keys live in the OS keychain.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from . import __version__

APP_NAME = "securitysight"


def _data_dir(explicit: str | None = None) -> str:
    d = explicit or os.environ.get("PCRM_DATA")
    if not d:
        import platformdirs
        d = platformdirs.user_data_dir(APP_NAME, APP_NAME)
    os.makedirs(d, exist_ok=True)
    os.environ["PCRM_DATA"] = d        # align cisa_kev cache + any child process
    return d


# --------------------------------------------------------------- commands
def cmd_run(args) -> int:
    data = _data_dir(args.data)
    from .pipeline import run
    from .secrets import SecretStore, injected_env
    with injected_env(SecretStore()):          # load keychain keys for this run only
        summary = run(collector_filter=args.collectors, cadence=args.cadence,
                      data_root=data, alert=not args.no_alert, dry_run=args.dry_run)
    print(f"done: {summary['new']} new, {summary['recurring']} recurring, "
          f"{summary['total_in_lake']} in lake. alert: {summary['alert']}", file=sys.stderr)
    if summary["skipped"]:
        print("skipped: " + ", ".join(f"{n} ({w})" for n, w in summary["skipped"]),
              file=sys.stderr)
    return 0


def cmd_serve(args) -> int:
    data = _data_dir(args.data)
    from .web import create_app
    app = create_app(data_root=data)
    print(f"securitysight reporting at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    return 0


def cmd_keys(args) -> int:
    from .secrets import SecretStore, known_secret_names, validate_key
    s = SecretStore()
    if args.keys_cmd == "list":
        from .store import Store, db_path
        meta = Store(db_path(_data_dir(args.data))).get_key_validations()
        for name in known_secret_names():
            v = meta.get(name, {})
            mark = "set" if s.exists(name) else "—"
            note = ""
            if v.get("validated_at"):
                note = f"   last validate: {'ok' if v['ok'] else 'FAILED'}"
            print(f"  {name:<20} {mark:<4}{note}")
        return 0
    if args.keys_cmd == "set":
        val = getpass.getpass(f"Value for {args.name} (input hidden): ")
        if not val:
            print("no value entered; nothing changed.", file=sys.stderr)
            return 1
        s.set(args.name, val)
        print(f"{args.name} stored in the OS keychain.")
        return 0
    if args.keys_cmd == "validate":
        r = validate_key(args.name, s.get(args.name))
        from .store import Store, db_path
        Store(db_path(_data_dir(args.data))).set_key_validation(args.name, r.get("ok", False))
        print(f"{args.name}: {'OK' if r['ok'] else 'INVALID'} — {r['detail']}")
        return 0 if r.get("ok") else 1
    if args.keys_cmd == "delete":
        s.delete(args.name)
        print(f"{args.name} removed from the keychain.")
        return 0
    return 2


def cmd_companies(args) -> int:
    from .store import Store, db_path
    from .config import ensure_config_seeded
    st = Store(db_path(_data_dir(args.data)))
    ensure_config_seeded(st)
    rows = st.list_companies()
    if not rows:
        print("  (no companies — add some, or `securitysight import`)")
    for c in rows:
        print(f"  {c['name']:<26} crit={c['criticality']:<4} "
              f"domains=[{','.join(c['domains'])}] tags=[{','.join(c['tags'])}]")
    return 0


def cmd_import(args) -> int:
    from .store import Store, db_path
    from .config import import_config_yaml
    st = Store(db_path(_data_dir(args.data)))
    import_config_yaml(st, args.companies, args.settings)
    print(f"imported {st.count_companies()} companies + settings.", file=sys.stderr)
    return 0


def cmd_export(args) -> int:
    from .store import Store, db_path
    from .config import export_config_yaml
    st = Store(db_path(_data_dir(args.data)))
    export_config_yaml(st, args.companies, args.settings)
    print(f"exported to {args.companies} / {args.settings}", file=sys.stderr)
    return 0


def cmd_reset(args) -> int:
    data = _data_dir(args.data)
    from .lake import reset_lake
    if not args.yes:
        verb = "PERMANENTLY DELETE" if args.purge else "archive"
        resp = input(f"This will {verb} the lake at {data} and clear all triage "
                     f"history. Continue? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted — nothing changed.", file=sys.stderr)
            return 1
    res = reset_lake(data, purge=args.purge)
    print(f"{res['action']}: {res.get('detail', '')}", file=sys.stderr)
    return 0


def cmd_init(args) -> int:
    data = _data_dir(args.data)
    from .store import Store, db_path
    from .config import ensure_config_seeded
    ensure_config_seeded(Store(db_path(data)))
    if args.demo:
        from seed_demo import seed
        res = seed(data)
        print(f"seeded {res['new']} demo findings.")
    print(f"Initialized at {data}.")
    print("Next: `securitysight keys set SHODAN_API_KEY` (etc.), then "
          "`securitysight run`, then `securitysight serve`.")
    return 0


def cmd_version(args) -> int:
    print(f"securitysight {__version__}")
    return 0


# --------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="securitysight",
        description="Passive attack-surface & threat monitor — CLI + local web reporting.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", default=None,
                        help="data directory (default: per-user dir or $PCRM_DATA)")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", parents=[common], help="run a collection")
    r.add_argument("--collectors", metavar="SUBSTR", help="only collectors matching SUBSTR")
    r.add_argument("--cadence", choices=["daily", "weekly"])
    r.add_argument("--no-alert", action="store_true", help="don't send Slack alerts")
    r.add_argument("--dry-run", action="store_true", help="print the Slack payload, don't post")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("serve", parents=[common], help="start the local web reporting server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    k = sub.add_parser("keys", help="manage API keys (stored in the OS keychain)")
    ks = k.add_subparsers(dest="keys_cmd", required=True)
    ks.add_parser("list", parents=[common]).set_defaults(func=cmd_keys)
    for kc in ("set", "validate", "delete"):
        kp = ks.add_parser(kc, parents=[common])
        kp.add_argument("name")
        kp.set_defaults(func=cmd_keys)

    sub.add_parser("companies", parents=[common], help="show the watchlist").set_defaults(func=cmd_companies)

    ip = sub.add_parser("import", parents=[common], help="import watchlist/settings from YAML")
    ip.add_argument("--companies", default="config/companies.yaml")
    ip.add_argument("--settings", default="config/settings.yaml")
    ip.set_defaults(func=cmd_import)

    ep = sub.add_parser("export", parents=[common], help="export watchlist/settings to YAML")
    ep.add_argument("--companies", default="config/companies.yaml")
    ep.add_argument("--settings", default="config/settings.yaml")
    ep.set_defaults(func=cmd_export)

    rs = sub.add_parser("reset", parents=[common], help="clear the data lake")
    rs.add_argument("--purge", action="store_true", help="delete instead of archiving")
    rs.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    rs.set_defaults(func=cmd_reset)

    it = sub.add_parser("init", parents=[common], help="initialize (optionally seed demo data)")
    it.add_argument("--demo", action="store_true", help="also load demo findings")
    it.set_defaults(func=cmd_init)

    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
