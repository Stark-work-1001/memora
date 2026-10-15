# memora v1.0.1 · Windows standalone release guide

This is the end-user guide. Repository architecture is documented in the source README.
All referenced projects, links and approaches are in [the reference inventory](docs/OPEN_SOURCE_REUSE.md);
licensing is in [third-party notices](THIRD_PARTY_NOTICES.md).

## Unpack and run

1. Extract `memora-1.0.1-windows-x64.zip`, keeping the entire directory together.
2. Launch `Memora.exe`. Python, Node, Rust and development tools are not required.
3. Choose local/cloud, protocol, endpoint and model in Model Assembly, then probe the service.
   No weights, keys, personal records or preconfigured private endpoints are included.

The bundled runtime runs the application; it does not bundle every inference engine or model.
Default model cards are templates, not detected live services. In-process GGUF bindings/GPU drivers
are optional; existing Ollama, llama-server or compatible HTTP services can be connected without them.
Cloud traffic requires explicit HTTPS configuration; keys come from the launching process environment.

This generic frozen build uses external services for GGUF inference. In-process GGUF requires
the optional binding in a source environment and a corresponding build. The Rust vector extension
is already bundled and is a separate component.

## Changes

- Compiled Rust vector top-k and RRF included; writable-buffer concurrency fixed.
- Peer heartbeat, resource tabs, logical project conversations, task leases and user responses.
- Ten model roles and editable workflows, external dispatcher confirmation and per-stage traces.
- Immutable Markdown revisions with original dates, source references and project titles.
- 2D/3D graphs, layouts, local best-view camera fitting, depth fog and directional hierarchy flow.
- Existing Memory Merge v2 memory schema and review APIs retained; new metadata uses sidecar stores.

## Upgrade and operate

Close the old app and back up private data first. Run the new version from a fresh extraction;
the existing application data directory remains in use. Its actual location is shown under storage
maintenance. The 1.0.0 baseline is preserved separately. Do not overlay old program files onto the
new extraction. See [operations](docs/OPERATIONS_1.0.1.md) for all three database backups/restoration.

MCP clients and the desktop must point to the same private data directory to share state. Cloud bots,
mobile clients and remote servers require their own client adapters. No universal agent discovery or
remote control is implied.

## Validation and limitations

Verify SHA256SUMS, RELEASE_VALIDATION.json and SMOKE_VALIDATION.json. Outputs are built without
private runtime data and scanned as described in [delivery/redaction](docs/DELIVERY_1.0.1.md).
Pattern checks are not a guarantee that every semantic identifier can be detected. Live cloud
credentials, every GPU/model and every Windows device are outside automated coverage. Workflows
have an explicit 30,000-character source limit; split long documents before running. A2A compliance,
a Tauri binary and arbitrary remote tool execution are not claimed.

New code is Apache-2.0; inherited licenses remain. Publication awaits the user's acceptance of
both public source and release privacy/quality.
