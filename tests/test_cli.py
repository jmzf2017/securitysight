"""Tests for the cross-platform CLI (pcrm/cli.py). All offline."""

import os

import pytest

from pcrm import cli, pipeline
from pcrm.store import Store, db_path


def test_version(capsys):
    assert cli.main(["version"]) == 0
    assert "securitysight" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_run_offline_writes_lake(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "select", lambda *a, **k: [])   # no collectors
    rc = cli.main(["run", "--data", str(tmp_path), "--no-alert"])
    assert rc == 0
    assert db_path(tmp_path).exists()                            # store created


def test_import_then_companies(tmp_path, capsys):
    cfg = tmp_path / "companies.yaml"
    cfg.write_text("companies:\n  - name: Globex\n    domains: [globex.example]\n    tags: [nginx]\n")
    settings = tmp_path / "settings.yaml"
    settings.write_text("alert_min_severity: high\n")
    assert cli.main(["import", "--data", str(tmp_path),
                     "--companies", str(cfg), "--settings", str(settings)]) == 0
    capsys.readouterr()
    assert cli.main(["companies", "--data", str(tmp_path)]) == 0
    assert "Globex" in capsys.readouterr().out


def test_reset_yes(tmp_path):
    # create a lake first
    Store(db_path(tmp_path)).commit()
    assert db_path(tmp_path).exists()
    assert cli.main(["reset", "--data", str(tmp_path), "--yes"]) == 0
    assert not db_path(tmp_path).exists()


def test_data_dir_honors_explicit_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv("PCRM_DATA", raising=False)
    d = cli._data_dir(str(tmp_path / "explicit"))
    assert os.path.isdir(d) and os.environ["PCRM_DATA"] == d     # also sets env
