"""Offline tests: run the AireOS parsers against the saved fixture files.
Run: .venv/bin/python src/test_parsers.py
Use sanitized captures for parser regressions; never commit raw private output.
"""
from pathlib import Path

import parsers

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def main() -> None:
    aps = parsers.parse_aireos_ap_summary((FIX / "aireos_ap_summary.txt").read_text())
    cdp = parsers.parse_aireos_cdp_detail((FIX / "aireos_cdp_detail.txt").read_text())
    rows = parsers.merge("test-2504", aps, cdp)

    assert len(rows) == 3, f"expected 3 APs, got {len(rows)}"
    by = {r["ap_name"]: r for r in rows}
    a = by["BLDG1-FL2-AP01"]
    assert a["eth_mac"] == "f07f.0611.2233", a["eth_mac"]
    assert a["model"] == "AIR-CAP1702I-B-K9"
    assert a["neighbor_name"] == "SW-BLDG1-IDF2.example.org"
    assert a["neighbor_ip"] == "10.20.1.2"
    assert a["neighbor_port"] == "GigabitEthernet1/0/12"
    b = by["BLDG2-FL1-AP03"]
    assert b["neighbor_name"] == "SW-BLDG2-MDF"
    assert b["neighbor_port"] == "GigabitEthernet1/0/24"
    assert parsers.norm_mac("F0:7F:06:11:22:33") == "f07f.0611.2233"
    assert parsers.norm_mac("84f1.47c0.28fc") == "84f1.47c0.28fc"
    # sanitized 2504 output captured 2026-10-02 (next-line IP, space in port name)
    real = parsers.parse_aireos_cdp_detail((FIX / "aireos_cdp_detail_SANITIZED.txt").read_text())
    r = real["AP0200.0000.0001"]
    assert r["neighbor_name"] == "020000000002", r
    assert r["neighbor_ip"] == "192.0.2.30", r
    assert r["neighbor_port"] == "Port 7", r
    print("AireOS parser tests: ALL PASS (fixtures + sanitized 2504 capture)")


if __name__ == "__main__":
    main()
