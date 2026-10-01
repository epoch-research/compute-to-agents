# Dataset License — Creative Commons Attribution 4.0 International (CC BY 4.0)

The **TraceLab public coding-agent trace dataset** — the sanitized, normalized JSONL
trace and the prebuilt DuckDB database distributed as GitHub Release assets (e.g.
`syfi_coding_trace.jsonl.gz` and `syfi_coding_trace.duckdb`) — is licensed under the
**Creative Commons Attribution 4.0 International License (CC BY 4.0)**.

> Note: This dataset license applies to the **released trace data only**. All source
> code in this repository (collection, sanitization, analysis, validation, and the web
> app) is licensed separately under the Apache License 2.0 — see [`LICENSE`](LICENSE).

## You are free to

- **Share** — copy and redistribute the material in any medium or format.
- **Adapt** — remix, transform, and build upon the material for any purpose, even
  commercially.

The licensor cannot revoke these freedoms as long as you follow the license terms.

## Under the following terms

- **Attribution** — You must give appropriate credit, provide a link to the license,
  and indicate if changes were made. You may do so in any reasonable manner, but not in
  any way that suggests the licensor endorses you or your use.
- **No additional restrictions** — You may not apply legal terms or technological
  measures that legally restrict others from doing anything the license permits.

Full legal text: https://creativecommons.org/licenses/by/4.0/legalcode

## How to attribute

When you use the dataset, please credit **TraceLab (SyFI Lab, University of Washington)**
and link back to <https://tracelab.cs.washington.edu>. A formal citation entry will be
added later.

## Privacy & responsible use

The dataset is built from real Claude Code / Codex sessions that have been **sanitized**:
session, round, turn, tool-call, project, and user identifiers are replaced with stable
pseudonyms, and local context (paths, `cwd`, tool inputs, etc.) is stripped before
release. Even so, please use the data responsibly and do not attempt to re-identify
contributors.
