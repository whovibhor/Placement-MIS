# helpers.py — Shared constants, utilities, DB helpers, analytics
import json
import os
import re
import statistics
from datetime import datetime, date, timedelta
from decimal import Decimal

import mysql.connector
from mysql.connector import Error

import config


# ── File upload config ───────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Excel headers (exact order & spelling expected in uploaded file) ──────────
EXPECTED_HEADERS = [
    "Sr No",
    "Registration Number",
    "Student Name",
    "Gender",
    "Course",
    "Resume Status",
    "Seeking Placement",
    "Department",
    "Offer Letters Status",
    "Status",
    "Company Name",
    "Designation",
    "CTC",
    "Joining Date",
    "Joining Status",
    "School Name",
    "Mobile Number",
    "Email ID",
    "Graduation Course",
    "Graduation/OGPA",
    "10%",
    "12%",
    "No of Backlogs",
    "Hometown",
    "Address",
    "Reason",
]

# Mapping: Excel header → DB column
HEADER_TO_COL = {
    "Sr No": "sr_no",
    "Registration Number": "reg_no",
    "Student Name": "student_name",
    "Gender": "gender",
    "Course": "course",
    "Resume Status": "resume_status",
    "Seeking Placement": "seeking_placement",
    "Department": "department",
    "Offer Letters Status": "offer_letter_status",
    "Status": "status",
    "Company Name": "company_name",
    "Designation": "designation",
    "CTC": "ctc",
    "Joining Date": "joining_date",
    "Joining Status": "joining_status",
    "School Name": "school_name",
    "Mobile Number": "mobile_number",
    "Email ID": "email",
    "Graduation Course": "graduation_course",
    "Graduation/OGPA": "graduation_ogpa",
    "10%": "percent_10",
    "12%": "percent_12",
    "No of Backlogs": "backlogs",
    "Hometown": "hometown",
    "Address": "address",
    "Reason": "reason",
}

DB_COLUMNS = list(HEADER_TO_COL.values())

# Columns displayed in UI (school_name removed, priority ordered)
DISPLAY_COLUMNS = [
    'sr_no', 'reg_no', 'student_name', 'gender', 'course',
    'mobile_number', 'email', 'seeking_placement', 'department',
    'status', 'company_name', 'designation', 'ctc', 'placed_date',
    'graduation_ogpa', 'percent_10', 'percent_12', 'backlogs',
    'hometown', 'address', 'reason',
    'resume_status', 'offer_letter_status', 'joining_date', 'joining_status',
    'graduation_course',
]

# Columns that are editable via inline editing (placed_date is auto-managed)
EDITABLE_COLUMNS = set(DB_COLUMNS) - {"sr_no", "reg_no", "placed_date"}

# Numeric column sets for type conversion
NUMERIC_FLOAT_COLS = {"ctc", "percent_10", "percent_12", "graduation_ogpa"}
NUMERIC_INT_COLS = {"backlogs"}


def to_float_or_none(v):
    """Convert a value to float or return None."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def to_int_or_none(v):
    """Convert a value to int (via float for '1.0' style) or return None."""
    if v is None:
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def normalize_row(row):
    """Convert Decimal values to float, date to str for JSON serialization."""
    if row is None:
        return None
    for k, v in row.items():
        if isinstance(v, Decimal):
            row[k] = float(v)
        elif isinstance(v, (date, datetime)):
            row[k] = v.strftime("%Y-%m-%d") if isinstance(v, date) else v.strftime("%Y-%m-%d %H:%M:%S")
    return row


def normalize_rows(rows):
    """Convert Decimal values in all rows to float."""
    for row in rows:
        normalize_row(row)
    return rows


# ── Database helpers ─────────────────────────────────────────────────────────
def get_connection():
    """Return a MySQL connection using credentials from config.py."""
    return mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        collation="utf8mb4_general_ci",
    )


def init_db():
    """Create the database and required tables if they don't exist."""
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        collation="utf8mb4_general_ci",
    )
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
    )
    cursor.execute(f"USE `{config.DB_NAME}`")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            sr_no              INT,
            reg_no             VARCHAR(50) PRIMARY KEY,
            student_name       VARCHAR(200),
            gender             VARCHAR(20),
            course             VARCHAR(100),
            resume_status      VARCHAR(100),
            seeking_placement  VARCHAR(100),
            department         VARCHAR(100),
            offer_letter_status VARCHAR(100),
            status             VARCHAR(100),
            company_name       VARCHAR(200),
            designation        VARCHAR(200),
            ctc                VARCHAR(100),
            joining_date       VARCHAR(100),
            joining_status     VARCHAR(100),
            school_name        VARCHAR(200),
            mobile_number      VARCHAR(50),
            email              VARCHAR(200),
            graduation_course  VARCHAR(100),
            graduation_ogpa    VARCHAR(50),
            percent_10         VARCHAR(50),
            percent_12         VARCHAR(50),
            backlogs           VARCHAR(50),
            hometown           VARCHAR(200),
            address            TEXT,
            reason             TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_versions (
            version_id     INT AUTO_INCREMENT PRIMARY KEY,
            filename       VARCHAR(255),
            uploaded_at    DATETIME,
            total_records  INT DEFAULT 0,
            inserted       INT DEFAULT 0,
            updated        INT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS version_snapshots (
            id                 INT AUTO_INCREMENT PRIMARY KEY,
            version_id         INT,
            sr_no              INT,
            reg_no             VARCHAR(50),
            student_name       VARCHAR(200),
            gender             VARCHAR(20),
            course             VARCHAR(100),
            resume_status      VARCHAR(100),
            seeking_placement  VARCHAR(100),
            department         VARCHAR(100),
            offer_letter_status VARCHAR(100),
            status             VARCHAR(100),
            company_name       VARCHAR(200),
            designation        VARCHAR(200),
            ctc                VARCHAR(100),
            joining_date       VARCHAR(100),
            joining_status     VARCHAR(100),
            school_name        VARCHAR(200),
            mobile_number      VARCHAR(50),
            email              VARCHAR(200),
            graduation_course  VARCHAR(100),
            graduation_ogpa    VARCHAR(50),
            percent_10         VARCHAR(50),
            percent_12         VARCHAR(50),
            backlogs           VARCHAR(50),
            hometown           VARCHAR(200),
            address            TEXT,
            reason             TEXT,
            FOREIGN KEY (version_id) REFERENCES upload_versions(version_id)
                ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_files (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            reg_no         VARCHAR(50),
            file_type      VARCHAR(50),
            original_name  VARCHAR(255),
            stored_name    VARCHAR(255),
            uploaded_at    DATETIME,
            FOREIGN KEY (reg_no) REFERENCES students(reg_no)
                ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edit_log (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            reg_no         VARCHAR(50),
            student_name   VARCHAR(200),
            field_name     VARCHAR(100),
            old_value      TEXT,
            new_value      TEXT,
            changed_at     DATETIME,
            INDEX idx_reg (reg_no),
            INDEX idx_time (changed_at)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cdm_edit_log (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            drive_id       INT,
            company_name   VARCHAR(200),
            field_name     VARCHAR(100),
            old_value      TEXT,
            new_value      TEXT,
            changed_at     DATETIME,
            INDEX idx_drive (drive_id),
            INDEX idx_cdm_time (changed_at)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_cache (
            id          INT PRIMARY KEY,
            data        JSON,
            updated_at  DATETIME
        )
    """)
    cursor.execute("INSERT IGNORE INTO analytics_cache (id, data, updated_at) VALUES (1, NULL, NOW())")
    conn.commit()

    # ── Add content_hash column to upload_versions (idempotent) ──────
    try:
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'upload_versions' AND COLUMN_NAME = 'content_hash'",
            (config.DB_NAME,)
        )
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE upload_versions ADD COLUMN content_hash VARCHAR(32) NULL")
            conn.commit()
    except Error:
        pass

    # ── Migrate numeric columns (safe, idempotent) ───────────────────
    try:
        cursor.execute(
            "SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'students' AND COLUMN_NAME = 'ctc'",
            (config.DB_NAME,)
        )
        col_info = cursor.fetchone()
        if col_info and col_info[0].upper() in ('VARCHAR', 'CHAR', 'TEXT'):
            for stmt in [
                "UPDATE students SET ctc = NULL WHERE ctc IS NOT NULL AND TRIM(ctc) NOT REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$'",
                "UPDATE students SET percent_10 = NULL WHERE percent_10 IS NOT NULL AND TRIM(percent_10) NOT REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$'",
                "UPDATE students SET percent_12 = NULL WHERE percent_12 IS NOT NULL AND TRIM(percent_12) NOT REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$'",
                "UPDATE students SET graduation_ogpa = NULL WHERE graduation_ogpa IS NOT NULL AND TRIM(graduation_ogpa) NOT REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$'",
                "UPDATE students SET backlogs = NULL WHERE backlogs IS NOT NULL AND TRIM(backlogs) NOT REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$'",
            ]:
                try:
                    cursor.execute(stmt)
                except Error:
                    pass
            conn.commit()

            for stmt in [
                "ALTER TABLE students MODIFY ctc DECIMAL(10,2) NULL",
                "ALTER TABLE students MODIFY percent_10 DECIMAL(5,2) NULL",
                "ALTER TABLE students MODIFY percent_12 DECIMAL(5,2) NULL",
                "ALTER TABLE students MODIFY graduation_ogpa DECIMAL(4,2) NULL",
                "ALTER TABLE students MODIFY backlogs INT NULL",
            ]:
                try:
                    cursor.execute(stmt)
                except Error:
                    pass
            conn.commit()
    except Error:
        pass

    # ── Add indexes (idempotent) ─────────────────────────────────────
    for stmt in [
        "CREATE INDEX idx_status ON students(status)",
        "CREATE INDEX idx_seeking ON students(seeking_placement)",
        "CREATE INDEX idx_course ON students(course)",
        "CREATE INDEX idx_department ON students(department)",
    ]:
        try:
            cursor.execute(stmt)
        except Error:
            pass

    # ── Add placed_date column to students (idempotent) ────────────────
    try:
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'students' AND COLUMN_NAME = 'placed_date'",
            (config.DB_NAME,)
        )
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE students ADD COLUMN placed_date DATE NULL AFTER status")
            cursor.execute(
                "UPDATE students s "
                "LEFT JOIN (SELECT reg_no, MIN(changed_at) AS first_placed "
                "  FROM edit_log WHERE field_name = 'status' AND new_value = 'Placed' "
                "  GROUP BY reg_no) e ON s.reg_no = e.reg_no "
                "SET s.placed_date = COALESCE(DATE(e.first_placed), CURDATE()) "
                "WHERE s.status = 'Placed' AND s.placed_date IS NULL"
            )
            conn.commit()
    except Error:
        pass

    try:
        cursor.execute("CREATE INDEX idx_placed_date ON students(placed_date)")
    except Error:
        pass

    # ── CDM tables ───────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id   VARCHAR(10) PRIMARY KEY,
            company_name VARCHAR(200) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_drives (
            drive_id          INT AUTO_INCREMENT PRIMARY KEY,
            company_id        VARCHAR(10),
            role              VARCHAR(200),
            ctc_text          VARCHAR(100),
            jd_received_date  DATE,
            process_date      DATE,
            data_shared       BOOLEAN,
            process_mode      VARCHAR(50),
            location          VARCHAR(200),
            received_by       VARCHAR(200),
            notes             TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drive_courses (
            drive_id    INT,
            course_name VARCHAR(100),
            PRIMARY KEY (drive_id, course_name),
            FOREIGN KEY (drive_id) REFERENCES company_drives(drive_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_hr (
            hr_id       INT AUTO_INCREMENT PRIMARY KEY,
            company_id  VARCHAR(10),
            name        VARCHAR(200),
            designation VARCHAR(200),
            email       VARCHAR(200),
            phone       VARCHAR(50),
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drive_rounds (
            round_id    INT AUTO_INCREMENT PRIMARY KEY,
            drive_id    INT,
            round_name  VARCHAR(100),
            round_order INT,
            FOREIGN KEY (drive_id) REFERENCES company_drives(drive_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drive_students (
            drive_id INT,
            reg_no   VARCHAR(50),
            status   VARCHAR(50),
            PRIMARY KEY (drive_id, reg_no),
            FOREIGN KEY (drive_id) REFERENCES company_drives(drive_id) ON DELETE CASCADE,
            FOREIGN KEY (reg_no) REFERENCES students(reg_no) ON DELETE CASCADE
        )
    """)
    try:
        cursor.execute("CREATE INDEX idx_drive_company ON company_drives(company_id)")
    except Error:
        pass

    # ── Add status column to company_drives (idempotent) ─────────
    try:
        cursor.execute("ALTER TABLE company_drives ADD COLUMN status VARCHAR(50) DEFAULT 'Upcoming'")
    except Error:
        pass

    # ── Add round_date to drive_rounds (idempotent) ──────────────
    try:
        cursor.execute("ALTER TABLE drive_rounds ADD COLUMN round_date DATE")
    except Error:
        pass

    # ── Add current_round to drive_students (idempotent) ─────────
    try:
        cursor.execute("ALTER TABLE drive_students ADD COLUMN current_round INT")
    except Error:
        pass

    # ── Add drive_type to companies (idempotent) ─────────────────
    try:
        cursor.execute("ALTER TABLE companies ADD COLUMN drive_type VARCHAR(50) DEFAULT NULL")
    except Error:
        pass

    # ── Company-level course and department linking ──────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_courses (
            company_id  VARCHAR(10),
            course_name VARCHAR(100),
            drive_type  VARCHAR(50) DEFAULT NULL,
            PRIMARY KEY (company_id, course_name),
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    """)
    # Migration: add drive_type column if table already exists without it
    try:
        cursor.execute("ALTER TABLE company_courses ADD COLUMN drive_type VARCHAR(50) DEFAULT NULL")
    except Error:
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_departments (
            company_id      VARCHAR(10),
            department_name VARCHAR(100),
            PRIMARY KEY (company_id, department_name),
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    """)

    # ── Course presets for quick selection ────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_presets (
            preset_id   INT AUTO_INCREMENT PRIMARY KEY,
            preset_name VARCHAR(100) NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_preset_items (
            preset_id   INT,
            course_name VARCHAR(100),
            PRIMARY KEY (preset_id, course_name),
            FOREIGN KEY (preset_id) REFERENCES course_presets(preset_id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


# ── Analytics cache helpers ──────────────────────────────────────────────────
def get_cached_analytics():
    """Return cached analytics dict, or None if cache is empty/stale."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT data FROM analytics_cache WHERE id = 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row["data"]:
            d = row["data"]
            return json.loads(d) if isinstance(d, str) else d
    except Error:
        pass
    return None


def save_analytics_cache(analytics):
    """Save a precomputed analytics dict to cache."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE analytics_cache SET data = %s, updated_at = NOW() WHERE id = 1",
            (json.dumps(analytics),),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Error:
        pass


def invalidate_analytics_cache():
    """Mark analytics cache as stale so next request recomputes."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE analytics_cache SET data = NULL, updated_at = NOW() WHERE id = 1")
        conn.commit()
        cursor.close()
        conn.close()
    except Error:
        pass


# ── Analytics computation ────────────────────────────────────────────────────
def compute_analytics(rows):
    """Compute all analytics from a list of student dicts."""
    total = len(rows)
    opted_in = sum(1 for r in rows if r.get("seeking_placement") == "Opted In")
    opted_out = sum(1 for r in rows if r.get("seeking_placement") == "Opted Out")
    not_registered = sum(1 for r in rows if r.get("seeking_placement") == "Not Registered")
    debarred = sum(1 for r in rows if r.get("seeking_placement") == "Debarred")
    placed = sum(1 for r in rows if r.get("status") == "Placed")

    def is_eligible(r):
        if r.get("seeking_placement") != "Opted In":
            return False
        try:
            return float(r.get("backlogs") or 0) < 3
        except (ValueError, TypeError):
            return True

    eligible = sum(1 for r in rows if is_eligible(r))
    ineligible = opted_in - eligible
    placement_rate = round((placed / eligible * 100), 1) if eligible else 0

    ctc_values = []
    for r in rows:
        if r.get("status") == "Placed" and r.get("ctc"):
            try:
                ctc_values.append(float(r["ctc"]))
            except (ValueError, TypeError):
                pass

    avg_ctc = round(sum(ctc_values) / len(ctc_values), 2) if ctc_values else 0
    median_ctc = round(statistics.median(ctc_values), 2) if ctc_values else 0
    max_ctc = max(ctc_values) if ctc_values else 0
    min_ctc = min(ctc_values) if ctc_values else 0

    dept_stats = {}
    for r in rows:
        dept = r.get("department") or "Unknown"
        if dept not in dept_stats:
            dept_stats[dept] = {"total": 0, "placed": 0, "eligible": 0}
        dept_stats[dept]["total"] += 1
        if r.get("status") == "Placed":
            dept_stats[dept]["placed"] += 1
        if is_eligible(r):
            dept_stats[dept]["eligible"] += 1
    dept_sorted = sorted(dept_stats.items(), key=lambda x: x[1]["placed"], reverse=True)
    dept_labels = [d[0] for d in dept_sorted]
    dept_placed = [d[1]["placed"] for d in dept_sorted]
    dept_total = [d[1]["total"] for d in dept_sorted]
    dept_eligible = [d[1]["eligible"] for d in dept_sorted]

    company_counts = {}
    for r in rows:
        if r.get("status") == "Placed" and r.get("company_name"):
            c = r["company_name"]
            company_counts[c] = company_counts.get(c, 0) + 1
    top_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    company_labels = [c[0] for c in top_companies]
    company_values = [c[1] for c in top_companies]

    gender_counts = {}
    for r in rows:
        g = r.get("gender") or "Not Specified"
        gender_counts[g] = gender_counts.get(g, 0) + 1

    gender_placement = {}
    for r in rows:
        g = r.get("gender") or "Not Specified"
        if g not in gender_placement:
            gender_placement[g] = {"total": 0, "placed": 0}
        gender_placement[g]["total"] += 1
        if r.get("status") == "Placed":
            gender_placement[g]["placed"] += 1

    top_company = top_companies[0][0] if top_companies else "N/A"
    unplaced_opted_in = sum(1 for r in rows if r.get("seeking_placement") == "Opted In" and r.get("status") != "Placed")

    ctc_ranges = [
        ("0-2", 0, 2), ("2-4", 2, 4), ("4-6", 4, 6), ("6-8", 6, 8),
        ("8-10", 8, 10), ("10-12", 10, 12), ("12-14", 12, 14), ("14+", 14, 9999),
    ]
    ctc_dist_labels = [r[0] + " LPA" for r in ctc_ranges]
    ctc_dist_values = [0] * len(ctc_ranges)
    for v in ctc_values:
        for i, (_, lo, hi) in enumerate(ctc_ranges):
            if lo <= v < hi:
                ctc_dist_values[i] += 1
                break

    dept_course_breakdown = {}
    for r in rows:
        dept = r.get("department") or "Unknown"
        course = r.get("course") or "Unknown"
        if dept not in dept_course_breakdown:
            dept_course_breakdown[dept] = {}
        if course not in dept_course_breakdown[dept]:
            dept_course_breakdown[dept][course] = {"total": 0, "placed": 0, "eligible": 0}
        dept_course_breakdown[dept][course]["total"] += 1
        if r.get("status") == "Placed":
            dept_course_breakdown[dept][course]["placed"] += 1
        if is_eligible(r):
            dept_course_breakdown[dept][course]["eligible"] += 1

    course_agg = {}
    for r in rows:
        course = r.get("course") or "Unknown"
        if course not in course_agg:
            course_agg[course] = {
                "department": r.get("department") or "Unknown",
                "total": 0, "seeking": 0, "eligible": 0,
                "ineligible_backlogs": 0, "has_backlogs": 0,
                "deemed_placed": 0, "placed": 0,
                "ctc_values": [],
            }
        agg = course_agg[course]
        agg["total"] += 1
        if r.get("seeking_placement") == "Opted In":
            agg["seeking"] += 1
        if is_eligible(r):
            agg["eligible"] += 1
        if r.get("seeking_placement") == "Opted In":
            try:
                bl = float(r.get("backlogs") or 0)
                if bl >= 3:
                    agg["ineligible_backlogs"] += 1
            except (ValueError, TypeError):
                pass
        try:
            bl = float(r.get("backlogs") or 0)
            if bl > 0:
                agg["has_backlogs"] += 1
        except (ValueError, TypeError):
            pass
        if r.get("status") == "Deemed Placed":
            agg["deemed_placed"] += 1
        if r.get("status") == "Placed":
            agg["placed"] += 1
            if r.get("ctc"):
                try:
                    agg["ctc_values"].append(float(r["ctc"]))
                except (ValueError, TypeError):
                    pass

    course_summary = []
    for course, agg in sorted(course_agg.items(), key=lambda x: x[1]["department"]):
        not_seeking = agg["total"] - agg["seeking"]
        gap_pct = round((agg["seeking"] - agg["eligible"]) / agg["seeking"] * 100, 1) if agg["seeking"] > 0 else 0
        unplaced = max(0, agg["eligible"] - agg["placed"] - agg["deemed_placed"])
        pending = unplaced
        achieved_pct = round(agg["placed"] / agg["eligible"] * 100, 1) if agg["eligible"] > 0 else 0
        avg_ctc_course = round(sum(agg["ctc_values"]) / len(agg["ctc_values"]), 2) if agg["ctc_values"] else 0
        course_summary.append({
            "department": agg["department"],
            "stream": course,
            "total": agg["total"],
            "seeking": agg["seeking"],
            "not_seeking": not_seeking,
            "eligible": agg["eligible"],
            "ineligible_backlogs": agg["ineligible_backlogs"],
            "gap_pct": gap_pct,
            "backlogs": agg["has_backlogs"],
            "deemed_placed": agg["deemed_placed"],
            "placed": agg["placed"],
            "unplaced": unplaced,
            "pending": pending,
            "target_pct": 100,
            "achieved_pct": achieved_pct,
            "avg_ctc": avg_ctc_course,
        })

    dept_agg = {}
    for r in rows:
        dept = r.get("department") or "Unknown"
        if dept not in dept_agg:
            dept_agg[dept] = {
                "total": 0, "opted_in": 0, "placed": 0,
                "ctc_values": [], "companies": set(),
            }
        da = dept_agg[dept]
        da["total"] += 1
        if r.get("seeking_placement") == "Opted In":
            da["opted_in"] += 1
        if r.get("status") == "Placed":
            da["placed"] += 1
            if r.get("ctc"):
                try:
                    da["ctc_values"].append(float(r["ctc"]))
                except (ValueError, TypeError):
                    pass
            if r.get("company_name"):
                da["companies"].add(r["company_name"])

    dept_summary = []
    sr = 1
    for dept, da in sorted(dept_agg.items()):
        placed_pct = round(da["placed"] / da["opted_in"] * 100, 1) if da["opted_in"] > 0 else 0
        highest = max(da["ctc_values"]) if da["ctc_values"] else 0
        avg_c = round(sum(da["ctc_values"]) / len(da["ctc_values"]), 2) if da["ctc_values"] else 0
        med_c = round(statistics.median(da["ctc_values"]), 2) if da["ctc_values"] else 0
        companies_list = sorted(da["companies"])
        dept_summary.append({
            "sr_no": sr,
            "school_name": dept,
            "total": da["total"],
            "opted_in": da["opted_in"],
            "placed": da["placed"],
            "placed_pct": placed_pct,
            "highest_ctc": highest,
            "avg_ctc": avg_c,
            "median_ctc": med_c,
            "unique_companies_count": len(companies_list),
            "unique_companies": ", ".join(companies_list),
        })
        sr += 1

    placement_dates = []
    for r in rows:
        if r.get("status") == "Placed" and r.get("placed_date"):
            pd_val = r["placed_date"]
            try:
                if isinstance(pd_val, str):
                    pd_val = datetime.strptime(pd_val, "%Y-%m-%d").date()
                elif isinstance(pd_val, datetime):
                    pd_val = pd_val.date()
                placement_dates.append(pd_val)
            except (ValueError, TypeError):
                pass

    placement_dates.sort()

    trend_daily_labels = []
    trend_daily_values = []
    if placement_dates:
        first_date = placement_dates[0]
        last_date = placement_dates[-1]
        day = first_date
        cumulative = 0
        date_counts = {}
        for d in placement_dates:
            date_counts[d] = date_counts.get(d, 0) + 1
        while day <= last_date:
            cumulative += date_counts.get(day, 0)
            trend_daily_labels.append(day.strftime("%Y-%m-%d"))
            trend_daily_values.append(cumulative)
            day += timedelta(days=1)

    trend_weekly_labels = []
    trend_weekly_values = []
    if placement_dates:
        week_counts = {}
        for d in placement_dates:
            iso = d.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            week_counts[wk_key] = week_counts.get(wk_key, 0) + 1
        first_date = placement_dates[0]
        last_date = placement_dates[-1]
        day = first_date
        seen_weeks = {}
        while day <= last_date:
            iso = day.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            if wk_key not in seen_weeks:
                seen_weeks[wk_key] = day
            day += timedelta(days=1)
        cumulative = 0
        for wk_key in sorted(seen_weeks.keys()):
            cumulative += week_counts.get(wk_key, 0)
            trend_weekly_labels.append(wk_key)
            trend_weekly_values.append(cumulative)

    trend_monthly_labels = []
    trend_monthly_values = []
    if placement_dates:
        month_counts = {}
        for d in placement_dates:
            mk = d.strftime("%Y-%m")
            month_counts[mk] = month_counts.get(mk, 0) + 1
        first_month = placement_dates[0].strftime("%Y-%m")
        last_month = placement_dates[-1].strftime("%Y-%m")
        ym = first_month
        cumulative = 0
        while ym <= last_month:
            cumulative += month_counts.get(ym, 0)
            trend_monthly_labels.append(ym)
            trend_monthly_values.append(cumulative)
            y, m = int(ym[:4]), int(ym[5:7])
            m += 1
            if m > 12:
                m = 1
                y += 1
            ym = f"{y}-{m:02d}"

    trend_daily_new = []
    if placement_dates:
        date_counts = {}
        for d in placement_dates:
            date_counts[d] = date_counts.get(d, 0) + 1
        first_date = placement_dates[0]
        last_date = placement_dates[-1]
        day = first_date
        while day <= last_date:
            trend_daily_new.append(date_counts.get(day, 0))
            day += timedelta(days=1)

    trend_weekly_new = []
    if placement_dates:
        week_counts = {}
        for d in placement_dates:
            iso = d.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            week_counts[wk_key] = week_counts.get(wk_key, 0) + 1
        for wk in trend_weekly_labels:
            trend_weekly_new.append(week_counts.get(wk, 0))

    trend_monthly_new = []
    if placement_dates:
        month_counts = {}
        for d in placement_dates:
            mk = d.strftime("%Y-%m")
            month_counts[mk] = month_counts.get(mk, 0) + 1
        for mk in trend_monthly_labels:
            trend_monthly_new.append(month_counts.get(mk, 0))

    return {
        "total": total,
        "opted_in": opted_in,
        "opted_out": opted_out,
        "not_registered": not_registered,
        "debarred": debarred,
        "eligible": eligible,
        "ineligible": ineligible,
        "placed": placed,
        "unplaced": unplaced_opted_in,
        "placement_rate": placement_rate,
        "avg_ctc": avg_ctc,
        "median_ctc": median_ctc,
        "max_ctc": max_ctc,
        "min_ctc": min_ctc,
        "top_company": top_company,
        "dept_labels": dept_labels,
        "dept_placed": dept_placed,
        "dept_total": dept_total,
        "dept_eligible": dept_eligible,
        "company_labels": company_labels,
        "company_values": company_values,
        "gender_counts": gender_counts,
        "gender_placement": gender_placement,
        "ctc_dist_labels": ctc_dist_labels,
        "ctc_dist_values": ctc_dist_values,
        "dept_course_breakdown": dept_course_breakdown,
        "course_summary": course_summary,
        "dept_summary": dept_summary,
        "trend_daily_labels": trend_daily_labels,
        "trend_daily_values": trend_daily_values,
        "trend_daily_new": trend_daily_new,
        "trend_weekly_labels": trend_weekly_labels,
        "trend_weekly_values": trend_weekly_values,
        "trend_weekly_new": trend_weekly_new,
        "trend_monthly_labels": trend_monthly_labels,
        "trend_monthly_values": trend_monthly_values,
        "trend_monthly_new": trend_monthly_new,
    }
