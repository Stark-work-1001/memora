# Contributing

Thanks for helping. The project values honesty about capability over feature count.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    POSIX: . .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m unittest discover -s tests -v
```

Optional: `pip install ./native` (Rust toolchain) for the vector kernel; `pip install -e '.[pdf]'`
for PDF import.

## Rules of the house

1. **Tests with every change.** Fix a bug with a test that fails before the fix. Keep the original
   0.1 tests (`tests/test_store.py`, `test_providers.py`, `test_operations.py`,
   `test_integration.py`) passing unchanged; they encode the original contracts.
2. **Docs in the same change.** Stale docs are treated as defects.
3. **Do not weaken a safety property to ship a feature** (review gate, screening, fail-closed judge,
   no silent egress, honest erasure). If a feature seems to need it, redesign the feature or argue it
   in docs/DECISIONS.md first.
4. **Retrieval changes come with numbers.** Run
   `memory-merge eval --dataset datasets/memory-eval-v1 --split dev --modes "lexical"` before and
   after; tune on `dev` only and report `test` once. `tests/test_eval.py` fails if dev quality drops.
5. **Schema changes come with a migration** in `schema.py` and a test that upgrades a database
   written by the previous release (see `tests/test_schema.py`, which uses the frozen 0.1 code).
6. **Never call lexical retrieval semantic, and never claim what was not measured.**

## Style

Match the surrounding code: compact functions, comments that explain *why*, typed errors from
`memory_merge/errors.py`, no new runtime dependencies without a decision entry.

## Commit and PR

Use the PR template. Keep personal data, databases and `.env` files out of commits (`.gitignore`
covers the usual paths).
