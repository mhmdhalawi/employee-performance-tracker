# Final test handover

## Reproducible command

From a fresh checkout with `uv` installed, run:

```bash
uv run python -m unittest discover -s tests -v
```

`uv run` restores the locked Python environment as needed. The acceptance suite does not
require `OPENAI_API_KEY`: it replaces only the planning-model call with a fixed, validated
calculation plan, while retaining the real multipart API, XLSX/CSV parsing, dataset binding,
validation, filtering, and deterministic scoring path.

## Committed benchmark package

- `tests/fixtures/cedar_30_sanitized.json` defines 30 fictional employees and the guardrail
  cohorts. Names and evidence URLs are generated placeholders.
- `tests/fixtures/cedar_30_expected.json` pins expected KPI outputs, the 0.1 parity tolerance,
  and the two accepted workbook discrepancies.
- `tests/benchmark_fixture.py` deterministically expands the specification into the seven
  source tables and an in-memory XLSX workbook.
- `tests/test_benchmark.py` verifies all 30 results, EMP-027 through EMP-030 confidence gating,
  duplicate exclusion, traceability, and the EMP-027/EMP-029 exception allowlist.
- `tests/test_api_integration.py` verifies XLSX and CSV uploads, JSON persistence, latest-dashboard
  restoration, persisted-plan filter recalculation, employee/team/period filters, invalid rows,
  malformed and unsupported files, oversized uploads, and invalid filters.

The fixture is intentionally synthetic. It reproduces the agreed acceptance guardrails without
copying employee-level content from the confidential source workbook.

## Verified output

Final run: 2026-09-02, Python 3.14, Windows.

```text
----------------------------------------------------------------------
Ran 38 tests in 2.666s

OK
```

The run reproduced 30 employee results, four duplicate-attendance exclusions, and the 60%
confidence gate for EMP-027 through EMP-030. EMP-027 and EMP-029 are the only allowed parity
exceptions: production retains duplicate exclusion, with documented workbook compliance
differences of 0.2304 and 0.3789 respectively.
