# memora 1.0.1 — execution and acceptance plan

Development continues in the relocated development directory. The original 1.0.0
source archive, validated Windows archive and unpacked desktop application are
preserved separately before any new code changes. Reference directories remain read-only.

| Requirement | Implementation boundary | Acceptance evidence |
| --- | --- | --- |
| Rust retrieval | Build and ship the existing PyO3 kernel; harden buffers and validation, extend native fusion; keep SQLite and memory schema compatible | Kernel parity, invalid-input tests, benchmarks, frozen executable kernel report |
| Workbench state | Distinguish dialogue, configured models, detected services, MCP peer heartbeats and imported archives | No fabricated connected status; TTL and peer tests |
| Model assembly | Explain Embedding/Judge/Router; editable additional roles and bounded workflows; external peer can dispatch using its own model | Per-stage input/output/model audit, validated plans, no generated SQL execution |
| Knowledge structure | Preserve six base memory categories; add domain/resource/level facets and typed directional hierarchy | Cycle rejection, provenance, cross-domain search option, no change to original review authority |
| Dated Markdown | Keep source dates and immutable versions; model reorganization creates a new draft; two-level collection summaries | Date preservation and historical-content tests |
| Brain | Rename navigation; 2D/3D and layout selection; selected-neighbour camera fitting and rotation; distance fog; directed hierarchy flow | Browser interactions, geometry checks, offline asset checks |
| Local agent resources | Tabs for Chat, Env, Skill, MCP, Plugin, Ghost, Organization, Subagent and processing history | Filter tests; declarative descriptions never execute |
| Conversations | Logical thread groups, projects, dates, agent, progress, intervention and valid origin links | Multiple-model turns remain in one logical thread; unknown states remain unknown |
| Remote peers | Separate MCP tools from agent task coordination; authenticated optional HTTP bridge for local/cloud/mobile peers | Authentication, task ownership, leases, retries and intervention states |
| Maintenance | Inventory and backup all stores, mirror recovery, processing records and installed runtime | Backup integrity and restore tests |
| Public delivery | Bilingual repository overview, technology decisions, research, plan and changelog; separate release guides | Allowlist, provenance/license review, privacy rules, SHA-256 and standalone smoke tests |

The supplied data-deidentification guide governs public and release outputs. Its
private copy, scraped website bundles, real archives, credentials, source roots,
development environments and build caches are excluded. Public attribution required
by licenses and synthetic fixtures are retained with their purpose documented.

Judge is advisory classification/verification; Router selects a permitted destination.
Neither the choice of a faster language nor a small model alone establishes correctness.
Memory hierarchy is a typed DAG, not proof that two nearby vectors have a causal link.
Domain filtering is optional: partition-first retrieval can lose cross-domain evidence.

No GitHub upload is part of local delivery until the user accepts the result.

## Implemented and checked

Backend suite: 136 tests run, 135 passing and one optional/platform-dependent skip. Frontend suite: six passing tests, including portrait/wide camera fitting. Hidden Electron interaction checks cover all main views, cloud configuration, ten role selectors, resource filtering, three dictionary layouts, 23 hierarchy layouts, and the 2D projection; no renderer console errors were captured. Frozen-runtime smoke and real authenticated MCP HTTP checks accompany the delivery. Detailed hashes and final test counts are generated into RELEASE_VALIDATION.json, not inferred from this plan.

Bounded implementation: one workflow document is limited to 30,000 characters; tasks are cooperative leased work, not arbitrary remote execution; hierarchy is recorded/visualized but does not inject unverified graph scores into retrieval; unrecorded tool definitions and unknown client states remain unknown.
