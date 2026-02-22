# CDM (Company Drive Management) — Complete Analysis

## Database Schema (6 Tables)

All tables created in `init_db()` at `app.py` line ~378.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `companies` | Company master | `company_id` (PK, VARCHAR(10)), `company_name` |
| `company_drives` | Drive records | `drive_id` (PK, auto), FK → companies, 10 fields (role, ctc_text, dates, process_mode, location, received_by, notes, status) |
| `drive_courses` | Courses per drive | Composite PK (drive_id, course_name), FK → drives |
| `company_hr` | HR contacts | `hr_id` PK, FK → companies, name/designation/email/phone |
| `drive_rounds` | Interview rounds | `round_id` PK, FK → drives, round_name/round_order/round_date |
| `drive_students` | Students in drives | Composite PK (drive_id, reg_no), FK → drives + students, status/current_round |

### Relationships
```
companies (1) ──< company_drives (N) ──< drive_courses (N)
                                      ──< drive_rounds (N)
                                      ──< drive_students (N) >── students
           ──< company_hr (N)
```

### Column Details

#### `companies`
| Column | Type | Constraints |
|--------|------|-------------|
| `company_id` | `VARCHAR(10)` | **PRIMARY KEY** |
| `company_name` | `VARCHAR(200)` | `NOT NULL` |

#### `company_drives`
| Column | Type | Constraints |
|--------|------|-------------|
| `drive_id` | `INT AUTO_INCREMENT` | **PRIMARY KEY** |
| `company_id` | `VARCHAR(10)` | FK → `companies(company_id) ON DELETE CASCADE` |
| `role` | `VARCHAR(200)` | |
| `ctc_text` | `VARCHAR(100)` | |
| `jd_received_date` | `DATE` | |
| `process_date` | `DATE` | |
| `data_shared` | `BOOLEAN` | |
| `process_mode` | `VARCHAR(50)` | |
| `location` | `VARCHAR(200)` | |
| `received_by` | `VARCHAR(200)` | |
| `notes` | `TEXT` | |
| `status` | `VARCHAR(50)` | `DEFAULT 'Upcoming'` (added idempotently) |

#### `drive_courses`
| Column | Type | Constraints |
|--------|------|-------------|
| `drive_id` | `INT` | **PK** (composite), FK → `company_drives(drive_id) ON DELETE CASCADE` |
| `course_name` | `VARCHAR(100)` | **PK** (composite) |

#### `company_hr`
| Column | Type | Constraints |
|--------|------|-------------|
| `hr_id` | `INT AUTO_INCREMENT` | **PRIMARY KEY** |
| `company_id` | `VARCHAR(10)` | FK → `companies(company_id) ON DELETE CASCADE` |
| `name` | `VARCHAR(200)` | |
| `designation` | `VARCHAR(200)` | |
| `email` | `VARCHAR(200)` | |
| `phone` | `VARCHAR(50)` | |

#### `drive_rounds`
| Column | Type | Constraints |
|--------|------|-------------|
| `round_id` | `INT AUTO_INCREMENT` | **PRIMARY KEY** |
| `drive_id` | `INT` | FK → `company_drives(drive_id) ON DELETE CASCADE` |
| `round_name` | `VARCHAR(100)` | |
| `round_order` | `INT` | |
| `round_date` | `DATE` | (added idempotently) |

#### `drive_students`
| Column | Type | Constraints |
|--------|------|-------------|
| `drive_id` | `INT` | **PK** (composite), FK → `company_drives(drive_id) ON DELETE CASCADE` |
| `reg_no` | `VARCHAR(50)` | **PK** (composite), FK → `students(reg_no) ON DELETE CASCADE` |
| `status` | `VARCHAR(50)` | |
| `current_round` | `INT` | (added idempotently) |

---

## 22 Backend Routes

### Page Routes
| Route | Method | Purpose |
|-------|--------|---------|
| `/cdm` | GET | Main CDM page — drives table + companies grid |
| `/cdm/company/<id>` | GET | Company detail — drives, HR contacts, student/round counts |
| `/cdm/import` | GET, POST | Excel import page (GET=form, POST=process) |

### Company CRUD
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm/company` | POST | Create company (checks duplicate name, auto-generates 4-char ID) |
| `/api/cdm/company/<id>` | PUT | Update company name |
| `/api/cdm/company/<id>` | DELETE | Cascade delete: drive_students → drive_rounds → drive_courses → company_drives → company_hr → companies |

### Drive CRUD
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm/drive` | POST | Create drive (requires company_id + role) |
| `/api/cdm/drive/<id>` | PUT | Inline field edit (validates field name, status values, date parsing, boolean conversion) |
| `/api/cdm/delete-drive/<id>` | POST | Delete drive + associated students, rounds, courses |

### HR Contacts
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm/hr` | POST | Add HR contact (requires company_id + name) |
| `/api/cdm/hr/<id>` | PUT | Inline field edit (email format validation) |
| `/api/cdm/hr/<id>` | DELETE | Delete HR contact |

### Student Linking
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm/drive/<id>/students` | GET | List students linked to a drive (joins students table for name/course/dept) |
| `/api/cdm/drive/<id>/students` | POST | Link student to drive (INSERT IGNORE, default status "Applied") |
| `/api/cdm/drive/<id>/students/<reg_no>` | PUT | Update student status/current_round in a drive |
| `/api/cdm/drive/<id>/students/<reg_no>` | DELETE | Remove student from drive |

### Round Management
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm/drive/<id>/rounds` | GET | List rounds for a drive (ordered by round_order) |
| `/api/cdm/drive/<id>/rounds` | POST | Add round (auto-increment round_order) |
| `/api/cdm/round/<id>` | DELETE | Delete a round |

### Data & Analytics
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/cdm` | GET | JSON list of all drives with aggregated courses |
| `/api/cdm/analytics` | GET | CTC stats, team performance (received_by), top companies by selections/CTC |
| `/api/cdm/calendar` | GET | Drives with process_date for calendar grid rendering |
| `/api/cdm/placement-sources` | GET | Companies that placed students (bridges students table ↔ CDM) |
| `/api/cdm/search` | GET | Search companies/drives by text (q param, min 2 chars, LIMIT 15) |
| `/api/cdm/search-students` | GET | Search student records for linking UI |

---

## Key Helper Functions

| Function | Purpose |
|----------|---------|
| `generate_company_id(name, cursor)` | Creates unique 4-char ID from name (first 2 + last 2 uppercase alphanumeric chars, appends number on collision) |
| `parse_date_field(val)` | Handles 6 date formats: `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-Mon-YYYY`, `DD Mon YYYY` |
| `parse_ctc_value(ctc_text)` | Extracts first numeric value from text like "6 LPA - 10 LPA" (splits on `-`, `&`, `,`, `/` separators first) |

### Constants
| Name | Content |
|------|---------|
| `CDM_EXCEL_HEADERS` | 16 Excel column → internal field name mappings |
| `CDM_EDITABLE_FIELDS` | 10 allowed inline-edit fields: role, ctc_text, jd_received_date, process_date, data_shared, process_mode, location, received_by, notes, status |

---

## Frontend — 3 Templates

### `cdm.html` (Main CDM Page, ~810 lines)

**Layout Structure:**
- Navbar with global search (overridden to search companies instead of students on this page)
- Header bar with buttons: Add Company, Import Excel, Export Excel, Column Toggle
- 3 Tabs: **Drives** | **Calendar** | **Placement Sources**

**Drives Tab:**
- **Summary Bar** — clickable filter tiles: All / Upcoming / Ongoing / Completed / Cancelled / On-Campus / Virtual
- **Companies Section** — collapsible grid of company chips (each links to detail page), shows drive count badge per company
- **DataTable** — 12 columns with inline editing, per-column search filters, column visibility toggle

**Calendar Tab (lazy-loaded):**
- Month navigation (prev/next buttons)
- 7-column CSS grid calendar
- Events color-coded by status (cyan=Upcoming, yellow=Ongoing, green=Completed, red=Cancelled)
- Data from `/api/cdm/calendar`

**Placement Sources Tab (lazy-loaded):**
- Stat cards (Total Placed, Recruiting Companies)
- 2 Chart.js charts: Top Placement Sources (horizontal bar), Avg CTC by Company (horizontal bar)
- Detail table: Company, Students Placed, Avg CTC, Max CTC, Courses
- Data from `/api/cdm/placement-sources`

**Modals:**
- Add Company Modal — single input for company name

### `cdm_company.html` (Company Detail Page, ~899 lines)

**Layout Structure:**
- Back to CDM link + editable company name (click-to-edit h3) + Delete Company button
- 3 Stat Cards: Total Drives, HR Contacts, Completed drives

**Drives Section:**
- Table with 15 columns: Drive#, Position, CTC, Status, Courses, JD Received, Process Date, Mode, Location, Received By, Data Shared, Notes, Students (button), Rounds (button), Actions (delete)
- All fields are inline-editable (click → input/select appears)
- Dropdown fields: status (Upcoming/Ongoing/Completed/Cancelled), process_mode (Online/Offline/Hybrid), data_shared (Yes/No)

**HR Contacts Section:**
- Table: Name, Designation, Email (mailto link), Phone, Actions (delete)
- All fields inline-editable

**5 Modals:**
1. **Student Linking Modal** — search students by name/reg_no/course, click to select, link button. Linked students table with status dropdown (Applied/Shortlisted/In Process/Selected/Rejected/On Hold). Unlink button per student.
2. **Rounds Modal** — add rounds with name + date, delete rounds. Rounds listed in order.
3. **Add HR Modal** — name, designation, email, phone fields
4. **Add Drive Modal** — role, CTC, process date, mode, location, status, notes fields
5. **Toast** for success/error notifications

### `cdm_upload.html` (Import Page)
- Drag & drop file upload area
- File type validation (.xlsx only)
- Expected columns reference (expandable details section)
- On success flash → "Go to CDM" button

---

## JavaScript Logic

### CDM Main Page JS

| Feature | Description |
|---------|-------------|
| Data initialization | Parses JSON from `#cdm-json` and `#companies-json` script tags embedded server-side |
| `updateStats()` | Counts modes/statuses across all drives, updates summary bar counters |
| `renderCompanies()` | Renders company chip grid with drive count badges |
| Toggle companies | Slide toggle for companies section visibility |
| Filter system init | Calls `initFilterSystem()` with custom `createdRow` callback for status badges |
| Filter tiles | Click handlers for status/mode filter tiles using `setPreFilter()` |
| Column visibility | Dynamic checkboxes per column, "Show All" / "Minimal" presets |
| **Inline editing** | Click on table cell → transforms to input/select. Supports dropdowns (status, process_mode, data_shared), date inputs, text inputs. Enter=save, Escape=cancel, blur=save-if-changed |
| `saveEdit()` | AJAX PUT to `/api/cdm/drive/<id>`, updates RAW_DATA in-place, refreshes badges/stats |
| Export Excel | Uses `xlsx-js-style` library. Styled headers (dark blue bg, white text, borders). Auto-width columns. Exports currently filtered/visible data only |
| Company search | Overrides `#globalSearch` input handler to hit `/api/cdm/search`, shows company results with status badges in dropdown |
| Calendar | Month grid rendering, prev/next navigation, lazy-loads from `/api/cdm/calendar`, auto-navigates to month of latest event |
| Placement Sources | Lazy-loads from `/api/cdm/placement-sources`, renders stat cards, detail table, and 2 Chart.js horizontal bar charts |
| Add Company | Modal form → POST `/api/cdm/company` → updates companies list in-place, opens company detail in new tab |

### Company Detail Page JS

| Feature | Description |
|---------|-------------|
| Drive inline editing | Click `.editable-drive` → input/select appears, AJAX PUT to `/api/cdm/drive/<id>` on save |
| Delete drive | Confirm dialog → POST `/api/cdm/delete-drive/<id>` → page reload |
| HR inline editing | Click `.editable-hr` → text input, AJAX PUT to `/api/cdm/hr/<id>` |
| Delete HR | Confirm → DELETE `/api/cdm/hr/<id>` → fade out row |
| Add HR | Modal form → POST `/api/cdm/hr` → page reload |
| **Student linking** | Modal with debounced student search (AJAX to `/api/cdm/search-students`), click-to-select, link button. Linked students table with live status dropdown (6 options). Unlink button with confirm |
| **Rounds management** | Modal with add form (name + date), POST to `/api/cdm/drive/<id>/rounds`. Rounds listed in order with delete button |
| Edit company name | Click h3 → large text input, AJAX PUT to `/api/cdm/company/<id>`, updates page title + breadcrumb |
| Delete company | Confirm (warns about cascade deletion) → DELETE `/api/cdm/company/<id>` → redirect to `/cdm` |
| Add Drive | Modal form (7 fields) → POST `/api/cdm/drive` → page reload |

---

## CSS Styling

All CDM-specific styles in `static/style.css` (~420 lines):

| Section | Description |
|---------|-------------|
| Calendar Grid | 7-col CSS grid, cell styling, event pills color-coded by status (4 colors) |
| Search Dropdown | Absolute positioned dropdown with item hover states |
| Tab Panels & Filters | Tab visibility toggling, filter tile pills with active state highlighting |
| Stat Cards | Flex layout stat cards with accent variant |
| Company Page Dropdown | Relative positioning for student search dropdown |
| Hero Section | 2-column grid hero with stat items (shared with dashboard) |
| Compact Summary Bar | Horizontal filter bar with separator dots between items |
| Companies Section | Responsive grid of company chips with hover effects and drive count badges |

---

## Data Flow

### Excel Import → Database
```
.xlsx file
  → POST /cdm/import
  → pandas read_excel
  → Header normalization (CDM_EXCEL_HEADERS mapping, 16 columns)
  → For each row:
      1. Extract company_name → generate/lookup company_id → INSERT INTO companies
      2. Parse fields (dates via parse_date_field, booleans, mode normalization)
      3. Duplicate drive detection (company_id + role + process_date match)
      4. INSERT INTO company_drives → get drive_id
      5. Parse comma-separated courses → INSERT INTO drive_courses
      6. If HR POC data exists → INSERT INTO company_hr (deduplicated by name)
  → Flash success message with import/skip counts
```

### Page Load → Render
```
GET /cdm
  → Server queries: drives JOIN companies + drive_courses aggregated
  → Also queries: all companies with LEFT JOIN drive count
  → Renders template with JSON data in <script> tags
  → Client-side: jQuery parses JSON → initFilterSystem() → DataTable rendered
  → Summary bar + companies grid populated
```

### Inline Edit Flow
```
Click table cell → cell content replaced with input/select element
  → User edits → Enter key or blur
  → AJAX PUT /api/cdm/drive/<id> with {field, value}
  → Server validates field name (whitelist), parses value per type
  → UPDATE company_drives SET <field> = <value>
  → Response {ok: true}
  → Client updates: cell display, RAW_DATA array, status badges, summary stats
```

### Lazy-Load Tabs
```
Tab click (Calendar/Sources/Analytics)
  → Check if already loaded (flag variable)
  → If not: AJAX GET to respective API endpoint
  → Parse response → render UI (calendar grid / charts / tables)
  → Set loaded flag to prevent re-fetch
```

---

## Interconnections with Other Modules

### Dashboard ↔ CDM
- **Hero section** (`dashboard.html`): "Company Drives" column loads from `/api/cdm/analytics` on page load — shows Companies, Drives, Completed, Selections, Avg CTC, Top CTC
- **CDM Analytics tab** on dashboard: Lazy-loaded view with:
  - Stat cards (drives, companies, CTC stats, total selections)
  - Team Performance table (member → companies brought, drives, selections, avg/highest CTC)
  - 4 Chart.js charts: Team Companies Brought, Team Selections, Top Placed Companies, Highest CTC Companies

### Students Module ↔ CDM
- `drive_students` table bridges the two modules via `reg_no` foreign key
- `/api/cdm/search-students` queries the `students` table for the linking UI
- `/api/cdm/drive/<id>/students` GET joins `drive_students` with `students` for name/course/department
- Student statuses in drives: Applied → Shortlisted → In Process → Selected / Rejected / On Hold
- **No direct FK** between `students.company_name` (free text in students table) and `companies` table

### Placement Sources (Bridge between Students & CDM)
- `/api/cdm/placement-sources` runs **two separate queries**:
  1. From `students` table: `WHERE status='Placed'` grouped by `company_name` → gets placed_count, avg_ctc, max_ctc, courses
  2. From `drive_students` joined with CDM tables: `WHERE ds.status='Selected'` grouped by `company_name`
- Cross-references: for each placement source company, shows `linked_placed` if that company also appears in CDM with selected students
- This effectively **bridges** the student placement data with the CDM drive tracking system

### Navigation
- All pages include CDM in the navbar: link to `/cdm`
- CDM pages load the global student search script but the main CDM page overrides it for company search
- Company detail pages link back to main CDM page

---

## Complete Feature List

### Major Features (10)
1. **Company CRUD** — create (with auto-generated 4-char ID), rename (inline click-to-edit), cascade delete (removes all related data)
2. **Drive CRUD** — create via modal (7 fields), inline-edit all 10 fields with type-appropriate inputs, delete with confirmation
3. **HR Contact Management** — add via modal, inline-edit all fields, delete with fade animation
4. **Student Linking** — search students, link to drive, track through 6 statuses (Applied → Shortlisted → In Process → Selected/Rejected/On Hold), unlink
5. **Round Management** — add rounds with name + date, auto-ordered, delete individual rounds
6. **Excel Import** — upload .xlsx, parses 16 columns, auto-creates companies, deduplicates drives & HR contacts
7. **Excel Export** — styled .xlsx with dark blue headers, white text, borders, auto-width columns, exports only currently filtered/visible data
8. **Calendar View** — month grid with color-coded drive events, month navigation, lazy-loaded
9. **Placement Sources Analytics** — bridges students table with CDM, shows which companies placed students and cross-references with CDM tracking
10. **CDM Team Analytics** — CTC stats (fixed parsing), team performance breakdown by received_by field, top companies by selections & CTC

### Minor Features (16)
11. **Inline cell editing** — click-to-edit with dropdowns for enum fields (status, mode, data_shared), date pickers for dates, text inputs for others
12. **Column visibility toggle** — individual column show/hide checkboxes, "Show All" / "Minimal" preset buttons
13. **Status filter tiles** — quick-filter summary bar pills (All/Upcoming/Ongoing/Completed/Cancelled/On-Campus/Virtual)
14. **Company search** — navbar global search overridden on CDM page to search companies via `/api/cdm/search` with debounced autocomplete dropdown
15. **Student search** — debounced search in linking modal by name/reg_no/course
16. **Companies grid** — collapsible chip list showing all companies with drive count badges, links to detail pages
17. **Toast notifications** — success/error feedback for all CRUD operations
18. **Per-company stat cards** — Total Drives, HR Contacts, Completed count on company detail page
19. **Color-coded status badges** — Bootstrap badges with status-specific colors throughout all views
20. **Duplicate drive detection** — skips duplicate drives on Excel import (matches company_id + role + process_date)
21. **Company ID generation** — auto-generated 4-char IDs from company names with collision handling (appends incrementing number)
22. **Multi-format date parsing** — supports 6 different date formats commonly found in Excel files
23. **Smart CTC text parsing** — extracts numeric values from free-text CTC fields, handles range separators (`-`, `&`, `,`, `/`)
24. **Email format validation** — regex check on HR email field updates
25. **Data Shared boolean toggle** — stored as boolean, displayed as "Yes"/"No", edited via dropdown
26. **Navbar search override** — CDM page replaces default student search behavior with company search
