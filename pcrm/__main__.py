"""Enable `python -m pcrm <command>` as a cross-platform entry point."""

from .cli import main

raise SystemExit(main())
