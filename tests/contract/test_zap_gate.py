import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import zap_gate


def report(*alerts):
    return {"site": [{"@name": "https://dev.example", "alerts": list(alerts)}]}


def write(tmp_path, data) -> str:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_high_risk_alert_fails(tmp_path) -> None:
    path = write(tmp_path, report({"pluginid": "40018", "alert": "SQL Injection", "riskcode": "3"}))
    assert zap_gate.main([path]) == 1


def test_medium_and_low_pass(tmp_path) -> None:
    path = write(
        tmp_path,
        report(
            {"pluginid": "10038", "alert": "CSP", "riskcode": "2"},
            {"pluginid": "1", "riskcode": "1"},
        ),
    )
    assert zap_gate.main([path]) == 0


def test_triaged_high_risk_passes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        zap_gate, "load_triaged", lambda: {"40018": "false positive, see triage doc"}
    )
    path = write(tmp_path, report({"pluginid": "40018", "alert": "SQL Injection", "riskcode": "3"}))
    assert zap_gate.main([path]) == 0
