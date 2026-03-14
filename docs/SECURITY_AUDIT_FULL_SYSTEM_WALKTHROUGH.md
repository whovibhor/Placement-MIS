# Placenest — Full Security Audit & End-to-End System Walkthrough

**Audit date:** 2026-03-14  
**Scope:** Flask app, Data module, CDM module, DB access patterns, file upload flows, analytics and export APIs  
**Audited files:** `app.py`, `helpers.py`, `routes_data.py`, `routes_cdm.py`, templates/static behavior

---

## 1) Executive Summary

This system is a server-rendered Flask monolith with two functional domains:
- **Data domain** (`/data`, student lifecycle, logs, file attachments, analytics)
- **CDM domain** (`/cdm`, company-drive-round workflows, student progression, exports, alerts)

### High-level security posture
- ✅ Good baseline against SQL injection (parameterized queries are used broadly)
- ✅ Strong auditability for core mutations (`edit_log`, `cdm_edit_log`, `drive_round_transitions`)
- ✅ Defensive data normalization before JSON responses
- ⚠️ No authentication/authorization boundary on sensitive APIs
- ⚠️ No CSRF protection on state-changing routes
- ⚠️ File upload controls are minimal (extension/content limits not strongly enforced)
- ⚠️ Operational secrets are in source (`config.py`) and Flask secret is non-persistent random per restart

---

## 2) Runtime Architecture Walkthrough

## 2.1 App boot
1. `app.py` creates Flask app and loads `UPLOAD_FOLDER` from `helpers.py`.
2. `register_data_routes(app)` and `register_cdm_routes(app)` mount domain routes.
3. `init_db()` auto-creates/migrates schema at startup (table create + idempotent alters/indexes).

## 2.2 Request lifecycle
1. Browser requests server-rendered pages (`/data`, `/cdm`, `/student/:reg_no`, etc.).
2. Pages embed JSON payloads (`tojson`) for initial rendering.
3. Mutations happen through JSON/POST APIs from jQuery AJAX.
4. DB writes commit synchronously per request.
5. Certain writes invalidate analytics cache (`invalidate_analytics_cache`).

---

## 3) Database Walkthrough (How logic persists)

## 3.1 Core Data tables
- `students`: master student state
- `edit_log`: field-level student edit audit trail
- `student_files`: uploaded file metadata
- `upload_versions`, `version_snapshots`: upload versioning/snapshots
- `analytics_cache`: cached dashboard aggregates

## 3.2 CDM tables
- `companies`: company header
- `company_drives`: each drive under company
- `drive_courses`: per-drive allowed courses + drive_type
- `drive_students`: student participation + status/current_round
- `drive_rounds`: ordered rounds per drive
- `company_hr`: HR contacts
- `cdm_edit_log`: non-course drive field edits
- `course_presets`, `course_preset_items`: reusable course sets
- `drive_round_transitions`: append-only round/status transition audit

## 3.3 Integrity model
- Foreign keys with cascade are used for most child entities.
- Transition governance:
  - Final-round `Selected` is normalized to `Placed` in CDM mutation paths.
  - `Placed` sync bridge updates `/data` `students` row (status + placement metadata).
  - Transition events are appended to `drive_round_transitions` (`single_update`, `bulk_update`, `round_deleted`).

---

## 4) API Walkthrough (How each module works)

## 4.1 Platform routes (`app.py`)
- `/` redirect to dashboard
- `/upload` Excel intake + upsert + version snapshot
- `/download-template/student`, `/download-template/cdm`
- `/dashboard` analytics page
- `/drop-all`, `/drop-cdm` destructive maintenance operations
- `/logs`, `/versions/:id`, `/api/version/:id`, `/delete-version/:id`

## 4.2 Data routes (`routes_data.py`)
- `/data`: table + analytics bootstrap
- `PUT /api/student/:reg_no`: single inline edit + `edit_log`
- `PUT /api/student/:reg_no/bulk-update`: multi-field edit + `edit_log`
- `DELETE /api/student/:reg_no`: delete student
- `/student/:reg_no`: profile page
- `POST /student/:reg_no/upload-file`: attachment upload + `student_files`
- `/uploads/:filename`: serve uploaded file
- `POST /student/:reg_no/delete-file/:file_id`: remove file record + disk file
- `/api/edit-log`, `/api/students`, `/api/search`

## 4.3 CDM routes (`routes_cdm.py`)
- `/cdm`: CDM shell page (drives/calendar/mini stats tabs)
- `/cdm/company/:company_id`: company-drive detail workspace
- Company/drive CRUD APIs
- HR CRUD APIs
- Round CRUD + normalization on round delete
- Student link/unlink/update/bulk-round-update APIs
- `GET /api/cdm/drive/:id/round-transitions`: transition audit feed
- Calendar endpoint: `GET /api/cdm/calendar`
- SLA endpoint: `GET /api/cdm/alerts`
- Exports: `GET /api/cdm/drive/:id/export.xlsx`, `.../export.pdf`
- Presets and search endpoints

---

## 5) Security Controls Currently Present

## 5.1 Good controls
1. **Parameterized SQL**: dynamic values passed via placeholders in most queries.
2. **Input validation**:
   - numeric coercion for CTC/backlogs/percent fields
   - basic email/mobile checks in Data inline edits
3. **Audit trails**:
   - `edit_log` (Data)
   - `cdm_edit_log` (CDM drive edits)
   - `drive_round_transitions` (progression/status)
4. **State normalization**:
   - round bounds and normalization on deletion
   - final-round placement normalization
5. **JSON normalization** to avoid Decimal/date serialization issues.

## 5.2 Gaps / risks

### Critical
1. **No authentication / authorization**
   - All mutation endpoints are callable without user identity checks.
   - Any user with network access can mutate records or trigger destructive routes.

### High
2. **No CSRF protection**
   - Browser-based authenticated sessions (if introduced later) will be CSRF-vulnerable.
   - Current POST/PUT/DELETE forms and AJAX routes do not require CSRF tokens.

3. **Hardcoded DB credentials in source**
   - `config.py` includes plain credentials.
   - Risk: leakage via repo sharing/backups.

4. **Destructive maintenance endpoints exposed**
   - `/drop-all`, `/drop-cdm` are sensitive and should be admin-only + strongly gated.

### Medium
5. **File upload hardening incomplete**
   - Student file upload stores original extension; no strict MIME validation.
   - No explicit max file size enforcement and no malware scanning.

6. **Potential unbounded query parameters**
   - `limit`/`page` style params should be clamped globally to prevent heavy queries.

7. **Inconsistent secret handling**
   - `SECRET_KEY = os.urandom(24)` changes each restart; session continuity breaks and deployment behavior is non-deterministic.

### Low
8. **Error detail exposure**
   - Some APIs return raw DB exception strings to clients.

---

## 6) Calendar & SLA Logic Notes (Current Behavior)

1. Calendar data source: `/api/cdm/calendar` emits events from drives with non-null `process_date`.
2. Frontend month/week/day views match events by date key.
3. SLA source: `/api/cdm/alerts` computes stale/overdue/missing flags by drive.

**Recent hardening included:**
- Added backend `process_date_key` in calendar API response for robust plotting.
- Frontend now normalizes date variants (`YYYY-MM-DD`, ISO datetime, etc.) before matching.
- SLA alerts rendered within Mini Stats tab as requested.

---

## 7) Recommended Remediation Plan

## Phase 1 (Immediate)
1. Add authentication + role-based authorization middleware.
2. Protect all state-changing endpoints; restrict destructive admin routes.
3. Add CSRF tokens for form and AJAX mutations.
4. Move DB creds and Flask secret to environment variables.

## Phase 2 (Short-term)
5. Add request validation schemas (Marshmallow/Pydantic) for mutation payloads.
6. Add upload restrictions:
   - allowlist extensions + MIME sniffing
   - max file size
   - safe filename policy and optional malware scan hook
7. Replace raw error messages with generic client-safe responses + server-side logging.

## Phase 3 (Operational)
8. Add rate limiting (Flask-Limiter) for search and mutation endpoints.
9. Add structured security logs (actor, endpoint, payload hash, result).
10. Add scheduled integrity checks (CDM↔Data placement consistency reports).

---

## 8) Full Functional Walkthrough Checklist (for review)

Use this for manual review/UAT:

1. **Upload MIS** → verify insert/update counts + version snapshot creation.
2. **Inline Data edit** → verify `edit_log` row and analytics invalidation.
3. **Student file upload/delete** → verify both DB metadata and disk file behavior.
4. **Create company + drive** → verify `companies`, `company_drives`, `drive_courses`.
5. **Link student to drive** → verify `drive_students` row.
6. **Add rounds** → verify `drive_rounds` order sequence.
7. **Promote to final** with `Selected` input → verify CDM status resolves to `Placed`.
8. **Cross-sync check** → verify `/data` `students.status` becomes `Placed`.
9. **Transition logs check** → verify `drive_round_transitions` append-only entries.
10. **Delete round** → verify round normalization + `round_deleted` transition entries.
11. **Calendar view** → verify all non-null process-date drives render in month/week/day.
12. **Mini stats SLA** → verify alerts list and counts load in Mini Stats tab.
13. **Export XLSX/PDF** → verify downloads and content format.

---

## 9) Final Assessment

The system has strong functional depth, good mutation auditability, and practical data integrity bridges between CDM and Data modules. The primary security risk is **missing access control and CSRF defenses**, not core business logic correctness. Once authn/authz + CSRF + secret management are implemented, this can move to a much stronger production-ready posture.
