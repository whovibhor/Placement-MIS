# Placement MIS — Full Architecture & Implementation

---

## 1. Project Structure

```
MIS Placements/
├── config.py                  # DB credentials & Flask secret
├── app.py                     # Flask server — all routes & DB logic
├── schema.sql                 # Reference SQL (app auto-creates tables)
├── fix_sr_no.py               # One-time migration script
├── requirements.txt           # pip dependencies
├── static/
│   └── style.css              # Dark theme + filter widget CSS
└── templates/
    ├── upload.html             # Excel upload page
    ├── dashboard.html          # Main data table + filters
    ├── versions.html           # Version history list
    └── version_detail.html     # Snapshot viewer + filters
```

---

## 2. Database Layer

**Engine:** MySQL on `localhost:3307`, charset `utf8mb4`, collation `utf8mb4_general_ci`.

**Three tables:**

| Table | Purpose | Key |
|---|---|---|
| `students` | Live student placement data (latest state) | `reg_no` (PK) |
| `upload_versions` | Metadata per upload (filename, timestamp, counts) | `version_id` (auto-increment PK) |
| `version_snapshots` | Frozen copy of each upload's rows | `id` (auto-increment PK), FK → `upload_versions.version_id` ON DELETE CASCADE |

**`students` table** — 26 columns matching the Excel template:

```
sr_no (INT), reg_no (VARCHAR PK), student_name, gender, course,
resume_status, seeking_placement, department, offer_letter_status,
status, company_name, designation, ctc, joining_date, joining_status,
school_name, mobile_number, email, graduation_course, graduation_ogpa,
percent_10, percent_12, backlogs, hometown, address (TEXT), reason (TEXT)
```

**Auto-creation:** `init_db()` in `app.py` runs at startup — creates the database and all three tables with `CREATE TABLE IF NOT EXISTS`.

---

## 3. Excel Upload Flow

**Route:** `POST /upload` → `app.py`

```
User uploads .xlsx
       │
       ▼
  ┌─────────────────┐
  │ Validate file    │  .xlsx only, not empty
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ pd.read_excel()  │  Read with openpyxl engine
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Normalize headers│  str.strip() each column name
  │                  │  HEADER_ALIASES: "0.1"→"10%", "0.12"→"12%"
  └────────┬────────┘  (pandas reads "10%" as float 0.1)
           ▼
  ┌─────────────────┐
  │ Validate headers │  Set-based: every EXPECTED_HEADER must exist
  │                  │  Extra columns are silently dropped
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Rename → DB cols │  HEADER_TO_COL mapping
  │ NaN → None       │  pd.notnull() filter
  │ sr_no → int      │  to_int_or_none() handles "1.0" → 1
  │ others → str     │  .strip() all string columns
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ UPSERT per row   │  INSERT ... ON DUPLICATE KEY UPDATE
  │                  │  Checks SELECT 1 first → counts insert vs update
  └────────┬────────┘
           ▼
  ┌─────────────────────────┐
  │ Save version snapshot    │
  │ 1. INSERT upload_versions│  filename, timestamp, counts
  │ 2. INSERT version_snapshots│  copy every row with version_id
  └─────────────────────────┘
```

**Key design decisions:**

- `reg_no` is the **primary key** — uploading the same student again updates their record (upsert)
- Every upload creates a **frozen snapshot** so you can view historical state
- The `ON DELETE CASCADE` on `version_snapshots.version_id` means deleting a version auto-deletes its snapshot rows

---

## 4. Dashboard — Data Loading

**Route:** `GET /dashboard` → `app.py`

```python
cursor.execute("SELECT * FROM students ORDER BY sr_no")
rows = cursor.fetchall()   # list of dicts (dictionary=True cursor)
return render_template("dashboard.html", students_json=rows)
```

**In the template** (`dashboard.html`):

```html
<script id="json-data" type="application/json">{{ students_json | tojson }}</script>
```

```javascript
var LOCAL_DATA = JSON.parse(document.getElementById('json-data').textContent);
```

**Why this approach instead of AJAX:**

| Approach | Latency | Why |
|---|---|---|
| ~~AJAX `/api/students`~~ | 2 round-trips (page + data) | Was slow — data arrived late, filters couldn't populate |
| **Inline `tojson`** | 1 round-trip (page with data) | Data is immediately available — zero delay for DataTables and filters |

The Jinja `tojson` filter serializes the Python list-of-dicts into JSON. It's placed in a `<script type="application/json">` tag (not `text/javascript`) so VS Code's JS parser doesn't choke on the `{{ }}` Jinja syntax.

---

## 5. DataTables Initialization

`dashboard.html`:

```javascript
var DATA_KEYS = [
    'sr_no', 'reg_no', 'student_name', 'gender', 'course', ...
    // 26 keys matching DB column names, in display order
];

var table = $('#studentsTable').DataTable({
    data: LOCAL_DATA,                          // ← no AJAX, direct array
    columns: DATA_KEYS.map(k => ({ data: k })),// ← maps keys to columns
    order: [[0, 'asc']],                       // sort by sr_no
    pageLength: 25,
    scrollX: true,                             // horizontal scroll for 26 cols
    dom: 'Blfrtip',                            // Buttons + length + filter + table + info + pagination
    buttons: ['csvHtml5', 'excelHtml5'],       // Export buttons (JSZip for Excel)
    initComplete: function() {
        populateAllFilters(this.api());         // ← populate filters AFTER table is ready
    }
});
```

**Column mapping flow:**

```
DB row dict:  { sr_no: 1, reg_no: "REG001", student_name: "John", ... }
DATA_KEYS[0]: "sr_no"        → <th>Sr No</th>         (column 0)
DATA_KEYS[1]: "reg_no"       → <th>Reg No</th>        (column 1)
DATA_KEYS[2]: "student_name" → <th>Student Name</th>  (column 2)
...
```

---

## 6. Column Filter System

This is the most complex frontend feature. Here's how it works:

### 6a. HTML Structure

The table header has **two rows**: one for column titles, one for filter widgets.

```html
<thead>
    <tr id="headerRow">          <!-- Column titles (Sr No, Reg No, ...) -->
    <tr id="filterRow"></tr>     <!-- Filter buttons (built by JS) -->
</thead>
```

Each filter cell is built dynamically:

```
┌──────────────────────────────────┐
│  [▼ All]  ← cf-btn (trigger)    │  ← <th> in filterRow
│                                  │
│  ┌──── cf-panel (dropdown) ────┐ │
│  │ [Search values...]          │ │  ← cf-search
│  │ [Select All] [Deselect All] │ │  ← cf-batch (cf-sel / cf-desel)
│  │ ☑ Opted In                  │ │
│  │ ☑ Not Opted In              │ │  ← cf-list <ul> with <li> items
│  │ ☑ (Blank)                   │ │
│  │ ─────────────────────────── │ │
│  │ 3 / 3          [Apply]     │ │  ← cf-foot (cf-count / cf-apply)
│  └─────────────────────────────┘ │
└──────────────────────────────────┘
```

### 6b. Populating Filter Values

`dashboard.html` — `populateAllFilters()`:

```javascript
function populateAllFilters(api) {
    api.columns().every(function(ci) {
        var key = DATA_KEYS[ci];     // e.g. "status"
        var seen = {};

        // Iterate ALL rows in LOCAL_DATA (not just visible page)
        LOCAL_DATA.forEach(function(row) {
            var raw = String(row[key]).trim();  // "Opted In", "opted in" → normalized
            var norm = raw.toLowerCase();        // case-insensitive dedup key
            if (!(norm in seen)) seen[norm] = raw;  // keep FIRST casing encountered
        });

        // Sort: blanks first, then alphabetical with numeric awareness
        var vals = Object.values(seen);
        vals.sort(/* locale-aware, numeric */);

        // Build HTML in one batch (fast) instead of per-item .append()
        var html = '';
        vals.forEach(function(val) {
            html += '<li data-val="..."><label><input checkbox checked><span>...</span></label></li>';
        });
        $list.html(html);   // single DOM write
    });
}
```

**Dedup logic:** `"Opted In"` and `"opted in"` share the same lowercase key `"opted in"` → only one entry appears. The first casing encountered is kept as the display value.

### 6c. Applying a Filter

When the user unchecks items and clicks **Apply** → `applyFilter(col)`:

```
User unchecks "Not Opted In", clicks Apply
       │
       ▼
┌─────────────────────────┐
│ Collect checked values   │  sel = ["Opted In"]
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Build regex              │  regex = "^(Opted In)$"
│                          │  (each value escaped for special chars)
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ DataTables column search │  table.column(col).search(regex, true, false).draw()
│                          │  arg2=true: regex mode
│                          │  arg3=false: no smart search
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Update button text       │  "▼ All" → "▼ 1 sel" + red highlight
└─────────────────────────┘
```

**Blank handling:** If `(Blank)` is selected, the regex includes `|)$` to match empty strings: `^(Opted In|)$`.

**If all selected or none selected** → clears the filter (shows everything).

### 6d. Event Delegation

All event handlers are **scoped to `#filterRow`** using jQuery's delegated event syntax:

```javascript
$fr.on('click', '.cf-btn', ...)       // Open/close dropdown
$fr.on('click', '.cf-list li', ...)   // Toggle checkbox
$fr.on('click', '.cf-list li label', function(e) { e.preventDefault(); })  // Prevent double-toggle
$fr.on('click', '.cf-sel', ...)       // Select All visible
$fr.on('click', '.cf-desel', ...)     // Deselect All visible
$fr.on('click', '.cf-apply', ...)     // Apply + close
$fr.on('mousedown', '.cf-panel', ...) // Prevent close on internal click
$(document).on('mousedown', ...)      // Close on outside click
```

**Why `e.preventDefault()` on label?** Without it, clicking the label triggers: (1) the label's native checkbox toggle, (2) the event bubbles to `<li>` which also toggles → net zero change. The `preventDefault` on label stops its native behavior, so only the `<li>` handler toggles.

### 6e. Panel Positioning

The dropdown uses `position: fixed` (not absolute) to escape any `overflow: hidden` containers:

```javascript
var r = this.getBoundingClientRect();     // button's screen position
$panel.css({ top: r.bottom + 2, left: r.left }).addClass('open');

// Clamp to viewport right edge
if (r.left + panelWidth > window.innerWidth) {
    $panel.css('left', window.innerWidth - panelWidth - 8);
}
```

---

## 7. Version History

| Route | Purpose |
|---|---|
| `GET /versions` | Lists all uploads with timestamp, record counts |
| `GET /versions/<id>` | Shows snapshot data for that upload (same DataTable + filters) |
| `POST /delete-version/<id>` | Deletes version + snapshots (CASCADE) |

The version detail page (`version_detail.html`) uses the **exact same** filter + DataTable code as the dashboard, but reads from `version_snapshots` instead of `students`.

---

## 8. CSS Architecture

`style.css` — ~540 lines, organized in sections:

| Section | Purpose |
|---|---|
| `:root` variables | Colors: `--bg-dark: #121212`, `--accent-red: #e53935`, etc. |
| Navbar | Dark bar with red bottom border |
| Cards, Forms, Buttons | Dark-themed Bootstrap overrides |
| Tables | Dark striped/hover rows, uppercase headers |
| DataTables overrides | Dark pagination, search box, sort arrows |
| `cf-*` classes | Filter widget: `cf-wrap`, `cf-btn`, `cf-panel`, `cf-search`, `cf-batch`, `cf-list`, `cf-foot`, `cf-apply`, `cf-count` |
| Scrollbar | Dark-themed scrollbar for WebKit browsers |

---

## 9. Data Flow Summary

```
                Excel File (.xlsx)
                      │
                      ▼
              ┌───────────────┐
              │  POST /upload  │  (Flask)
              │  pandas read   │
              │  validate/norm │
              │  UPSERT MySQL  │
              │  save snapshot │
              └───────┬───────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌──────────────┐
   │students │  │upload_   │  │version_      │
   │  table  │  │versions  │  │snapshots     │
   │(latest) │  │(metadata)│  │(frozen copy) │
   └────┬────┘  └────┬─────┘  └──────┬───────┘
        │             │               │
        ▼             ▼               ▼
   GET /dashboard  GET /versions  GET /versions/<id>
        │             │               │
        ▼             ▼               ▼
   SELECT * →      SELECT * →     SELECT * WHERE
   students_json   versions list   version_id = X
        │                              │
        ▼                              ▼
   {{ tojson }}                    {{ tojson }}
   in <script>                     in <script>
        │                              │
        ▼                              ▼
   JSON.parse →                    JSON.parse →
   LOCAL_DATA                      LOCAL_DATA
        │                              │
        ▼                              ▼
   DataTable(data: LOCAL_DATA)     DataTable(data: LOCAL_DATA)
   + populateAllFilters()          + populateAllFilters()
```

---

## 10. Tech Stack Summary

| Layer | Tech |
|---|---|
| **Backend** | Flask (Python 3.13), pandas + openpyxl |
| **Database** | MySQL 8 on port 3307, `mysql-connector-python` |
| **Frontend** | jQuery 3.7, Bootstrap 5.3, DataTables 1.13.7, JSZip |
| **Styling** | Custom dark theme CSS with CSS variables |
| **Data transfer** | Jinja2 `tojson` filter (inline, no AJAX) |
