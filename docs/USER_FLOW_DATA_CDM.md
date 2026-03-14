# Placenest — Detailed User Flow (/data and /cdm)

This document describes what users can see, what they can click, what opens, what they can enter, where data is saved, and where it appears later.

---

## 1) Global Navigation Flow

### Top navbar (all main pages)
- Brand: **Placenest**
- Main links:
  - **Dashboard** (`/`)
  - **Data** (`/data`)
  - **CDM** (`/cdm`)
  - **More** → Upload/Export and Logs & Versions

### Common behavior
- User can move between modules at any time from navbar.
- Many actions open detail pages in the same tab (notably student from CDM drive students now opens same tab).

---

## 2) /data Module — Student Data Management

## 2.1 What user sees on `/data`
- Student data table (DataTables-based) with searchable/sortable rows.
- Column visibility controls:
  - Show All
  - Minimal
  - Column toggles
- Save view modal/action.
- Table hint: click student name to open profile.

## 2.2 Main actions on `/data`

### A) Inline update student field
1. User edits a student field in table/profile edit paths.
2. Frontend calls `PUT /api/student/<reg_no>` with `{ field, value }`.
3. Backend validates editable fields and types.
4. Data saved in `students` table.
5. Change logged to `edit_log`.
6. Analytics cache invalidated.
7. Updated value appears in `/data` table and profile.

### B) Delete student
1. User triggers delete.
2. Frontend calls `DELETE /api/student/<reg_no>`.
3. Student row removed from `students`.
4. Analytics cache invalidated.
5. Student disappears from table/search.

### C) Open student profile
1. User clicks student name.
2. Navigates to `/student/<reg_no>`.
3. Profile shows full student data + uploaded files.

### D) Bulk update from profile
1. User edits multiple fields in profile.
2. Frontend sends `PUT /api/student/<reg_no>/bulk-update` with `fields` object.
3. Backend updates changed fields only.
4. Each field change logged in `edit_log`.
5. `placed_date` auto-managed if `status` changes to/from `Placed`.

### E) Student file operations
- Upload file: `POST /student/<reg_no>/upload-file`
  - Saved physically in `uploads/`
  - Metadata saved in `student_files`
- View file: `GET /uploads/<filename>`
- Delete file: `POST /student/<reg_no>/delete-file/<file_id>`
  - Deletes both disk file and `student_files` row

### F) Data retrieval/search/logs
- Full student data feed: `GET /api/students`
- Quick search suggestions: `GET /api/search?q=...`
- Edit log feed: `GET /api/edit-log`

## 2.3 Where `/data` writes and where user sees it
- `students` → main table + profile
- `edit_log` → logs/versions pages
- `student_files` + `uploads/` → profile file section

---

## 3) /cdm Module — Company & Drive Management

## 3.1 What user sees on `/cdm`
- 3 tabs:
  1. **Drives**
  2. **Calendar**
  3. **Placement Sources**
- **Add Company** button.
- Companies area:
  - companies list/chips
  - primary company tiles
  - optional sheet/table view
- Filters (status/mode) and column controls.

## 3.2 Add Company flow (current)

### User inputs in Add Company modal
- Company Name (required)
- Process Date
- Mode
- Location
- Received By (Owner/SPOC)
- Notes

### Save path
1. User clicks **Add Company**.
2. Frontend calls `POST /api/cdm/company` with above fields.
3. Backend creates `company_id` and inserts into `companies`.
4. Company appears in:
   - company list/chips
   - company tile view
5. User can open company detail page (`/cdm/company/<company_id>`).

> Departments and company-level course selection are removed from company creation flow.

## 3.3 Drives tab on `/cdm`
- Shows all drives with status/mode/course info.
- Company tile “Open Company” opens company detail page.
- Sheet view lists drive rows and columns including **Courses**.

## 3.4 Company detail page `/cdm/company/<company_id>`

### What user sees
- Company header + actions
- Drive cards + table view toggle
- Add Drive modal
- Edit Drive modal
- Drive Students modal
- Drive Rounds modal
- HR contacts panel and add/edit/delete actions

### A) Add Drive flow
1. User clicks **Add Drive**.
2. User enters:
   - Position/Role
   - CTC
   - Course + Drive Type selections (for each selected course)
   - Process Date
   - Mode
   - Location
   - Status
   - Notes
3. Validation:
   - Role required
   - At least one course required
   - Every selected course requires drive type
4. Frontend calls `POST /api/cdm/drive`.
5. Backend writes:
   - `company_drives` row
   - `drive_courses` rows (`course_name`, `drive_type` per drive)
6. Drive appears in card and sheet views.
7. Courses column displays comma-separated values (e.g., `B.Tech CSE (Core), B.Tech IT (Mandatory)`).

### B) Edit Drive flow
1. User clicks **Edit** on drive card/table row.
2. Edit modal pre-fills existing values, including parsed course/type tags.
3. User updates any field.
4. Frontend sends field-wise `PUT /api/cdm/drive/<drive_id>`.
5. For `courses`, backend rewrites `drive_courses` rows for that drive.
6. Updated values render after reload.

### C) Drive Students flow
1. User clicks **Students** on a drive.
2. Modal opens and fetches linked students via `GET /api/cdm/drive/<drive_id>/students`.
3. User can:
   - Search and link one student: `POST /api/cdm/drive/<drive_id>/students`
   - Update link status/current round: `PUT /api/cdm/drive/<drive_id>/students/<reg_no>`
   - Unlink student: `DELETE /api/cdm/drive/<drive_id>/students/<reg_no>`
   - Bulk import from Excel: `POST /api/cdm/drive/<drive_id>/students/bulk`
4. Student name click now opens `/student/<reg_no>` in same tab (better back navigation).

### D) Drive Rounds flow
1. User clicks **Rounds** on a drive.
2. Modal loads rounds via `GET /api/cdm/drive/<drive_id>/rounds`.
3. Add round via `POST /api/cdm/drive/<drive_id>/rounds`.
4. Delete round via `DELETE /api/cdm/round/<round_id>`.

### E) HR contacts flow
- Add HR: `POST /api/cdm/hr`
- Edit HR field: `PUT /api/cdm/hr/<hr_id>`
- Delete HR: `DELETE /api/cdm/hr/<hr_id>`
- Visible in HR cards on company detail page.

### F) Delete drive/company flow
- Delete drive: `POST /api/cdm/delete-drive/<drive_id>`
  - Removes linked students, rounds, drive courses, then drive
- Delete company: `DELETE /api/cdm/company/<company_id>`
  - Cascades through related drive/HR/link data

## 3.5 Calendar tab flow
- On opening Calendar tab, frontend calls `GET /api/cdm/calendar`.
- Events grouped by `process_date` and rendered month-wise.
- User can navigate prev/next month.

## 3.6 Placement Sources tab flow
- On opening Placement Sources tab, frontend calls `GET /api/cdm/placement-sources`.
- Shows:
  - total placed
  - top source chart
  - avg CTC chart
  - source details table

## 3.7 CDM supporting APIs used by UI
- `GET /api/cdm` (drives feed)
- `GET /api/cdm/search?q=...` (global company search)
- `GET /api/cdm/analytics` (analytics cards/charts)
- `GET /api/cdm/unique-courses-departments` (course options from student data)
- `GET/POST/DELETE /api/cdm/course-presets` (preset utilities)
- `GET /api/cdm/edit-log` (drive edit history)

---

## 4) Data Persistence Map (What saves where)

### /data
- Student master values → `students`
- Student field edit history → `edit_log`
- Student files metadata → `student_files`
- Uploaded file binaries → `uploads/`

### /cdm
- Company basic info → `companies`
- Drive records → `company_drives`
- Per-drive courses + drive type → `drive_courses`
- Drive-student links/status/round progression → `drive_students`
- Drive rounds → `drive_rounds`
- HR contacts → `company_hr`
- CDM edit history → `cdm_edit_log`
- Course presets → `course_presets`, `course_preset_items`

---

## 5) End-to-End Example (CDM)

1. User opens `/cdm` and clicks **Add Company**.
2. Fills company details and saves.
3. Opens that company page.
4. Clicks **Add Drive**, selects role/CTC/courses+type/status/etc, saves.
5. Drive appears in card + sheet with comma-separated course labels.
6. Opens Students modal, links students, updates statuses.
7. Clicks a student name → opens profile in same tab.
8. User uses browser Back to return to previous page naturally.

---

## 6) UX Notes
- Current navigation favors in-context workflows.
- Same-tab student navigation from CDM improves back-stack continuity.
- Drive-level course ownership avoids duplicate entry and keeps sheet/card consistency.
