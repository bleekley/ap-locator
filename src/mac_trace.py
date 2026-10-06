"""Fallback for APs with no CDP data: trace an AP's wired MAC through switch
MAC address tables to obtain a candidate port for manual verification.

Usage: python src/mac_trace.py <ap_eth_mac> <seed_switch_ip>

Logic: log into the seed switch, find which port the MAC lives on.
If that port is a trunk/uplink with a CDP neighbor that is a switch,
hop to that neighbor and repeat. Missing neighbor data leaves the
location unresolved and requires manual verification. Uses SWITCH_* creds from .env
(falls back to WLC_* creds).
"""
import re
import sys

from netmiko import ConnectHandler

import config
from parsers import checked_output, norm_mac

MAX_HOPS = 10


def find_port(conn, mac: str) -> str | None:
    out = checked_output(conn.send_command(f"show mac address-table address {mac}"))
    ports = set()
    for line in out.splitlines():
        if mac.lower() not in line.lower():
            continue
        m = re.search(r"\s([A-Za-z]+[\d/]+|Port-channel\d+)\s*$", line)
        if m:
            ports.add(m.group(1))
    if len(ports) > 1:
        raise ValueError("MAC is learned on multiple ports; location is unresolved.")
    return next(iter(ports), None)


def cdp_switch_on_port(conn, port: str) -> str | None:
    out = checked_output(conn.send_command(f"show cdp neighbors {port} detail"))
    neighbors = []
    for block in re.split(r"(?=Device ID:)", out):
        if not re.search(r"Capabilities:.*\bSwitch\b", block, re.I):
            continue
        ip = re.search(r"IP address:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if not ip:
            raise ValueError("Switch neighbor has no management IP; location is unresolved.")
        neighbors.append(ip.group(1))
    if len(neighbors) > 1:
        raise ValueError("Multiple switch neighbors; location is unresolved.")
    return neighbors[0] if neighbors else None


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: python src/mac_trace.py <ap_eth_mac> <seed_switch_ip>")
    mac = norm_mac(sys.argv[1])
    if not re.fullmatch(r"[0-9a-f]{4}(?:\.[0-9a-f]{4}){2}", mac):
        sys.exit("Provide a valid 12-digit wired MAC address.")
    host = sys.argv[2]
    cred = config.creds("SWITCH")

    visited = set()
    for hop in range(1, MAX_HOPS + 1):
        if host in visited:
            sys.exit(f"UNRESOLVED: switch loop at {host}.")
        visited.add(host)
        conn = ConnectHandler(device_type="cisco_xe", host=host, **cred)
        try:
            hostname = conn.find_prompt().strip("#>")
            port = find_port(conn, mac)
            if not port:
                sys.exit(f"Hop {hop}: {hostname} ({host}) has no entry for {mac}. "
                         "Is the AP up? MAC tables age out after ~5 min of silence.")
            nxt = cdp_switch_on_port(conn, port)
        except ValueError as e:
            sys.exit(f"UNRESOLVED: {hostname} ({host}): {e}")
        finally:
            conn.disconnect()
        if nxt:
            print(f"Hop {hop}: {hostname} ({host}) port {port} -> next switch {nxt}")
            host = nxt
        else:
            sys.exit(f"UNRESOLVED: MAC {mac} is learned on {hostname} ({host}) port {port}, "
                     "but no next switch could be established. Verify the interface, downstream "
                     "topology and AP identity manually; this is not a confirmed AP access port.")
    sys.exit(f"Gave up after {MAX_HOPS} hops (loop?).")


if __name__ == "__main__":
    main()
