# Placement MIS — Complete Project Architecture

> **Last updated**: February 2026  
> **Stack**: Python 3.13 · Flask · MySQL 8 · jQuery 3.7 · DataTables 1.13.7 · Bootstrap 5.3 · Chart.js 4.4.1  
> **Port**: `localhost:5000` (Flask dev server) · MySQL on port `3307`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Database Layer](#3-database-layer)
4. [Backend — app.py](#4-backend--apppy)
5. [Frontend — Templates](#5-frontend--templates)
6. [Static Assets](#6-static-assets)
7. [Feature-by-Feature Breakdown](#7-feature-by-feature-breakdown)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Optimization Notes & Potential Improvements](#9-optimization-notes--potential-improvements)

---

## 1. Project Overview

This is a **Management Information System (MIS) for college placement data**. It allows administrators to:

- Upload placement data from Excel (.xlsx) files
- View, filter, and search student records in a rich data table
- See analytics dashboards with charts
- Edit student records inline (with full change logging)
- Upload documents per student (resumes, offer letters)
- Export filtered data to professionally formatted Excel sheets
- Maintain version history of every upload

The app follows a **server-rendered monolith** pattern: Flask serves HTML templates with embedded JSON data, and jQuery handles client-side interactivity. There is no SPA framework — all routing is server-side, with AJAX used only for search, inline editing, and change logs.

---

## 2. Directory Structure

```
MIS Placements/
├── app.py                    # Flask application — all routes, logic, DB operations
├── config.py                 # Database credentials, secret key
├── requirements.txt          # Python dependencies (4 packages)
├── schema.sql                # Reference SQL schema (app auto-creates tables)
├── fix_sr_no.py              # One-time script to fix serial numbers
├── static/
│   ├── style.css             # Global dark-theme CSS (~1412 lines)
│   ├── filterSystem.js       # Reusable Excel-style column filter engine (~364 lines)
│   └── globalSearch.js       # Navbar autocomplete search widget (~65 lines)
├── templates/
│   ├── dashboard.html        # Analytics dashboard with 7 charts (~312 lines)
│   ├── data.html             # Data table page with filters, export, saved views (~662 lines)
│   ├── upload.html           # Excel upload page (~98 lines)
│   ├── student_profile.html  # Individual student profile with inline editing (~364 lines)
│   ├── versions.html         # Version history + Change Log tabs (~207 lines)
│   └── version_detail.html   # Snapshot data for a specific upload version (~95 lines)
└── uploads/                  # Uploaded student files (resumes, offer letters, etc.)
```

---

## 3. Database Layer

### 3.1 Connection Configuration (`config.py`)

```python
DB_HOST     = "localhost"
DB_PORT     = 3307
DB_USER     = "root"
DB_PASSWORD = "admin"
DB_NAME     = "placementmis"
```

Connection is created per-request via `get_connection()` — there is **no connection pooling**. Each route opens a connection, runs queries, and closes it.

### 3.2 Tables (5 total, auto-created by `init_db()`)

#### `students` — Main data table (1537 rows)

| Column | Type | Notes |
|--------|------|-------|
| `sr_no` | INT | Serial number from Excel, NOT auto-increment |
| `reg_no` | VARCHAR(50) | **PRIMARY KEY** — Registration number |
| `student_name` | VARCHAR(200) | |
| `gender` | VARCHAR(20) | Male / Female |
| `course` | VARCHAR(100) | e.g., "B Tech CSE", "MBA", "BCA" |
| `resume_status` | VARCHAR(100) | Yes / No |
| `seeking_placement` | VARCHAR(100) | Opted In / Opted Out / Not Registered / Debarred |
| `department` | VARCHAR(100) | e.g., "Computer Science", "Management" |
| `offer_letter_status` | VARCHAR(100) | Yes / No / Mail Only / LOI / Confirmation Message |
| `status` | VARCHAR(100) | Placed / Unplaced |
| `company_name` | VARCHAR(200) | |
| `designation` | VARCHAR(200) | |
| `ctc` | VARCHAR(100) | Stored as string, parsed to float when needed |
| `joining_date` | VARCHAR(100) | Stored as string (not DATE type) |
| `joining_status` | VARCHAR(100) | Joined / Not Joined / Pending |
| `school_name` | VARCHAR(200) | Not displayed in UI (hidden from DISPLAY_COLUMNS) |
| `mobile_number` | VARCHAR(50) | |
| `email` | VARCHAR(200) | |
| `graduation_course` | VARCHAR(100) | |
| `graduation_ogpa` | VARCHAR(50) | |
| `percent_10` | VARCHAR(50) | 10th grade percentage |
| `percent_12` | VARCHAR(50) | 12th grade percentage |
| `backlogs` | VARCHAR(50) | Number of backlogs, parsed for eligibility |
| `hometown` | VARCHAR(200) | |
| `address` | TEXT | |
| `reason` | TEXT | Reason (for opted out, etc.) |

**Design choice**: All numeric-like fields (CTC, backlogs, percentages) are stored as VARCHAR. This avoids parsing errors on upload but requires `float()` / `parseFloat()` at runtime for computations.

#### `upload_versions` — Upload history

| Column | Type | Notes |
|--------|------|-------|
| `version_id` | INT AUTO_INCREMENT | PK |
| `filename` | VARCHAR(255) | Original Excel filename |
| `uploaded_at` | DATETIME | |
| `total_records` | INT | |
| `inserted` | INT | New records count |
| `updated` | INT | Existing records updated count |

#### `version_snapshots` — Full data snapshot per upload

Mirrors every column of `students` plus `version_id` FK. Stores the **exact state of each record at upload time**, enabling historical comparison.

- FK: `version_id → upload_versions(version_id) ON DELETE CASCADE`

#### `student_files` — Uploaded documents

| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | PK |
| `reg_no` | VARCHAR(50) | FK → students(reg_no) ON DELETE CASCADE |
| `file_type` | VARCHAR(50) | resume / offer_letter / loi / confirmation / other |
| `original_name` | VARCHAR(255) | User's original filename |
| `stored_name` | VARCHAR(255) | UUID-based stored filename |
| `uploaded_at` | DATETIME | |

Files are physically stored in `./uploads/` directory with names like `{reg_no}_{type}_{uuid8}.ext`.

#### `edit_log` — Change tracking

| Column | Type | Notes |
|--------|------|-------|
| `id` | INT AUTO_INCREMENT | PK |
| `reg_no` | VARCHAR(50) | Which student |
| `student_name` | VARCHAR(200) | Denormalized for display convenience |
| `field_name` | VARCHAR(100) | Which column was changed |
| `old_value` | TEXT | Previous value |
| `new_value` | TEXT | New value |
| `changed_at` | DATETIME | When |
| | Indexes | `idx_reg(reg_no)`, `idx_time(changed_at)` |

### 3.3 Schema Design Observations

- **No foreign keys from `edit_log` to `students`** — Allows edit log to survive even if student is deleted.
- **`student_name` is denormalized in `edit_log`** — Avoids a JOIN when displaying the log. Trade-off: if student name changes, old log entries still show the old name.
- **All fields are VARCHAR/TEXT** — Maximum flexibility but no database-level type validation. All validation happens in Python.
- **No `created_at` or `updated_at` on students table** — No timestamp tracking for when a student record was last modified (edit_log serves this purpose indirectly).

---

## 4. Backend — app.py

### 4.1 Application Setup (Lines 1–97)

```python
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import pandas as pd, mysql.connector, re, statistics, os, uuid
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
```

**Key constants defined**:

| Constant | Purpose |
|----------|---------|
| `EXPECTED_HEADERS` (26 items) | Exact Excel column names expected in uploaded files |
| `HEADER_TO_COL` | Maps Excel header names → DB column names (e.g., "Registration Number" → "reg_no") |
| `DB_COLUMNS` | Ordered list of all 26 DB column names |
| `DISPLAY_COLUMNS` | Same as DB_COLUMNS minus `school_name` (25 columns shown in UI) |
| `EDITABLE_COLUMNS` | All columns except `sr_no` and `reg_no` — controls which fields can be edited via API |

### 4.2 Database Helpers (Lines 97–220)

#### `get_connection()`
Creates a new MySQL connection per call using config credentials. Uses `utf8mb4` charset with `utf8mb4_general_ci` collation.

**Concern**: No connection pooling. Every route opens and closes its own connection. Under load, this would hit MySQL's max_connections limit.

#### `init_db()`
Called once at startup (`if __name__ == "__main__"`). Creates the database and all 5 tables using `CREATE TABLE IF NOT EXISTS`. This makes the app self-bootstrapping — no manual SQL needed.

### 4.3 Analytics Engine (`compute_analytics()`, Lines 222–367)

This is the core analytics function. It takes a list of student dicts and returns a comprehensive analytics dictionary.

**Eligibility Logic** (used throughout the app):
```python
def is_eligible(r):
    if r.get("seeking_placement") != "Opted In":
        return False
    try:
        return float(r.get("backlogs") or 0) < 3
    except (ValueError, TypeError):
        return True  # If backlogs is not a number, assume eligible
```

A student is **eligible** if:
1. They have `seeking_placement == "Opted In"`, AND
2. Their `backlogs` count is less than 3 (or not a valid number → assumed eligible)

**Computed metrics**:

| Metric | Formula |
|--------|---------|
| `total` | `len(rows)` |
| `opted_in` | Count where `seeking_placement == "Opted In"` |
| `opted_out` | Count where `seeking_placement == "Opted Out"` |
| `not_registered` | Count where `seeking_placement == "Not Registered"` |
| `debarred` | Count where `seeking_placement == "Debarred"` |
| `eligible` | Count matching `is_eligible()` |
| `ineligible` | `opted_in - eligible` |
| `placed` | Count where `status == "Placed"` |
| `unplaced` | `opted_in AND NOT placed` |
| `placement_rate` | `placed / eligible * 100` |
| `avg_ctc` | Mean of CTC values from placed students |
| `median_ctc` | Median of CTC values |
| `max_ctc` / `min_ctc` | Extremes |
| `dept_labels/placed/total/eligible` | Per-department breakdown, sorted by placed count descending |
| `company_labels/values` | Top 10 companies by placement count |
| `gender_counts` | Count per gender |
| `gender_placement` | Placed vs total per gender |
| `ctc_dist_labels/values` | CTC histogram in 2 LPA buckets (0-2, 2-4, ..., 14+) |
| `dept_course_breakdown` | Nested: department → course → {total, placed, eligible} |
| `top_company` | Company with most placements |

**CTC parsing**: CTC is stored as VARCHAR. The function does `float(r["ctc"])` and silently skips failures. This means invalid CTC values like "N/A" or empty strings are simply excluded from statistics.

### 4.4 Routes

#### `GET /` → redirect to `/dashboard`
Simple redirect. Index page sends users to the analytics dashboard.

#### `GET /upload` + `POST /upload` — Excel Upload

**GET**: Renders the upload form.

**POST flow**:
1. Validate file exists and has `.xlsx` extension
2. Read with `pandas.read_excel(file, engine="openpyxl")`
3. **Normalize headers**: Strip whitespace, apply aliases (`"0.1"` → `"10%"`, `"0.12"` → `"12%"`)
4. **Validate headers**: Check all 26 expected headers are present
5. **Clean data**:
   - `sr_no`: Convert to int (via float intermediate for "1.0" style values)
   - All other fields: Convert to string, strip whitespace, convert `"nan"` and empty strings to `None`
6. **Fix percent decimals**: For `percent_10` and `percent_12`:
   - Strip `"CGPA"` / `"GPA"` prefixes
   - Convert `"__"` / `"_"` / `""` to None
   - If value is between 0 and 1 (exclusive), multiply by 100 (e.g., `0.6` → `60`)
7. **Upsert to MySQL**: Uses `INSERT ... ON DUPLICATE KEY UPDATE` for each row
   - Tracks `inserted` vs `updated` counts
8. **Save version snapshot**: Creates `upload_versions` entry, then copies all rows to `version_snapshots` with the version_id
9. Flash success/error message, redirect back to upload page

**Data cleaning logic detail** (percent fix):
```python
def fix_pct(v):
    if v is None: return None
    cleaned = re.sub(r'^(C?GPA)\s*', '', v, flags=re.IGNORECASE).strip()
    if cleaned in ('__', '_', ''): return None
    try:
        num = float(cleaned)
        if 0 < num <= 1:
            num = round(num * 100, 1)
            cleaned = str(int(num)) if num == int(num) else str(num)
    except ValueError:
        pass
    return cleaned
```

This handles messy Excel data where percentages might be entered as decimals (0.85), with prefixes ("CGPA 8.5"), or as placeholder characters ("__").

#### `GET /dashboard` — Analytics Dashboard

Fetches all students, computes analytics via `compute_analytics()`, passes to `dashboard.html`. The template renders:
- Stat cards (Total, Opted In, Eligible, Placed, Placement Rate, CTC stats)
- 7 Chart.js charts
- Department → Course breakdown (collapsible)
- Recent changes (AJAX from `/api/edit-log?limit=15`)

#### `GET /data` — Data Table Page

Fetches all students, computes analytics (for tile counts), passes both `students_json` and `analytics` to `data.html`. The heavy lifting happens client-side — filterSystem.js handles the table.

#### `PUT /api/student/<reg_no>` — Inline Edit (Single Field)

**Flow**:
1. Parse JSON body: `{ "field": "...", "value": "..." }`
2. Validate `field` is in `EDITABLE_COLUMNS`
3. Empty string → None
4. **Data validation**:
   - `ctc`: Must parse as `float()`
   - `email`: Must match `^[^@\s]+@[^@\s]+\.[^@\s]+$`
   - `mobile_number`: Must have at least 10 digits (counted via `re.findall(r'\d', ...)`)
5. Fetch current value from DB
6. If unchanged → return early with `unchanged: true`
7. Update the field
8. Insert into `edit_log` with old_value, new_value, timestamp
9. Return success JSON

**Security**: Uses `EDITABLE_COLUMNS` whitelist — `sr_no` and `reg_no` cannot be modified.

**Concern**: The SQL uses f-string for column name (`f"UPDATE students SET \`{field}\` = %s"`). While the field is validated against `EDITABLE_COLUMNS`, this is technically SQL injection-adjacent. Parameterized column names aren't possible in MySQL, so the whitelist validation is the defense.

#### `DELETE /api/student/<reg_no>` — Delete Student

Simple delete by reg_no. Returns 404 if not found.

#### `GET /student/<reg_no>` — Student Profile Page

Fetches student data + uploaded files, renders `student_profile.html`. If student not found, flashes error and redirects to dashboard.

#### `POST /student/<reg_no>/upload-file` — File Upload for Student

1. Receives multipart file + `file_type` field
2. Generates unique filename: `{reg_no}_{file_type}_{uuid8}{ext}`
3. Saves to `uploads/` directory
4. Records in `student_files` table

#### `GET /uploads/<filename>` — Serve Uploaded Files

Uses Flask's `send_from_directory` to serve files from the uploads folder.

#### `POST /student/<reg_no>/delete-file/<file_id>` — Delete an Uploaded File

Deletes from both disk and database.

#### `PUT /api/student/<reg_no>/bulk-update` — Bulk Field Update

Used by the student profile page. Accepts `{ "fields": { "field1": "value1", "field2": "value2" } }`. Updates each changed field individually and logs each change to `edit_log`.

**Logic**: Iterates through fields, skips unchanged ones, updates each individually. This means N SQL UPDATE statements for N changed fields (not a single multi-column UPDATE).

#### `GET /api/edit-log` — Change Log API (Paginated)

Supports:
- `limit` (default 200)
- `page` (default 1)
- `reg_no` (optional filter for a specific student)

Returns: `{ data: [...], page, total_pages, total_count }`

Formats `changed_at` as `"%d %b %Y, %I:%M %p"` (e.g., "22 Feb 2026, 03:45 PM").

#### `GET /api/students` — All Students as JSON

Simple API returning all students ordered by sr_no.

#### `GET /api/search` — Global Search

Searches across `student_name`, `reg_no`, `course`, and `company_name` using `LIKE %query%`. Returns top 15 matches. Requires minimum 2 characters.

#### `POST /drop-all` — Delete All Students

Destructive: `DELETE FROM students`. Used from the upload page's "danger zone".

#### `GET /versions` — Version History Page

Lists all upload versions ordered by date descending.

#### `GET /versions/<version_id>` — Version Snapshot Detail

Fetches all `version_snapshots` for a specific version, renders them in a DataTable.

#### `GET /api/version/<version_id>` — Version Snapshot as JSON

Returns snapshot data as JSON for API consumption.

#### `POST /delete-version/<version_id>` — Delete a Version

Removes both `version_snapshots` and `upload_versions` entries.

### 4.5 App Startup

```python
if __name__ == "__main__":
    init_db()              # Create database + tables if not exist
    app.run(debug=True, port=5000)
```

---

## 5. Frontend — Templates

### 5.1 Shared Patterns Across All Templates

- **Navbar**: Every page has the same navbar with brand link, global search input, and 4 nav links (Upload, Dashboard, Data, Versions)
- **Dark theme**: All pages use `style.css` which provides a dark background (#121212) with red (#e53935) accents
- **Global search**: Input `#globalSearch` + dropdown `#globalSearchResults`, powered by `globalSearch.js` on every page
- **No template inheritance**: Each template is a standalone HTML file — no Jinja2 `{% extends %}`. Common elements (navbar, head) are duplicated across templates
- **Flash messages**: Standard Flask flash pattern with `get_flashed_messages(with_categories=true)`

### 5.2 `dashboard.html` (~312 lines)

**Purpose**: Analytics-only dashboard. No data table — that moved to `/data`.

**Layout**:
```
[Navbar]
[Stat Cards Row 1] — Total, Opted In, Eligible, Placed, Placement Rate
[CTC Summary Row]  — Avg CTC, Median CTC, Highest CTC, Top Recruiter
[Muted Row]        — Opted Out, Ineligible
[Charts Grid]      — 7 charts in 2-column grid
[Dept Breakdown]   — Collapsible department → course tables
[Recent Changes]   — AJAX-loaded recent edit log
```

**Data binding**: Analytics object serialized into `<script id="analytics-data" type="application/json">{{ analytics | tojson }}</script>`, parsed with `JSON.parse()`.

**7 Charts (Chart.js 4.4.1)**:

| Chart | Type | Data Source | Spans |
|-------|------|-------------|-------|
| Department-wise | Horizontal Bar | `dept_labels`, `dept_placed`, `dept_eligible`, `dept_total` | 2 cols |
| Placement Status | Doughnut | Computed from placed/eligible/ineligible/opted-out | 1 col |
| Top Companies | Horizontal Bar | `company_labels`, `company_values` (top 10) | 1 col |
| Gender Distribution | Doughnut | `gender_counts` | 1 col |
| Gender Placement | Bar | `gender_placement[gender].placed/total` | 1 col |
| CTC Distribution | Bar | `ctc_dist_labels`, `ctc_dist_values` (histogram) | 2 cols |

**Dept → Course Breakdown** (JS-generated):
Iterates `analytics.dept_course_breakdown`, creates Bootstrap collapsible blocks. Each department shows an inline summary ("X Placed / Y Eligible / Z Total") and expands to a table with per-course details including placement rate.

**Recent Changes** (AJAX):
`$.getJSON('/api/edit-log?limit=15')` fetches recent edits, renders a table with time, reg_no (linked to profile), student name, field changed, old value (red), new value (green).

### 5.3 `data.html` (~662 lines)

**Purpose**: The main data table with all filtering, export, and column management features.

**Layout**:
```
[Navbar]
[Data Toolbar]     — Export Excel, Columns toggle, Save View, Saved Views dropdown
[Filter Tiles]     — All Students / By Status (5) / By Program (4)
[Stats Panel]      — Contextual stats when a filter tile is active
[Save View Modal]  — Name input, confirm button
[Export Modal]     — Column picker with Select All/Deselect All, export button
[Data Table]       — 25-column DataTable with filter row
```

**Data injection**: `{{ students_json | tojson }}` → `<script id="json-data">` → `JSON.parse()`.

**Column Order** (25 columns, school_name excluded):
```
Sr No → Reg No → Student Name → Gender → Course → Department →
Mobile Number → Email → Seeking Placement → Status →
Company Name → Designation → CTC → Graduation/OGPA →
10% → 12% → Backlogs → Hometown → Address → Reason →
Resume Status → Offer Letter Status → Joining Date →
Joining Status → Graduation Course
```

**Key JavaScript sections** (all in a single `$(document).ready()` block):

1. **DATA_KEYS & HEADER_MAP**: Define column order and display names
2. **filterApi initialization**: Calls `initFilterSystem()` with data, keys, and table config
3. **Column Visibility Toggle**: Creates checkboxes for each column in the Columns dropdown. Uses DataTables `table.column(idx).visible()` API. "Minimal" preset shows only 9 key columns.
4. **Filter Definitions**: `FILTER_FUNCTIONS` object with 10 filter functions (all, placed, unplaced, eligible, ineligible, opted_out, cse, mba, bba, pharmacy)
5. **Program tile counts**: Computes CSE/MBA/BBA/Pharmacy counts from raw data on page load
6. **Stats computation**: `computeViewStats(data)` calculates total, opted in, eligible, placed, mean/median/highest CTC, placement rate for the currently filtered view
7. **Tile click handler**: Mutual exclusion — clicking any tile sets `activeFilter`, highlights it, and calls `filterApi.setPreFilter()`
8. **Export with column picker**: Opens modal with checkboxes, builds AOA (array of arrays), applies styles via xlsx-js-style
9. **Saved Views**: CRUD system using localStorage

### 5.4 `upload.html` (~98 lines)

**Purpose**: Simple form to upload .xlsx files + danger zone to delete all data.

**Key logic**:
- File input accepts only `.xlsx`
- On submit: Disables button, shows spinner with "Processing..."
- On file select: Shows filename below input field
- "Drop All Data" button behind a `confirm()` guard

### 5.5 `student_profile.html` (~364 lines)

**Purpose**: Detailed view of a single student with inline editing, file management, and change history.

**Layout**:
```
[Navbar]
[Toast Notification]
[Profile Header]      — Name, reg_no, department, course, status/eligibility badges
[Personal Info]        — Editable grid: Name, Gender, Mobile, Email, Hometown, Address
[Academic Info]        — Editable grid: Course, Department, Grad Course, OGPA, 10%, 12%, Backlogs
[Placement Info]       — Editable: Seeking Placement, Resume Status, Status, Reason
  [Placement Details]  — Conditional: Company, Designation, CTC, Offer Letter, Joining Date/Status
[Files/Documents]      — List + upload form
[Change History]       — AJAX-loaded table
```

**Inline Editing Mechanism** (detailed):

1. **Click** on `.editable-field` (the value display span)
2. If field already has an input/select → return (prevent double-edit)
3. Read `data-field` from parent `.profile-field`, get current text (treat "—" as empty)
4. **Create input**:
   - If `data-choices` attribute exists on the `.editable-field` → create `<select>` with those options + "— Clear —"
   - Otherwise → create `<input type="text">`
5. Replace text content with the input element, focus it
6. **Save triggers**: `blur` event (with 100ms setTimeout to avoid race conditions), `Enter` key, or `change` on selects
7. **`saveField()` function**:
   - Read new value from the input
   - Restore text display immediately (optimistic UI)
   - If unchanged → return
   - If field is `status` and value is `Placed` → slide down `#placementDetails`; otherwise slide up
   - Send `PUT /api/student/{reg_no}` with `{ field, value }`
   - **Success**: Show green toast, reload change log
   - **Error**: Show red toast, revert display text to original value
8. **Escape key**: Revert to original without saving

**Placement details visibility**: The "Company Name / Designation / CTC / Offer Letter / Joining Date / Status" section is only shown when `status == "Placed"`. Changing the Status field dynamically shows/hides this section.

**Change History**: `loadChangeLog()` fetches `GET /api/edit-log?reg_no={REG_NO}&limit=50`, renders table with time, field (underscores replaced with spaces for readability), old value (red text), new value (green text). Called on page load and after every successful edit.

### 5.6 `versions.html` (~207 lines)

**Purpose**: Two-tab page: Upload Versions table + Change Log viewer.

**Upload Versions Tab**:
- Table: Version #, Filename, Uploaded At, Total Records, Inserted (green badge), Updated (yellow badge)
- Actions per row: "View Data" link → `/versions/{id}`, "Delete" form → POST

**Change Log Tab**:
- Lazy-loaded: Only fetches data when tab is first activated
- Client-side search filter on reg_no/name
- Configurable limit (50/100/200)
- Server-side pagination with Prev/Page X of Y/Next controls
- Each row: Time, Reg No (linked to profile), Student Name, Field Changed, Old Value (red), New Value (green)

### 5.7 `version_detail.html` (~95 lines)

**Purpose**: Shows snapshot data for a specific upload version in a DataTable.

Uses `initFilterSystem()` with all 26 columns (including `school_name`). Back button to versions page. No global search on this page.

---

## 6. Static Assets

### 6.1 `style.css` (~1412 lines) — Dark Minimal Theme

**Design system**:

| Variable | Value | Usage |
|----------|-------|-------|
| `--bg-dark` | `#121212` | Page background |
| `--bg-card` | `#1e1e1e` | Card/panel backgrounds |
| `--bg-surface` | `#2a2a2a` | Input fields, table headers, secondary surfaces |
| `--bg-hover` | `#333333` | Hover states |
| `--text-primary` | `#f0f0f0` | Main text |
| `--text-secondary` | `#a0a0a0` | Labels, muted text |
| `--accent-red` | `#e53935` | Primary action color (buttons, borders, highlights) |
| `--accent-red-hover` | `#ff5252` | Hover state for red elements |
| `--accent-white` | `#ffffff` | Headers, strong emphasis |
| `--border-color` | `#3a3a3a` | Default borders |

**Major CSS sections**:

| Section | Lines | What It Styles |
|---------|-------|----------------|
| Reset & Body | 20–29 | Box-sizing, dark background, font stack |
| Navbar | 31–57 | Dark card BG, red bottom border, nav links |
| Cards | 59–83 | Dark cards with rounded corners |
| Forms | 85–116 | Dark inputs with red focus glow |
| Buttons | 118–185 | Red primary, outlined variants |
| Alerts | 187–211 | Semi-transparent colored backgrounds |
| Typography | 213–228 | Headers, muted text, hr |
| Tables | 230–274 | Dark theme table overrides |
| Badges | 276–289 | Green success, yellow warning |
| DataTables Overrides | 291–354 | Length/filter/info/paginate dark theme |
| Column Filters (.cf-*) | 356–506 | Complete filter dropdown system |
| Scrollbar | 508–522 | Custom webkit scrollbar |
| Upload Page | 536–646 | Upload form, dropzone, danger zone |
| DataTables Layout | 648–714 | Top bar (length + search), bottom bar (info + paginate) |
| Stat Cards | 716–778 | Dashboard stat cards with hover lift |
| Charts | 780–831 | Chart grid layout, canvas sizing |
| Quick-View Tiles | 833–884 | Clickable filter tiles with active glow |
| Program Stats Panel | 886–928 | Contextual stats panel with red border |
| Table Hints | 930–945 | Italic hint text, clickable student name (blue, cursor pointer) |
| Profile Page | 972–1072 | Profile header, info grid, files list |
| Dashboard Sections | 1074–1094 | Section cards with red titles |
| Inline Editing | 1096–1132 | Editable field hover border, inline input styling |
| Nav Tabs | 1134–1160 | Dark theme tab overrides |
| Global Search | 1174–1260 | Search input, dropdown, result items |
| Dept Breakdown | 1262–1312 | Collapsible department blocks |
| Data Toolbar | 1314–1332 | Flex toolbar with button overrides |
| Saved Views | 1334–1378 | Dropdown items with delete button |
| Sticky Header | 1390–1404 | Sticky thead with z-index layering |
| Column/Export Toggle | 1406–1412 | Checkbox dark theme, .btn-xs |

### 6.2 `filterSystem.js` (~364 lines) — Excel-Style Column Filter Engine

**Architecture**: A reusable module exported as `initFilterSystem(opts)`. Returns a public API object.

**Initialization flow**:
1. Pre-normalize all data values to trimmed strings (avoids repeated string conversion)
2. Cache unique values per column in a single scan (Set per column)
3. Build filter row: For each column, adds a `<th>` with a `▼ All` button to `#filterRow`, and appends a `.cf-panel` div to `<body>`
4. Initialize DataTable with the data

**8 Optimizations implemented**:

| # | Optimization | How |
|---|-------------|-----|
| 1 | Pre-normalize data | All values → `String(v).trim()` once at load. No conversion during filtering |
| 2 | Compiled Set filters | `ACTIVE_FILTERS` values compiled to `Set` objects for O(1) lookup |
| 3 | Single-pass filter | One loop through data with all predicates checked per row |
| 4 | Draw without pagination reset | `table.draw(false)` preserves current page |
| 5 | Short-circuit | If no column filters active → skip filter loop entirely |
| 6 | Cached unique values | `COLUMN_UNIQUE_VALUES` computed once, used for all filter panel populations |
| 7 | Lazy population | Filter panel checkboxes only built on first open (not upfront for all 25 columns) |
| 8 | Extracted module | Reusable across data.html and version_detail.html |

**Filter panel interaction flow**:
1. Click `▼ All` button → opens `.cf-panel` positioned below the button
2. First open: Lazy-populate checkboxes from `COLUMN_UNIQUE_VALUES` (sorted, blanks first)
3. User can search (text filter on visible checkboxes), select/deselect with batch buttons
4. Click "Apply" → Reads checked values, stores in `ACTIVE_FILTERS[columnKey]`
5. `applyAllFilters()` runs:
   - Start with `preFilterFn ? LOCAL_DATA.filter(preFilterFn) : LOCAL_DATA`
   - If no column filters: show pre-filtered set
   - Compile active filters to Set objects
   - Single-pass: keep rows where all compiled filters match
   - Replace DataTable data and redraw

**Pre-filter system**: External code (data.html's tile click handler) calls `filterApi.setPreFilter(fn)` to set a pre-filter function. This runs before column filters. Pre-filter + column filters compose: pre-filter narrows the dataset, then column filters further narrow within that set.

**Public API** (returned object):

| Method | Signature | Description |
|--------|-----------|-------------|
| `setPreFilter` | `(fn) → void` | Set/clear pre-filter function. `null` clears. Immediately reapplies filters |
| `getColumnFilters` | `() → object` | Returns deep copy of current `ACTIVE_FILTERS` state |
| `setColumnFilters` | `(filters) → void` | Restores a previously saved filter state. Updates button labels & checkboxes |
| `clearColumnFilters` | `() → void` | Clears all column filters, resets all buttons to "▼ All" |
| `getCurrentData` | `() → array` | Returns the currently filtered dataset (pre-filter + column filters applied) |
| `getRawData` | `() → array` | Returns the full pre-normalized dataset (no filters) |
| `getTable` | `() → DataTable` | Returns the DataTable instance for direct manipulation |

### 6.3 `globalSearch.js` (~65 lines) — Navbar Autocomplete

**Pattern**: Self-executing IIFE with debounced AJAX search.

**Flow**:
1. User types in `#globalSearch` input
2. Input event fires → clears previous debounce timer
3. If < 2 characters → hide dropdown, return
4. After 250ms debounce → `$.getJSON('/api/search?q=...')`
5. Render results in `#globalSearchResults` dropdown:
   - Each result: Student name + "Placed" badge (if applicable) + reg_no + course
   - Click → navigates to `/student/{reg_no}`
6. Enter key → navigates to first result
7. Click outside → hides dropdown
8. Focus on input → re-shows dropdown if it has content

---

## 7. Feature-by-Feature Breakdown

### 7.1 Excel Upload & Data Ingestion

**Files involved**: `app.py` (POST /upload route), `upload.html`

**Logic**:
- Pandas reads .xlsx with openpyxl engine
- Header normalization handles Excel quirks (e.g., "0.1" column name for 10%)
- Data cleaning pipeline: null handling → string conversion → percent decimal fix → CGPA prefix strip
- UPSERT via `INSERT ... ON DUPLICATE KEY UPDATE` — new students are inserted, existing ones updated
- Every upload creates a version snapshot (full copy of all uploaded rows)

**Concern**: The entire DataFrame is iterated row-by-row with `cursor.execute()` inside a loop. For 1537 rows this is fine, but for larger datasets (10000+), `executemany()` or batch inserts would be significantly faster.

### 7.2 Analytics Dashboard

**Files involved**: `app.py` (compute_analytics), `dashboard.html`

**Logic**:
- All computation happens server-side in Python
- Single pass through data for most metrics (though multiple `sum()` and `filter()` calls means ~10 passes total)
- Chart.js charts are initialized client-side from the serialized analytics JSON
- Department → Course breakdown is a nested object generated server-side, rendered client-side with JS

**Concern**: `compute_analytics()` does many passes through the data (one per metric). A single-pass approach would be more efficient for large datasets but would sacrifice readability.

### 7.3 Data Table with Filtering

**Files involved**: `data.html`, `filterSystem.js`, `style.css`

**Architecture**:
```
[Tile Tiles]      ──▶ setPreFilter(fn)  ──▶ ┌─────────────────────┐
[Column Filters]  ──▶ ACTIVE_FILTERS{}  ──▶ │ applyAllFilters()   │
                                            │ 1. preFilter(data)   │
                                            │ 2. column filters    │
                                            │ 3. table.rows.add()  │
                                            │ 4. table.draw(false) │
                                            └─────────────────────┘
```

**Two-layer filtering**:
1. **Pre-filter (tile)**: Course-level or status-level filter. Only one active at a time (mutual exclusion via `qv-tile--active` class management)
2. **Column filters**: Excel-style per-column value selection. Multiple can be active simultaneously. Compose with pre-filter.

**Mutual exclusion for tiles**: When clicking any tile, ALL tiles lose `qv-tile--active`, then only the clicked one gets it. `setPreFilter()` replaces the previous pre-filter entirely.

**Program tile definitions**:
- **CSE**: Matches 5 courses: B Tech AI, B Tech CSE, BCA, MCA, MTech CS (using `indexOf() === 0` for prefix matching)
- **MBA**: Courses starting with "MBA"
- **BBA**: Courses starting with "BBA"
- **Pharmacy**: Courses starting with "B Pharmacy" or "M Pharmacy"

### 7.4 Column Visibility Toggle

**Files involved**: `data.html`, `style.css`

**Logic**:
- On page load: Iterates `DATA_KEYS`, creates a checkbox per column in the `#colToggleMenu` dropdown
- Checkbox change → `table.column(colIdx).visible(bool)` — DataTables native API
- "Show All" button: Checks all boxes and triggers change
- "Minimal" button: Shows only 9 key columns (sr_no, reg_no, student_name, course, department, seeking_placement, status, company_name, ctc)

**The dropdown uses `data-bs-auto-close="outside"`** — it stays open when clicking inside (so you can toggle multiple columns without reopening).

### 7.5 Export to Formatted Excel

**Files involved**: `data.html`, `style.css`

**Library**: `xlsx-js-style@1.2.0` — a fork of SheetJS that supports cell styling. The free SheetJS (`xlsx@0.18.5`) does NOT support styles; it was replaced specifically for this feature.

**Export flow**:
1. Click "Export Excel" → `filterApi.getCurrentData()` gets the currently filtered data
2. If no data → alert, return
3. Build checkboxes in Export Modal for each column
4. User selects/deselects columns, clicks "Export"
5. Build AOA (array of arrays): headers row + data rows
6. **Serial number reset**: If `sr_no` is included, values are reset to 1, 2, 3... (not the original sr_no from the database)
7. Create worksheet from AOA
8. **Apply styles**:
   - Header cells: Dark blue (#1B3A6B) background, white bold text (11pt), center aligned, wrap text, thin black borders on all sides
   - Data cells: Center aligned, thin black borders on all sides
9. **Auto-fit column widths**: Scans all values per column, sets width to `Math.min(maxLength + 2, 45)` characters
10. Create workbook, write file. Filename: `placement_{filter_name}_{date}.xlsx`

**Style objects used**:
```javascript
headerStyle = {
    font: { bold: true, color: { rgb: 'FFFFFF' }, sz: 11 },
    fill: { fgColor: { rgb: '1B3A6B' } },
    alignment: { horizontal: 'center', vertical: 'center', wrapText: true },
    border: { top/bottom/left/right: { style: 'thin', color: { rgb: '000000' } } }
};
cellStyle = {
    alignment: { horizontal: 'center', vertical: 'center' },
    border: { top/bottom/left/right: { style: 'thin', color: { rgb: '000000' } } }
};
```

### 7.6 Saved Views (localStorage)

**Files involved**: `data.html`

**Storage**: `localStorage` key `pmis_saved_views` — array of view objects.

**View object structure**:
```json
{
    "name": "User-entered name",
    "filter": "placed",                    // activeFilter key
    "filterLabel": "Placed",               // Display label
    "columnFilters": { "department": ["CS", "IT"] },  // ACTIVE_FILTERS snapshot
    "createdAt": "2026-02-22T10:30:00.000Z"
}
```

**Operations**:
- **Save**: Captures current `activeFilter` + `filterApi.getColumnFilters()`, prompts for name, stores to localStorage
- **Load**: Sets `activeFilter`, highlights correct tile, calls `setPreFilter()` + `setColumnFilters()`
- **Delete**: Removes from array by index, re-renders menu
- **Render**: Shows saved views in a dropdown with name, filter label, and column filter count

**Concern**: localStorage is per-browser, per-origin. Views are not shared between users or persisted to the server. If localStorage is cleared, all saved views are lost.

### 7.7 Inline Editing (Student Profile)

**Files involved**: `student_profile.html`, `app.py` (PUT /api/student)

**Architecture**:
- Click editable field → DOM swap: text → input/select
- Edit → blur/Enter/change → AJAX PUT → success toast + log refresh / error toast + revert
- Server validates field name against whitelist, validates data format (CTC, email, phone), logs change

**The inline editing uses optimistic UI**: The display text is updated immediately when the user finishes editing, before the AJAX response comes back. If the server returns an error, the text is reverted to the original value.

### 7.8 Change Logging

**Files involved**: `app.py` (edit_log table, `/api/edit-log`), `student_profile.html`, `versions.html`, `dashboard.html`

**Every field edit creates a log entry** with:
- Who (reg_no + student_name)
- What (field_name)
- Old value vs new value
- When (timestamp)

**Change log is displayed in 3 places**:
1. Dashboard — Last 15 changes (AJAX)
2. Versions page — Full paginated log (AJAX with search)
3. Student profile — Student-specific log (AJAX, last 50 entries)

### 7.9 Version History

**Files involved**: `app.py`, `versions.html`, `version_detail.html`

**Every Excel upload** creates:
1. An `upload_versions` record (metadata: filename, date, counts)
2. Full copies of all uploaded rows in `version_snapshots`

This allows historical comparison — you can see exactly what data was in any previous upload.

**Concern**: Version snapshots duplicate all student data. For 1537 students and 10 uploads, that's 15,370 snapshot rows. This grows linearly with uploads × records. No automatic cleanup mechanism exists.

### 7.10 Global Search

**Files involved**: `globalSearch.js`, `app.py` (GET /api/search)

**Architecture**: Client-side autocomplete widget using debounced AJAX.
- 250ms debounce prevents excessive API calls
- Server does `LIKE %query%` across 4 fields (name, reg_no, course, company)
- Results limited to 15
- Displayed in a positioned dropdown below the search input

### 7.11 Student File Management

**Files involved**: `app.py`, `student_profile.html`

**Upload flow**: Multipart form → UUID-based stored name → save to disk + record in DB
**Download**: Direct file serving via `/uploads/{stored_name}`
**Delete**: Remove from disk + database

**File types supported**: resume, offer_letter, loi, confirmation, other

### 7.12 Sticky Table Header

**Files involved**: `style.css`

```css
.table-responsive { max-height: calc(100vh - 120px); overflow-y: auto; }
#studentsTable thead tr#headerRow th { position: sticky; top: 0; z-index: 11; }
#studentsTable thead tr#filterRow th { position: sticky; top: 32px; z-index: 10; }
```

The header row sticks at the top of the scrollable container. The filter row sticks just below it (32px offset). Z-index layering ensures headers stay above content and filter panels.

---

## 8. Data Flow Diagrams

### 8.1 Excel Upload Flow

```
User selects .xlsx file
    │
    ▼
POST /upload (multipart)
    │
    ├── Validate file extension (.xlsx only)
    ├── pandas.read_excel() with openpyxl engine
    ├── Normalize headers (strip whitespace, aliases)
    ├── Validate all 26 expected headers present
    ├── Clean data:
    │   ├── sr_no → int
    │   ├── All others → string (strip, nan→None)
    │   └── Percentages → fix decimals, strip prefixes
    │
    ├── For each row:
    │   ├── Check if reg_no exists → INSERT or UPDATE
    │   └── Track inserted/updated counts
    │
    ├── Create upload_versions record
    ├── Copy all rows to version_snapshots
    │
    └── Flash success message → redirect to /upload
```

### 8.2 Data Page Rendering Flow

```
GET /data
    │
    ├── Fetch all students from MySQL
    ├── compute_analytics(rows) → analytics dict
    ├── render_template("data.html", students_json=rows, analytics=analytics)
    │
    ▼ (Client-side)
    │
    ├── Parse JSON data from <script> tag
    ├── initFilterSystem() → creates DataTable + filter UI
    ├── Build column toggle checkboxes
    ├── Compute program tile counts
    │
    ▼ (User interaction)
    │
    ├── Click tile → setPreFilter(fn) → applyAllFilters()
    ├── Click column filter → lazy-populate → select values → apply → applyAllFilters()
    ├── Toggle column → table.column(idx).visible()
    ├── Click Export → open modal → select columns → build styled XLSX → download
    └── Click student name → window.open('/student/{reg_no}')
```

### 8.3 Inline Edit Flow

```
Click .editable-field
    │
    ├── Create <input> or <select>
    ├── Focus input
    │
    ▼ (User types, then blur/Enter)
    │
    ├── Read new value
    ├── Restore display text (optimistic)
    ├── PUT /api/student/{reg_no} { field, value }
    │
    ▼ (Server)
    │
    ├── Validate field in EDITABLE_COLUMNS
    ├── Validate data format (CTC/email/phone)
    ├── Fetch old value
    ├── If unchanged → return early
    ├── UPDATE students SET field = value
    ├── INSERT into edit_log
    │
    ▼ (Response)
    │
    ├── Success → green toast, reload change log
    └── Error → red toast, revert display text
```

---

## 9. Optimization Notes & Potential Improvements

### 9.1 Current Optimizations Already Implemented

| Area | Optimization | Impact |
|------|-------------|--------|
| filterSystem.js | Pre-normalize data at load | Avoids repeated string conversion during filtering |
| filterSystem.js | Cached unique values per column | Single scan instead of re-scanning on each filter open |
| filterSystem.js | Lazy population of filter panels | Only builds checkboxes when user first opens a column filter |
| filterSystem.js | Compiled Set-based filtering | O(1) lookup per value instead of O(n) array search |
| filterSystem.js | Single-pass multi-filter | One loop through data with all predicates, not N loops |
| filterSystem.js | Short-circuit on no filters | Skips filter loop entirely when no column filters active |
| DataTables | `deferRender: true` | Only renders visible rows to DOM |
| DataTables | `draw(false)` | Preserves pagination position on filter changes |
| Global Search | 250ms debounce | Prevents excessive API calls while typing |
| Export | AOA (array of arrays) | More efficient than json_to_sheet for styled exports |

### 9.2 Potential Backend Improvements

1. **Connection Pooling**: Currently `get_connection()` creates a new MySQL connection per request. Use `mysql.connector.pooling.MySQLConnectionPool` or SQLAlchemy with connection pooling to reuse connections.

2. **Batch Inserts on Upload**: The upload loop does `cursor.execute()` per row (1537 times). Using `cursor.executemany()` or building a single multi-row INSERT would be 5-10x faster.

3. **compute_analytics() Efficiency**: Currently makes ~10 passes through the data (one per metric). Could be refactored to single-pass where all counters are accumulated in one loop.

4. **SQL Injection Surface**: `f"UPDATE students SET \`{field}\` = %s"` uses an f-string for the column name. While the field is validated against `EDITABLE_COLUMNS`, using a dictionary lookup to map field names to pre-written SQL fragments would be safer.

5. **Index Optimization**: The `students` table only has a PK index on `reg_no`. Adding indexes on `status`, `seeking_placement`, `course`, and `department` would speed up filtered queries (though currently all filtering is client-side, these would help if server-side filtering is added).

6. **Paginated Data API**: Currently `/data` sends ALL students to the client as JSON. For very large datasets (10000+ students), server-side pagination with DataTables Ajax would be more memory-efficient.

7. **Version Snapshot Storage**: Each upload creates a full copy. Using diff-based storage (only storing changed fields) or a separate history table with timestamps would reduce storage by ~90%.

8. **Error Handling**: Many routes have bare `except Error:` blocks that silently return empty data. More specific error handling and logging would help debugging.

### 9.3 Potential Frontend Improvements

1. **Template Inheritance**: All 6 templates duplicate the navbar, head section, and script imports. Using Jinja2 `{% extends "base.html" %}` with `{% block content %}` would eliminate ~50 lines of duplication per template.

2. **Client-Side Data Duplication**: `data.html` receives the full student list as JSON AND computes analytics server-side. The analytics could be computed client-side from the same JSON, eliminating the need for `compute_analytics()` to run before every data page load.

3. **Change Event Batching**: The column visibility toggle triggers `table.column(idx).visible()` on each checkbox change. When using "Show All", this fires 25 individual column visibility changes. Batching these into a single DataTables redraw would be smoother.

4. **Export Modal Memory**: Each click on "Export Excel" rebuilds all 25 checkboxes. Caching the modal content and just showing/hiding it would be slightly more efficient.

5. **Saved Views Persistence**: Views stored in localStorage are browser-specific and easily lost. A server-side storage option (database table) would make views persistent and shareable.

6. **Accessibility**: The filter system uses custom click handlers on `<li>` elements and manual checkbox toggling. Using proper `<button>` or `<label>` elements with ARIA attributes would improve screen reader support.

7. **Mobile Responsiveness**: The data table with 25 columns is not ideal on mobile. While `scrollX: true` helps, dedicated mobile views or column priority hiding would improve the experience.

### 9.4 Architecture-Level Observations

1. **No Authentication**: The app has no login system. Anyone with access to the URL can view, edit, and delete all data. For a production deployment, at minimum basic auth or session-based login should be added.

2. **No CSRF Protection**: Forms use standard POST without CSRF tokens. Flask-WTF or manual CSRF token handling should be added for security.

3. **No Input Sanitization for XSS**: Student names and other text fields are inserted into HTML via jQuery's `.html()` in some places. While Jinja2 auto-escapes in templates, client-side HTML injection is possible through the DataTable rendering. DataTables does escape by default, but custom render functions should be audited.

4. **Debug Mode**: `app.run(debug=True)` is hardcoded. In production, this exposes the Werkzeug debugger which allows arbitrary code execution. Should be controlled via environment variable.

5. **Secret Key**: `SECRET_KEY = os.urandom(24)` regenerates on every app restart, invalidating all sessions. Should use a fixed key from environment variables in production.

6. **File Upload Security**: Uploaded files are served directly via `send_from_directory`. File type validation (magic bytes, not just extension) and virus scanning should be considered for production.

---

## Appendix: External Dependencies

### Python Packages (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| `flask` | Latest | Web framework, routing, templating, request handling |
| `pandas` | Latest | Excel file reading and data manipulation |
| `openpyxl` | Latest | Excel (.xlsx) file engine used by pandas |
| `mysql-connector-python` | Latest | MySQL database driver |

### CDN Libraries (loaded in HTML)

| Library | Version | CDN URL | Purpose |
|---------|---------|---------|---------|
| Bootstrap CSS | 5.3.0 | `cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css` | UI framework |
| Bootstrap JS | 5.3.0 | `cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js` | Dropdowns, modals, toasts |
| jQuery | 3.7.0 | `code.jquery.com/jquery-3.7.0.min.js` | DOM manipulation, AJAX |
| DataTables CSS | 1.13.7 | `cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css` | Table styling |
| DataTables JS | 1.13.7 | `cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js` | Table features |
| DataTables BS5 | 1.13.7 | `cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js` | Bootstrap integration |
| Chart.js | 4.4.1 | `cdn.jsdelivr.net/npm/chart.js` | Dashboard charts |
| xlsx-js-style | 1.2.0 | `cdn.jsdelivr.net/npm/xlsx-js-style@1.2.0/dist/xlsx.bundle.js` | Styled Excel export |
