# GEDCOM Network Editor — Plan

## Status: COMPLETE ✓

All implementation steps done. File: `familyTree/gedcom-editor.html`

---

## Context
Browser-based GEDCOM editor styled after the existing D3 network plots
(`Fernandez-Alvarez-network.html`, `Molina-Prous-network.html`). Load any GEDCOM file,
view it as an interactive force-directed graph, select a person to focus on, control how
many relationship hops are visible, edit that person's data, and export the modified GEDCOM.

---

## Architecture: single-file pure-browser app

```
┌─────────────────────────────────────────────────────────────┐
│  Header: [Open GEDCOM] · stats · hops slider · controls     │
├──────────────────┬──────────────────────────────────────────┤
│  Edit Panel      │  D3 Network Canvas                       │
│  (slide-in,      │                                          │
│   280px wide)    │  BEFORE selection:                       │
│                  │   Search: [          ]                   │
│  Fields:         │   ← select a person to start            │
│  • Given name    │                                          │
│  • Surname       │  AFTER selection:                        │
│  • Sex           │  • N-hop subgraph around selected person │
│  • Birth date    │  • Selected node: gold ring, larger      │
│  • Birth place   │  • Marriage edges (orange solid)         │
│  • Death date    │  • Parent→child (green dashed+arrow)     │
│  • Death place   │  • Other networks: grey, dimmed (35%)   │
│  • Note          │                                          │
│  ─── Links ───   │                                          │
│  • Spouses list  │                                          │
│    [+ add] [x]   │                                          │
│  • Children list │                                          │
│    [+ add] [x]   │                                          │
│  • Parents list  │                                          │
│    [+ add] [x]   │                                          │
│                  │                                          │
│  [Save person]   │                                          │
│  [Export GEDCOM] │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## Data model (in-memory after parsing)

```javascript
persons = {
  '@I0001@': {
    id, givn, surn, sex, birth_date, birth_plac,
    deat_date, deat_plac, note,
    fams: ['@F0001@'],  // families as spouse
    famc: ['@F0000@'],  // family as child
    raw_lines: [...]    // original GEDCOM lines for round-trip
  }
}

families = {
  '@F0001@': { id, husb, wife, chil: [], marr_date, marr_plac, raw_lines: [] }
}
```

---

## Implemented features

### GEDCOM parser ✓
- `<input type="file" accept=".ged">` + `FileReader` API — fully offline, no server
- Parse line-by-line: `level xref tag value`
- Populates `persons` and `families` maps
- Stores `raw_lines` per record for safe round-trip export

### Initial state & person search ✓
- On file load: canvas shows a centred search box (translated per active language)
- Real-time filtering → dropdown list of matches (name + ID)
- Clicking a result selects that person → triggers N-hop subgraph render

### N-hop neighborhood filter ✓
- BFS over family graph: FAMS→FAM→(HUSB/WIFE/CHIL) and FAMC→FAM→(HUSB/WIFE)
- Slider range: 1–6 hops, default 2
- Selection change OR hop change → recompute subgraph → restart D3 simulation

### D3 network rendering ✓
- D3 v7 from CDN; force simulation: link distance 80, charge -200, collision 14
- Node colours: M=#3b82f6, F=#ec4899, U=#6b7280
- Selected node: gold (#fbbf24) stroke + larger radius (10px vs 6px)
- Marriage edges: orange solid (#d97706); parent→child: green dashed (#34d399) + arrowhead
- Drag to pin/unpin; zoom + pan on background drag
- Dead persons: small ✝ cross marker

### "Otras redes" checkbox ✓
- Default checked; shows all disconnected connected components alongside selected subgraph
- Other-network nodes rendered with: 35% opacity, dark grey fill (#374151), dashed stroke
- Other-network links rendered at 20% opacity
- Other-network labels dimmed (#4b5563)

### Edit panel ✓
- Slides in from left on node click (CSS `transform: translateX`)
- Person fields: given name, surname, sex (select), birth date, birth place, death date, death place, note (textarea)
- Links section: spouses / children / parents with [✕ remove] and [+ Add …] buttons
- Add buttons open inline search modal → creates/updates FAM records
- [Save person] writes changes back to `persons` map, re-renders
- [Export GEDCOM] reconstructs full GEDCOM and triggers `<a download>` save
- [+ New person] creates a blank INDI record

### Internationalisation (i18n) ✓
- Language selector (EN / DE / ES) in header; default EN
- `LANGS` object contains all UI strings for all three languages
- `t(key)` helper returns current-language string
- `applyLang()` updates all `[data-i18n]`, `[data-i18n-placeholder]`, `[data-i18n-title]` elements on switch
- All dynamic JS strings (tooltip labels, stats bar, modal titles, new-person defaults, remove-link tooltips) use `t()`
- Export date locale follows selected language (en-GB / de-DE / es-ES)

### GEDCOM export (round-trip) ✓
- Iterates `raw_lines` per record; substitutes edited field values in-place
- Inserts new lines for added fields (e.g. new death date)
- Reassembles header + all INDI records + all FAM records + TRLR
- Downloads as `<original-filename>-edited.ged`

---

## Controls (header bar)

| Control | Purpose |
|---------|---------|
| `<input type="file">` | Load GEDCOM file |
| Hops slider (1–6) | N-hop neighbourhood depth |
| Force slider | Repulsion strength |
| Link distance slider | Edge length |
| Names checkbox | Show/hide labels |
| Other networks checkbox | Show/hide disconnected networks (dimmed) |
| Search box | Highlight matching nodes |
| Reset button | Clear pins, fit graph |
| Language selector (EN/DE/ES) | Switch UI language; default EN |

---

## Implementation steps (all complete ✓)

1. ✓ HTML skeleton: header bar, side panel div, SVG canvas, search overlay
2. ✓ CSS: dark theme, slide-in panel, search overlay, tooltip
3. ✓ JS GEDCOM parser: `parseGED(text)` → `{persons, families}` with `raw_lines`
4. ✓ `buildFullGraph()` → `{allNodes, allLinks}`
5. ✓ `getNeighbors(personId, hops)` BFS traversal
6. ✓ `renderSubgraph(personId, hops)` → D3 simulation with zoom/drag
7. ✓ Search overlay: filter → dropdown → select person
8. ✓ Edit panel: person fields form + links section
9. ✓ Link editing: `addSpouse`, `removeSpouseLink`, `addChild`, `removeChildLink`, `addParent`, `removeParentLink`
10. ✓ `savePersonEdits()` → write form → persons map, refresh subgraph
11. ✓ `exportGED()` → reconstruct GEDCOM, download
12. ✓ "Other networks" feature: show all disconnected components, visually dimmed
13. ✓ i18n: EN / DE / ES language selector; all UI strings translated via `LANGS` + `t()`

---

## Verification

- Open `gedcom-editor.html` in browser
- Load `Fernandez-Alvarez.ged` (37 persons — small, good for testing)
- Verify all 37 nodes appear; zoom/pan works
- Click a node → panel opens with correct data, graph shrinks to N-hop neighbourhood
- Change hops slider → graph updates
- Check "Otras redes" → disconnected networks appear as dim grey clusters
- Edit a field, click Save → tooltip and label update immediately
- Click Export → download file; open in Gramps to confirm validity
- Repeat with `Molina-Prous.ged` (110 persons) for larger file handling
