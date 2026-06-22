"""Load the watchlist and settings from config/."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Company


def load_companies(path: str | Path = "config/companies.yaml") -> list[Company]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return [Company.from_dict(c) for c in data.get("companies", [])]


def load_settings(path: str | Path = "config/settings.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}
