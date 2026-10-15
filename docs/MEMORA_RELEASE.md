# Building memora 1.0.1

The public release uses an allowlisted source snapshot and a Windows x64 Electron directory
containing a frozen Python backend. Runtime data and model weights are excluded.

## Build

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python -m pip install -e . pyinstaller build
# Build native with compiler path remapping; Rust and MSVC are required.
$env:RUSTFLAGS="--remap-path-prefix=$env:USERPROFILE=build-user --remap-path-prefix=$PWD=memora-source"
.venv/Scripts/python -m pip install ./native
npm --prefix frontend ci
npm --prefix frontend run build
.venv/Scripts/python tools/build_architecture.py
.venv/Scripts/python -m unittest discover -s tests -v
.venv/Scripts/python tools/build_desktop.py
.venv/Scripts/python tools/dependency_inventory.py
.venv/Scripts/python tools/release_memora.py
```

`tools/build_desktop.py` creates an isolated source snapshot under the build directory before
freezing Python, so embedded Python code filenames do not contain the developer's home directory.
It copies only `memory_merge` source and prebuilt static assets. The Electron renderer has
Node integration disabled, context isolation and sandboxing enabled, and navigation restricted
to its own loopback backend. The shell owns and shuts down its backend process.

## Release contents

- `memora-1.0.1-source.zip`: source, both READMEs, licenses, dependency inventory, tests, graph source
  copies and prebuilt graph assets. The upstream AI dictionary dataset is excluded.
- `memora-1.0.1-windows-x64.zip`: unpack and run `Memora.exe`; no Python installation is required.
- `SHA256SUMS`, `RELEASE_VALIDATION.json`, `RELEASE_MANIFEST.json`: integrity and privacy checks.

Version 1.0.1 ships Web and Electron. Tauri, rerankers, autonomous tool execution, generic MCP
client orchestration and universal agent-database discovery are extension directions, not delivered
capabilities. Optional model inference libraries and weights are not bundled in the desktop release.

The document workspace has its own version database and immutable Markdown mirrors. Runtime
`documents/` content and all three databases are excluded from distribution. See
[compatibility boundaries](COMPATIBILITY.md) and [graph repairs](GRAPH_REPAIRS.md).

## Privacy validation

The source and desktop packages are built from explicit allowlists. Private archives, sources,
databases, keys, environment files, model profiles, build logs, local paths, screenshots containing
private data and caches are excluded. Compiler home paths in inherited WASM are sanitized in the
copied asset before bundling. Known secret patterns and workstation markers are checked in source,
embedded WASM and unpacked binaries. Validation output contains paths relative to the release only.

Pattern scans have limits and do not prove all possible private identifiers are absent. The public
artifact contains only application code, synthetic test fixtures and attributed dependencies.

## Publishing

After explicit user acceptance of privacy and functionality, publish the sanitized source snapshot to the public `Stark-work-1001/memora` repository.
Create the `v1.0.1` tag and release using the bilingual release notes, upload the validated
assets, then verify the published files and asset checksums. If approved, publication uses
GitHub's browser interface using an existing signed-in session. No additional CLI token, OAuth
grant or deployment key is required.

All cited project repositories, project links and open-source approaches are listed in both READMEs,
the release notes and `docs/OPEN_SOURCE_REUSE.md`; complete installed dependencies are enumerated
in `docs/DEPENDENCIES.md` and their corresponding license bundles.
