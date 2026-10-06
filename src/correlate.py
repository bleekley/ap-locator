"""Correlate collected APs with switch inventory; retain collection provenance."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import config

UNKNOWN = "UNKNOWN - needs manual follow-up"
RESULT_COLUMNS = ["street_address", "matched_switch", "match_method", "location_status"]


def clean(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def load_inventory(path: Path) -> pd.DataFrame:
    df = (pd.read_excel(path, dtype=str, keep_default_na=False)
          if path.suffix.lower() == ".xlsx"
          else pd.read_csv(path, dtype=str, keep_default_na=False))
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("Switch inventory has duplicate normalized column names.")
    missing = {"hostname", "mgmt_ip", "street_address"} - set(df.columns)
    if missing:
        raise ValueError(f"Switch inventory is missing columns: {sorted(missing)}")
    for column in df.columns:
        df[column] = df[column].map(clean)
    df["hostname"] = df["hostname"].str.lower()
    return df


def match_row(ap: pd.Series, inv: pd.DataFrame) -> pd.Series:
    nip = clean(ap.get("neighbor_ip", ""))
    nname = clean(ap.get("neighbor_name", "")).lower()
    result = {"street_address": UNKNOWN, "matched_switch": "",
              "match_method": "no match", "location_status": "unmatched"}
    extras = [c for c in inv.columns if c not in {"hostname", "mgmt_ip", "street_address"}]
    result.update({f"inventory_{c}": "" for c in extras})
    for column, key, method in (
        ("mgmt_ip", nip, "neighbor IP"),
        ("hostname", nname, "hostname"),
        ("hostname", nname.split(".")[0], "hostname (domain stripped)"),
    ):
        if not key:
            continue
        hit = inv[inv[column] == key]
        if hit.empty:
            continue
        result["match_method"] = method
        if len(hit) > 1:
            result["location_status"] = "ambiguous inventory match"
            return pd.Series(result)
        r = hit.iloc[0]
        result["matched_switch"] = r["hostname"]
        result.update({f"inventory_{c}": r[c] for c in extras})
        address = clean(r["street_address"])
        if not address:
            result["location_status"] = "missing street address"
        else:
            result.update(street_address=address, location_status="matched")
        return pd.Series(result)
    return pd.Series(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("switch_inventory", type=Path)
    parser.add_argument("--allow-partial", action="store_true",
                        help="Explicitly generate a visibly incomplete report after controller failures.")
    args = parser.parse_args()
    inv = load_inventory(args.switch_inventory)
    ap_csv = config.OUTPUT / "ap_inventory.csv"
    status_file = config.OUTPUT / "collection_status.json"
    if not ap_csv.exists() or not status_file.exists():
        parser.error("Inventory and collection status are required. Run src/collect.py first.")
    status = json.loads(status_file.read_text(encoding="utf-8"))
    if status.get("inventory_sha256") != hashlib.sha256(ap_csv.read_bytes()).hexdigest():
        parser.error("Inventory does not match collection status. Rerun src/collect.py.")
    if not status.get("complete") and not args.allow_partial:
        parser.error("Collection is incomplete. Fix failed controllers and rerun, or use --allow-partial.")
    aps = pd.read_csv(ap_csv, dtype=str, keep_default_na=False)
    columns = RESULT_COLUMNS + [f"inventory_{c}" for c in inv.columns
                               if c not in {"hostname", "mgmt_ip", "street_address"}]
    matches = pd.DataFrame([match_row(ap, inv) for _, ap in aps.iterrows()], columns=columns)
    aps = pd.concat([aps, matches], axis=1)
    completeness = "COMPLETE" if status["complete"] else "INCOMPLETE - controllers failed"
    source = status.get("source", "controller SSH")
    aps["collection_source"] = source
    aps["collection_status"] = completeness
    aps["collected_utc"] = status["finished_utc"]
    site = (aps.groupby("street_address", dropna=False)
            .agg(ap_count=("ap_name", "size"),
                 models=("model", lambda s: ", ".join(sorted(set(s)))))
            .reset_index().sort_values("ap_count", ascending=False))
    site["collection_source"] = source
    site["collection_status"] = completeness
    site["collected_utc"] = status["finished_utc"]
    overview = pd.DataFrame([{
        "collection_status": completeness, "started_utc": status["started_utc"],
        "finished_utc": status["finished_utc"], "ap_count": len(aps),
        "matched_count": int((aps["location_status"] == "matched").sum()),
        "collection_source": source,
    }])
    out = config.OUTPUT / "ap_location_report.xlsx"
    temp = out.with_name("ap_location_report.tmp.xlsx")
    with pd.ExcelWriter(temp, engine="openpyxl") as xl:
        overview.to_excel(xl, sheet_name="Run Summary", index=False)
        pd.DataFrame(status["controllers"]).to_excel(xl, sheet_name="Controller Status", index=False)
        aps.to_excel(xl, sheet_name="AP Locations", index=False)
        site.to_excel(xl, sheet_name="Per-Site Summary", index=False)
    temp.replace(out)
    print(f"Wrote {out} ({completeness})")
    print(f"Matched {(aps['location_status'] == 'matched').sum()} of {len(aps)} APs to a street address.")
    for _, r in aps[aps["location_status"] != "matched"].iterrows():
        print(f"  - {r['ap_name']}: {r['location_status']} neighbor={r['neighbor_name']}/{r['neighbor_ip']}")


if __name__ == "__main__":
    main()
