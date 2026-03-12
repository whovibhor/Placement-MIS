# Placement MIS — Architecture Reference

> **Last updated:** March 2026
> **Stack:** Python 3.13 · Flask · MySQL 8 · jQuery 3.7 · DataTables 1.13.7 · Bootstrap 5.3 · Chart.js 4.4.1
> **Port:** `localhost:5000` (Flask dev server) · MySQL on port `3307`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Backend Modules](#3-backend-modules)
4. [Database Layer](#4-database-layer)
5. [Route Inventory](#5-route-inventory)
6. [Frontend — Templates](#6-frontend--templates)
7. [Static Assets](#7-static-assets)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Key Design Decisions](#9-key-design-decisions)

---

## 1. Project Overview

**Placement MIS** is a server-rendered web application for managing college placement data. It follows a **modular Flask monolith** pattern:

- Flask serves Jinja2 HTML templates with embedded JSON data (no SPA framework)
- jQuery handles all client-side interactivity (inline editing, filter dropdowns, charts)
- AJAX is used only for search, inline field editing, and change log fetching
- The backend is split across four Python files: `app.py`, `helpers.py`, `routes_data.py`, `routes_cdm.py`

### Two major modules

| Module | Purpose |
|---|---|
| **Students / MIS** | Upload Excel data, view/edit student records, analytics dashboard, version history |
| **CDM** (Company Drive Management) | Track company recruitment drives, HR contacts, interview rounds, student participation |

---

## 2. Directory Structure

```
Placement-MIS/
├── app.py                    # Flask entry point — registers route modules, upload & version routes
├── config.py                 # DB credentials and Flask secret key
├── helpers.py                # Shared constants, DB utilities, analytics engine, init_db()
├── routes_data.py            # Student data routes (data table, inline edit, profiles, files, change log)
├── routes_cdm.py             # CDM routes (companies, drives, HR, rounds, students, analytics)
├── requirements.txt          # Python dependencies (flask, pandas, openpyxl, mysql-connector-python)
├── schema.sql                # Reference SQL schema (tables auto-created by init_db() on startup)
├── fix_sr_no.py              # One-time migration script for serial numbers
│
├── static/
│   ├── style.css             # Global dark-theme CSS (~1400+ lines)
│   ├── filterSystem.js       # Reusable Excel-style column filter engine (~364 lines)
│   └── globalSearch.js       # Navbar autocomplete student search widget (~65 lines)
│
├── templates/
│   ├── upload.html           # Excel upload page
│   ├── dashboard.html        # Analytics dashboard (7 Chart.js charts)
│   ├── data.html             # Data table: filters, inline editing, export, saved views
│   ├── student_profile.html  # Individual student profile with inline editing and file upload
│   ├── versions.html         # Upload version history + change log tabs
│   ├── version_detail.html   # Snapshot viewer for a specific upload version
│   ├── cdm.html              # CDM: drives table, calendar, placement sources tabs
│   ├── cdm_company.html      # Company detail: drives, HR contacts, student linking, rounds
│   └── cdm_upload.html       # CDM Excel import page
│
└── uploads/                  # Uploaded student documents (resumes, offer letters, etc.)
```

---

## 3. Backend Modules

### `app.py` — Flask Entry Point (406 lines)

Registers the two route modules and owns the following routes directly:

- `GET /` → redirect to `/dashboard`
- `GET /dashboard` → renders analytics dashboard (uses analytics cache)
- `GET, POST /upload` → Excel upload, upsert to `students`, snapshot versioning
- `POST /drop-all` → delete all student records (admin)
- `POST /drop-cdm` → delete all CDM data (admin)
- `GET /logs` → upload version list
- `GET /versions/<id>` → snapshot detail for one version
- `GET /api/version/<id>` → snapshot as JSON
- `POST /delete-version/<id>` → delete version + snapshot rows

**Startup:**

```python
if __name__ == "__main__":
    init_db()          # Create DB + all tables if missing
    app.run(debug=True, port=5000)
```

---

### `helpers.py` — Shared Utilities (876 lines)

Contains everything shared between modules:

| Symbol | Type | Purpose |
|---|---|---|
| `UPLOAD_FOLDER` | constant | Absolute path to `uploads/` directory |
| `EXPECTED_HEADERS` | list | 26 Excel column names expected in uploaded file |
| `HEADER_TO_COL` | dict | Maps Excel headers → DB column names |
| `DB_COLUMNS` | list | Ordered list of all 26 DB column names |
| `DISPLAY_COLUMNS` | list | Columns shown in UI (26 columns, `school_name` hidden) |
| `EDITABLE_COLUMNS` | set | Columns editable via inline edit (excludes `sr_no`, `reg_no`, `placed_date`) |
| `NUMERIC_FLOAT_COLS` | set | `{ctc, percent_10, percent_12, graduation_ogpa}` |
| `NUMERIC_INT_COLS` | set | `{backlogs}` |
| `to_float_or_none(v)` | function | Safe float conversion, returns None on failure |
| `to_int_or_none(v)` | function | Safe int conversion, handles `"1.0"` → `1` |
| `normalize_row(row)` | function | Converts `Decimal` → `float`, `date` → ISO string in a DB row dict |
| `normalize_rows(rows)` | function | Applies `normalize_row` to a list of rows |
| `get_connection()` | function | Opens a `mysql.connector` connection using `config.py` credentials |
| `init_db()` | function | Creates the database and all 13 tables (idempotent) |
| `get_cached_analytics()` | function | Returns analytics JSON from `analytics_cache` table, or None |
| `save_analytics_cache(data)` | function | Writes analytics dict to `analytics_cache` table |
| `invalidate_analytics_cache()` | function | Sets `analytics_cache.data = NULL` to force recompute |
| `compute_analytics(rows)` | function | Computes all dashboard analytics from a list of student row dicts |

**DB connection pattern:** One connection opened per request — no pooling.

---

### `routes_data.py` — Student Data Routes (395 lines)

Registered via `register_data_routes(app)`. All routes are defined inside the function to avoid circular imports.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/data` | Data table page with students JSON and analytics |
| `PUT` | `/api/student/<reg_no>` | Inline-edit one field with validation and edit log |
| `DELETE` | `/api/student/<reg_no>` | Delete a student record |
| `GET` | `/student/<reg_no>` | Student profile page |
| `POST` | `/student/<reg_no>/upload-file` | Upload a document for a student |
| `GET` | `/uploads/<filename>` | Serve a stored student document |
| `POST` | `/student/<reg_no>/delete-file/<file_id>` | Delete a student document |
| `PUT` | `/api/student/<reg_no>/bulk-update` | Update multiple fields at once (from profile page) |
| `GET` | `/api/edit-log` | JSON: field-level change history (paginated, filterable) |
| `GET` | `/api/students` | JSON: all student records |
| `GET` | `/api/search` | JSON: autocomplete student search (name/reg_no) |

---

### `routes_cdm.py` — CDM Routes (1233 lines)

Registered via `register_cdm_routes(app)`. All routes are defined inside `register_cdm_routes()`.

#### Helper functions at module level

| Function | Purpose |
|---|---|
| `generate_company_id(name, cursor)` | Creates unique 4-char ID from company name (first 2 + last 2 uppercase alphanumeric chars, appends number on collision) |
| `parse_date_field(val)` | Handles 6 date formats: `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-Mon-YYYY`, `DD Mon YYYY` |
| `parse_ctc_value(ctc_text)` | Extracts first numeric value from free-text CTC like `"6 LPA - 10 LPA"` |

#### Route inventory

**Page routes:**

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/cdm` | CDM main page (drives table, companies grid, calendar, placement sources) |
| `GET` | `/cdm/company/<id>` | Company detail page |
| `GET, POST` | `/cdm/import` | CDM Excel import (GET = form, POST = process) |

**Company CRUD:**

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/cdm/company` | Create company (auto-generates 4-char ID) |
| `PUT` | `/api/cdm/company/<id>` | Update company name |
| `DELETE` | `/api/cdm/company/<id>` | Delete company (cascades all related data) |

**Drive CRUD:**

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/cdm/drive` | Create drive |
| `PUT` | `/api/cdm/drive/<id>` | Inline-edit one drive field |
| `POST` | `/api/cdm/delete-drive/<id>` | Delete drive |

**HR Contacts:**

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/cdm/hr` | Add HR contact |
| `PUT` | `/api/cdm/hr/<id>` | Update HR contact field (with email validation) |
| `DELETE` | `/api/cdm/hr/<id>` | Delete HR contact |

**Student Linking:**

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/cdm/drive/<id>/students` | List students linked to a drive |
| `POST` | `/api/cdm/drive/<id>/students` | Link student to drive |
| `PUT` | `/api/cdm/drive/<id>/students/<reg_no>` | Update student status/round in a drive |
| `DELETE` | `/api/cdm/drive/<id>/students/<reg_no>` | Unlink student from drive |
| `POST` | `/api/cdm/drive/<id>/students/bulk` | Bulk-import students from Excel |
| `GET` | `/api/cdm/student-template` | Download bulk import template |

**Round Management:**

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/cdm/drive/<id>/rounds` | List rounds for a drive |
| `POST` | `/api/cdm/drive/<id>/rounds` | Add round |
| `DELETE` | `/api/cdm/round/<id>` | Delete round |

**Data & Analytics:**

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/cdm` | All drives as JSON (with aggregated courses) |
| `GET` | `/api/cdm/analytics` | CTC stats, team performance, top companies |
| `GET` | `/api/cdm/calendar` | Drives with process_date for calendar rendering |
| `GET` | `/api/cdm/placement-sources` | Companies that placed students (bridges students ↔ CDM) |
| `GET` | `/api/cdm/search` | Search companies/drives by text |
| `GET` | `/api/cdm/search-students` | Search students for linking UI |
| `GET` | `/api/cdm/edit-log` | CDM field-level change history |

---

## 4. Database Layer

**Engine:** MySQL 8 on `localhost:3307`, charset `utf8mb4`, collation `utf8mb4_general_ci`.

All tables are auto-created by `init_db()` in `helpers.py` using `CREATE TABLE IF NOT EXISTS`. Idempotent `ALTER TABLE` statements add columns and indexes to existing databases when upgrading.

### Students Module — 6 Tables

#### `students` — Live placement data (26 + 1 columns)

| Column | Type | Notes |
|---|---|---|
| `sr_no` | INT | Serial number from Excel |
| `reg_no` | VARCHAR(50) | **PRIMARY KEY** |
| `student_name` | VARCHAR(200) | |
| `gender` | VARCHAR(20) | |
| `course` | VARCHAR(100) | e.g., "B Tech CSE", "MBA" |
| `resume_status` | VARCHAR(100) | Yes / No |
| `seeking_placement` | VARCHAR(100) | Opted In / Opted Out / Not Registered / Debarred |
| `department` | VARCHAR(100) | |
| `offer_letter_status` | VARCHAR(100) | Yes / No / Mail Only / LOI / Confirmation Message |
| `status` | VARCHAR(100) | Placed / Unplaced |
| `placed_date` | DATE | Auto-set when status becomes "Placed" |
| `company_name` | VARCHAR(200) | |
| `designation` | VARCHAR(200) | |
| `ctc` | DECIMAL(10,2) | |
| `joining_date` | VARCHAR(100) | Stored as string |
| `joining_status` | VARCHAR(100) | Joined / Not Joined / Pending |
| `school_name` | VARCHAR(200) | Hidden from UI |
| `mobile_number` | VARCHAR(50) | |
| `email` | VARCHAR(200) | |
| `graduation_course` | VARCHAR(100) | |
| `graduation_ogpa` | DECIMAL(4,2) | |
| `percent_10` | DECIMAL(5,2) | |
| `percent_12` | DECIMAL(5,2) | |
| `backlogs` | INT | |
| `hometown` | VARCHAR(200) | |
| `address` | TEXT | |
| `reason` | TEXT | |

**Indexes:** `idx_status`, `idx_seeking`, `idx_course`, `idx_department`, `idx_placed_date`

#### `upload_versions` — Upload metadata

| Column | Type | Notes |
|---|---|---|
| `version_id` | INT AUTO_INCREMENT | **PK** |
| `filename` | VARCHAR(255) | Original filename |
| `uploaded_at` | DATETIME | |
| `total_records` | INT | |
| `inserted` | INT | New rows |
| `updated` | INT | Changed rows |
| `content_hash` | VARCHAR(32) | MD5 of sorted CSV content |

#### `version_snapshots` — Frozen upload copies

Mirrors the `students` table structure plus `version_id`. `FOREIGN KEY (version_id) REFERENCES upload_versions(version_id) ON DELETE CASCADE`.

#### `student_files` — Student documents

| Column | Type |
|---|---|
| `id` | INT AUTO_INCREMENT PK |
| `reg_no` | VARCHAR(50) FK → students |
| `file_type` | VARCHAR(50) |
| `original_name` | VARCHAR(255) |
| `stored_name` | VARCHAR(255) |
| `uploaded_at` | DATETIME |

#### `edit_log` — Student change history

| Column | Type |
|---|---|
| `id` | INT AUTO_INCREMENT PK |
| `reg_no` | VARCHAR(50) |
| `student_name` | VARCHAR(200) |
| `field_name` | VARCHAR(100) |
| `old_value` | TEXT |
| `new_value` | TEXT |
| `changed_at` | DATETIME |

#### `analytics_cache` — Computed analytics (singleton)

| Column | Type |
|---|---|
| `id` | INT PK (always 1) |
| `data` | JSON |
| `updated_at` | DATETIME |

### CDM Module — 7 Tables

#### Entity Relationships

```
companies (1) ──< company_drives (N) ──< drive_courses  (N)
                                      ──< drive_rounds   (N)
                                      ──< drive_students (N) >── students
           ──< company_hr (N)
```

#### `companies`

| Column | Type |
|---|---|
| `company_id` | VARCHAR(10) **PK** (auto-generated 4-char) |
| `company_name` | VARCHAR(200) NOT NULL |

#### `company_drives`

| Column | Type | Notes |
|---|---|---|
| `drive_id` | INT AUTO_INCREMENT **PK** | |
| `company_id` | VARCHAR(10) FK → companies (CASCADE) | |
| `role` | VARCHAR(200) | Job title/role |
| `ctc_text` | VARCHAR(100) | Free-text CTC (e.g., "6-10 LPA") |
| `jd_received_date` | DATE | |
| `process_date` | DATE | Interview/drive date |
| `data_shared` | BOOLEAN | |
| `process_mode` | VARCHAR(50) | Online / Offline / Hybrid |
| `location` | VARCHAR(200) | |
| `received_by` | VARCHAR(200) | Team member who sourced the drive |
| `notes` | TEXT | |
| `status` | VARCHAR(50) | Upcoming / Ongoing / Completed / Cancelled |

#### `drive_courses`

Composite PK (`drive_id`, `course_name`). FK → company_drives (CASCADE).

#### `company_hr`

| Column | Type |
|---|---|
| `hr_id` | INT AUTO_INCREMENT PK |
| `company_id` | VARCHAR(10) FK → companies (CASCADE) |
| `name` | VARCHAR(200) |
| `designation` | VARCHAR(200) |
| `email` | VARCHAR(200) |
| `phone` | VARCHAR(50) |

#### `drive_rounds`

| Column | Type |
|---|---|
| `round_id` | INT AUTO_INCREMENT PK |
| `drive_id` | INT FK → company_drives (CASCADE) |
| `round_name` | VARCHAR(100) |
| `round_order` | INT |
| `round_date` | DATE |

#### `drive_students`

Composite PK (`drive_id`, `reg_no`). FK → company_drives (CASCADE) + students (CASCADE).

| Column | Type |
|---|---|
| `status` | VARCHAR(50) — Applied / Shortlisted / In Process / Selected / Rejected / On Hold |
| `current_round` | INT |

#### `cdm_edit_log` — CDM change history

Mirrors `edit_log` structure but references `drive_id` instead of `reg_no`.

---

## 5. Route Inventory

### Students Module

| Method | Route | Handler | File |
|---|---|---|---|
| `GET` | `/` | `index` | `app.py` |
| `GET` | `/dashboard` | `dashboard` | `app.py` |
| `GET, POST` | `/upload` | `upload` | `app.py` |
| `POST` | `/drop-all` | `drop_all` | `app.py` |
| `POST` | `/drop-cdm` | `drop_cdm` | `app.py` |
| `GET` | `/logs` | `logs_page` | `app.py` |
| `GET` | `/versions/<id>` | `version_detail` | `app.py` |
| `GET` | `/api/version/<id>` | `api_version` | `app.py` |
| `POST` | `/delete-version/<id>` | `delete_version` | `app.py` |
| `GET` | `/data` | `data_page` | `routes_data.py` |
| `PUT` | `/api/student/<reg_no>` | `update_student` | `routes_data.py` |
| `DELETE` | `/api/student/<reg_no>` | `delete_student` | `routes_data.py` |
| `GET` | `/student/<reg_no>` | `student_profile` | `routes_data.py` |
| `POST` | `/student/<reg_no>/upload-file` | `upload_student_file` | `routes_data.py` |
| `GET` | `/uploads/<filename>` | `serve_upload` | `routes_data.py` |
| `POST` | `/student/<reg_no>/delete-file/<id>` | `delete_student_file` | `routes_data.py` |
| `PUT` | `/api/student/<reg_no>/bulk-update` | `bulk_update_student` | `routes_data.py` |
| `GET` | `/api/edit-log` | `api_edit_log` | `routes_data.py` |
| `GET` | `/api/students` | `api_students` | `routes_data.py` |
| `GET` | `/api/search` | `api_search` | `routes_data.py` |

### CDM Module (all in `routes_cdm.py`)

| Method | Route | Handler |
|---|---|---|
| `GET` | `/cdm` | `cdm_page` |
| `GET` | `/api/cdm` | `api_cdm` |
| `GET, POST` | `/cdm/import` | `cdm_import` |
| `GET` | `/cdm/company/<id>` | `cdm_company_detail` |
| `POST` | `/api/cdm/delete-drive/<id>` | `cdm_delete_drive` |
| `POST` | `/api/cdm/drive` | `cdm_create_drive` |
| `PUT` | `/api/cdm/drive/<id>` | `cdm_update_drive` |
| `GET` | `/api/cdm/edit-log` | `api_cdm_edit_log` |
| `PUT` | `/api/cdm/hr/<id>` | `cdm_update_hr` |
| `DELETE` | `/api/cdm/hr/<id>` | `cdm_delete_hr` |
| `POST` | `/api/cdm/hr` | `cdm_add_hr` |
| `GET` | `/api/cdm/search` | `cdm_search` |
| `POST` | `/api/cdm/company` | `cdm_create_company` |
| `PUT` | `/api/cdm/company/<id>` | `cdm_update_company` |
| `DELETE` | `/api/cdm/company/<id>` | `cdm_delete_company` |
| `GET` | `/api/cdm/analytics` | `cdm_analytics` |
| `GET` | `/api/cdm/drive/<id>/students` | `cdm_drive_students` |
| `POST` | `/api/cdm/drive/<id>/students` | `cdm_link_student` |
| `PUT` | `/api/cdm/drive/<id>/students/<reg_no>` | `cdm_update_drive_student` |
| `DELETE` | `/api/cdm/drive/<id>/students/<reg_no>` | `cdm_unlink_student` |
| `POST` | `/api/cdm/drive/<id>/students/bulk` | bulk import |
| `GET` | `/api/cdm/student-template` | template download |
| `GET` | `/api/cdm/drive/<id>/rounds` | `cdm_drive_rounds` |
| `POST` | `/api/cdm/drive/<id>/rounds` | `cdm_add_round` |
| `DELETE` | `/api/cdm/round/<id>` | `cdm_delete_round` |
| `GET` | `/api/cdm/calendar` | calendar data |
| `GET` | `/api/cdm/placement-sources` | placement sources |
| `GET` | `/api/cdm/search-students` | student search for linking |

---

## 6. Frontend — Templates

### Data Loading Pattern

All templates use **inline JSON** (not AJAX) for initial data:

```html
<!-- Server injects data into a <script type="application/json"> tag -->
<script id="json-data" type="application/json">{{ students_json | tojson }}</script>
```

```javascript
// Client parses it synchronously — zero latency for filters and tables
var LOCAL_DATA = JSON.parse(document.getElementById('json-data').textContent);
```

This avoids a second round-trip and ensures filters can populate immediately.

### Template Inventory

| Template | Route | Key JS Dependencies |
|---|---|---|
| `upload.html` | `/upload` | Bootstrap only |
| `dashboard.html` | `/dashboard` | Chart.js 4.4.1 |
| `data.html` | `/data` | DataTables 1.13.7, jQuery, `filterSystem.js`, `xlsx-js-style` |
| `student_profile.html` | `/student/<reg_no>` | jQuery AJAX |
| `versions.html` | `/logs` | jQuery AJAX (change log tab) |
| `version_detail.html` | `/versions/<id>` | DataTables, `filterSystem.js` |
| `cdm.html` | `/cdm` | DataTables, Chart.js, `filterSystem.js`, `xlsx-js-style` |
| `cdm_company.html` | `/cdm/company/<id>` | jQuery AJAX |
| `cdm_upload.html` | `/cdm/import` | Bootstrap only |

---

## 7. Static Assets

### `style.css` (~1400+ lines)

Organized in labeled sections:

| Section | Purpose |
|---|---|
| `:root` variables | Color palette — `--bg-dark: #121212`, `--accent-red: #e53935`, etc. |
| Navbar | Dark bar with 2px red bottom border |
| Cards, Forms, Buttons | Dark-themed Bootstrap overrides |
| Tables | Dark striped/hover rows, uppercase headers |
| DataTables overrides | Dark pagination, search box, sort arrows |
| `cf-*` classes | Column filter widget: `cf-wrap`, `cf-btn`, `cf-panel`, `cf-search`, `cf-list`, `cf-apply`, `cf-count` |
| Hero section | 2-column grid stat display used by dashboard and CDM |
| Calendar | 7-column CSS grid, event pills color-coded by status |
| Scrollbar | Dark scrollbar for WebKit browsers |

### `filterSystem.js` (~364 lines)

A reusable module that provides Excel-style per-column filter dropdowns. Called as:

```javascript
initFilterSystem(dataTable, rawData, dataKeys, filterRowId);
```

Each column gets a `▼ All` dropdown with:
- Live search within the dropdown values
- Select All / Deselect All buttons
- Checkbox list (deduplicated, case-insensitive, locale-sorted)
- Apply button that builds a regex and calls `column().search(regex, true, false).draw()`
- `position: fixed` dropdown to escape `overflow: hidden` containers

### `globalSearch.js` (~65 lines)

Navbar autocomplete search: queries `/api/search?q=<text>` (debounced 250 ms), renders a floating dropdown with up to 10 results linking to student profiles.

---

## 8. Data Flow Diagrams

### Excel Upload Flow

```
User uploads .xlsx
      │
      ▼
┌─────────────────────┐
│ Validate file type   │  .xlsx only
│ pd.read_excel()      │
│ Normalize headers    │  strip(), HEADER_ALIASES ("0.1"→"10%")
│ Validate headers     │  set-based check vs EXPECTED_HEADERS
│ Rename → DB cols     │  HEADER_TO_COL mapping
│ Clean values         │  NaN→None, str.strip(), percent fix
│ Type convert         │  ctc/percent→DECIMAL, backlogs→INT
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Compare vs DB        │  SELECT existing rows, field-by-field diff
│ Count inserted/updated│
│ UPSERT (batch)       │  INSERT … ON DUPLICATE KEY UPDATE
│ Auto-set placed_date │  When status becomes "Placed"
└──────────┬──────────┘
           │ (if changes detected)
           ▼
┌─────────────────────┐
│ Save version snapshot│
│ 1. INSERT upload_versions (metadata + content_hash)
│ 2. INSERT version_snapshots (copy of all rows)
│ 3. invalidate_analytics_cache()
└─────────────────────┘
```

### Dashboard Flow

```
GET /dashboard
  → get_cached_analytics()        (read analytics_cache table)
  → If None: SELECT * FROM students
             compute_analytics(rows)
             save_analytics_cache(analytics)
  → render_template("dashboard.html", analytics=analytics)
  → Chart.js renders charts from embedded JSON in template
```

### Inline Edit Flow (Students)

```
User clicks cell → input appears
User types new value → presses Enter
  → AJAX PUT /api/student/<reg_no>  { field, value }
  → Server: whitelist check (EDITABLE_COLUMNS)
            type validation (float/int/email/phone)
            SELECT old value → compare
            UPDATE students SET <field> = <value>
            INSERT INTO edit_log (old_value, new_value, changed_at)
            invalidate_analytics_cache()
  → Response { ok: true, value: <new_value> }
  → Cell shows new value, reverts if error
```

### CDM Page Load

```
GET /cdm
  → Server queries drives JOIN companies JOIN drive_courses
  → Also queries companies list with drive counts
  → Renders template with JSON in two <script type="application/json"> tags
  → Client: jQuery parses JSON → initFilterSystem() → DataTable rendered
            Summary bar updated, companies grid rendered
```

---

## 9. Key Design Decisions

### No Connection Pooling
Each Flask route opens a fresh `mysql.connector` connection, uses it, and closes it. Simple and sufficient for a single-admin tool; upgrade to pooling if concurrent usage grows.

### Analytics Cache
`compute_analytics()` is expensive (aggregates 1500+ rows). The result is stored as JSON in the `analytics_cache` table (a singleton row). The cache is invalidated on every upload or inline edit.

### Upsert Strategy
`reg_no` is the natural primary key. `INSERT ... ON DUPLICATE KEY UPDATE` lets every upload act as a full sync — new students are added, existing ones are updated, nothing is deleted.

### Version Snapshots
Every upload with real changes creates a frozen copy in `version_snapshots`. This provides audit history and allows rollback comparison without storing diffs. `ON DELETE CASCADE` keeps cleanup automatic.

### Content Hash
Each version stores an MD5 hash of the sorted CSV. Uploading identical data (no field changes) skips snapshot creation entirely, keeping the history meaningful.

### Modular Routes
The app started as a monolithic `app.py` and was split into `routes_data.py` and `routes_cdm.py` to improve maintainability. Both modules use the `register_*_routes(app)` pattern to avoid circular imports.

### Inline JSON vs AJAX
Initial page data (students, drives) is embedded as `<script type="application/json">{{ data | tojson }}</script>`. This eliminates the second round-trip, ensuring DataTables and filter dropdowns populate immediately on page load. AJAX is only used for subsequent mutations (edits, search).
