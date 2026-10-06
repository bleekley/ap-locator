"""Parsers for controller CLI output. Pure functions: text in, list-of-dicts out.

Every parser returns rows in the ONE shared schema:
  controller, ap_name, model, eth_mac, ap_ip, state,
  neighbor_name, neighbor_ip, neighbor_port
"""
import re

MAC_DOT = r"[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}"
MAC_COLON = r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}"
IP = r"\d{1,3}(?:\.\d{1,3}){3}"


def norm_mac(mac: str) -> str:
    """Normalize any MAC format to lowercase aabb.ccdd.eeff."""
    hex_only = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    if len(hex_only) != 12:
        return mac.lower()
    return f"{hex_only[0:4]}.{hex_only[4:8]}.{hex_only[8:12]}"


# ---------------- 9800 (IOS-XE) ----------------

def parse_9800_ap_summary(text: str) -> list[dict]:
    rows = []
    pat = re.compile(
        rf"^(\S+)\s+\d+\s+(\S+)\s+({MAC_DOT})\s+{MAC_DOT}\s+\S+\s+\S+\s+({IP})\s+(\S+)",
        re.M,
    )
    for m in pat.finditer(text):
        rows.append(
            {
                "ap_name": m.group(1),
                "model": m.group(2),
                "eth_mac": norm_mac(m.group(3)),
                "ap_ip": m.group(4),
                "state": m.group(5),
            }
        )
    return rows


def parse_9800_cdp(text: str) -> dict[str, dict]:
    """show ap cdp neighbor -> {ap_name: {neighbor_name, neighbor_ip, neighbor_port}}"""
    out = {}
    pat = re.compile(rf"^(\S+)\s+{IP}\s+(\S+)\s+({IP})\s+(.+?)\s*$", re.M)
    for m in pat.finditer(text):
        if m.group(1).lower() in ("ap", "number"):
            continue
        out[m.group(1)] = {
            "neighbor_name": m.group(2),
            "neighbor_ip": m.group(3),
            "neighbor_port": m.group(4),
        }
    return out


# ---------------- AireOS (2504 / 5508 etc.) ----------------

def parse_aireos_ap_summary(text: str) -> list[dict]:
    rows = []
    pat = re.compile(
        rf"^(\S+)\s+\d+\s+(\S+)\s+({MAC_COLON})\s+.+?\s+(?:US|\S\S)\s+({IP})\s+\d+",
        re.M,
    )
    for m in pat.finditer(text):
        rows.append(
            {
                "ap_name": m.group(1),
                "model": m.group(2),
                "eth_mac": norm_mac(m.group(3)),
                "ap_ip": m.group(4),
                "state": "Registered",
            }
        )
    return rows


def parse_aireos_cdp_detail(text: str) -> dict[str, dict]:
    """show ap cdp neighbors detail all -> {ap_name: {...}}

    Blocks look like:
      AP Name:AP1700-BLDG1
      AP IP address:10.10.10.5
      Device ID: SW-BLDG1.example.gov
      Entry address(es): 10.20.1.2
      Port ID (outgoing port): GigabitEthernet1/0/12
    """
    out = {}
    blocks = re.split(r"(?=AP Name\s*:)", text)
    for b in blocks:
        name = re.search(r"AP Name\s*:\s*(\S+)", b)
        dev = re.search(r"Device ID\s*:\s*(\S+)", b)
        # IP is inline ("Entry address(es): 1.2.3.4") on some builds, or on
        # the following line ("Entry address(es):\n  IP address: 1.2.3.4")
        addr = re.search(rf"Entry address\(es\)\s*:\s*(?:\n\s*IP address\s*:\s*)?({IP})", b)
        # port value may contain spaces, e.g. "Port 7" on Meraki/unmanaged gear
        port = re.search(r"Port ID \(outgoing port\)\s*:\s*(.+?)\s*$", b, re.M)
        if name and dev:
            out[name.group(1)] = {
                "neighbor_name": dev.group(1),
                "neighbor_ip": addr.group(1) if addr else "",
                "neighbor_port": port.group(1) if port else "",
            }
    return out


# ---------------- merge ----------------

def merge(controller: str, aps: list[dict], cdp: dict[str, dict]) -> list[dict]:
    rows = []
    for ap in aps:
        n = cdp.get(ap["ap_name"], {})
        rows.append(
            {
                "controller": controller,
                **ap,
                "neighbor_name": n.get("neighbor_name", ""),
                "neighbor_ip": n.get("neighbor_ip", ""),
                "neighbor_port": n.get("neighbor_port", ""),
            }
        )
    return rows


def checked_output(text: str) -> str:
    """Reject CLI errors instead of interpreting them as empty tables."""
    if re.search(
        r"(?im)^\s*%|authorization failed|not authorized|permission denied|"
        r"invalid (?:input|command)|unknown command|command not found|"
        r"incomplete command|ambiguous command|incorrect usage|syntax error",
        text,
    ):
        raise ValueError("Device rejected a show command; check account privileges and software syntax.")
    return text


def validated_summary(text: str, parser) -> list[dict]:
    checked_output(text)
    count = re.search(r"Number of APs\s*[.:]*\s*(\d+)\b", text, re.I)
    if count is None:
        raise ValueError("Unrecognized AP summary: missing declared AP count.")
    rows = parser(text)
    if len(rows) != int(count.group(1)):
        raise ValueError(f"AP summary count mismatch: controller declares {count.group(1)}, parsed {len(rows)}.")
    if len({r["ap_name"] for r in rows}) != len(rows):
        raise ValueError("AP summary contains duplicate names.")
    return rows
