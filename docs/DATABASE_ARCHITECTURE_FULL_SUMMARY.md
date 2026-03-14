# Placenest — Full Database Architecture Summary

Last updated: 2026-03-14  
Source of truth used: runtime schema initialization in `helpers.py` + active write paths in `routes_data.py` and `routes_cdm.py`.

---

## 1) High-Level Database Domains

- **Student domain**: `students`, `edit_log`, `student_files`, `upload_versions`, `version_snapshots`, `analytics_cache`
- **CDM domain**: `companies`, `company_drives`, `drive_courses`, `drive_students`, `drive_rounds`, `company_hr`, `cdm_edit_log`
- **CDM preset domain**: `course_presets`, `course_preset_items`

---

## 2) Relationship Map (Logical)

- `companies (1) -> (N) company_drives`
- `company_drives (1) -> (N) drive_courses`
- `company_drives (1) -> (N) drive_rounds`
- `company_drives (1) -> (N) drive_students`
- `students (1) -> (N) drive_students`
- `companies (1) -> (N) company_hr`
- `students (1) -> (N) student_files`
- `upload_versions (1) -> (N) version_snapshots`
- `course_presets (1) -> (N) course_preset_items`

---

## 3) Table-by-Table Detailed Schema

## 3.1 `students`
Primary purpose: master student records used in `/data`, profile, and CDM student linking.

| Column | Type | Key | Notes |
|---|---|---|---|
| `sr_no` | `INT` |  | serial from uploads |
| `reg_no` | `VARCHAR(50)` | **PK** | unique student identifier |
| `student_name` | `VARCHAR(200)` |  |  |
| `gender` | `VARCHAR(20)` |  |  |
| `course` | `VARCHAR(100)` | IDX `idx_course` |  |
| `resume_status` | `VARCHAR(100)` |  |  |
| `seeking_placement` | `VARCHAR(100)` | IDX `idx_seeking` | Opted In/Out etc |
| `department` | `VARCHAR(100)` | IDX `idx_department` |  |
| `offer_letter_status` | `VARCHAR(100)` |  |  |
| `status` | `VARCHAR(100)` | IDX `idx_status` | Placed/Unplaced etc |
| `placed_date` | `DATE` | IDX `idx_placed_date` | added via migration |
| `company_name` | `VARCHAR(200)` |  | placed company name |
| `designation` | `VARCHAR(200)` |  |  |
| `ctc` | `DECIMAL(10,2)` |  | migrated from text |
| `joining_date` | `VARCHAR(100)` |  | kept as string in schema |
| `joining_status` | `VARCHAR(100)` |  |  |
| `school_name` | `VARCHAR(200)` |  |  |
| `mobile_number` | `VARCHAR(50)` |  |  |
| `email` | `VARCHAR(200)` |  |  |
| `graduation_course` | `VARCHAR(100)` |  |  |
| `graduation_ogpa` | `DECIMAL(4,2)` |  | migrated from text |
| `percent_10` | `DECIMAL(5,2)` |  | migrated from text |
| `percent_12` | `DECIMAL(5,2)` |  | migrated from text |
| `backlogs` | `INT` |  | migrated from text |
| `hometown` | `VARCHAR(200)` |  |  |
| `address` | `TEXT` |  |  |
| `reason` | `TEXT` |  |  |

Writes happen from: upload pipeline + `/api/student/<reg_no>` + `/api/student/<reg_no>/bulk-update` + delete API.

---

## 3.2 `upload_versions`
Tracks each uploaded dataset version.

| Column | Type | Key | Notes |
|---|---|---|---|
| `version_id` | `INT AUTO_INCREMENT` | **PK** |  |
| `filename` | `VARCHAR(255)` |  |  |
| `uploaded_at` | `DATETIME` |  |  |
| `total_records` | `INT` |  | default `0` |
| `inserted` | `INT` |  | default `0` |
| `updated` | `INT` |  | default `0` |
| `content_hash` | `VARCHAR(32)` |  | added by migration |

---

## 3.3 `version_snapshots`
Historical snapshot rows per upload version.

| Column | Type | Key | Notes |
|---|---|---|---|
| `id` | `INT AUTO_INCREMENT` | **PK** |  |
| `version_id` | `INT` | **FK** | -> `upload_versions.version_id` |
| `sr_no` … `reason` | same as `students` shape |  | snapshot payload |

`version_snapshots` duplicates nearly all student columns intentionally for audit/version restore.

---

## 3.4 `student_files`
Stores uploaded file metadata for each student.

| Column | Type | Key | Notes |
|---|---|---|---|
| `id` | `INT AUTO_INCREMENT` | **PK** |  |
| `reg_no` | `VARCHAR(50)` | **FK** | -> `students.reg_no` |
| `file_type` | `VARCHAR(50)` |  | resume, offer, etc |
| `original_name` | `VARCHAR(255)` |  | user file name |
| `stored_name` | `VARCHAR(255)` |  | disk-safe generated name |
| `uploaded_at` | `DATETIME` |  |  |

Physical binary file is stored in filesystem `uploads/` (not inside DB).

---

## 3.5 `edit_log`
Student edit audit log.

| Column | Type | Key | Notes |
|---|---|---|---|
| `id` | `INT AUTO_INCREMENT` | **PK** |  |
| `reg_no` | `VARCHAR(50)` | IDX `idx_reg` | student reference (not FK constrained) |
| `student_name` | `VARCHAR(200)` |  | denormalized snapshot |
| `field_name` | `VARCHAR(100)` |  | edited column |
| `old_value` | `TEXT` |  |  |
| `new_value` | `TEXT` |  |  |
| `changed_at` | `DATETIME` | IDX `idx_time` |  |

---

## 3.6 `cdm_edit_log`
Drive edit audit log (CDM).

| Column | Type | Key | Notes |
|---|---|---|---|
| `id` | `INT AUTO_INCREMENT` | **PK** |  |
| `drive_id` | `INT` | IDX `idx_drive` | drive reference |
| `company_name` | `VARCHAR(200)` |  | denormalized snapshot |
| `field_name` | `VARCHAR(100)` |  | edited drive field |
| `old_value` | `TEXT` |  |  |
| `new_value` | `TEXT` |  |  |
| `changed_at` | `DATETIME` | IDX `idx_cdm_time` |  |

---

## 3.7 `analytics_cache`
Stores serialized analytics JSON.

| Column | Type | Key | Notes |
|---|---|---|---|
| `id` | `INT` | **PK** | seeded with row `id=1` |
| `data` | `JSON` |  | cached analytics payload |
| `updated_at` | `DATETIME` |  | cache timestamp |

---

## 3.8 `companies`
Company master.

| Column | Type | Key | Notes |
|---|---|---|---|
| `company_id` | `VARCHAR(10)` | **PK** | generated short ID |
| `company_name` | `VARCHAR(200)` |  | required |
| `received_by` | `VARCHAR(200)` |  | owner/SPOC |
| `notes` | `TEXT` |  |  |

Writes happen from: `POST/PUT /api/cdm/company`.

---

## 3.9 `company_drives`
Drive records per company.

| Column | Type | Key | Notes |
|---|---|---|---|
| `drive_id` | `INT AUTO_INCREMENT` | **PK** |  |
| `company_id` | `VARCHAR(10)` | **FK + IDX** | -> `companies.company_id` |
| `role` | `VARCHAR(200)` |  | position |
| `ctc_text` | `VARCHAR(100)` |  | text CTC representation |
| `jd_received_date` | `DATE` |  |  |
| `process_date` | `DATE` |  | drive-level date |
| `data_shared` | `BOOLEAN` |  | yes/no stored as bool |
| `location` | `VARCHAR(200)` |  | drive-level venue |
| `jd_briefing_done` | `BOOLEAN` |  | JD briefing session completion flag |
| `jd_briefing_date` | `DATE` |  | JD briefing session date |
| `jd_briefing_conducted_by` | `VARCHAR(200)` |  | briefing owner/facilitator |
| `notes` | `TEXT` |  |  |
| `status` | `VARCHAR(50)` |  | default `Upcoming` |

Writes happen from: `POST /api/cdm/drive`, `PUT /api/cdm/drive/<id>`, delete-drive flow.

---

## 3.10 `drive_courses`
Per-drive course eligibility + type.

| Column | Type | Key | Notes |
|---|---|---|---|
| `drive_id` | `INT` | **PK(part) + FK** | -> `company_drives.drive_id` |
| `course_name` | `VARCHAR(100)` | **PK(part)** | prevents duplicate course per drive |
| `drive_type` | `VARCHAR(50)` |  | Mandatory/Core/Interest Based |

Composite PK: **(`drive_id`, `course_name`)**.

Writes happen from:
- `POST /api/cdm/drive` (insert rows)
- `PUT /api/cdm/drive/<id>` when `field='courses'` (delete + reinsert)
- delete-drive / delete-company cascades.

---

## 3.11 `company_hr`
HR contacts for a company.

| Column | Type | Key | Notes |
|---|---|---|---|
| `hr_id` | `INT AUTO_INCREMENT` | **PK** |  |
| `company_id` | `VARCHAR(10)` | **FK** | -> `companies.company_id` |
| `name` | `VARCHAR(200)` |  |  |
| `designation` | `VARCHAR(200)` |  |  |
| `email` | `VARCHAR(200)` |  |  |
| `phone` | `VARCHAR(50)` |  |  |

Writes happen from: `POST/PUT/DELETE /api/cdm/hr...`.

---

## 3.12 `drive_rounds`
Round definitions per drive.

| Column | Type | Key | Notes |
|---|---|---|---|
| `round_id` | `INT AUTO_INCREMENT` | **PK** |  |
| `drive_id` | `INT` | **FK** | -> `company_drives.drive_id` |
| `round_name` | `VARCHAR(100)` |  |  |
| `round_order` | `INT` |  | sequential order |
| `round_date` | `DATE` |  | added by migration |

Writes happen from: `GET/POST /api/cdm/drive/<id>/rounds`, delete round API.

---

## 3.13 `drive_students`
Join table linking students to drives with status progression.

| Column | Type | Key | Notes |
|---|---|---|---|
| `drive_id` | `INT` | **PK(part) + FK** | -> `company_drives.drive_id` |
| `reg_no` | `VARCHAR(50)` | **PK(part) + FK** | -> `students.reg_no` |
| `status` | `VARCHAR(50)` |  | Applied/Selected/etc |
| `current_round` | `INT` |  | added by migration |

Composite PK: **(`drive_id`, `reg_no`)**.

Writes happen from: student link/update/unlink APIs and bulk import API.

---

## 3.14 `course_presets`
Preset header table for CDM course shortcuts.

| Column | Type | Key | Notes |
|---|---|---|---|
| `preset_id` | `INT AUTO_INCREMENT` | **PK** |  |
| `preset_name` | `VARCHAR(100)` | **UNIQUE** |  |

---

## 3.15 `course_preset_items`
Preset items table.

| Column | Type | Key | Notes |
|---|---|---|---|
| `preset_id` | `INT` | **PK(part) + FK** | -> `course_presets.preset_id` |
| `course_name` | `VARCHAR(100)` | **PK(part)** | unique within preset |

Composite PK: **(`preset_id`, `course_name`)**.

---

## 4) Duplicate / Overlapping Data in Current Design

These are intentional or legacy overlaps currently present:

1. **Denormalized names in logs**
   - `edit_log.student_name` duplicates `students.student_name`
   - `cdm_edit_log.company_name` duplicates `companies.company_name`

2. **Snapshot duplication**
   - `version_snapshots` duplicates student payload for version history.

---

## 5) What User Input Is NOT Saved to Database (Current)

## 5.1 Explicitly not DB-persisted (client/session only)

- **Saved Views in `/data`**
  - View name, active quick-filter, column filter config
  - Stored in browser `localStorage` key: `pmis_saved_views`
  - Not written to any SQL table.

- **UI state controls (all pages)**
  - Column visibility toggles
  - Selected quick-filter tiles
  - Search box text (`globalSearch`, student search in modal)
  - Tab switch state (Drives/Calendar/Sources)
  - Calendar month navigation state
  - Modal open/close state
  - Not persisted in DB.

## 5.2 Inputs that may appear but are currently legacy/dead paths

- Company-level course/department model has been removed from schema; course eligibility is drive-level only (`drive_courses`).

## 5.3 Important note about files

- Uploaded files are **not** stored as blobs in DB.
- DB stores metadata in `student_files`; actual file bytes are stored in filesystem `uploads/`.

---

## 6) Primary Keys, Composite Keys, and Duplicate Prevention

- Single-column PKs:
  - `students.reg_no`
  - `companies.company_id`
  - `company_drives.drive_id`
  - `company_hr.hr_id`
  - `drive_rounds.round_id`
  - `upload_versions.version_id`
  - `version_snapshots.id`
  - `student_files.id`
  - `edit_log.id`
  - `cdm_edit_log.id`
  - `course_presets.preset_id`
  - `analytics_cache.id`

- Composite PKs (duplicate protection):
  - `drive_courses (drive_id, course_name)`
  - `drive_students (drive_id, reg_no)`
  - `course_preset_items (preset_id, course_name)`

- Extra uniqueness:
  - `course_presets.preset_name` is `UNIQUE`.

---

## 7) Current Write Coverage by Feature (Quick Matrix)

| Feature | Tables Written |
|---|---|
| Student inline edit/bulk edit | `students`, `edit_log` |
| Student delete | `students` |
| Student file upload/delete | `student_files` + filesystem `uploads/` |
| Data analytics cache refresh | `analytics_cache` |
| Company create/update/delete | `companies` (+ cascading related deletes) |
| Drive create/edit/delete | `company_drives`, `drive_courses`, `cdm_edit_log` |
| Drive student linking/status/bulk | `drive_students` |
| Drive rounds | `drive_rounds` |
| HR CRUD | `company_hr` |
| Course presets CRUD | `course_presets`, `course_preset_items` |
| Upload versioning pipeline | `upload_versions`, `version_snapshots`, `students` |

---

## 8) Schema Drift Note

- `database/schema.sql` currently defines only `students` base shape.
- Runtime schema in `helpers.py` is broader and includes all operational tables/migrations above.
- For accurate production architecture, use `helpers.py` behavior as the authoritative schema initializer.
