"""Generate a labeled synthetic report without SSH or credentials."""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config
import correlate
import parsers


def main():
    out = ROOT / "output" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "fixtures"
    aps = parsers.validated_summary(
        (fixtures / "9800_ap_summary_SYNTHETIC.txt").read_text(),
        parsers.parse_9800_ap_summary,
    )
    cdp = parsers.parse_9800_cdp((fixtures / "9800_cdp_SYNTHETIC.txt").read_text())
    rows = parsers.merge("synthetic-9800", aps, cdp)
    inventory = out / "ap_inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    timestamp = datetime.now(timezone.utc).isoformat()
    status = {
        "source": "SYNTHETIC DEMO - not live device data",
        "started_utc": timestamp, "finished_utc": timestamp,
        "complete": True,
        "inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
        "controllers": [{"name": "synthetic-9800", "host": "not contacted",
                         "type": "9800", "status": "complete", "ap_count": len(rows), "error": ""}],
    }
    (out / "collection_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    switches = out / "switch_inventory.csv"
    switches.write_text("hostname,mgmt_ip,street_address,owner\n"
                        'sw-a,10.0.1.1,"100 Example Avenue, Example City",Demo Team\n', encoding="utf-8")
    original_output, original_args = config.OUTPUT, sys.argv
    try:
        config.OUTPUT = out
        sys.argv = ["correlate.py", str(switches)]
        correlate.main()
    finally:
        config.OUTPUT, sys.argv = original_output, original_args
    print("SYNTHETIC DEMO: no network devices were contacted.")


if __name__ == "__main__":
    main()
