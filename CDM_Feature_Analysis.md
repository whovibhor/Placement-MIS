# CDM (Company Drive Management) — Complete Feature Analysis

## 1. Core Concept
The **Company Drive Management (CDM)** module is the central hub for managing recruitment activities. It decouples "Companies" from "Drives", allowing a single company entity to have multiple recruitment drives over time. It tracks HR contacts and manages the student selection process per drive.

**Key Evolution**: The system now supports **Per-Course Drive Types**. Instead of a company being globally "Mandatory" or "Core", each course offered by the company is individually tagged. This allows scenarios like "MBA: Mandatory, BBA: Interest Based" for the same company.

## 2. Data Architecture

### Database Schema
All tables are initialized in `helpers.py`.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `companies` | Company master record | `company_id` (PK, 4-char code), `company_name` |
| `company_courses` | **NEW**: Courses & Drive Types | `company_id` (FK), `course_name`, **`drive_type`** (enum: Mandatory, Core, Interest Based) |
| `company_departments`| Departments map | `company_id` (FK), `department_name` |
| `company_drives` | Individual recruitment events | `drive_id` (PK), `company_id` (FK), role, CTC, dates, status |
| `company_hr` | HR contact persons | `hr_id` (PK), `company_id` (FK), details |
| `drive_rounds` | Selection process rounds | `round_id` (PK), `drive_id` (FK), name, date |
| `drive_students` | Student tracking in drives | `drive_id` + `reg_no` (Composite PK), status (Applied, Selected, etc.) |

### Key Relationships
- **One Company** has **Many Drives** (`companies` 1:N `company_drives`)
- **One Company** has **Many HR Contacts** (`companies` 1:N `company_hr`)
- **One Company** is mapped to **Many Courses**, each with its own **Drive Type** (`companies` 1:N `company_courses`)

---

## 3. Key Feature Logic

### A. Company Management (CRUD)
- **Creation**: Companies are created with a Name. A unique 4-character `company_id` is auto-generated (e.g., "ACDS" from "Activity Beds").
- **Course & Drive Type Mapping (Per-Course Logic)**:
  - **Granularity**: Drive Type is now a property of the *link* between a company and a course, not the company itself.
  - **Storage**: Data is stored in the `company_courses` table.
  - **Logic**: When filtering eligibility, the system checks the specific drive type for the student's course.
- **Department Mapping**: Companies are also tagged with relevant departments (e.g., "Management", "IT") for broader categorization.

### B. Drive Management
- **Drives** are the executable events. A drive is linked to a company but has its own specific:
  - **Role/Profile** (e.g., "Management Trainee")
  - **CTC** package
  - **Process Date** & **Mode** (Virtual/On-Campus)
  - **Status** (Upcoming, Ongoing, Completed, Cancelled)
- **Student Lifecycle**: Students are linked to drives. Their status moves through stages (Applied -> Shortlisted -> Selected).

### C. Presets & Bulk Actions
- **Course Presets**: Users can select predefined groups of courses (e.g., "All Management") to quickly populate the course list.
- **Bulk Drive Type**:
  - In "Add Company" and "Edit Company" modals, a **bulk toolbar** allows applying a single drive type (e.g., "Mandatory") to all currently checked courses.
  - Users can also manually override the drive type for individual courses using inline dropdowns.

---

## 4. UI/UX Design

### Dashboard (`/cdm`)
- **View Modes**:
  - **Drives List**: Tabular view of all active drives.
  - **Companies Grid**: Card-based grid showing all companies.
- **Company Card**:
  - Displays Company Name and ID.
  - **Aggregate Badges**: Summarizes the drive types. E.g., if a company has 3 Mandatory courses and 2 Interest Based, it shows "3 Mandatory" (Red) and "2 Interest Based" (Green) badges.
- **Add Company Modal**:
  - **Structure**: Name input (full width) + Course/Dept selection.
  - **Dynamic Interactivity**:
    - **Course Rows**: Each course is a row with a checkbox.
    - **Inline Selector**: Checking a course reveals a hidden Drive Type dropdown for that specific course.
    - **Bulk Tool**: "Apply to checked" button sets all visible dropdowns to a selected value.

### Company Detail Page (`/cdm/company/<id>`)
- **Header**:
  - Shows Company Name and ID.
  - **Course Badges**: Lists all linked courses. Each course badge includes a nested, colored badge indicating its Drive Type (Red=Mandatory, Blue=Core, Green=Interest Based).
- **Edit Info Modal**:
  - Similar to the Add Modal, allows modifying course selection and updating per-course drive types.
  - Pre-populates existing values from `company_courses`.
- **Related Entities**:
  - **Drives**: List of all drives with inline editing.
  - **HR Contacts**: Manage multiple HR persons.
  - **Stats**: Cards for total drives, HR count, etc.

---

## 5. Technical Implementation Details

### Backend (Flask)
- **`routes_cdm.py`**:
  - **`cdm_create_company`**: Accepts `courses` as a list of objects `{course_name, drive_type}`. Inserts into `companies` (name only) and `company_courses` (course + drive_type).
  - **`cdm_update_company`**:
    - Updates `company_name` in `companies` table.
    - **Full Synchronization**: Deletes *all* existing entries in `company_courses` and `company_departments` for the ID, then re-inserts the new list. This avoids complex diffing logic.
  - **`cdm_page` & `cdm_company_detail`**:
    - Queries join `companies` with `company_courses`.
    - Data is transformed into nested JSON objects before rendering templates.

### Frontend (jQuery + Bootstrap)
- **State Management**:
  - **`renderCompanies()`**: Iterates through the JSON data to build the grid view. Calculates badge aggregates on the fly.
  - **`renderCourseCheckboxes()`**: Dynmically builds the course list. Handles the logic of showing/hiding the drive type dropdown based on checkbox state.
- **Data Submission**:
  - Forms collect data by iterating over checked `.addCourse-cb` elements.
  - For each checked course, it finds the corresponding `.addCourse-dt` value and constructs a `{course_name, drive_type}` object to send to the API.

---

## 6. Legacy / Backward Compatibility
- **`companies.drive_type` Column**: The `companies` table still retains a `drive_type` column from the previous design. It is now **deprecated** and no longer written to or read from by the application logic. All drive type data lives in `company_courses`.
- **Migration**: A schema migration in `helpers.py` ensures the new `company_courses` table includes the `drive_type` column.
