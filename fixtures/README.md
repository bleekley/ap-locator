# Public test fixtures

All street addresses are fictional. Do not add original lab/customer captures here.
Use the Git-ignored `private/` directory for local material, then sanitize before
creating a public fixture.

| File | Provenance |
|---|---|
| `aireos_ap_summary.txt` | Synthetic AireOS summary for three AP model families |
| `aireos_cdp_detail.txt` | Synthetic CDP neighbors; inline management IP format |
| `aireos_cdp_detail_SANITIZED.txt` | Sanitized 2504 capture: next-line IP and a space-containing port name; names/IPs/MACs replaced |
| `9800_ap_summary_SYNTHETIC.txt` | Synthetic 9800 summary, not an original live capture |
| `9800_cdp_SYNTHETIC.txt` | Synthetic 9800 CDP output paired with the summary |
| `switch_inventory_SAMPLE.xlsx` | Fictional address mapping for the AireOS examples |

The sanitized 2504 fixture retains formatting relevant to parser behavior,
including `Entry address(es):` followed by an `IP address:` line and `Port 7`.
It is not a complete inventory or a CML topology export.
