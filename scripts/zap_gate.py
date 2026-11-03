"""Fail CI on untriaged High-risk ZAP findings.

ZAP's own exit codes treat everything as warnings, so this reads the JSON reports
and fails when an alert with riskcode >= 3 (High) is not listed in
.zap/triaged.json (each entry: pluginid + reason, reviewed in docs/security/zap-triage.md).

    python scripts/zap_gate.py report_json.json [more.json ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HIGH = 3
TRIAGED = Path(__file__).resolve().parents[1] / ".zap" / "triaged.json"


def load_triaged() -> dict[str, str]:
    if not TRIAGED.exists():
        return {}
    return {str(item["pluginid"]): item["reason"] for item in json.loads(TRIAGED.read_text())}


def alerts(report: dict) -> list[dict]:
    found = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            found.append({**alert, "site": site.get("@name", "")})
    return found


def main(paths: list[str]) -> int:
    triaged = load_triaged()
    blocking, summary = [], {0: 0, 1: 0, 2: 0, 3: 0}
    for path in paths:
        for alert in alerts(json.loads(Path(path).read_text())):
            risk = int(alert.get("riskcode", 0))
            summary[risk] = summary.get(risk, 0) + 1
            if risk >= HIGH and str(alert.get("pluginid")) not in triaged:
                blocking.append(alert)

    labels = {3: "High", 2: "Medium", 1: "Low", 0: "Informational"}
    print("ZAP findings: " + ", ".join(f"{labels[r]} {summary[r]}" for r in (3, 2, 1, 0)))
    for alert in blocking:
        print(f"  BLOCKING [{alert.get('pluginid')}] {alert.get('alert')} on {alert['site']}")
    if blocking:
        print("Fix them, or triage in .zap/triaged.json + docs/security/zap-triage.md.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
