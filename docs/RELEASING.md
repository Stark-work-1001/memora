# Releasing

One version string, defined in `memory_merge/__init__.py` (PEP 440, e.g. `0.2.0a1`). The git tag is
`v` + that string (`v0.2.0a1`). `pyproject.toml` reads the version from the code; `tools/release.py`
refuses to build if `CHANGELOG.md` or the release notes name a different version.

(0.1 shipped with three strings for one release: tag `0.1.0`, documents `v0.1.0-alpha.1`, package
`0.1.0a1`. They all denote the same code; see CHANGELOG.md.)

## Build

```bash
python tools/release.py
```

The script:

1. collects files by allowlist (`INCLUDE` patterns) and fails on any unexpected file, symlink or CRLF
   line ending (hashes must not depend on the checkout platform; `.gitattributes` pins LF);
2. scans every included file for machine paths, emails, phone numbers, token patterns and private
   markers (per-file exemptions only for path-validation test fixtures);
3. checks the version in CHANGELOG.md and both release notes, and that local Markdown links resolve;
4. runs the full test suite from the checkout;
5. builds a ZIP with fixed metadata twice and requires identical bytes;
6. verifies every archive entry against its source, unpacks it, and runs the test suite again from the
   unpacked tree;
7. writes `dist/memory-merge-vX-source.zip`, `dist/SHA256SUMS`, `dist/RELEASE_VALIDATION.json`;
   the per-file manifest is inside the archive as `RELEASE_MANIFEST.json`.

Nothing is uploaded or tagged.

## Publish (manual)

1. Commit, push, and let CI pass on all three platforms.
2. `git tag v0.2.0a1 && git push origin v0.2.0a1`.
3. Create a GitHub Release from the tag, **mark it Pre-release** for any `a`/`b`/`rc` version, attach
   the ZIP and `SHA256SUMS`, paste `RELEASE_NOTES.en.md` and `RELEASE_NOTES.zh-CN.md`.
4. Download the attached ZIP and compare its SHA-256 with `SHA256SUMS`.
5. Optional: build the wheel (`python -m build`) and publish to PyPI; the package name is
   `memory-merge-local`. Not done for 0.2.0a1.

The published 0.1 release (`memory-merge-v0.1.0-alpha.1`) is marked as a full release although its
own guide asked for Pre-release; correcting that flag on GitHub is a manual step for the maintainer.
