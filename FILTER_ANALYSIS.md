# Filter System — Complete Analysis & UI Architecture

> **Generated**: February 2026  
> **Scope**: Screenshot analysis, filter logic, data flow, UX design, duplicate audit, full UI structure

---

## 1. Screenshot Analysis (Attached Image)

The screenshot captures the **column filter panel** for the **"Seeking Placement"** column in its **open/active state**. Here is exactly what is visible:

### Visual Breakdown (Top → Bottom)

| Zone | Element | Details |
|------|---------|---------|
| **Header Row** | Column headers | `SEEKING PLACEMENT` and `DEPARTMENT` are visible. Dark background (`#2a2a2a`), white uppercase text, 0.82rem font. |
| **Filter Row** | Filter buttons | Two buttons visible. The left one (Seeking Placement) shows **`▼ 1 sel`** with the `.cf-active` class (red border, red text, red-tinted background). The right one (Department) shows **`▼ All`** in default gray state. |
| **Panel** | `.cf-panel` | Red-bordered dropdown (`1px solid #e53935`), dark card background (`#1e1e1e`), 8px border-radius, 230px wide, heavy shadow (`0 8px 24px rgba(0,0,0,0.7)`). Positioned `fixed` on `<body>`, aligned just below the filter button. |
| **Search** | `.cf-search` | Text input with placeholder "Search values…". Dark surface background, subtle border, 0.78rem font. |
| **Batch Row** | `.cf-batch` | Two buttons side-by-side: **Select All** and **Deselect All**. Both have transparent background, 0.7rem font, 1px border. Uses `flex: 1` for equal width. |
| **Value List** | `.cf-list` | 7 unique values displayed as checkbox rows: `(Blank)`, `Debarded/Opted In`, `Debarded/Opted Out`, `Left`, `Not Registered`, **`Opted In`** ✅ (checked, red accent), `Opted Out`. Scrollable area capped at `max-height: 210px`. |
| **Footer** | `.cf-foot` | Left: **`2 / 7`** count (2 checked out of 7 total). Right: **Apply** button (red background `#e53935`, white text, 4px border-radius). Separated by a top border (`1px solid #3a3a3a`). |

### Key Observations from Screenshot

1. **The `1 sel` label on the button** means: After the last Apply, only 1 value was selected. The user has now checked a 2nd one ("Opted In") bringing the counter to `2 / 7`, but hasn't clicked Apply yet — so the button still says `1 sel`.
2. **The red checkbox accent** (`accent-color: var(--accent-red)`) makes the checked checkbox match the theme's primary red.
3. **`(Blank)` is unchecked** — the panel correctly treats empty/null values as a filterable `(Blank)` entry.
4. **(Blank) sorts first** — the sorting function puts empty strings before all other values (`if (a === '') return -1`).

---

## 2. Filter System — Complete Logic & Flow

### 2.1 Data Architecture

```
Server (Flask/MySQL)
    │
    ├── SELECT * FROM students ORDER BY sr_no
    │
    └── Jinja2 renders: {{ students_json | tojson }}
             │
             ▼
Browser (JavaScript)
    │
    ├── <script id="json-data" type="application/json">...</script>
    │         │
    │         ▼
    ├── LOCAL_DATA = JSON.parse(document.getElementById('json-data').textContent)
    │         │           ↑ Array of row objects [{sr_no:1, reg_no:"...", ...}, ...]
    │         │
    │         ├── Feeds DataTable:  table = DataTable({ data: LOCAL_DATA, ... })
    │         │
    │         └── Feeds Filters:   populateAllFilters() reads LOCAL_DATA
    │
    └── ACTIVE_FILTERS = {}   ← Global object tracking which columns have active filters
```

**Key Design Decision**: Data is embedded inline via `<script type="application/json">` — NOT loaded via AJAX. This eliminates a network round-trip and avoids VS Code IDE parser errors that would occur if `{{ tojson }}` was inside a `<script>` tag containing JS code.

### 2.2 DOM Structure

```
<body>
  ├── <nav>                          ← Navbar
  ├── <div.container-fluid>          ← Main content
  │     └── <table #studentsTable>
  │           └── <thead>
  │                 ├── <tr #headerRow>   ← Column names (26 <th>)
  │                 └── <tr #filterRow>   ← Filter buttons (26 <th>, each with a .cf-btn)
  │
  ├── <div .cf-panel data-col="0">   ← Panel for column 0 (Sr No)
  ├── <div .cf-panel data-col="1">   ← Panel for column 1 (Reg No)
  ├── ...                            ← One panel per column
  └── <div .cf-panel data-col="25">  ← Panel for column 25 (Reason)
```

**Critical Architecture**: Panels are appended to `<body>`, NOT inside `<th>` cells.

**Why?** DataTables with `scrollX: true` **clones the entire `<thead>`** to create a fixed header. If panels lived inside `<th>`, the cloned header would contain duplicate panels trapped in an `overflow: hidden` wrapper. By placing panels on `<body>`:
- They exist exactly once
- They render above everything (`position: fixed; z-index: 99999`)
- They are immune to DataTables DOM manipulation

### 2.3 Initialization Flow

```
$(document).ready()
    │
    ├── 1. Parse JSON data → LOCAL_DATA array
    │
    ├── 2. Build filter UI
    │     ├── For each of 26 columns:
    │     │     ├── Append <th> with .cf-btn button to #filterRow (inside table)
    │     │     └── Append .cf-panel div to <body> (outside table)
    │     └── Each button has data-col="0..25"
    │         Each panel has data-col="0..25" (matching)
    │
    ├── 3. Initialize DataTable
    │     ├── data: LOCAL_DATA (array of objects)
    │     ├── columns: mapped from DATA_KEYS array
    │     ├── deferRender: true (only renders visible rows)
    │     ├── searching: false (disables DataTables built-in search entirely)
    │     ├── scrollX: true (enables horizontal scrolling → triggers thead clone)
    │     ├── dom: 'Blfrtip' (Buttons, length, filter, processing, table, info, pagination)
    │     └── initComplete → calls populateAllFilters()
    │
    └── 4. populateAllFilters()
          └── For each of 26 DATA_KEYS:
                ├── Scan LOCAL_DATA to extract unique values (case-insensitive dedup)
                ├── Sort: (Blank) first, then locale-aware alphabetical with numeric sorting
                ├── Generate checkbox HTML, all checked by default
                └── Update count display (e.g. "7 / 7")
```

### 2.4 DATA_KEYS Mapping

The `DATA_KEYS` array maps column index (0–25) to database field names:

```
Index │ DATA_KEY              │ Table Header
──────┼───────────────────────┼──────────────────────
  0   │ sr_no                 │ Sr No
  1   │ reg_no                │ Reg No
  2   │ student_name          │ Student Name
  3   │ gender                │ Gender
  4   │ course                │ Course
  5   │ resume_status         │ Resume Status
  6   │ seeking_placement     │ Seeking Placement      ← Shown in screenshot
  7   │ department            │ Department
  8   │ offer_letter_status   │ Offer Letter Status
  9   │ status                │ Status
 10   │ company_name          │ Company Name
 11   │ designation           │ Designation
 12   │ ctc                   │ CTC
 13   │ joining_date          │ Joining Date
 14   │ joining_status        │ Joining Status
 15   │ school_name           │ School Name
 16   │ mobile_number         │ Mobile Number
 17   │ email                 │ Email
 18   │ graduation_course     │ Graduation Course
 19   │ graduation_ogpa       │ Graduation/OGPA
 20   │ percent_10            │ 10%
 21   │ percent_12            │ 12%
 22   │ backlogs              │ Backlogs
 23   │ hometown              │ Hometown
 24   │ address               │ Address
 25   │ reason                │ Reason
```

### 2.5 User Interaction Flow

```
User clicks .cf-btn (e.g. "▼ All" on Seeking Placement column)
    │
    ├── $(document).on('click', '.cf-btn', handler)
    │     ├── e.stopPropagation() — prevents document mousedown from immediately closing
    │     ├── Close any other open panel: $('.cf-panel.open').removeClass('open')
    │     ├── If THIS panel was closed:
    │     │     ├── Get button bounding rect via getBoundingClientRect()
    │     │     ├── Position panel: top = rect.bottom + 2, left = rect.left
    │     │     ├── Overflow check: if panel extends past window right edge, shift left
    │     │     ├── Add 'open' class → panel becomes visible (display: block)
    │     │     └── Focus search input, clear previous search
    │     └── If THIS panel was already open:
    │           └── It was already closed by the "close all" line above → toggle effect
    │
    ▼
Panel is now open. User can:

    ┌─────────────────────────────────────────────────────────────┐
    │  A) TYPE IN SEARCH BOX                                      │
    │     └── $(document).on('input', '.cf-search', handler)      │
    │           └── For each <li>, toggle visibility based on     │
    │               whether <span> text contains search term      │
    │               (case-insensitive .indexOf() match)           │
    │                                                             │
    │  B) CLICK A CHECKBOX ROW                                    │
    │     └── $(document).on('click', '.cf-list li', handler)     │
    │           ├── If click target was NOT the checkbox itself:  │
    │           │     └── Manually toggle checkbox.checked        │
    │           └── Update count display (e.g. "2 / 7")          │
    │                                                             │
    │  C) CLICK "SELECT ALL"                                      │
    │     └── $(document).on('click', '.cf-sel', handler)         │
    │           ├── Check all VISIBLE checkboxes (search-aware)   │
    │           └── Update count                                  │
    │                                                             │
    │  D) CLICK "DESELECT ALL"                                    │
    │     └── $(document).on('click', '.cf-desel', handler)       │
    │           ├── Uncheck all VISIBLE checkboxes                │
    │           └── Update count                                  │
    │                                                             │
    │  E) CLICK "APPLY"                                           │
    │     └── $(document).on('click', '.cf-apply', handler)       │
    │           ├── Get column index from panel's data-col        │
    │           ├── Call applyFilter(col) — see filter engine     │
    │           └── Close panel: .removeClass('open')             │
    │                                                             │
    │  F) CLICK OUTSIDE                                           │
    │     └── $(document).on('mousedown', handler)                │
    │           └── If click target isn't inside .cf-panel or     │
    │               .cf-btn → close all open panels              │
    │               (does NOT apply the filter — just closes)    │
    └─────────────────────────────────────────────────────────────┘
```

### 2.6 Filter Engine (Core Algorithm)

#### `applyFilter(col)` — Reads UI state into ACTIVE_FILTERS

```javascript
function applyFilter(col) {
    var key = DATA_KEYS[col];          // e.g. "seeking_placement"
    var $p = getPanel(col);
    var $lis = $p.find('.cf-list li');
    var tot = $lis.length;             // total unique values (e.g. 7)
    var sel = [];

    // Collect checked values
    $lis.each(function() {
        if ($(this).find('input').is(':checked'))
            sel.push($(this).attr('data-val'));   // raw string value
    });

    // Update button text and ACTIVE_FILTERS
    var $btn = $('.cf-btn[data-col="' + col + '"]');
    if (sel.length === 0 || sel.length === tot) {
        // All selected (or none) = no filter active
        delete ACTIVE_FILTERS[key];
        $btn.text('▼ All').removeClass('cf-active');
    } else {
        // Partial selection = filter active
        ACTIVE_FILTERS[key] = sel;   // e.g. ["Opted In"]
        $btn.text('▼ ' + sel.length + ' sel').addClass('cf-active');
    }

    applyAllFilters();  // Re-render table
}
```

**Design Decision**: `sel.length === 0` is treated same as "all selected" — both clear the filter. This prevents accidental "show nothing" states.

#### `applyAllFilters()` — The Single-Pass Array Filter

```javascript
function applyAllFilters() {
    // 1. Check if ANY filter is active
    var hasAny = false;
    for (var k in ACTIVE_FILTERS) {
        if (ACTIVE_FILTERS[k] && ACTIVE_FILTERS[k].length > 0) {
            hasAny = true; break;
        }
    }

    // 2. Filter LOCAL_DATA array (or skip if no filters)
    var filtered = hasAny ? LOCAL_DATA.filter(function(row) {
        for (var key in ACTIVE_FILTERS) {
            var allowed = ACTIVE_FILTERS[key];      // e.g. ["Opted In", "Left"]
            if (!allowed || allowed.length === 0) continue;
            var val = (row[key] === null || row[key] === undefined)
                      ? '' : String(row[key]).trim();
            if (allowed.indexOf(val) === -1) return false;  // NOT in allowed → exclude
        }
        return true;  // Passed ALL active column filters
    }) : LOCAL_DATA;

    // 3. Replace DataTable contents
    table.clear();
    table.rows.add(filtered);
    table.draw();
}
```

**Filter logic is AND across columns**: If "Seeking Placement" = `["Opted In"]` AND "Department" = `["CSE", "IT"]`, then a row must be "Opted In" AND be either "CSE" or "IT" to appear.

**Filter logic is OR within a column**: If "Seeking Placement" = `["Opted In", "Left"]`, a row appears if its value is either "Opted In" OR "Left".

This matches Microsoft Excel's filter behavior exactly.

### 2.7 Value Population Logic (Dedup)

```javascript
function populateAllFilters() {
    DATA_KEYS.forEach(function(key, ci) {
        var seen = {};
        LOCAL_DATA.forEach(function(row) {
            var v = row[key];
            var raw = (v === null || v === undefined) ? '' : String(v).trim();
            var norm = raw.toLowerCase();        // Case-insensitive key
            if (!(norm in seen)) seen[norm] = raw;   // Keep first casing encountered
        });
        var vals = Object.keys(seen).map(function(k) { return seen[k]; });
        vals.sort(function(a, b) {
            if (a === '') return -1;     // (Blank) always first
            if (b === '') return 1;
            return a.localeCompare(b, undefined, { numeric: true });
        });
        // ... render checkboxes, all checked by default
    });
}
```

**Dedup strategy**: Uses `toLowerCase()` as key but stores the **first encountered casing** as the display value. This means if data contains both "Opted In" and "opted in", only ONE checkbox appears (whichever case was seen first in the data).

**Sorting**: `localeCompare` with `{ numeric: true }` so "10%" sorts after "9%" (not after "1%").

### 2.8 ACTIVE_FILTERS Object (State Model)

```
ACTIVE_FILTERS = {
    // Only keys with active partial selections exist
    "seeking_placement": ["Opted In"],           // col 6 — 1 value selected
    "department":        ["CSE", "IT", "ECE"]    // col 7 — 3 values selected
    // All other columns: absent (= no filter = show all)
}
```

- **Key** = database column name (from `DATA_KEYS`)
- **Value** = array of selected string values
- **Absent key** = no filter on that column (show everything)
- **Key deleted** when user selects all values or deselects all values

---

## 3. Event Delegation & DataTables Compatibility

### Why `$(document).on()` Instead of Direct Binding

DataTables with `scrollX: true` performs this DOM manipulation:

```
Original <thead>           DataTables Clone
┌──────────────────┐       ┌──────────────────┐
│ #headerRow       │  →→→  │ (cloned header)  │  ← This is what users SEE
│ #filterRow       │  →→→  │ (cloned filters) │  ← Contains cloned .cf-btn buttons
└──────────────────┘       └──────────────────┘
                                 ↑ Visible
       ↑ Hidden inside .dataTables_scrollHead (overflow: hidden)
```

The **cloned buttons** have no event listeners attached. Using `$(document).on('click', '.cf-btn', handler)` works because:
1. Click bubbles up from cloned `.cf-btn` → document
2. Document handler checks if target matches `.cf-btn` selector
3. Works regardless of whether the button is original or cloned

### Global Button Selector

```javascript
var $btn = $('.cf-btn[data-col="' + col + '"]');
```

This selects **both** the original and cloned button — so when the button text is updated to `▼ 1 sel`, both copies update. Users always see the correct state.

---

## 4. Duplicate Implementation Audit

### dashboard.html vs version_detail.html

These two files contain **nearly identical filter implementations** (~180 lines of shared JS). Here is a line-by-line comparison:

| Feature | dashboard.html | version_detail.html | Status |
|---------|---------------|---------------------|--------|
| JSON source | `students_json` (via Flask) | `snap_json` (via Flask) | **Different** — correct |
| Table ID | `#studentsTable` | `#versionTable` | **Different** — correct |
| LOCAL_DATA parse | Identical | Identical | **DUPLICATE** |
| Filter cell builder loop | Identical | Identical | **DUPLICATE** |
| DATA_KEYS array | Identical | Identical | **DUPLICATE** |
| ACTIVE_FILTERS object | Identical | Identical | **DUPLICATE** |
| DataTable init options | Nearly identical | Nearly identical | **DUPLICATE** (only `language.emptyTable` differs) |
| `applyAllFilters()` | Identical | Identical | **DUPLICATE** |
| `populateAllFilters()` | Identical | Identical | **DUPLICATE** |
| `getPanel()` | Identical | Identical | **DUPLICATE** |
| `countUpdate()` | Identical | Identical | **DUPLICATE** |
| `applyFilter()` | Identical | Identical | **DUPLICATE** |
| All 8 event handlers | Identical | Identical | **DUPLICATE** |

### Duplication Summary

- **~180 lines** of JavaScript are copy-pasted between the two templates
- **Functions duplicated**: `applyAllFilters`, `populateAllFilters`, `getPanel`, `countUpdate`, `applyFilter`
- **Constants duplicated**: `DATA_KEYS` array (26 entries)
- **Event handlers duplicated**: 8 `$(document).on(...)` blocks

### Potential Refactor (Not Implemented — For Reference)

All shared code could be extracted to a `static/filter.js` file. The templates would only need to specify:
1. The table ID (`#studentsTable` vs `#versionTable`)
2. The JSON data variable name
3. Any custom DataTable language options

This would reduce each template's JS to ~15 lines.

---

## 5. Dashboard Sheet — UI Structure

### 5.1 Page Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                               │
│ ┌──────────────┐                    ┌────────┐ ┌──────────┐ ┌──────┐│
│ │ Placement MIS│                    │ Upload │ │Dashboard │ │Versns││
│ └──────────────┘                    └────────┘ └──────────┘ └──────┘│
│  (brand, left)                               (nav links, right)     │
├──────────────────────────────────────────────────────────────────────┤
│ CONTENT AREA (container-fluid, mt-4, px-4)                          │
│                                                                      │
│  <h3>Student Placement Dashboard</h3>                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ DATATABLE CONTROLS                                              │  │
│  │ [Export CSV] [Export Excel]    Show [25 ▼] records              │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │ HEADER ROW (scrollX — horizontally scrollable)                  │  │
│  │ ┌──────┬──────┬─────────────┬────────┬────────┬─── ... ──┐    │  │
│  │ │Sr No │Reg No│Student Name │Gender  │Course  │   ...    │    │  │
│  │ ├──────┼──────┼─────────────┼────────┼────────┼─── ... ──┤    │  │
│  │ │▼ All │▼ All │▼ All        │▼ All   │▼ All   │   ...    │    │  │
│  │ └──────┴──────┴─────────────┴────────┴────────┴─── ... ──┘    │  │
│  │                                                                  │  │
│  │ DATA ROWS                                                       │  │
│  │ │  1   │ 2201 │ John Doe    │ Male   │ B.Tech │   ...    │    │  │
│  │ │  2   │ 2202 │ Jane Smith  │ Female │ M.Tech │   ...    │    │  │
│  │ │ ...  │ ...  │ ...         │ ...    │ ...    │   ...    │    │  │
│  │                                                                  │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │ FOOTER: Showing 1 to 25 of N students    « 1 2 3 ... n »      │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Table Structure

The `<table>` has **28 rows in the header**: 1 header row + 1 filter row, and then DataTables renders data rows in `<tbody>`.

**26 columns** spanning the full student data model:
- Identity: Sr No, Reg No, Student Name, Gender
- Academic: Course, School Name, Graduation Course, Graduation/OGPA, 10%, 12%, Backlogs
- Placement: Resume Status, Seeking Placement, Department, Status, Offer Letter Status
- Employment: Company Name, Designation, CTC, Joining Date, Joining Status
- Contact: Mobile Number, Email, Hometown, Address
- Other: Reason

### 5.3 DataTable Configuration

```javascript
{
    data: LOCAL_DATA,                    // Inline JSON, no AJAX
    columns: DATA_KEYS.map(k => ({data: k})),
    order: [[0, 'asc']],                // Default sort: Sr No ascending
    pageLength: 25,                      // 25 rows per page
    lengthMenu: [10, 25, 50, 100, 500], // Page size options
    scrollX: true,                       // Horizontal scroll for 26 columns
    deferRender: true,                   // Only render visible page (performance)
    searching: false,                    // Disable DataTables search (we use our own)
    dom: 'Blfrtip',                      // Layout: Buttons, length, filter, r, table, info, pagination
    buttons: [CSV, Excel]                // Export buttons via JSZip
}
```

**`searching: false`** is critical — it disables DataTables' built-in global search box and column search APIs. All filtering is handled by our custom array engine.

**`deferRender: true`** — DataTables creates DOM nodes only for the currently visible page. With 500+ rows and 26 columns, this avoids creating 13,000+ `<td>` elements upfront.

---

## 6. Overall UI Design System

### 6.1 Color Palette (CSS Variables)

```css
:root {
    --bg-dark:         #121212;    /* Page background */
    --bg-card:         #1e1e1e;    /* Card/panel backgrounds */
    --bg-surface:      #2a2a2a;    /* Input fields, table headers */
    --bg-hover:        #333333;    /* Hover states */
    --text-primary:    #f0f0f0;    /* Main text */
    --text-secondary:  #a0a0a0;    /* Muted text, labels */
    --accent-red:      #e53935;    /* Primary accent (buttons, active states, borders) */
    --accent-red-hover:#ff5252;    /* Hover state for accent */
    --accent-white:    #ffffff;    /* Headlines, active nav */
    --border-color:    #3a3a3a;    /* Subtle borders */
    --border-light:    #444;       /* Lighter borders */
}
```

**Design philosophy**: Dark minimal theme with **white text for readability** and **red (`#e53935`) as the single accent color**. This creates a high-contrast, professional look suitable for data-heavy dashboards.

### 6.2 Typography

- **Font stack**: `'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif` — native Windows/Mac fonts
- **Table headers**: 0.82rem, uppercase, 600 weight, 0.5px letter-spacing
- **Table data**: 0.82rem, normal weight
- **Filter button text**: 0.74rem
- **Filter panel text**: 0.78rem
- **Brand**: 1.3rem, 700 weight, 1px letter-spacing

### 6.3 Component Design

#### Navbar
- Fixed background: `#1e1e1e`
- Red bottom border: `2px solid #e53935`
- Nav links: gray → white+red background on hover/active
- Padding: `0.6rem 1.5rem`

#### Cards (Upload Page)
- Background: `#1e1e1e`
- Border: `1px solid #3a3a3a`, 12px radius
- Header: Solid red background (`#e53935`)
- Footer: Surface color (`#2a2a2a`)

#### Data Table
- Striped rows alternating between `#1e1e1e` and `#2a2a2a`
- Hover: `#333333`
- All borders: `#3a3a3a`
- Pagination: Rounded buttons, red for current page

#### Filter Buttons (`.cf-btn`)
- Default: gray bg (`#333`), gray text, gray border
- Hover: red border, white text
- Active (filter applied): red border, red text, 10% red background tint
- Full width of cell, left-aligned, text overflow with ellipsis

#### Filter Panel (`.cf-panel`)
- Fixed position on body, z-index 99999
- Red border, dark background, heavy shadow
- 230px wide, 8px border-radius
- Max list height: 210px with custom dark scrollbar

#### Buttons
- Primary: Red background, white text, 8px radius
- Hover: lighter red + slight `translateY(-1px)` lift + red shadow
- Outline variants: transparent bg with colored border

### 6.4 Scrollbar Styling

```css
::-webkit-scrollbar       { height: 8px; width: 8px; }
::-webkit-scrollbar-track { background: #2a2a2a; }
::-webkit-scrollbar-thumb { background: #3a3a3a; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #555; }
```

The filter list has a thinner scrollbar (5px) to save space.

### 6.5 Page-by-Page UI Summary

| Page | Layout | Key Components |
|------|--------|---------------|
| **Upload** (`/upload`) | Centered card (col-lg-6) | File input, upload button with spinner, flash messages, "Drop All Data" in footer |
| **Dashboard** (`/dashboard`) | Full-width (`container-fluid`) | DataTable with 26 columns, filter row, export buttons, pagination |
| **Versions** (`/versions`) | Container | Simple table listing uploads (version #, filename, date, counts, view/delete actions) |
| **Version Detail** (`/versions/<id>`) | Full-width (`container-fluid`) | DataTable identical to dashboard but showing snapshot data, with back button |

---

## 7. Filter Panel CSS Architecture (Full Detail)

### Layering (Z-Index)

```
z-index: 99999  ← .cf-panel (highest — ensures it's above everything)
z-index: (auto) ← DataTables scrollHead wrapper
z-index: (auto) ← Bootstrap navbar
z-index: (auto) ← Normal page content
```

### Panel State Machine (CSS)

```
.cf-panel {
    display: none;            ← Hidden by default
    position: fixed;          ← Positioned relative to viewport
}

.cf-panel.open {
    display: block;           ← Shown when class 'open' is added
}
```

**Positioning is dynamic** (set via JS `getBoundingClientRect()`):
```javascript
var r = this.getBoundingClientRect();      // Button's viewport position
$panel.css({ top: r.bottom + 2, left: r.left });
// Overflow correction:
if (r.left + pw > window.innerWidth) $panel.css('left', window.innerWidth - pw - 8);
```

### Interactive States

```
.cf-btn               → cursor: pointer, gray bg/text/border
.cf-btn:hover         → red border, white text
.cf-btn.cf-active     → red border, red text, rgba(red, 0.1) background

.cf-list li           → cursor: pointer, user-select: none
.cf-list li:hover     → #333 background, white text

.cf-batch button      → transparent bg, hover → gray bg + red border
.cf-apply             → solid red bg, hover → lighter red
.cf-search            → dark surface bg, focus → red border
```

---

## 8. Data Flow Diagram (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UPLOAD FLOW                                   │
│                                                                      │
│  Excel File (.xlsx)                                                  │
│      │                                                               │
│      ▼                                                               │
│  [Flask /upload POST]                                                │
│      ├── pd.read_excel() → DataFrame                                │
│      ├── Normalize headers (strip whitespace, fix "0.1"→"10%")     │
│      ├── Validate against EXPECTED_HEADERS (set comparison)          │
│      ├── Rename columns via HEADER_TO_COL mapping                   │
│      ├── NaN → None, sr_no → int, others → str.strip()             │
│      ├── UPSERT into `students` table (ON DUPLICATE KEY UPDATE)     │
│      ├── Create `upload_versions` record                            │
│      └── Copy rows into `version_snapshots` linked to version       │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                       DISPLAY FLOW                                   │
│                                                                      │
│  [Flask /dashboard GET]                                              │
│      ├── SELECT * FROM students ORDER BY sr_no                      │
│      ├── cursor.fetchall() → list of dicts                          │
│      └── render_template("dashboard.html", students_json=rows)      │
│              │                                                       │
│              ▼                                                       │
│  [Jinja2 Template]                                                   │
│      └── {{ students_json | tojson }}                                │
│              │  embedded in <script type="application/json">        │
│              ▼                                                       │
│  [Browser JavaScript]                                                │
│      ├── JSON.parse() → LOCAL_DATA (array of objects)               │
│      ├── DataTable({ data: LOCAL_DATA }) → renders table            │
│      └── populateAllFilters() → extracts unique values per column   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                       FILTER FLOW                                    │
│                                                                      │
│  User clicks filter button                                           │
│      │                                                               │
│      ▼                                                               │
│  Panel opens (positioned via getBoundingClientRect)                  │
│      │                                                               │
│      ├── User checks/unchecks values                                │
│      │                                                               │
│      ▼                                                               │
│  User clicks "Apply"                                                 │
│      │                                                               │
│      ├── applyFilter(col):                                          │
│      │     ├── Read checked values from panel checkboxes            │
│      │     ├── Update ACTIVE_FILTERS[key] = selectedValues          │
│      │     └── Update button text: "▼ All" or "▼ N sel"            │
│      │                                                               │
│      ├── applyAllFilters():                                         │
│      │     ├── LOCAL_DATA.filter(row => {                           │
│      │     │     for each key in ACTIVE_FILTERS:                    │
│      │     │       if row[key] not in ACTIVE_FILTERS[key] → false  │
│      │     │     return true                                        │
│      │     │   })                                                    │
│      │     ├── table.clear()                                        │
│      │     ├── table.rows.add(filtered)                             │
│      │     └── table.draw()                                         │
│      │                                                               │
│      └── Panel closes                                                │
│                                                                      │
│  DataTable re-renders with filtered subset                           │
│  Info bar updates: "Showing 1 to N of M students"                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Edge Cases & Behavior Notes

| Scenario | Behavior |
|----------|----------|
| **All values checked** | Filter removed (`delete ACTIVE_FILTERS[key]`), button shows "▼ All" |
| **No values checked** | Same as above — treated as "show all", not "show nothing" |
| **Null/undefined values** | Converted to empty string `''`, displayed as "(Blank)" |
| **Duplicate casing** | "Opted In" and "opted in" deduped to single checkbox (first casing preserved) |
| **Search in panel** | Filters the checkbox list visually (`.toggle()`), does NOT affect data filter |
| **Select All with search** | Only checks **visible** (matched) checkboxes, not hidden ones |
| **Deselect All with search** | Only unchecks **visible** checkboxes |
| **Close without Apply** | Panel closes, no filter change. Previous filter state preserved. |
| **Multiple column filters** | AND logic — row must pass ALL column filters to appear |
| **Within one column** | OR logic — row value must be in the selected set |
| **Export with filter active** | Exports ONLY the currently visible (filtered) rows |
| **Panel overflow right** | Auto-corrects: `left = window.innerWidth - panelWidth - 8` |

---

## 10. Performance Characteristics

| Aspect | Implementation | Impact |
|--------|---------------|--------|
| **Data loading** | Inline JSON (no AJAX) | Zero network latency after page load |
| **Filtering** | `Array.filter()` on LOCAL_DATA | O(n × m) per filter apply (n=rows, m=active filters) |
| **Value matching** | `Array.indexOf()` | O(k) per check (k=selected values in column) |
| **DOM update** | `table.clear(); table.rows.add(); table.draw()` | DataTables handles efficient re-render |
| **Deferred render** | `deferRender: true` | Only visible page creates DOM nodes |
| **Checkbox dedup** | Single pass with `seen` object | O(n) per column during population |

---

## 11. Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend | Flask | Latest | HTTP routing, template rendering |
| Database | MySQL | 8.x | Data persistence (localhost:3307) |
| ORM / Data | pandas + openpyxl | Latest | Excel parsing |
| DB Driver | mysql-connector-python | Latest | MySQL communication |
| Frontend Table | DataTables.js | 1.13.7 | Table rendering, pagination, sorting, export |
| Frontend Framework | Bootstrap | 5.3.0 | Layout, utility classes |
| DOM Library | jQuery | 3.7.0 | DOM manipulation, event handling |
| Export | JSZip | 3.10.1 | Excel export via DataTables Buttons |
| Templating | Jinja2 | (bundled w/ Flask) | Server-side HTML generation |
| Styling | Custom CSS | — | Dark theme with `cf-*` filter component classes |
