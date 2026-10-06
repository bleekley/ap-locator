"""Step 1: log into every controller in controllers.csv, pull AP + CDP data,
write output/ap_inventory.csv. Credentials come from .env only."""
import csv
import hashlib
import json
from datetime import datetime, timezone
import sys

from netmiko import ConnectHandler

import config
import parsers

FIELDS = [
    "controller", "ap_name", "model", "eth_mac", "ap_ip", "state",
    "neighbor_name", "neighbor_ip", "neighbor_port",
]


def collect_9800(name: str, host: str, cred: dict) -> list[dict]:
    conn = ConnectHandler(device_type="cisco_xe", host=host, **cred)
    try:
        aps = parsers.validated_summary(conn.send_command("show ap summary"), parsers.parse_9800_ap_summary)
        cdp = parsers.parse_9800_cdp(parsers.checked_output(conn.send_command("show ap cdp neighbor")))
    finally:
        conn.disconnect()
    return parsers.merge(name, aps, cdp)


def collect_aireos(name: str, host: str, cred: dict) -> list[dict]:
    conn = ConnectHandler(device_type="cisco_wlc", host=host, **cred)
    try:
        aps = parsers.validated_summary(conn.send_command("show ap summary"), parsers.parse_aireos_ap_summary)
        cdp = parsers.parse_aireos_cdp_detail(
            parsers.checked_output(conn.send_command("show ap cdp neighbors detail all"))
        )
    finally:
        conn.disconnect()
    return parsers.merge(name, aps, cdp)


def main() -> None:
    rows: list[dict] = []
    failures = []
    controllers = config.controllers()  # Validate everything before touching output.
    credentials = {c["name"]: config.creds_for(c["name"]) for c in controllers}
    started = datetime.now(timezone.utc).isoformat()
    statuses = []
    for c in controllers:
        label = f"{c['name']} ({c['host']}, {c['type']})"
        print(f"Collecting from {label} ...")
        try:
            fn = collect_9800 if c["type"] == "9800" else collect_aireos
            got = fn(c["name"], c["host"], credentials[c["name"]])
            print(f"  {len(got)} APs")
            rows.extend(got)
            statuses.append({**c, "status": "complete", "ap_count": len(got), "error": ""})
        except Exception as e:  # noqa: BLE001 - report and keep going
            print(f"  FAILED: {e}")
            failures.append(label)
            statuses.append({**c, "status": "failed", "ap_count": 0, "error": type(e).__name__})

    config.OUTPUT.mkdir(exist_ok=True)
    out = config.OUTPUT / "ap_inventory.csv"
    temp = out.with_suffix(".csv.tmp")
    with open(temp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    manifest = {
        "source": "controller SSH",
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "complete": not failures,
        "inventory_sha256": hashlib.sha256(temp.read_bytes()).hexdigest(),
        "controllers": statuses,
    }
    status = config.OUTPUT / "collection_status.json"
    status_temp = status.with_suffix(".json.tmp")
    status_temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # A crash between replacements is detected by the report's hash check.
    temp.replace(out)
    status_temp.replace(status)
    print(f"\nWrote {len(rows)} APs to {out}")
    if failures:
        print("Controllers that failed (rerun after fixing):")
        for x in failures:
            print(f"  - {x}")
        sys.exit(1)


if __name__ == "__main__":
    main()
