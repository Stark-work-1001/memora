# Brain graph implementation and reference

Reference site: [The AI Coding Dictionary](https://www.aicodingdictionary.com/).
Its About panel links to [mattpocock/dictionary-of-ai-coding](https://github.com/mattpocock/dictionary-of-ai-coding).
Inspection on 2026-10-15 found dictionary content and tooling in that public repository,
but no top-level license or distributable frontend component source. Public page access
does not itself grant a license to republish the site's compiled application or content.
Memora therefore does not bundle that website's JavaScript, brand assets, audio or dataset.

The interaction reference is a quiet 3D term cloud, searchable concepts, selected-neighbour
emphasis, readable definitions, related-node navigation and optional section colors.
Memora implements these interactions using its existing attributed MIT graph copies,
Three.js and original controls in `frontend/graph-workbench.ts` / `.css`.

## Repairs in the copied code

- Added the missing `.om3d-*` standalone label styles and connected label clicks to selection.
- Added missing standalone pointer and keyboard navigation: drag to orbit, Shift/right-drag
  to pan, wheel or +/- to zoom, and Esc/Home to return to an overview.
- Added Chinese/English body and title search, keyboard result selection, purpose-specific
  layout selection, category color controls and clear operation hints.
- Initialized a light scene background, improved CJK label width estimation and adaptive
  label depth limits, and reserved camera margins for readable node names.
- Connected selected-node neighbourhood camera framing and refitted settled physics layouts.
- Removed per-frame inspector DOM replacement so rotating the graph does not interrupt clicks.
- Changed selected dictionary edges from additive blending to normal blending: dark links
  on a light background must remain visible.
- Made the dictionary detail pane responsive and reserved graph space for it; the pane
  breakpoint uses the stable host width to avoid oscillating between side and bottom layouts.
- Restricted Markdown links to safe schemes, escaped imported HTML and kept all assets local.

The outline retains its copied Rust/WASM physics engine and available layout algorithms;
the dictionary retains deterministic note-layout computation. Existing data content stays
quoted and cannot create new memory approval actions. Search, colors and layout choices
operate only on the current visual projection.

Synthetic preview data is stored outside release inputs. No real conversation is needed
to preview the workbench, and no user's archive is included in the screenshots or packages.


## 1.0.1

Added a Canvas 2D projection for semantics and typed hierarchy; three dictionary layouts; click focus chooses local orientation before fitting; camera-relative fog starts before the graph center; hierarchy focus chooses orientation and edges carry optional parent-to-child shader pulses. Existing 23 hierarchy layouts and copied Rust/WASM remain. Website bundles and dictionary data are not included. Original copies remain unmodified in the reference directory.
