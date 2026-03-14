# Placenest — Mermaid User Flow (/data and /cdm)

This file provides visual user-flow diagrams for both modules.

## 1) Global Navigation

```mermaid
flowchart LR
    A[User Opens Placenest] --> B[Dashboard /]
    B --> C[Data /data]
    B --> D[CDM /cdm]
    B --> E[Upload / Export]
    B --> F[Logs & Versions]

    C --> G[Student Profile /student/:reg_no]
    D --> H[Company Detail /cdm/company/:company_id]
    H --> G
```

## 2) /data Detailed Flow

```mermaid
flowchart TD
    A[/data page load/] --> B[Load students table]
    B --> B1[GET /api/students]

    B --> C[User edits student field]
    C --> C1[PUT /api/student/:reg_no]
    C1 --> C2[(students)]
    C1 --> C3[(edit_log)]
    C1 --> C4[Invalidate analytics cache]

    B --> D[User bulk updates in profile]
    D --> D1[/student/:reg_no/]
    D1 --> D2[PUT /api/student/:reg_no/bulk-update]
    D2 --> D3[(students)]
    D2 --> D4[(edit_log)]

    B --> E[User deletes student]
    E --> E1[DELETE /api/student/:reg_no]
    E1 --> E2[(students)]

    D1 --> F[Upload file]
    F --> F1[POST /student/:reg_no/upload-file]
    F1 --> F2[(student_files)]
    F1 --> F3[(uploads folder)]

    D1 --> G[Delete file]
    G --> G1[POST /student/:reg_no/delete-file/:file_id]
    G1 --> G2[(student_files)]
    G1 --> G3[(uploads folder)]

    B --> H[Search]
    H --> H1[GET /api/search?q=]

    B --> I[View edit logs]
    I --> I1[GET /api/edit-log]
```

## 3) /cdm Main Flow

```mermaid
flowchart TD
    A[/cdm page load/] --> B[Drives Tab]
    A --> C[Calendar Tab]
    A --> D[Placement Sources Tab]

    B --> B1[GET /api/cdm]
    B --> B2[Add Company]
    B2 --> B3[POST /api/cdm/company]
    B3 --> B4[(companies)]
    B3 --> E[Open Company Profile /cdm/company/:company_id]

    B --> B5[Open Company from tile/list]
    B5 --> E

    C --> C1[GET /api/cdm/calendar]
    D --> D1[GET /api/cdm/placement-sources]

    B --> S[Global search company]
    S --> S1[GET /api/cdm/search?q=]
```

## 4) Company Detail Flow (/cdm/company/:company_id)

```mermaid
flowchart TD
    A[/cdm/company/:company_id/] --> B[View Drive Cards + Sheet]
    A --> C[View HR Panel]

    B --> D[Add Drive]
    D --> D1[Enter Role, CTC, Course+DriveType, dates/mode/location/status/notes]
    D1 --> D2[POST /api/cdm/drive]
    D2 --> D3[(company_drives)]
    D2 --> D4[(drive_courses with drive_type)]

    B --> E[Edit Drive]
    E --> E1[PUT /api/cdm/drive/:drive_id field-wise]
    E1 --> E2[(company_drives)]
    E1 --> E3[(drive_courses rewrite when field=courses)]
    E1 --> E4[(cdm_edit_log for non-course fields)]

    B --> F[Manage Students]
    F --> F1[GET /api/cdm/drive/:drive_id/students]
    F --> F2[POST link student]
    F --> F3[PUT update status/round]
    F --> F4[DELETE unlink student]
    F --> F5[POST bulk import students]

    F --> F6[Click Student Name]
    F6 --> G[/student/:reg_no opens in same tab/]
    G --> H[Browser Back returns to previous page]

    B --> I[Manage Rounds]
    I --> I1[GET /api/cdm/drive/:drive_id/rounds]
    I --> I2[POST add round]
    I --> I3[DELETE round]

    C --> J[Add HR]
    J --> J1[POST /api/cdm/hr]
    C --> K[Edit HR]
    K --> K1[PUT /api/cdm/hr/:hr_id]
    C --> L[Delete HR]
    L --> L1[DELETE /api/cdm/hr/:hr_id]

    B --> M[Delete Drive]
    M --> M1[POST /api/cdm/delete-drive/:drive_id]

    A --> N[Delete Company]
    N --> N1[DELETE /api/cdm/company/:company_id]
```

## 5) Persistence Map

```mermaid
flowchart LR
    A[/data actions/] --> S1[(students)]
    A --> S2[(edit_log)]
    A --> S3[(student_files)]
    A --> S4[(uploads folder)]

    B[/cdm actions/] --> C1[(companies)]
    B --> C2[(company_drives)]
    B --> C3[(drive_courses)]
    B --> C4[(drive_students)]
    B --> C5[(drive_rounds)]
    B --> C6[(company_hr)]
    B --> C7[(cdm_edit_log)]
    B --> C8[(course_presets)]
    B --> C9[(course_preset_items)]
```

## 6) Same-tab Student Navigation (Sequence)

```mermaid
sequenceDiagram
    participant U as User
    participant C as CDM Company Page
    participant P as Student Profile Page

    U->>C: Open Drive Students modal
    U->>C: Click student name
    C->>P: Navigate to /student/:reg_no (same tab)
    U->>P: Review profile data/files
    U->>C: Click browser Back
    Note over U,C: Returns to previous page in history stack
```
