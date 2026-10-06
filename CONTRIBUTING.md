# Contributing

Start with a small, reproducible issue or pull request. Describe the controller
model/software version, expected behavior, actual behavior, and relevant exception
category. Do not publish private device data or credentials.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s src -p 'test_*.py'
python examples/offline_demo.py
```

No live credentials or network access are needed by the tests or demo. Python
3.10+ is supported; GitHub Actions exercises 3.10, 3.12, and 3.13.

## Parser changes

1. Sanitize a representative capture: replace real hostnames, IP/MAC addresses,
   site addresses, identifiers and metadata. Never include passwords or session logs.
2. Preserve whitespace, headings, table structure, and counts that reproduce the bug.
3. Add the fixture under `fixtures/` with provenance in its README. Distinguish
   synthetic examples from sanitized real captures.
4. Add a regression covering the failure and correct output. Preserve the
   declared-count checks; an unrecognized format must not silently become zero APs.
5. Run the full offline suite and update the user/lab guides if supported behavior changes.

Keep parsing separate from SSH operations. Do not put network calls in regression
tests. Preserve the distinction between a confirmed inventory match and unresolved
location evidence. Never assert successful physical placement from absent CDP.

## Before submitting

Inspect `git diff --cached` and `git diff --check`. Exclude `.env`, controller
lists, private captures, generated output, and customer inventories. Git ignore
rules do not prevent accidental forced additions. Any live validation report
should state exact software versions and topology limits without exposing secrets.
