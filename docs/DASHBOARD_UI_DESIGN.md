# Dashboard — Complete UI Design & Layout Reference

> **Generated**: February 2026  
> **File**: `templates/dashboard.html`  
> **Route**: `GET /dashboard`  
> **Purpose**: Main data view — displays all student placement records with sorting, pagination, Excel-style column filters, and export.

---

## 1. Full Page Visual Layout

```
┌─── BROWSER VIEWPORT ──────────────────────────────────────────────────────────────┐
│                                                                                    │
│  ┌─── NAVBAR (.navbar) ────────────────────────────────────────────────────────┐   │
│  │                                                                              │   │
│  │   Placement MIS                              Upload   Dashboard   Versions   │   │
│  │   (brand, bold white)                        (gray)   (RED BG)    (gray)     │   │
│  │                                                                              │   │
│  ├──── 2px solid #e53935 (red bottom border) ──────────────────────────────────┤   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
│  ┌─── CONTENT AREA (.container-fluid mt-4 px-4) ──────────────────────────────┐   │
│  │                                                                              │   │
│  │   Student Placement Dashboard                                                │   │
│  │   (h3, white, bold 700)                                                      │   │
│  │                                                                              │   │
│  │  ┌─── DATATABLES WRAPPER (.dataTables_wrapper) ─────────────────────────┐   │   │
│  │  │                                                                        │   │   │
│  │  │  ┌─── TOOLBAR ROW ──────────────────────────────────────────────┐     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  │  [Export CSV] [Export Excel]          Show [25 ▼] records     │     │   │   │
│  │  │  │  (gray border) (green border)        (dropdown, dark bg)      │     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  └────────────────────────────────────────────────────────────────┘     │   │   │
│  │  │                                                                        │   │   │
│  │  │  ┌─── TABLE (.dataTables_scrollHead + .dataTables_scrollBody) ──┐     │   │   │
│  │  │  │  ← horizontal scroll (scrollX: true) →                        │     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  │  ┌─ HEADER ROW (#headerRow) ─────────────────────── ··· ──┐  │     │   │   │
│  │  │  │  │ SR NO │ REG NO │ STUDENT NAME │ GENDER │ COURSE │ ··· │  │     │   │   │
│  │  │  │  ├─ FILTER ROW (#filterRow) ─────────────────────── ··· ──┤  │     │   │   │
│  │  │  │  │ ▼ All │ ▼ All  │ ▼ All        │ ▼ All  │ ▼ All  │ ··· │  │     │   │   │
│  │  │  │  ├────────────────────────────────────────────────── ··· ──┤  │     │   │   │
│  │  │  │  │   1   │ 22001  │ John Doe     │ Male   │ B.Tech │ ··· │  │     │   │   │
│  │  │  │  │   2   │ 22002  │ Jane Smith   │ Female │ M.Tech │ ··· │  │     │   │   │
│  │  │  │  │   3   │ 22003  │ Bob Wilson   │ Male   │ B.Tech │ ··· │  │     │   │   │
│  │  │  │  │  ...  │  ...   │ ...          │  ...   │  ...   │ ··· │  │     │   │   │
│  │  │  │  │  25   │ 22025  │ Alice Brown  │ Female │ MBA    │ ··· │  │     │   │   │
│  │  │  │  └────────────────────────────────────────────────── ··· ──┘  │     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  └────────────────────────────────────────────────────────────────┘     │   │   │
│  │  │                                                                        │   │   │
│  │  │  ┌─── FOOTER ROW ──────────────────────────────────────────────┐     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  │  Showing 1 to 25 of 350 students       « 1  2  3 ... 14 »   │     │   │   │
│  │  │  │  (gray text)                            (pagination buttons)  │     │   │   │
│  │  │  │                                                                │     │   │   │
│  │  │  └────────────────────────────────────────────────────────────────┘     │   │   │
│  │  │                                                                        │   │   │
│  │  └────────────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                              │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
│  ┌─── FILTER PANELS (appended to <body>, invisible until opened) ──────────────┐   │
│  │  <div .cf-panel data-col="0"> ... </div>   (26 panels, all display: none)    │   │
│  │  <div .cf-panel data-col="1"> ... </div>                                     │   │
│  │  ...                                                                          │   │
│  │  <div .cf-panel data-col="25"> ... </div>                                    │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Navbar — Detailed Design

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Placement MIS                                  Upload  Dashboard  Versions  │
│  ▲                                               ▲       ▲          ▲       │
│  │                                               │       │          │       │
│  navbar-brand                                    nav-link nav-link   nav-link│
│  #fff, 1.3rem                                    .active  (active)          │
│  font-weight: 700                                = red bg             gray  │
│  letter-spacing: 1px                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
  ═══════════ 2px solid #e53935 (red accent border at bottom) ═══════════════
```

### CSS Implementation

| Property | Value | Purpose |
|----------|-------|---------|
| `background` | `#1e1e1e` | Dark card background |
| `border-bottom` | `2px solid #e53935` | Red accent separator |
| `padding` | `0.6rem 1.5rem` | Compact spacing |
| Brand color | `#ffffff` | White, high contrast |
| Brand weight | `700` | Bold for emphasis |
| Link color (default) | `#a0a0a0` | Gray, secondary |
| Link color (hover/active) | `#ffffff` on `#e53935` bg | White text on red pill |
| Link border-radius | `6px` | Rounded pill shape |
| Link transition | `all 0.2s` | Smooth hover effect |

### HTML Structure
```html
<nav class="navbar navbar-expand-lg">
    <div class="container-fluid">
        <a class="navbar-brand" href="/">Placement MIS</a>
        <div class="navbar-nav ms-auto">
            <a class="nav-link" href="/upload">Upload</a>
            <a class="nav-link active" href="/dashboard">Dashboard</a>  ← RED BG
            <a class="nav-link" href="/versions">Versions</a>
        </div>
    </div>
</nav>
```

---

## 3. Page Title

```
Student Placement Dashboard
```

| Property | Value |
|----------|-------|
| Element | `<h3>` |
| Color | `#ffffff` (via `h3 { color: var(--accent-white) }`) |
| Font weight | `700` |
| Margin | `mb-3` (Bootstrap, 1rem bottom) |
| Container | `.container-fluid mt-4 px-4` (full width, 1.5rem top, 1.5rem horizontal padding) |

---

## 4. Export Buttons — Toolbar

```
┌─────────────────┐  ┌──────────────────┐                    ┌──────────────────┐
│  Export CSV      │  │  Export Excel     │                    │ Show  25 ▼  records│
│  (gray outline)  │  │  (green outline)  │                    │ (length dropdown)  │
└─────────────────┘  └──────────────────┘                    └──────────────────┘
```

### Export CSV Button

| Property | Value |
|----------|-------|
| Class | `btn btn-sm btn-outline-secondary` |
| Text color | `#a0a0a0` |
| Border | `1px solid #3a3a3a` |
| Border radius | `8px` |
| Hover | bg `#333333`, text `#f0f0f0` |
| Generated by | DataTables Buttons extension (`extend: 'csvHtml5'`) |

### Export Excel Button

| Property | Value |
|----------|-------|
| Class | `btn btn-sm btn-outline-success` |
| Text color | `#4caf50` (Material green) |
| Border | `1px solid #4caf50` |
| Border radius | `8px` |
| Hover | bg `#4caf50`, text `white` |
| Generated by | DataTables Buttons extension (`extend: 'excelHtml5'`) |
| Dependency | JSZip 3.10.1 (generates .xlsx client-side) |

### Page Length Dropdown

| Property | Value |
|----------|-------|
| Options | `[10, 25, 50, 100, 500]` |
| Default | `25` |
| Background | `#2a2a2a` |
| Border | `1px solid #3a3a3a` |
| Text color | `#f0f0f0` |
| Border radius | `6px` |
| Label | `"Show _MENU_ records"` |

### Toolbar Layout

The DataTables `dom` option `'Blfrtip'` controls the order:
```
B = Buttons (Export CSV, Export Excel)
l = Length dropdown (Show N records)
f = Filter input (disabled — searching: false)
r = Processing indicator
t = Table
i = Info ("Showing 1 to 25 of N students")
p = Pagination
```

The `.dt-buttons` class has `margin-bottom: 12px` to separate buttons from the table.

---

## 5. Data Table — Structure & Styling

### 5.1 Table Element

```html
<table id="studentsTable" class="table table-striped table-bordered table-hover" style="width:100%">
```

| Class | Effect |
|-------|--------|
| `table` | Base Bootstrap table styling |
| `table-striped` | Alternating row colors (`#1e1e1e` / `#2a2a2a`) |
| `table-bordered` | All cell borders (`#3a3a3a`) |
| `table-hover` | Row highlight on hover (`#333333`) |
| `width: 100%` | Full container width (required for DataTables scrollX) |

### 5.2 Header Row (#headerRow)

26 columns displayed as uppercase labels:

```
┌────────┬────────┬──────────────┬────────┬────────┬────────────────┬───────────────────┬────────────┐
│ SR NO  │ REG NO │ STUDENT NAME │ GENDER │ COURSE │ RESUME STATUS  │ SEEKING PLACEMENT │ DEPARTMENT │ ···
└────────┴────────┴──────────────┴────────┴────────┴────────────────┴───────────────────┴────────────┘
```

| Property | Value |
|----------|-------|
| Background | `#2a2a2a` (via `.table th`) |
| Text color | `#ffffff` |
| Font size | `0.82rem` |
| Font weight | `600` |
| Text transform | `uppercase` |
| Letter spacing | `0.5px` |
| White space | `nowrap` (no text wrapping) |
| Border color | `#3a3a3a` |

Each `<th>` also has a DataTables sort indicator arrow (opacity: 0.7):
- Default: both arrows (unsorted)
- `sorting_asc`: up arrow active
- `sorting_desc`: down arrow active

Clicking a header sorts that column. Default sort: column 0 (Sr No) ascending.

### 5.3 Complete Column List (26 Columns)

```
 #  │ Header Text          │ Data Key            │ Category
────┼──────────────────────┼─────────────────────┼──────────────
  1 │ Sr No                │ sr_no               │ Identity
  2 │ Reg No               │ reg_no              │ Identity
  3 │ Student Name         │ student_name        │ Identity
  4 │ Gender               │ gender              │ Identity
  5 │ Course               │ course              │ Academic
  6 │ Resume Status        │ resume_status       │ Placement
  7 │ Seeking Placement    │ seeking_placement   │ Placement
  8 │ Department           │ department          │ Placement
  9 │ Offer Letter Status  │ offer_letter_status │ Placement
 10 │ Status               │ status              │ Placement
 11 │ Company Name         │ company_name        │ Employment
 12 │ Designation          │ designation         │ Employment
 13 │ CTC                  │ ctc                 │ Employment
 14 │ Joining Date         │ joining_date        │ Employment
 15 │ Joining Status       │ joining_status      │ Employment
 16 │ School Name          │ school_name         │ Academic
 17 │ Mobile Number        │ mobile_number       │ Contact
 18 │ Email                │ email               │ Contact
 19 │ Graduation Course    │ graduation_course   │ Academic
 20 │ Graduation/OGPA      │ graduation_ogpa     │ Academic
 21 │ 10%                  │ percent_10          │ Academic
 22 │ 12%                  │ percent_12          │ Academic
 23 │ Backlogs             │ backlogs            │ Academic
 24 │ Hometown             │ hometown            │ Contact
 25 │ Address              │ address             │ Contact
 26 │ Reason               │ reason              │ Other
```

### 5.4 Filter Row (#filterRow)

Below the header row, a second `<tr>` contains one filter button per column:

```
┌──────────┬──────────┬──────────────┬──────────┬──────────┬────── ··· ────┐
│  ▼ All   │  ▼ All   │  ▼ All       │  ▼ All   │  ▼ 3 sel │    ···       │
│  (gray)  │  (gray)  │  (gray)      │  (gray)  │  (RED)   │              │
└──────────┴──────────┴──────────────┴──────────┴──────────┴────── ··· ────┘
```

Each cell contains:
```html
<th>
  <div class="cf-wrap">
    <button type="button" class="cf-btn" data-col="0">▼ All</button>
  </div>
</th>
```

**Button States:**

| State | Text | CSS Class | Visual |
|-------|------|-----------|--------|
| No filter | `▼ All` | `.cf-btn` | Gray bg `#333`, gray text `#a0a0a0`, gray border `#3a3a3a` |
| Hover | `▼ All` | `.cf-btn:hover` | Red border `#e53935`, white text `#fff` |
| Filter active | `▼ 3 sel` | `.cf-btn.cf-active` | Red border, red text `#e53935`, tinted bg `rgba(229,57,53,0.1)` |

**Button CSS properties:**
```
width: 100%              ← fills the cell
text-align: left         ← left-aligned text
padding: 3px 8px         ← compact
font-size: 0.74rem       ← smallest text on page
border-radius: 4px       ← subtle rounding
white-space: nowrap       ← no wrapping
overflow: hidden          ← clips long text
text-overflow: ellipsis   ← shows "..." if text is too long
transition: 0.15s         ← smooth hover
```

### 5.5 Data Rows (tbody)

Each row displays one student record across 26 cells:

```
│  1  │ 22001 │ John Doe    │ Male   │ B.Tech │ Verified │ Opted In │ CSE │ ··· │
│  2  │ 22002 │ Jane Smith  │ Female │ M.Tech │ Pending  │ Left     │ IT  │ ··· │
```

| Property | Value |
|----------|-------|
| Font size | `0.82rem` |
| Text color | `#f0f0f0` |
| Vertical align | `middle` |
| Even rows bg | `#1e1e1e` (card bg) |
| Odd rows bg | `#2a2a2a` (surface bg) |
| Hover bg | `#333333` |
| Hover text | `#ffffff` |
| Border | `1px solid #3a3a3a` |

### 5.6 Horizontal Scrolling

Because the table has 26 columns, DataTables `scrollX: true` enables horizontal scrolling:

```
┌── .dataTables_scrollHead ─────────────────────────────────────┐
│  Contains CLONED <thead> — this is what users see             │
│  (original thead hidden in overflow: hidden wrapper)          │
└───────────────────────────────────────────────────────────────┘
┌── .dataTables_scrollBody ─────────────────────────────────────┐
│  Contains <tbody> — scrollable horizontally AND vertically    │
│  ◄══════════════ scrollbar at bottom ═══════════════════════► │
└───────────────────────────────────────────────────────────────┘
```

Scrollbar styling:
```
Height: 8px
Track: #2a2a2a
Thumb: #3a3a3a, 4px border-radius
Thumb hover: #555
```

---

## 6. Filter Panel — Detailed Component Design

When a user clicks a `▼ All` button, a filter panel opens below it:

```
        ▼ 1 sel          ▼ All
        ┌───────────────────────┐
        │  ┌─────────────────┐  │
        │  │ Search values…  │  │  ← .cf-search (text input)
        │  └─────────────────┘  │
        │                       │
        │  ┌──────┐  ┌────────┐ │
        │  │Sel Al│  │Desel Al│ │  ← .cf-batch (flex row)
        │  └──────┘  └────────┘ │
        │                       │
        │  ☐ (Blank)            │  ← .cf-list <ul>
        │  ☐ Debarded/Opted In  │     (scrollable, max 210px)
        │  ☐ Debarded/Opted Out │
        │  ☐ Left               │
        │  ☐ Not Registered     │
        │  ☑ Opted In           │  ← checked = red accent
        │  ☐ Opted Out          │
        │                       │
        │  ─────────────────    │  ← border-top separator
        │  2 / 7       [Apply]  │  ← .cf-foot (flex row)
        │                       │
        └───────────────────────┘
                230px wide
```

### 6.1 Panel Container (.cf-panel)

| Property | Value | Notes |
|----------|-------|-------|
| `display` | `none` / `block` | Toggled via `.open` class |
| `position` | `fixed` | Relative to viewport, not parent |
| `z-index` | `99999` | Above everything |
| `background` | `#1e1e1e` | Dark card bg |
| `border` | `1px solid #e53935` | Red accent border |
| `border-radius` | `8px` | Rounded corners |
| `width` | `230px` | Fixed width |
| `box-shadow` | `0 8px 24px rgba(0,0,0,0.7)` | Heavy dark shadow |
| `padding` | `10px` | Inner spacing |

**Positioning logic** (JavaScript):
```
Button clicked → getBoundingClientRect()
Panel top  = button.bottom + 2px
Panel left = button.left
If panel overflows right edge → shift left to fit
```

### 6.2 Search Input (.cf-search)

| Property | Value |
|----------|-------|
| `width` | `100%` |
| `padding` | `5px 8px` |
| `font-size` | `0.78rem` |
| `background` | `#2a2a2a` (surface) |
| `border` | `1px solid #3a3a3a` |
| `border-radius` | `5px` |
| `color` | `#f0f0f0` |
| `margin-bottom` | `6px` |
| Focus border | `#e53935` (red) |
| Placeholder | `"Search values…"` |

**Behavior**: Typing filters the checkbox list in real-time (case-insensitive substring match). Hidden items are excluded from Select All / Deselect All.

### 6.3 Batch Buttons (.cf-batch)

```
┌──────────────┐  ┌──────────────┐
│  Select All   │  │ Deselect All │
└──────────────┘  └──────────────┘
```

| Property | Value |
|----------|-------|
| Layout | `display: flex; gap: 6px` |
| Each button | `flex: 1` (equal width) |
| Padding | `3px 0` |
| Font | `0.7rem, weight 600` |
| Background | `transparent` |
| Border | `1px solid #3a3a3a` |
| Border radius | `4px` |
| Text color | `#a0a0a0` (secondary) |
| Hover bg | `#333333` |
| Hover text | `#f0f0f0` |
| Hover border | `#e53935` (red) |
| Margin bottom | `6px` |

**Behavior**: Only affects **visible** checkboxes (respects search filter).

### 6.4 Value List (.cf-list)

| Property | Value |
|----------|-------|
| `max-height` | `210px` |
| `overflow-y` | `auto` (scrollbar when needed) |
| `list-style` | `none` |
| `padding` / `margin` | `0` |
| Scrollbar width | `5px` (thinner than page scrollbar) |
| Scrollbar thumb | `#3a3a3a`, 3px radius |

**Each list item (`<li>`):**

```html
<li data-val="Opted In">
  <label>
    <input type="checkbox" checked>
    <span>Opted In</span>
  </label>
</li>
```

| Property | Value |
|----------|-------|
| Padding | `3px 6px` |
| Border radius | `4px` |
| Font size | `0.78rem` |
| Text color | `#a0a0a0` |
| Hover bg | `#333333` |
| Hover text | `#f0f0f0` |
| `cursor` | `pointer` |
| `user-select` | `none` |

**Label layout:**
```
display: flex; align-items: center; gap: 6px; width: 100%
```

**Checkbox styling:**
```
accent-color: #e53935 (red when checked)
cursor: pointer
flex-shrink: 0
```

**Special values:**
- Empty/null data → displayed as `(Blank)`
- `(Blank)` always sorted first
- Duplicates with different casing deduped (first occurrence's casing preserved)

### 6.5 Footer (.cf-foot)

```
 2 / 7                                    [Apply]
 ▲                                          ▲
 .cf-count                                  .cf-apply
```

**Count label (.cf-count):**

| Property | Value |
|----------|-------|
| Font size | `0.72rem` |
| Color | `#a0a0a0` |
| Font weight | `600` |
| Format | `checked / total` |

**Apply button (.cf-apply):**

| Property | Value |
|----------|-------|
| Padding | `4px 14px` |
| Font size | `0.75rem` |
| Font weight | `600` |
| Background | `#e53935` (red) |
| Color | `white` |
| Border | `none` |
| Border radius | `4px` |
| Hover bg | `#ff5252` (lighter red) |

**Footer container:**
```
display: flex
align-items: center
justify-content: space-between
margin-top: 6px
padding-top: 6px
border-top: 1px solid #3a3a3a    ← visual separator
```

---

## 7. Pagination — Detailed Design

```
 Showing 1 to 25 of 350 students                  «  Previous   1   2   3  ···  14   Next  »
 ▲                                                                 ▲
 .dataTables_info                                                  .dataTables_paginate
```

### Info Text (.dataTables_info)

| Property | Value |
|----------|-------|
| Color | `#a0a0a0` |
| Margin | `8px 0` |
| Format | `"Showing _START_ to _END_ of _TOTAL_ students"` |
| Empty state | `"No student records found. Upload an Excel file first."` |

### Pagination Buttons

| State | Background | Text Color | Border |
|-------|-----------|------------|--------|
| Default | `transparent` | `#a0a0a0` | `1px solid #3a3a3a` |
| Hover | `#333333` | `white` | `#e53935` |
| Current page | `#e53935` (red) | `white` | `#e53935` |
| Disabled | Same as default | Same | opacity `0.35` |

All pagination buttons have:
```
border-radius: 6px
margin: 0 2px
```

---

## 8. DataTable Configuration (Complete)

```javascript
{
    data: LOCAL_DATA,                          // Pre-normalized array of objects
    columns: DATA_KEYS.map(k => ({data: k})), // 26 column definitions
    order: [[0, 'asc']],                       // Default: sort by Sr No ascending
    pageLength: 25,                            // Show 25 rows per page
    lengthMenu: [10, 25, 50, 100, 500],       // Dropdown options
    scrollX: true,                             // Horizontal scroll (26 cols need it)
    deferRender: true,                         // Only render visible rows (perf)
    searching: false,                          // Disable built-in search box
    dom: 'Blfrtip',                            // Layout order of controls
    buttons: [
        { extend: 'csvHtml5',   text: 'Export CSV',   className: 'btn btn-sm btn-outline-secondary' },
        { extend: 'excelHtml5', text: 'Export Excel',  className: 'btn btn-sm btn-outline-success' }
    ],
    language: {
        lengthMenu: "Show _MENU_ records",
        info: "Showing _START_ to _END_ of _TOTAL_ students",
        emptyTable: "No student records found. Upload an Excel file first."
    }
}
```

### What Each Option Does

| Option | Value | Effect |
|--------|-------|--------|
| `data` | `LOCAL_DATA` | Pre-normalized JSON array (all values are strings) |
| `columns` | mapped from DATA_KEYS | Maps object keys to columns |
| `order` | `[[0, 'asc']]` | Sr No ascending by default |
| `pageLength` | `25` | Default page size |
| `lengthMenu` | `[10,25,50,100,500]` | Available page sizes |
| `scrollX` | `true` | Enables horizontal scroll; causes DataTables to clone `<thead>` |
| `deferRender` | `true` | DOM nodes created only for visible page |
| `searching` | `false` | Removes global search box entirely |
| `dom` | `'Blfrtip'` | Controls UI element order |
| `buttons` | CSV + Excel | Two export buttons in toolbar |

---

## 9. Color Palette — Complete Reference

### CSS Custom Properties

```css
:root {
    --bg-dark:          #121212     /* Body background */
    --bg-card:          #1e1e1e     /* Cards, panels, table bg */
    --bg-surface:       #2a2a2a     /* Headers, inputs, odd rows */
    --bg-hover:         #333333     /* Hover states */
    --text-primary:     #f0f0f0     /* Body text */
    --text-secondary:   #a0a0a0     /* Labels, muted text */
    --accent-red:       #e53935     /* Primary accent */
    --accent-red-hover: #ff5252     /* Accent hover state */
    --accent-white:     #ffffff     /* Headlines, active text */
    --border-color:     #3a3a3a     /* All borders */
    --border-light:     #444        /* Lighter borders */
}
```

### Color Usage Map

```
#121212  ░░░░░░░░░░░  Page background
#1e1e1e  ▓▓▓▓▓▓▓▓▓▓▓  Navbar, cards, panels, even table rows
#2a2a2a  ████████████  Table headers, inputs, odd table rows
#333333  ████████████  Hover states, filter buttons default bg
#3a3a3a  ────────────  All borders
#a0a0a0  Text         Secondary/muted text
#f0f0f0  Text         Primary body text
#ffffff  Text         Headlines, active elements
#e53935  ■■■■■■■■■■■  Red accent (buttons, active filters, borders)
#ff5252  ■■■■■■■■■■■  Red hover state
#4caf50  ■■■■■■■■■■■  Green (Export Excel button only)
```

---

## 10. Typography Reference

| Element | Size | Weight | Color | Transform |
|---------|------|--------|-------|-----------|
| Navbar brand | 1.3rem | 700 | #ffffff | none |
| Nav links | 0.9rem | 500 | #a0a0a0 / #fff | none |
| Page heading (h3) | default | 700 | #ffffff | none |
| Table headers | 0.82rem | 600 | #ffffff | uppercase |
| Table data | 0.82rem | normal | #f0f0f0 | none |
| Filter button | 0.74rem | normal | #a0a0a0 / #e53935 | none |
| Panel search | 0.78rem | normal | #f0f0f0 | none |
| Panel batch buttons | 0.7rem | 600 | #a0a0a0 | none |
| Panel list items | 0.78rem | 400 | #a0a0a0 | none |
| Panel count | 0.72rem | 600 | #a0a0a0 | none |
| Panel Apply button | 0.75rem | 600 | #ffffff | none |
| DataTables info | default | normal | #a0a0a0 | none |
| Font family | `'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif` |

---

## 11. Interactive States & Transitions

### Hover Effects

| Element | Default | Hover |
|---------|---------|-------|
| Nav link | gray text, transparent bg | white text, red bg |
| Table row | striped bg | `#333333` bg, white text |
| Filter button | gray border/text | red border, white text |
| Pagination button | gray border/text | `#333` bg, white text, red border |
| Export CSV | gray border/text | `#333` bg, lighter text |
| Export Excel | green border/text | green bg, white text |
| Panel list item | transparent bg | `#333` bg, lighter text |
| Batch button | transparent, gray border | `#333` bg, red border |
| Apply button | `#e53935` bg | `#ff5252` bg (lighter) |

### Transitions

| Element | Property | Duration |
|---------|----------|----------|
| Nav links | `all` | `0.2s` |
| Filter button | `border-color, color` | `0.15s` |
| Batch buttons | `all` | `0.15s` |
| Apply button | `background` | `0.15s` |
| List items | `background` | `0.1s` |
| Primary buttons | `all` | `0.2s` |

---

## 12. Responsive Behavior

| Aspect | Implementation |
|--------|---------------|
| **Container** | `.container-fluid` — full viewport width on all screens |
| **Horizontal overflow** | `scrollX: true` — DataTables adds horizontal scrollbar for 26 columns |
| **Vertical overflow** | DataTables pagination (25 rows default) prevents vertical overflow |
| **Navbar** | `navbar-expand-lg` — collapses to hamburger on small screens (Bootstrap behavior) |
| **Filter panel position** | `position: fixed` + dynamic calculation — adapts to button position |
| **Panel overflow** | Right-edge detection: if panel would extend past viewport, shifts left |
| **Table columns** | `white-space: nowrap` on headers — never wrap, always scroll |

---

## 13. External Dependencies Loaded

```html
<!-- CSS -->
Bootstrap 5.3.0               ← Grid, utilities, base styles
DataTables 1.13.7 (Bootstrap) ← Table widget styles
Buttons 2.4.2 (Bootstrap)     ← Export button styles
style.css                      ← Custom dark theme (overrides everything)

<!-- JavaScript -->
jQuery 3.7.0                   ← DOM manipulation, event handling
Bootstrap 5.3.0 bundle         ← Bootstrap components (popovers, modals, etc.)
DataTables 1.13.7              ← Table rendering engine
DataTables Bootstrap 5 adapter ← Bootstrap 5 integration
Buttons 2.4.2                  ← Export button framework
Buttons Bootstrap 5 adapter    ← Bootstrap styling for buttons
Buttons HTML5                  ← CSV/Excel export logic
JSZip 3.10.1                   ← .xlsx file generation (client-side)
filterSystem.js                ← Custom filter engine (shared module)
```

**Load order is critical**: jQuery → Bootstrap → DataTables → Buttons → JSZip → filterSystem.js → inline `<script>` init.

---

## 14. Data Flow (Dashboard Specific)

```
 Flask Server                    Browser
 ──────────                      ───────
 GET /dashboard
       │
       ├─ SELECT * FROM students
       │  ORDER BY sr_no
       │       │
       │       ▼
       │  rows = cursor.fetchall()
       │  (list of dicts)
       │       │
       ▼       ▼
 render_template("dashboard.html",
     students_json = rows)
       │
       ▼
 Jinja2 renders:
 <script type="application/json">
   {{ students_json | tojson }}    ──────►  "[{\"sr_no\":\"1\",...},...]"
 </script>                                  (double-escaped JSON string)
       │
       ▼ ─── Page delivered to browser ───
                                            │
                                     JSON.parse(textContent)
                                            │
                                            ▼
                                     initFilterSystem({
                                       data: parsedArray,
                                       ...
                                     })
                                            │
                                     ┌──────┴───────┐
                                     │              │
                              Pre-normalize    Cache uniques
                              all values       per column
                                     │              │
                                     ▼              ▼
                              DataTable.init()  Ready for
                              (renders rows)   lazy filter
                                               population
```

---

## 15. Empty State

When no data exists in the database:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Export CSV] [Export Excel]                        Show 25 ▼ records     │
├──────────────────────────────────────────────────────────────────────────┤
│ SR NO │ REG NO │ STUDENT NAME │ GENDER │ COURSE │ ...                   │
│ ▼ All │ ▼ All  │ ▼ All        │ ▼ All  │ ▼ All  │ ...                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│              No student records found. Upload an Excel file first.       │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ Showing 0 to 0 of 0 students                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

The empty message is styled in the table cell, centered, using DataTables' `language.emptyTable` config.

---

## 16. Z-Index Stacking Order

```
Layer 5:  z-index 99999   .cf-panel.open         ← Filter dropdown (topmost)
Layer 4:  (auto)           Bootstrap navbar       ← Navigation bar
Layer 3:  (auto)           .dataTables_scrollHead ← Cloned sticky header
Layer 2:  (auto)           .dataTables_scrollBody ← Table content
Layer 1:  (auto)           .container-fluid       ← Page content
Layer 0:  (auto)           body                   ← Background #121212
```
