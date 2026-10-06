# User guide

[Back to README](../README.md) · [Lab setup](LAB.md) · [Workflow](WORKFLOW.md)

## 1. Install

You need Python 3.10+, network reachability to controller management interfaces,
and an account permitted to execute the show commands listed below.

### macOS / Linux

```bash
git clone https://github.com/bleekley/ap-locator.git
cd ap-locator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
cp controllers.example.csv controllers.csv
```

### Windows PowerShell

```powershell
git clone https://github.com/bleekley/ap-locator.git
cd ap-locator
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item controllers.example.csv controllers.csv
```

Use `.\.venv\Scripts\python.exe` instead of `python` in the commands below if
your virtual environment is not activated. This avoids changing execution policy.

To preview the report without network access, run `python examples/offline_demo.py`.

## 2. Configure credentials

Edit `.env` locally:

```dotenv
WLC_USERNAME=inventory-user
WLC_PASSWORD='replace-with-your-password'
WLC_ENABLE='replace-with-enable-secret-if-required'
```

Use a read-only account with sufficient command authorization. The collectors
request show commands; Netmiko also performs platform-specific session preparation
such as pagination changes. Confirm the account works with those operations.
Providing an enable secret does not cause these scripts to call `enable()`.

Single-quote values containing spaces or `#` as appropriate for dotenv syntax.
Remove unused placeholder values. Environment variables already set in the shell
take precedence over `.env`.

If a controller needs separate credentials, derive the key from its name:
uppercase it and replace dashes with underscores. For controller `branch-2504`:

```dotenv
CRED_BRANCH_2504_USERNAME=legacy-inventory-user
CRED_BRANCH_2504_PASSWORD='replace-with-password'
CRED_BRANCH_2504_ENABLE='replace-if-required'
```

Set both override username and password. Otherwise the global credentials are used.
Optional `SWITCH_USERNAME`, `SWITCH_PASSWORD`, and `SWITCH_ENABLE` are used only
for MAC tracing; blank values fall back to the corresponding WLC credentials.

`.env`, `controllers.csv`, `output/`, and `fixtures/private/` are ignored by Git.
Do not force-add them. Git ignore rules are not a security boundary: inspect files
before sharing, avoid passwords in commands/issues, and retire engagement-specific
credentials when no longer needed.

## 3. List controllers

Edit `controllers.csv`:

```csv
name,host,type
hq-9800,192.0.2.10,9800
branch-2504,192.0.2.20,aireos
```

Replace the documentation addresses with reachable hosts. Required columns are
`name`, `host`, `type`; valid types are `9800` and `aireos`. Names and hosts must
be nonblank and unique. Invalid lists are rejected before collection.

## 4. Prepare switch inventory

Use `.xlsx` (first worksheet) or `.csv`. The required columns are:

| Column | Meaning |
|---|---|
| `hostname` | Switch name to match against the AP's CDP neighbor |
| `mgmt_ip` | Address advertised by the switch in CDP, when available |
| `street_address` | Site address to assign to APs attached to that switch |

Column names are normalized to lowercase with spaces converted to underscores.
Hostnames are case-insensitive; addresses are matched as text. Blank match keys
are ignored. Use unique keys: multiple matching rows are flagged as ambiguous,
even if they happen to contain the same address. Blank addresses remain unresolved.
Additional columns such as `site_code` or `owner` are copied into matched AP rows
with an `inventory_` prefix.

[Sample workbook](../fixtures/switch_inventory_SAMPLE.xlsx) contains fictional
addresses. Replace it with your actual inventory for live work and keep that file
outside the repository or in an ignored private directory.

## 5. Collect

```bash
python src/collect.py
```

| Controller type | Commands |
|---|---|
| `9800` | `show ap summary`, `show ap cdp neighbor` |
| `aireos` | `show ap summary`, `show ap cdp neighbors detail all` |

One SSH connection is opened per controller, sequentially. Controller-declared
AP totals must match parsed rows. A rejected command or unsupported summary format
fails that controller instead of being treated as zero APs. A declared zero-AP
controller is valid.

Outputs:

- `output/ap_inventory.csv`: AP rows from successful controllers.
- `output/collection_status.json`: every controller's result, error category,
  UTC timestamps, and CSV checksum.

A failed controller produces exit code 1 after the other controllers are attempted.
Fix the cause and rerun the whole list. Keep the CSV and status file together;
manually editing the CSV invalidates its checksum. These are overwritten on a new
run, so copy both elsewhere if you need an archive.

## 6. Build and read the report

```bash
python src/correlate.py path/to/switch_inventory.xlsx
```

Open `output/ap_location_report.xlsx`:

1. **Run Summary:** check source, timestamps, collection completeness, and match count.
2. **Controller Status:** verify every expected controller is listed and successful.
3. **AP Locations:** inspect `location_status`, match method, switch, and port.
4. **Per-Site Summary:** reconcile AP totals, including the UNKNOWN bucket.

Matching order is neighbor IP, exact hostname, then hostname with the DNS suffix
removed. The first matching key must identify a single inventory row; ambiguity
stops matching rather than falling through to a weaker key. A unique match with
no street address remains UNKNOWN. This is an inference from your inventory;
verify switch addresses and exceptional topologies before planning site work.

`COMPLETE` describes controller collection, not location certainty. The report
counts registered APs visible in the collected summaries; it is not an inventory
of powered-off or otherwise absent APs.

### Reviewing an incomplete run

Normal reporting refuses incomplete collection. If you deliberately want to inspect
the successful subset:

```bash
python src/correlate.py path/to/switch_inventory.xlsx --allow-partial
```

The workbook is labeled `INCOMPLETE - controllers failed`; use Controller Status
to see the omissions. Do not use that subset as a complete migration scope.

If reporting fails, an existing workbook remains unchanged. Always check its run
timestamp. Legacy CSVs without collection status require a fresh collection.

## 7. Investigate unresolved locations

First check for duplicated keys, incorrect inventory values, blank street addresses,
or missing CDP. If needed, investigate the AP's wired MAC:

```bash
python src/mac_trace.py aabb.ccdd.eeff 192.0.2.30
```

The seed must be a reachable switch in the AP's Layer 2 forwarding path. The tool
runs `show mac address-table address <mac>` and
`show cdp neighbors <port> detail`, then follows a unique switch neighbor.

It stops with a nonzero exit and `UNRESOLVED` when the next switch cannot be
established. The last learned port is a lead, not a confirmed AP access port.
Verify interface state, downstream topology and endpoint identity manually.
MAC aging, routed boundaries, missing CDP, port channels, ambiguous entries, and
loops can prevent progress. Live multi-switch traversal is still unverified.

## 8. Use model data for migration planning

The tool lists models; it does not classify replacement versus rejoin. Confirm the
exact AP/controller/software combination and distinguish joining capability from
Cisco support and your organization's lifecycle policy.

For example, Cisco's 17.12 release notes list 3800 APs. Wave 1 1700/2700/3700
joining is release-specific; from 17.12.4 through that train they can join without
TAC support. This is not a recommendation to deploy that release or those APs.
Consult [Cisco's compatibility matrix](https://www.cisco.com/c/en/us/td/docs/wireless/compatibility/matrix/compatibility-matrix.html)
and the [target release notes](https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/17-12/release-notes/rn-17-12-9800.html)
before finalizing a migration design or BOM.

## Troubleshooting

| Symptom | Next step |
|---|---|
| Missing credentials | Fill in `.env`; check for shell environment overrides |
| Invalid controller list | Correct headers, blank fields, types, or duplicate names/hosts |
| SSH failure | Verify routing, firewall rules, account permissions and controller SSH behavior |
| CLI rejected / AP count mismatch | Inspect controller output and software version; add a sanitized fixture before changing the parser |
| Missing/mismatched collection status | Rerun collection; keep its CSV and JSON together |
| Incomplete collection | Fix failed controllers; use `--allow-partial` only for intentional subset review |
| UNKNOWN location | Inspect `location_status`, CDP fields and inventory keys/address |
| No MAC entry | Check AP wired MAC, Layer 2 path, AP connectivity and MAC aging |

Before sharing a bug report, remove credentials, actual hostnames, IP/MAC addresses,
site addresses, and identifying metadata. See [contributing](../CONTRIBUTING.md).
