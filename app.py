from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, timedelta
from decimal import Decimal
import statistics
import os
import uuid
import re
import json
import hashlib
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ── File upload config ───────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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
    # Student files table (for resumes, offer letters, etc.)
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
    # Change log table — tracks every individual field edit
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

    # Analytics cache table
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
            # Clean non-numeric values before type change
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

            # Alter to proper numeric types
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
            # Backfill: use edit_log date when status was changed to Placed
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

    # ── Add index on placed_date (idempotent) ────────────────────────
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
    # Future-ready tables
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
    # Index on company_drives.company_id
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


# ── Analytics helper ─────────────────────────────────────────────────────────
def compute_analytics(rows):
    """Compute all analytics from a list of student dicts."""
    total = len(rows)
    opted_in = sum(1 for r in rows if r.get("seeking_placement") == "Opted In")
    opted_out = sum(1 for r in rows if r.get("seeking_placement") == "Opted Out")
    not_registered = sum(1 for r in rows if r.get("seeking_placement") == "Not Registered")
    debarred = sum(1 for r in rows if r.get("seeking_placement") == "Debarred")
    placed = sum(1 for r in rows if r.get("status") == "Placed")

    # Eligible = Opted In + backlogs < 3
    def is_eligible(r):
        if r.get("seeking_placement") != "Opted In":
            return False
        try:
            return float(r.get("backlogs") or 0) < 3
        except (ValueError, TypeError):
            return True  # If backlogs is not a number, assume eligible

    eligible = sum(1 for r in rows if is_eligible(r))
    ineligible = opted_in - eligible

    # Placement rate = Placed / Eligible
    placement_rate = round((placed / eligible * 100), 1) if eligible else 0

    # CTC stats (from placed students with numeric CTC)
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

    # Department-wise
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

    # Top companies
    company_counts = {}
    for r in rows:
        if r.get("status") == "Placed" and r.get("company_name"):
            c = r["company_name"]
            company_counts[c] = company_counts.get(c, 0) + 1
    top_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    company_labels = [c[0] for c in top_companies]
    company_values = [c[1] for c in top_companies]

    # Gender split
    gender_counts = {}
    for r in rows:
        g = r.get("gender") or "Not Specified"
        gender_counts[g] = gender_counts.get(g, 0) + 1

    # Gender-wise placement
    gender_placement = {}
    for r in rows:
        g = r.get("gender") or "Not Specified"
        if g not in gender_placement:
            gender_placement[g] = {"total": 0, "placed": 0}
        gender_placement[g]["total"] += 1
        if r.get("status") == "Placed":
            gender_placement[g]["placed"] += 1

    top_company = top_companies[0][0] if top_companies else "N/A"

    # Quick-view counts
    unplaced_opted_in = sum(1 for r in rows if r.get("seeking_placement") == "Opted In" and r.get("status") != "Placed")

    # CTC distribution histogram (for chart)
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

    # Department → Course breakdown (nested)
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

    # ── Course Summary (per-stream aggregation) ──────────────────────────
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
        # Opted In but has backlogs >= 3 (ineligible due to backlogs)
        if r.get("seeking_placement") == "Opted In":
            try:
                bl = float(r.get("backlogs") or 0)
                if bl >= 3:
                    agg["ineligible_backlogs"] += 1
            except (ValueError, TypeError):
                pass
        # Has any backlogs > 0
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

    # ── Department Summary (per-school aggregation) ──────────────────────
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

    # ── Placement Trend (daily → aggregate to weekly/monthly) ────────────
    # Collect all placed_date values
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

    # Sort dates
    placement_dates.sort()

    # Build daily cumulative data
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

    # Build weekly cumulative (ISO week)
    trend_weekly_labels = []
    trend_weekly_values = []
    if placement_dates:
        week_counts = {}
        for d in placement_dates:
            iso = d.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            week_counts[wk_key] = week_counts.get(wk_key, 0) + 1
        # Build sorted weeks from first to last
        first_date = placement_dates[0]
        last_date = placement_dates[-1]
        day = first_date
        seen_weeks = {}
        while day <= last_date:
            iso = day.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            if wk_key not in seen_weeks:
                seen_weeks[wk_key] = day  # Monday of that week
            day += timedelta(days=1)
        cumulative = 0
        for wk_key in sorted(seen_weeks.keys()):
            cumulative += week_counts.get(wk_key, 0)
            trend_weekly_labels.append(wk_key)
            trend_weekly_values.append(cumulative)

    # Build monthly cumulative
    trend_monthly_labels = []
    trend_monthly_values = []
    if placement_dates:
        month_counts = {}
        for d in placement_dates:
            mk = d.strftime("%Y-%m")
            month_counts[mk] = month_counts.get(mk, 0) + 1
        # Build sorted months
        first_month = placement_dates[0].strftime("%Y-%m")
        last_month = placement_dates[-1].strftime("%Y-%m")
        ym = first_month
        cumulative = 0
        while ym <= last_month:
            cumulative += month_counts.get(ym, 0)
            trend_monthly_labels.append(ym)
            trend_monthly_values.append(cumulative)
            # Next month
            y, m = int(ym[:4]), int(ym[5:7])
            m += 1
            if m > 12:
                m = 1
                y += 1
            ym = f"{y}-{m:02d}"

    # Per-day NEW placements (not cumulative — for bar chart)
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

    # Per-week NEW placements
    trend_weekly_new = []
    if placement_dates:
        week_counts = {}
        for d in placement_dates:
            iso = d.isocalendar()
            wk_key = f"{iso[0]}-W{iso[1]:02d}"
            week_counts[wk_key] = week_counts.get(wk_key, 0) + 1
        for wk in trend_weekly_labels:
            trend_weekly_new.append(week_counts.get(wk, 0))

    # Per-month NEW placements
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


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    # ── POST: process uploaded file ──────────────────────────────────────
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("upload"))

    if not file.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files are accepted.", "danger")
        return redirect(url_for("upload"))

    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        flash(f"Could not read Excel file: {e}", "danger")
        return redirect(url_for("upload"))

    # ── Normalise column names (strip whitespace) ──────────────────────
    HEADER_ALIASES = {"0.1": "10%", "0.12": "12%"}
    normalized = []
    for h in df.columns:
        s = str(h).strip()
        if s in HEADER_ALIASES:
            s = HEADER_ALIASES[s]
        normalized.append(s)
    df.columns = normalized

    # ── Validate headers ─────────────────────────────────────────────────
    file_headers = set(df.columns)
    missing = [h for h in EXPECTED_HEADERS if h not in file_headers]
    if missing:
        flash(
            f"Invalid template. Please upload correct MIS format. "
            f"Missing columns: {missing}",
            "danger",
        )
        return redirect(url_for("upload"))

    df = df[EXPECTED_HEADERS]
    df.rename(columns=HEADER_TO_COL, inplace=True)
    df = df.where(pd.notnull(df), None)
    # Force object dtype so None stays None (not numpy.nan)
    for col in DB_COLUMNS:
        df[col] = df[col].astype(object).where(df[col].notna(), None)

    df["sr_no"] = df["sr_no"].apply(to_int_or_none)

    def to_str_or_none(v):
        if v is None:
            return None
        s = str(v).strip()
        if s.lower() == "nan" or s == "":
            return None
        return s

    for col in DB_COLUMNS:
        if col == "sr_no":
            continue
        df[col] = df[col].apply(to_str_or_none)

    # ── Fix percent decimals on upload (0.6 → 60) ───────────────────────
    import re as _re
    for col in ["percent_10", "percent_12"]:
        def fix_pct(v):
            if v is None:
                return None
            # Strip GPA/CGPA prefix
            cleaned = _re.sub(r'^(C?GPA)\s*', '', v, flags=_re.IGNORECASE).strip()
            # Convert garbage like '__' to None
            if cleaned in ('__', '_', ''):
                return None
            try:
                num = float(cleaned)
                if 0 < num <= 1:
                    num = round(num * 100, 1)
                    cleaned = str(int(num)) if num == int(num) else str(num)
            except ValueError:
                pass
            return cleaned
        df[col] = df[col].apply(fix_pct)

    # ── Convert numeric columns to proper types ──────────────────────────
    for col in ["ctc", "percent_10", "percent_12", "graduation_ogpa"]:
        df[col] = df[col].apply(to_float_or_none)
    df["backlogs"] = df["backlogs"].apply(to_int_or_none)

    # ── Upsert into MySQL (batch) ────────────────────────────────────────
    inserted = 0
    updated = 0

    placeholders = ", ".join(["%s"] * len(DB_COLUMNS))
    cols_joined = ", ".join(DB_COLUMNS)
    update_clause = ", ".join(
        [f"{c} = VALUES({c})" for c in DB_COLUMNS if c != "reg_no"]
    )
    upsert_sql = (
        f"INSERT INTO students ({cols_joined}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch full existing data for accurate change detection
        cursor.execute("SELECT * FROM students")
        existing_rows = {row["reg_no"]: row for row in cursor.fetchall()}

        # Compare uploaded data against DB to find real changes
        values_list = []
        for _, row in df.iterrows():
            values = tuple(
                None if (v is not None and isinstance(v, float) and pd.isna(v)) else v
                for c in DB_COLUMNS for v in [row[c]]
            )
            values_list.append(values)
            reg = row["reg_no"]
            if reg not in existing_rows:
                inserted += 1
            else:
                # Field-by-field comparison for real updates
                db_row = existing_rows[reg]
                for col in DB_COLUMNS:
                    if col == "reg_no":
                        continue
                    new_val = row[col]
                    old_val = db_row.get(col)
                    # Normalize Decimal for comparison
                    if isinstance(old_val, Decimal):
                        old_val = float(old_val)
                    # Compare as strings to handle type mismatches
                    if str(new_val if new_val is not None else "") != str(old_val if old_val is not None else ""):
                        updated += 1
                        break

        # Always do the upsert (idempotent sync)
        cursor2 = conn.cursor()
        cursor2.executemany(upsert_sql, values_list)
        conn.commit()

        # Auto-set placed_date for newly placed students (via upload)
        now_date = datetime.now().strftime("%Y-%m-%d")
        for _, row in df.iterrows():
            reg = row["reg_no"]
            new_status = row.get("status")
            if new_status == "Placed":
                old_status = existing_rows.get(reg, {}).get("status") if reg in existing_rows else None
                if old_status != "Placed":
                    cursor2 = conn.cursor()
                    cursor2.execute(
                        "UPDATE students SET placed_date = %s WHERE reg_no = %s AND placed_date IS NULL",
                        (now_date, reg),
                    )
                    cursor2.close()
            elif reg in existing_rows and existing_rows[reg].get("status") == "Placed" and new_status != "Placed":
                # Student was un-placed, clear the date
                cursor2 = conn.cursor()
                cursor2.execute(
                    "UPDATE students SET placed_date = NULL WHERE reg_no = %s",
                    (reg,),
                )
                cursor2.close()
        conn.commit()

        cursor2 = conn.cursor()

        total = inserted + updated
        has_real_changes = (inserted + updated) > 0

        if has_real_changes:
            # ── Compute content hash ─────────────────────────────────────
            sorted_df = df.sort_values("reg_no").reset_index(drop=True)
            data_hash = hashlib.md5(
                sorted_df[DB_COLUMNS].to_csv(index=False).encode("utf-8")
            ).hexdigest()

            # ── Save version snapshot (batch) ────────────────────────────
            cursor3 = conn.cursor()
            cursor3.execute(
                "INSERT INTO upload_versions (filename, uploaded_at, total_records, inserted, updated, content_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (file.filename, datetime.now(), total, inserted, updated, data_hash),
            )
            version_id = cursor3.lastrowid

            snap_cols = ", ".join(DB_COLUMNS)
            snap_placeholders = ", ".join(["%s"] * (len(DB_COLUMNS) + 1))
            snap_sql = (
                f"INSERT INTO version_snapshots (version_id, {snap_cols}) "
                f"VALUES ({snap_placeholders})"
            )
            snap_values_list = []
            for _, row in df.iterrows():
                values = (version_id,) + tuple(
                    None if (v is not None and isinstance(v, float) and pd.isna(v)) else v
                    for c in DB_COLUMNS for v in [row[c]]
                )
                snap_values_list.append(values)
            cursor3.executemany(snap_sql, snap_values_list)

            conn.commit()
            cursor3.close()

            # Invalidate analytics cache after data change
            invalidate_analytics_cache()

            flash(
                f"Upload successful. {total} records processed, "
                f"{inserted} new, {updated} updated. Version #{version_id} created.",
                "success",
            )
        else:
            flash(
                f"No changes detected — uploaded data matches the current database. "
                f"No new version created.",
                "info",
            )

        cursor.close()
        conn.close()

    except Error as e:
        flash(f"Database error: {e}", "danger")

    return redirect(url_for("upload"))


@app.route("/dashboard")
def dashboard():
    try:
        analytics = get_cached_analytics()
        if not analytics:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM students ORDER BY sr_no")
            rows = cursor.fetchall()
            normalize_rows(rows)
            analytics = compute_analytics(rows)
            cursor.close()
            conn.close()
            save_analytics_cache(analytics)
    except Error:
        analytics = {}
    return render_template("dashboard.html", analytics=analytics)


@app.route("/data")
def data_page():
    """Data sheet page with table, quick-view tiles, inline editing."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students ORDER BY sr_no")
        rows = cursor.fetchall()
        normalize_rows(rows)
        analytics = get_cached_analytics()
        if not analytics:
            analytics = compute_analytics(rows)
            save_analytics_cache(analytics)
        cursor.close()
        conn.close()
    except Error:
        rows = []
        analytics = {}
    return render_template("data.html", students_json=rows, analytics=analytics)


# ── Inline Editing API ───────────────────────────────────────────────────────
@app.route("/api/student/<reg_no>", methods=["PUT"])
def update_student(reg_no):
    """Update a single field of a student record."""
    data = request.get_json()
    if not data or "field" not in data:
        return jsonify({"error": "Missing field"}), 400

    field = data["field"]
    value = data.get("value")

    # Security: only allow known editable columns
    if field not in EDITABLE_COLUMNS:
        return jsonify({"error": f"Field '{field}' is not editable"}), 400

    # Empty string → NULL
    if value is not None and str(value).strip() == "":
        value = None

    # ── Data Validation & Type Conversion ──────────────────────────────
    if value is not None:
        if field in NUMERIC_FLOAT_COLS:
            converted = to_float_or_none(value)
            if converted is None:
                return jsonify({"error": f"{field.replace('_',' ').title()} must be a numeric value"}), 400
            value = converted
        elif field in NUMERIC_INT_COLS:
            converted = to_int_or_none(value)
            if converted is None:
                return jsonify({"error": f"{field.replace('_',' ').title()} must be a whole number"}), 400
            value = converted
        elif field == "email":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', str(value)):
                return jsonify({"error": "Invalid email format"}), 400
        elif field == "mobile_number":
            if len(re.findall(r'\d', str(value))) < 10:
                return jsonify({"error": "Mobile number must have at least 10 digits"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch old value + student name for logging
        cursor.execute(
            f"SELECT `{field}`, student_name FROM students WHERE reg_no = %s",
            (reg_no,),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        old_value = row.get(field)
        if isinstance(old_value, Decimal):
            old_value = float(old_value)
        student_name = row.get("student_name", "")

        # Only update if value actually changed
        if str(old_value or "") == str(value or ""):
            cursor.close()
            conn.close()
            return jsonify({"ok": True, "reg_no": reg_no, "field": field, "value": value, "unchanged": True})

        cursor.execute(
            f"UPDATE students SET `{field}` = %s WHERE reg_no = %s",
            (value, reg_no),
        )

        # Auto-set placed_date when status changes to Placed
        if field == "status" and value == "Placed":
            cursor.execute(
                "UPDATE students SET placed_date = CURDATE() WHERE reg_no = %s AND placed_date IS NULL",
                (reg_no,),
            )
        elif field == "status" and value != "Placed":
            cursor.execute(
                "UPDATE students SET placed_date = NULL WHERE reg_no = %s",
                (reg_no,),
            )

        # Log the change
        cursor.execute(
            "INSERT INTO edit_log (reg_no, student_name, field_name, old_value, new_value, changed_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (reg_no, student_name, field, str(old_value) if old_value is not None else None,
             str(value) if value is not None else None, datetime.now()),
        )

        conn.commit()
        cursor.close()
        conn.close()

        invalidate_analytics_cache()

        return jsonify({"ok": True, "reg_no": reg_no, "field": field, "value": value})
    except Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/<reg_no>", methods=["DELETE"])
def delete_student(reg_no):
    """Delete a single student record."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE reg_no = %s", (reg_no,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        if affected == 0:
            return jsonify({"error": "Student not found"}), 404
        invalidate_analytics_cache()
        return jsonify({"ok": True, "deleted": reg_no})
    except Error as e:
        return jsonify({"error": str(e)}), 500


# ── Student Profile ──────────────────────────────────────────────────────────
@app.route("/student/<reg_no>")
def student_profile(reg_no):
    """Show a student's full profile page."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE reg_no = %s", (reg_no,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for("dashboard"))
        normalize_row(student)

        # Get uploaded files for this student
        cursor.execute(
            "SELECT * FROM student_files WHERE reg_no = %s ORDER BY uploaded_at DESC",
            (reg_no,),
        )
        files = cursor.fetchall()
        cursor.close()
        conn.close()
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("dashboard"))

    return render_template("student_profile.html", student=student, files=files)


@app.route("/student/<reg_no>/upload-file", methods=["POST"])
def upload_student_file(reg_no):
    """Upload a file (resume, offer letter, etc.) for a student."""
    file = request.files.get("file")
    file_type = request.form.get("file_type", "resume")

    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("student_profile", reg_no=reg_no))

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{reg_no}_{file_type}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
    file.save(file_path)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO student_files (reg_no, file_type, original_name, stored_name, uploaded_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (reg_no, file_type, file.filename, stored_name, datetime.now()),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"File '{file.filename}' uploaded successfully.", "success")
    except Error as e:
        flash(f"Database error: {e}", "danger")

    return redirect(url_for("student_profile", reg_no=reg_no))


@app.route("/uploads/<filename>")
def serve_upload(filename):
    """Serve uploaded files."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/student/<reg_no>/delete-file/<int:file_id>", methods=["POST"])
def delete_student_file(reg_no, file_id):
    """Delete an uploaded file."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT stored_name FROM student_files WHERE id = %s AND reg_no = %s", (file_id, reg_no))
        row = cursor.fetchone()
        if row:
            # Delete from disk
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], row["stored_name"])
            if os.path.exists(fpath):
                os.remove(fpath)
            cursor.execute("DELETE FROM student_files WHERE id = %s", (file_id,))
            conn.commit()
            flash("File deleted.", "success")
        cursor.close()
        conn.close()
    except Error as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("student_profile", reg_no=reg_no))


# ── Bulk update API (for student profile) ────────────────────────────────────
@app.route("/api/student/<reg_no>/bulk-update", methods=["PUT"])
def bulk_update_student(reg_no):
    """Update multiple fields at once (from student profile page)."""
    data = request.get_json()
    if not data or "fields" not in data:
        return jsonify({"error": "Missing fields"}), 400

    fields = data["fields"]  # dict of {field: value}
    invalid = [f for f in fields if f not in EDITABLE_COLUMNS]
    if invalid:
        return jsonify({"error": f"Non-editable fields: {invalid}"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get current values for logging
        cursor.execute("SELECT * FROM students WHERE reg_no = %s", (reg_no,))
        current = cursor.fetchone()
        if not current:
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        normalize_row(current)
        student_name = current.get("student_name", "")
        changes = []

        for field, value in fields.items():
            if value is not None and str(value).strip() == "":
                value = None

            # Convert numeric fields
            if value is not None:
                if field in NUMERIC_FLOAT_COLS:
                    value = to_float_or_none(value)
                elif field in NUMERIC_INT_COLS:
                    value = to_int_or_none(value)

            old_val = current.get(field)
            if str(old_val or "") == str(value or ""):
                continue  # skip unchanged

            cursor.execute(
                f"UPDATE students SET `{field}` = %s WHERE reg_no = %s",
                (value, reg_no),
            )
            cursor.execute(
                "INSERT INTO edit_log (reg_no, student_name, field_name, old_value, new_value, changed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (reg_no, student_name, field,
                 str(old_val) if old_val is not None else None,
                 str(value) if value is not None else None,
                 datetime.now()),
            )
            changes.append(field)

        # Auto-set placed_date if status was changed
        if "status" in changes:
            new_status = fields.get("status")
            if new_status == "Placed":
                cursor.execute(
                    "UPDATE students SET placed_date = CURDATE() WHERE reg_no = %s AND placed_date IS NULL",
                    (reg_no,),
                )
            elif new_status != "Placed":
                cursor.execute(
                    "UPDATE students SET placed_date = NULL WHERE reg_no = %s",
                    (reg_no,),
                )

        conn.commit()
        cursor.close()
        conn.close()

        if changes:
            invalidate_analytics_cache()

        return jsonify({"ok": True, "reg_no": reg_no, "changed": changes})
    except Error as e:
        return jsonify({"error": str(e)}), 500


# ── Change Log API ───────────────────────────────────────────────────────────
@app.route("/api/edit-log")
def api_edit_log():
    """Return edit log entries with pagination support."""
    limit = request.args.get("limit", 200, type=int)
    page = request.args.get("page", 1, type=int)
    reg_no = request.args.get("reg_no", None)
    offset = (page - 1) * limit
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get total count
        if reg_no:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM edit_log WHERE reg_no = %s", (reg_no,)
            )
        else:
            cursor.execute("SELECT COUNT(*) as cnt FROM edit_log")
        total_count = cursor.fetchone()["cnt"]

        if reg_no:
            cursor.execute(
                "SELECT * FROM edit_log WHERE reg_no = %s ORDER BY changed_at DESC LIMIT %s OFFSET %s",
                (reg_no, limit, offset),
            )
        else:
            cursor.execute(
                "SELECT * FROM edit_log ORDER BY changed_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
        rows = cursor.fetchall()
        for r in rows:
            if r.get("changed_at"):
                r["changed_at"] = r["changed_at"].strftime("%d %b %Y, %I:%M %p")
        cursor.close()
        conn.close()

        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        return jsonify({
            "data": rows,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
        })
    except Error as e:
        return jsonify({"data": [], "error": str(e)}), 500


# ── Other routes ─────────────────────────────────────────────────────────────
@app.route("/api/students")
def api_students():
    """Return all student records as JSON."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students ORDER BY sr_no")
        rows = cursor.fetchall()
        normalize_rows(rows)
        cursor.close()
        conn.close()
        return jsonify({"data": rows})
    except Error as e:
        return jsonify({"data": [], "error": str(e)}), 500


@app.route("/api/search")
def api_search():
    """Global student search — search by name, reg_no, course, company."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        like = f"%{q}%"
        cursor.execute(
            "SELECT reg_no, student_name, course, department, status, company_name "
            "FROM students WHERE "
            "student_name LIKE %s OR reg_no LIKE %s OR course LIKE %s OR company_name LIKE %s "
            "ORDER BY student_name LIMIT 15",
            (like, like, like, like),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"results": rows})
    except Error as e:
        return jsonify({"results": [], "error": str(e)}), 500


@app.route("/drop-all", methods=["POST"])
def drop_all():
    """Delete all student records from the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students")
        count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        invalidate_analytics_cache()
        flash(f"All student data deleted. {count} records removed.", "success")
    except Error as e:
        flash(f"Database error: {e}", "danger")
    return redirect(url_for("upload"))


# ── CDM — Company Data Management ───────────────────────────────────────────
CDM_EXCEL_HEADERS = {
    "Company ID": "company_id",
    "Company Name": "company_name",
    "Date JD Received": "jd_received_date",
    "Data Shared(Y/N)": "data_shared",
    "Process Date": "process_date",
    "Recieved By": "received_by",
    "Course": "course",
    "Position Offered": "role",
    "CTC": "ctc_text",
    "HR POC Name": "hr_name",
    "HR POC Designation": "hr_designation",
    "HR POC Email": "hr_email",
    "HR POC Phone": "hr_phone",
    "Process Mode(On-Campus / Virtual)": "process_mode",
    "Location": "location",
    "Notes": "notes",
}


def generate_company_id(name, cursor):
    """Generate a unique 4-char company ID from the name."""
    clean = ''.join(c for c in name.upper() if c.isalnum())
    if len(clean) >= 4:
        cid = clean[:2] + clean[-2:]
    else:
        cid = (clean + "XXXX")[:4]
    base = cid
    i = 1
    while True:
        cursor.execute("SELECT 1 FROM companies WHERE company_id=%s", (cid,))
        if not cursor.fetchone():
            return cid
        cid = f"{base}{i}"
        i += 1


def parse_date_field(val):
    """Parse a date value from Excel into 'YYYY-MM-DD' or None."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


@app.route("/cdm")
def cdm_page():
    """Company Data Management — drives list page."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.drive_id, d.company_id, c.company_name, d.role, d.ctc_text,
                   d.jd_received_date, d.process_date, d.data_shared,
                   d.process_mode, d.location, d.received_by, d.notes, d.status
            FROM company_drives d
            JOIN companies c ON d.company_id = c.company_id
            ORDER BY d.drive_id DESC
        """)
        drives = cursor.fetchall()
        normalize_rows(drives)

        # Attach courses list per drive
        drive_ids = [d["drive_id"] for d in drives]
        course_map = {}
        if drive_ids:
            format_ids = ",".join(["%s"] * len(drive_ids))
            cursor.execute(
                f"SELECT drive_id, course_name FROM drive_courses WHERE drive_id IN ({format_ids})",
                tuple(drive_ids),
            )
            for row in cursor.fetchall():
                course_map.setdefault(row["drive_id"], []).append(row["course_name"])
        for d in drives:
            d["courses"] = ", ".join(course_map.get(d["drive_id"], []))
            d["data_shared"] = "Yes" if d.get("data_shared") else "No"

        # Fetch all companies (including those without drives)
        cursor.execute("""
            SELECT c.company_id, c.company_name,
                   COUNT(d.drive_id) AS drive_count
            FROM companies c
            LEFT JOIN company_drives d ON c.company_id = d.company_id
            GROUP BY c.company_id, c.company_name
            ORDER BY c.company_name
        """)
        companies = cursor.fetchall()

        cursor.close()
        conn.close()
    except Error as e:
        drives = []
        companies = []
        flash(f"Database error: {e}", "danger")
    return render_template("cdm.html", drives_json=drives, companies_json=companies)


@app.route("/api/cdm")
def api_cdm():
    """JSON endpoint for CDM drives data."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.drive_id, d.company_id, c.company_name, d.role, d.ctc_text,
                   d.jd_received_date, d.process_date, d.data_shared,
                   d.process_mode, d.location, d.received_by, d.notes, d.status
            FROM company_drives d
            JOIN companies c ON d.company_id = c.company_id
            ORDER BY d.drive_id DESC
        """)
        drives = cursor.fetchall()
        normalize_rows(drives)
        drive_ids = [d["drive_id"] for d in drives]
        course_map = {}
        if drive_ids:
            format_ids = ",".join(["%s"] * len(drive_ids))
            cursor.execute(
                f"SELECT drive_id, course_name FROM drive_courses WHERE drive_id IN ({format_ids})",
                tuple(drive_ids),
            )
            for row in cursor.fetchall():
                course_map.setdefault(row["drive_id"], []).append(row["course_name"])
        for d in drives:
            d["courses"] = ", ".join(course_map.get(d["drive_id"], []))
            d["data_shared"] = "Yes" if d.get("data_shared") else "No"
        cursor.close()
        conn.close()
        return jsonify({"data": drives})
    except Error as e:
        return jsonify({"data": [], "error": str(e)}), 500


@app.route("/cdm/import", methods=["GET", "POST"])
def cdm_import():
    """Import company drives from Excel."""
    if request.method == "GET":
        return render_template("cdm_upload.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("cdm_import"))
    if not file.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files are accepted.", "danger")
        return redirect(url_for("cdm_import"))

    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        flash(f"Could not read Excel file: {e}", "danger")
        return redirect(url_for("cdm_import"))

    # Normalize headers
    df.columns = [str(h).strip() for h in df.columns]
    df = df.where(pd.notnull(df), None)

    # Map to internal names
    col_map = {}
    for excel_h, internal in CDM_EXCEL_HEADERS.items():
        for col in df.columns:
            if col.strip().lower() == excel_h.strip().lower():
                col_map[col] = internal
                break
    df.rename(columns=col_map, inplace=True)

    # Check required columns
    required = {"company_name"}
    present = set(df.columns)
    missing = required - present
    if missing:
        flash(f"Missing required columns: {missing}", "danger")
        return redirect(url_for("cdm_import"))

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        companies_added = 0
        drives_added = 0
        hr_added = 0

        for _, row in df.iterrows():
            company_name = str(row.get("company_name", "")).strip() if row.get("company_name") else None
            if not company_name or company_name.lower() == "nan":
                continue

            # ── Company ──────────────────────────────────────────────
            company_id = str(row.get("company_id", "")).strip() if row.get("company_id") else None
            if not company_id or company_id.lower() == "nan":
                company_id = generate_company_id(company_name, cursor)

            cursor.execute("SELECT 1 FROM companies WHERE company_id=%s", (company_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO companies (company_id, company_name) VALUES (%s, %s)",
                    (company_id, company_name),
                )
                companies_added += 1

            # ── Drive ────────────────────────────────────────────────
            role = str(row.get("role", "")).strip() if row.get("role") else None
            if role and role.lower() == "nan":
                role = None
            ctc_text = str(row.get("ctc_text", "")).strip() if row.get("ctc_text") else None
            if ctc_text and ctc_text.lower() == "nan":
                ctc_text = None
            jd_date = parse_date_field(row.get("jd_received_date"))
            proc_date = parse_date_field(row.get("process_date"))
            data_shared_raw = str(row.get("data_shared", "")).strip().upper() if row.get("data_shared") else ""
            data_shared = True if data_shared_raw in ("Y", "YES", "TRUE", "1") else False
            process_mode = str(row.get("process_mode", "")).strip() if row.get("process_mode") else None
            if process_mode and process_mode.lower() == "nan":
                process_mode = None
            if process_mode:
                pm = process_mode.lower().replace("-", "").replace(" ", "")
                if "virtual" in pm:
                    process_mode = "Virtual"
                elif "campus" in pm:
                    process_mode = "On-Campus"
            location = str(row.get("location", "")).strip() if row.get("location") else None
            if location and location.lower() == "nan":
                location = None
            received_by = str(row.get("received_by", "")).strip() if row.get("received_by") else None
            if received_by and received_by.lower() == "nan":
                received_by = None
            notes = str(row.get("notes", "")).strip() if row.get("notes") else None
            if notes and notes.lower() == "nan":
                notes = None

            # ── Duplicate drive detection ────────────────────────────
            dup_check_sql = (
                "SELECT drive_id FROM company_drives "
                "WHERE company_id=%s AND role=%s"
            )
            dup_params = [company_id, role]
            if proc_date:
                dup_check_sql += " AND process_date=%s"
                dup_params.append(proc_date)
            else:
                dup_check_sql += " AND process_date IS NULL"
            cursor.execute(dup_check_sql, tuple(dup_params))
            if cursor.fetchone():
                # Skip duplicate drive
                continue

            cursor.execute(
                "INSERT INTO company_drives "
                "(company_id, role, ctc_text, jd_received_date, process_date, "
                "data_shared, process_mode, location, received_by, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (company_id, role, ctc_text, jd_date, proc_date,
                 data_shared, process_mode, location, received_by, notes, "Upcoming"),
            )
            drive_id = cursor.lastrowid
            drives_added += 1

            # ── Courses ──────────────────────────────────────────────
            courses_raw = str(row.get("course", "")).strip() if row.get("course") else ""
            if courses_raw and courses_raw.lower() != "nan":
                courses = [c.strip() for c in courses_raw.split(",") if c.strip()]
                if courses:
                    cursor.executemany(
                        "INSERT IGNORE INTO drive_courses (drive_id, course_name) VALUES (%s, %s)",
                        [(drive_id, c) for c in courses],
                    )

            # ── HR Contact ───────────────────────────────────────────
            hr_name = str(row.get("hr_name", "")).strip() if row.get("hr_name") else None
            if hr_name and hr_name.lower() == "nan":
                hr_name = None
            if hr_name:
                hr_desig = str(row.get("hr_designation", "")).strip() if row.get("hr_designation") else None
                if hr_desig and hr_desig.lower() == "nan":
                    hr_desig = None
                hr_email = str(row.get("hr_email", "")).strip() if row.get("hr_email") else None
                if hr_email and hr_email.lower() == "nan":
                    hr_email = None
                hr_phone = str(row.get("hr_phone", "")).strip() if row.get("hr_phone") else None
                if hr_phone and hr_phone.lower() == "nan":
                    hr_phone = None
                # Avoid duplicate HR entries
                cursor.execute(
                    "SELECT hr_id FROM company_hr WHERE company_id=%s AND name=%s",
                    (company_id, hr_name),
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO company_hr (company_id, name, designation, email, phone) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (company_id, hr_name, hr_desig, hr_email, hr_phone),
                    )
                    hr_added += 1

        conn.commit()
        cursor.close()
        conn.close()
        flash(
            f"CDM import successful — {companies_added} companies, "
            f"{drives_added} drives, {hr_added} HR contacts added.",
            "success",
        )
    except Error as e:
        flash(f"Database error: {e}", "danger")

    return redirect(url_for("cdm_page"))


@app.route("/cdm/company/<company_id>")
def cdm_company_detail(company_id):
    """Company detail page — drives + HR contacts."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM companies WHERE company_id=%s", (company_id,))
        company = cursor.fetchone()
        if not company:
            flash("Company not found.", "danger")
            return redirect(url_for("cdm_page"))

        cursor.execute(
            "SELECT * FROM company_drives WHERE company_id=%s ORDER BY drive_id DESC",
            (company_id,),
        )
        drives = cursor.fetchall()
        normalize_rows(drives)

        # Courses per drive + linked student counts + rounds
        for d in drives:
            cursor.execute(
                "SELECT course_name FROM drive_courses WHERE drive_id=%s",
                (d["drive_id"],),
            )
            d["courses"] = ", ".join([r["course_name"] for r in cursor.fetchall()])
            d["data_shared"] = "Yes" if d.get("data_shared") else "No"
            # Count linked students
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM drive_students WHERE drive_id=%s",
                (d["drive_id"],),
            )
            d["student_count"] = cursor.fetchone()["cnt"]
            # Count rounds
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM drive_rounds WHERE drive_id=%s",
                (d["drive_id"],),
            )
            d["round_count"] = cursor.fetchone()["cnt"]

        # HR contacts
        cursor.execute(
            "SELECT * FROM company_hr WHERE company_id=%s ORDER BY name",
            (company_id,),
        )
        hr_contacts = cursor.fetchall()

        cursor.close()
        conn.close()
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("cdm_page"))

    return render_template(
        "cdm_company.html",
        company=company,
        drives=drives,
        hr_contacts=hr_contacts,
    )


@app.route("/api/cdm/delete-drive/<int:drive_id>", methods=["POST"])
def cdm_delete_drive(drive_id):
    """Delete a single drive (cascades to courses)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drive_students WHERE drive_id=%s", (drive_id,))
        cursor.execute("DELETE FROM drive_rounds WHERE drive_id=%s", (drive_id,))
        cursor.execute("DELETE FROM drive_courses WHERE drive_id=%s", (drive_id,))
        cursor.execute("DELETE FROM company_drives WHERE drive_id=%s", (drive_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/drive", methods=["POST"])
def cdm_create_drive():
    """Create a new drive for a company."""
    data = request.get_json(silent=True) or {}
    company_id = (data.get("company_id") or "").strip()
    role = (data.get("role") or "").strip()
    if not company_id or not role:
        return jsonify({"ok": False, "error": "Company ID and role are required."}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT 1 FROM companies WHERE company_id=%s", (company_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "error": "Company not found."}), 404
        cursor.execute(
            "INSERT INTO company_drives (company_id, role, ctc_text, process_date, "
            "process_mode, location, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                company_id,
                role,
                data.get("ctc_text") or None,
                data.get("process_date") or None,
                data.get("process_mode") or None,
                data.get("location") or None,
                data.get("status") or "Upcoming",
                data.get("notes") or None,
            ),
        )
        drive_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "drive_id": drive_id})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CDM Inline Editing API ───────────────────────────────────────────────────
CDM_EDITABLE_FIELDS = {
    "role", "ctc_text", "jd_received_date", "process_date", "data_shared",
    "process_mode", "location", "received_by", "notes", "status"
}


@app.route("/api/cdm/drive/<int:drive_id>", methods=["PUT"])
def cdm_update_drive(drive_id):
    """Update a single field of a drive record (inline editing)."""
    data = request.get_json()
    if not data or "field" not in data:
        return jsonify({"error": "Missing field"}), 400

    field = data["field"]
    value = data.get("value")

    if field not in CDM_EDITABLE_FIELDS:
        return jsonify({"error": f"Field '{field}' is not editable"}), 400

    # Empty string → NULL
    if value is not None and str(value).strip() == "":
        value = None

    # Date fields validation
    if field in ("jd_received_date", "process_date") and value:
        value = parse_date_field(value)

    # Boolean field
    if field == "data_shared":
        if isinstance(value, str):
            value = True if value.strip().upper() in ("Y", "YES", "TRUE", "1") else False

    # Status validation
    if field == "status" and value:
        valid_statuses = {"Upcoming", "Ongoing", "Completed", "Cancelled"}
        if value not in valid_statuses:
            return jsonify({"error": f"Status must be one of: {', '.join(valid_statuses)}"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM company_drives WHERE drive_id=%s", (drive_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({"error": "Drive not found"}), 404

        old_value = row.get(field)
        if isinstance(old_value, Decimal):
            old_value = float(old_value)
        elif isinstance(old_value, (date, datetime)):
            old_value = old_value.strftime("%Y-%m-%d")

        cursor.execute(
            f"UPDATE company_drives SET `{field}` = %s WHERE drive_id = %s",
            (value, drive_id),
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Return display value for data_shared
        display_value = value
        if field == "data_shared":
            display_value = "Yes" if value else "No"

        return jsonify({"ok": True, "drive_id": drive_id, "field": field, "value": display_value})
    except Error as e:
        return jsonify({"error": str(e)}), 500


# ── CDM HR Management API ───────────────────────────────────────────────────
@app.route("/api/cdm/hr/<int:hr_id>", methods=["PUT"])
def cdm_update_hr(hr_id):
    """Update a single HR contact field."""
    data = request.get_json()
    if not data or "field" not in data:
        return jsonify({"error": "Missing field"}), 400

    field = data["field"]
    value = data.get("value")
    allowed = {"name", "designation", "email", "phone"}

    if field not in allowed:
        return jsonify({"error": f"Field '{field}' is not editable"}), 400

    if value is not None and str(value).strip() == "":
        value = None

    if field == "email" and value:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', str(value)):
            return jsonify({"error": "Invalid email format"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM company_hr WHERE hr_id=%s", (hr_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "HR contact not found"}), 404

        cursor.execute(
            f"UPDATE company_hr SET `{field}` = %s WHERE hr_id = %s",
            (value, hr_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "hr_id": hr_id, "field": field, "value": value})
    except Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cdm/hr/<int:hr_id>", methods=["DELETE"])
def cdm_delete_hr(hr_id):
    """Delete an HR contact."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM company_hr WHERE hr_id=%s", (hr_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/hr", methods=["POST"])
def cdm_add_hr():
    """Add a new HR contact to a company."""
    data = request.get_json()
    if not data or "company_id" not in data or "name" not in data:
        return jsonify({"error": "company_id and name are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO company_hr (company_id, name, designation, email, phone) "
            "VALUES (%s, %s, %s, %s, %s)",
            (data["company_id"], data["name"], data.get("designation"),
             data.get("email"), data.get("phone")),
        )
        hr_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "hr_id": hr_id})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CDM Company Search API ──────────────────────────────────────────────────
@app.route("/api/cdm/search")
def cdm_search():
    """Search companies and drives by name, role, location."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        like = f"%{q}%"
        cursor.execute(
            "SELECT DISTINCT c.company_id, c.company_name, d.role, d.ctc_text, d.status "
            "FROM companies c "
            "LEFT JOIN company_drives d ON c.company_id = d.company_id "
            "WHERE c.company_name LIKE %s OR d.role LIKE %s OR d.location LIKE %s "
            "ORDER BY c.company_name LIMIT 15",
            (like, like, like),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"results": rows})
    except Error as e:
        return jsonify({"results": [], "error": str(e)}), 500


# ── CDM Company CRUD API ─────────────────────────────────────────────────────
@app.route("/api/cdm/company", methods=["POST"])
def cdm_create_company():
    """Create a new company (with optional first drive)."""
    data = request.get_json(silent=True) or {}
    name = (data.get("company_name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name is required."}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Check duplicate name
        cursor.execute(
            "SELECT company_id FROM companies WHERE company_name = %s", (name,)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "error": "Company already exists.", "company_id": existing["company_id"]}), 409
        cid = generate_company_id(name, cursor)
        cursor.execute(
            "INSERT INTO companies (company_id, company_name) VALUES (%s, %s)",
            (cid, name),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "company_id": cid, "company_name": name})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/company/<company_id>", methods=["PUT"])
def cdm_update_company(company_id):
    """Update company name."""
    data = request.get_json(silent=True) or {}
    name = (data.get("company_name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name is required."}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT 1 FROM companies WHERE company_id=%s", (company_id,)
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "error": "Company not found."}), 404
        cursor.execute(
            "UPDATE companies SET company_name=%s WHERE company_id=%s",
            (name, company_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "company_name": name})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/company/<company_id>", methods=["DELETE"])
def cdm_delete_company(company_id):
    """Delete a company and all associated data."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Delete in order of foreign key dependencies
        cursor.execute(
            "DELETE ds FROM drive_students ds "
            "JOIN company_drives d ON ds.drive_id = d.drive_id "
            "WHERE d.company_id = %s",
            (company_id,),
        )
        cursor.execute(
            "DELETE dr FROM drive_rounds dr "
            "JOIN company_drives d ON dr.drive_id = d.drive_id "
            "WHERE d.company_id = %s",
            (company_id,),
        )
        cursor.execute(
            "DELETE dc FROM drive_courses dc "
            "JOIN company_drives d ON dc.drive_id = d.drive_id "
            "WHERE d.company_id = %s",
            (company_id,),
        )
        cursor.execute(
            "DELETE FROM company_drives WHERE company_id = %s", (company_id,)
        )
        cursor.execute(
            "DELETE FROM company_hr WHERE company_id = %s", (company_id,)
        )
        cursor.execute(
            "DELETE FROM companies WHERE company_id = %s", (company_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CDM Analytics API ────────────────────────────────────────────────────────

def parse_ctc_value(ctc_text):
    """Parse CTC text like '10 LPA', '6 LPA - 10 LPA', '6 LPA & 8 LPA' into a float.
    Returns the first (lowest) number found, or None if unparsable."""
    if not ctc_text:
        return None
    text = str(ctc_text).strip()
    # Split on common separators first to isolate individual values
    parts = re.split(r'\s*[-&,/]\s*', text)
    for part in parts:
        m = re.search(r'(\d+\.?\d*)', part)
        if m:
            val = float(m.group(1))
            if val > 0:
                return val
    return None


@app.route("/api/cdm/analytics")
def cdm_analytics():
    """Return CDM analytics data for charts and stats."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Total drives & companies
        cursor.execute("SELECT COUNT(*) AS total_drives FROM company_drives")
        total_drives = cursor.fetchone()["total_drives"]
        cursor.execute("SELECT COUNT(*) AS total_companies FROM companies")
        total_companies = cursor.fetchone()["total_companies"]

        # Status distribution (still needed for hero)
        cursor.execute(
            "SELECT IFNULL(status, 'Upcoming') AS status, COUNT(*) AS cnt "
            "FROM company_drives GROUP BY status"
        )
        status_dist = {r["status"]: r["cnt"] for r in cursor.fetchall()}

        # ── CTC analysis (fixed parsing) ─────────────────────────
        cursor.execute("SELECT ctc_text FROM company_drives WHERE ctc_text IS NOT NULL AND ctc_text != ''")
        ctc_rows = cursor.fetchall()
        ctc_values = []
        for r in ctc_rows:
            val = parse_ctc_value(r["ctc_text"])
            if val is not None:
                ctc_values.append(val)

        ctc_stats = {}
        if ctc_values:
            ctc_values.sort()
            ctc_stats["mean"] = round(sum(ctc_values) / len(ctc_values), 2)
            mid = len(ctc_values) // 2
            ctc_stats["median"] = round(
                (ctc_values[mid - 1] + ctc_values[mid]) / 2 if len(ctc_values) % 2 == 0 else ctc_values[mid], 2
            )
            ctc_stats["highest"] = round(max(ctc_values), 2)
            ctc_stats["lowest"] = round(min(ctc_values), 2)
            ctc_stats["count"] = len(ctc_values)

        # ── Companies with highest placed/selected students ──────
        cursor.execute("""
            SELECT c.company_name, COUNT(ds.reg_no) AS selected_count
            FROM drive_students ds
            JOIN company_drives d ON ds.drive_id = d.drive_id
            JOIN companies c ON d.company_id = c.company_id
            WHERE ds.status = 'Selected'
            GROUP BY c.company_id, c.company_name
            ORDER BY selected_count DESC
            LIMIT 10
        """)
        top_placed_companies = cursor.fetchall()

        # ── Companies with highest CTCs ──────────────────────────
        cursor.execute("""
            SELECT c.company_name, d.ctc_text
            FROM company_drives d
            JOIN companies c ON d.company_id = c.company_id
            WHERE d.ctc_text IS NOT NULL AND d.ctc_text != ''
        """)
        ctc_company_rows = cursor.fetchall()
        company_ctc_map = {}
        for r in ctc_company_rows:
            val = parse_ctc_value(r["ctc_text"])
            if val is not None:
                name = r["company_name"]
                if name not in company_ctc_map or val > company_ctc_map[name]:
                    company_ctc_map[name] = val
        highest_ctc_companies = sorted(
            [{"company_name": k, "ctc": v} for k, v in company_ctc_map.items()],
            key=lambda x: x["ctc"], reverse=True
        )[:10]

        # ── Team Performance (received_by) ───────────────────────
        cursor.execute("""
            SELECT d.received_by,
                   COUNT(DISTINCT d.drive_id) AS total_drives,
                   COUNT(DISTINCT d.company_id) AS companies_brought
            FROM company_drives d
            WHERE d.received_by IS NOT NULL AND d.received_by != ''
            GROUP BY d.received_by
            ORDER BY companies_brought DESC
        """)
        team_base = cursor.fetchall()

        # Get selections per team member
        cursor.execute("""
            SELECT d.received_by, COUNT(ds.reg_no) AS selections
            FROM company_drives d
            JOIN drive_students ds ON d.drive_id = ds.drive_id
            WHERE ds.status = 'Selected'
              AND d.received_by IS NOT NULL AND d.received_by != ''
            GROUP BY d.received_by
        """)
        team_selections = {r["received_by"]: r["selections"] for r in cursor.fetchall()}

        # Get CTC stats per team member
        cursor.execute("""
            SELECT d.received_by, d.ctc_text
            FROM company_drives d
            WHERE d.received_by IS NOT NULL AND d.received_by != ''
              AND d.ctc_text IS NOT NULL AND d.ctc_text != ''
        """)
        team_ctc_rows = cursor.fetchall()
        team_ctc_map = {}  # {person: [ctc_values]}
        for r in team_ctc_rows:
            val = parse_ctc_value(r["ctc_text"])
            if val is not None:
                team_ctc_map.setdefault(r["received_by"], []).append(val)

        team_performance = []
        for row in team_base:
            person = row["received_by"]
            ctc_list = team_ctc_map.get(person, [])
            team_performance.append({
                "name": person,
                "companies_brought": row["companies_brought"],
                "total_drives": row["total_drives"],
                "selections": team_selections.get(person, 0),
                "avg_ctc": round(sum(ctc_list) / len(ctc_list), 2) if ctc_list else None,
                "highest_ctc": round(max(ctc_list), 2) if ctc_list else None,
            })

        cursor.close()
        conn.close()

        return jsonify({
            "total_drives": total_drives,
            "total_companies": total_companies,
            "status_dist": status_dist,
            "ctc_stats": ctc_stats,
            "top_placed_companies": top_placed_companies,
            "highest_ctc_companies": highest_ctc_companies,
            "team_performance": team_performance,
        })
    except Error as e:
        return jsonify({"error": str(e)}), 500


# ── CDM Student Linking API ──────────────────────────────────────────────────
@app.route("/api/cdm/drive/<int:drive_id>/students", methods=["GET"])
def cdm_drive_students(drive_id):
    """Get students linked to a drive."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT ds.reg_no, ds.status, ds.current_round, s.student_name, s.course, s.department "
            "FROM drive_students ds "
            "JOIN students s ON ds.reg_no = s.reg_no "
            "WHERE ds.drive_id = %s ORDER BY s.student_name",
            (drive_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"students": rows})
    except Error as e:
        return jsonify({"students": [], "error": str(e)}), 500


@app.route("/api/cdm/drive/<int:drive_id>/students", methods=["POST"])
def cdm_link_student(drive_id):
    """Link a student to a drive."""
    data = request.get_json()
    if not data or "reg_no" not in data:
        return jsonify({"error": "reg_no is required"}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO drive_students (drive_id, reg_no, status, current_round) "
            "VALUES (%s, %s, %s, %s)",
            (drive_id, data["reg_no"], data.get("status", "Applied"), data.get("current_round", 0)),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/drive/<int:drive_id>/students/<reg_no>", methods=["PUT"])
def cdm_update_drive_student(drive_id, reg_no):
    """Update student status/round in a drive."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sets = []
        vals = []
        if "status" in data:
            sets.append("status = %s")
            vals.append(data["status"])
        if "current_round" in data:
            sets.append("current_round = %s")
            vals.append(data["current_round"])
        if not sets:
            cursor.close()
            conn.close()
            return jsonify({"error": "Nothing to update"}), 400
        vals.extend([drive_id, reg_no])
        cursor.execute(
            f"UPDATE drive_students SET {', '.join(sets)} WHERE drive_id = %s AND reg_no = %s",
            tuple(vals),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/drive/<int:drive_id>/students/<reg_no>", methods=["DELETE"])
def cdm_unlink_student(drive_id, reg_no):
    """Remove a student from a drive."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM drive_students WHERE drive_id = %s AND reg_no = %s",
            (drive_id, reg_no),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CDM Round Management API ────────────────────────────────────────────────
@app.route("/api/cdm/drive/<int:drive_id>/rounds", methods=["GET"])
def cdm_drive_rounds(drive_id):
    """Get rounds for a drive."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM drive_rounds WHERE drive_id = %s ORDER BY round_order",
            (drive_id,),
        )
        rows = cursor.fetchall()
        normalize_rows(rows)
        cursor.close()
        conn.close()
        return jsonify({"rounds": rows})
    except Error as e:
        return jsonify({"rounds": [], "error": str(e)}), 500


@app.route("/api/cdm/drive/<int:drive_id>/rounds", methods=["POST"])
def cdm_add_round(drive_id):
    """Add a round to a drive."""
    data = request.get_json()
    if not data or "round_name" not in data:
        return jsonify({"error": "round_name is required"}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT IFNULL(MAX(round_order), 0) + 1 AS next_order FROM drive_rounds WHERE drive_id = %s",
            (drive_id,),
        )
        next_order = cursor.fetchone()[0]
        round_date = parse_date_field(data.get("round_date"))
        cursor.execute(
            "INSERT INTO drive_rounds (drive_id, round_name, round_order, round_date) VALUES (%s, %s, %s, %s)",
            (drive_id, data["round_name"], next_order, round_date),
        )
        round_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "round_id": round_id, "round_order": next_order})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cdm/round/<int:round_id>", methods=["DELETE"])
def cdm_delete_round(round_id):
    """Delete a round."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drive_rounds WHERE round_id=%s", (round_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CDM Calendar Data API ───────────────────────────────────────────────────
@app.route("/api/cdm/calendar")
def cdm_calendar():
    """Return drives with dates for calendar view."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.drive_id, d.company_id, c.company_name, d.role, d.ctc_text,
                   d.process_date, d.jd_received_date, d.process_mode,
                   d.status, d.location
            FROM company_drives d
            JOIN companies c ON d.company_id = c.company_id
            WHERE d.process_date IS NOT NULL
            ORDER BY d.process_date
        """)
        rows = cursor.fetchall()
        normalize_rows(rows)
        cursor.close()
        conn.close()
        return jsonify({"events": rows})
    except Error as e:
        return jsonify({"events": [], "error": str(e)}), 500


# ── CDM Placement Source Analytics API ───────────────────────────────────────
@app.route("/api/cdm/placement-sources")
def cdm_placement_sources():
    """Which companies placed how many students (join with students table)."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Match by company name from students table
        cursor.execute("""
            SELECT s.company_name, COUNT(*) AS placed_count,
                   ROUND(AVG(s.ctc), 2) AS avg_ctc,
                   MAX(s.ctc) AS max_ctc,
                   GROUP_CONCAT(DISTINCT s.course SEPARATOR ', ') AS courses
            FROM students s
            WHERE s.status = 'Placed' AND s.company_name IS NOT NULL AND s.company_name != ''
            GROUP BY s.company_name
            ORDER BY placed_count DESC
        """)
        rows = cursor.fetchall()
        normalize_rows(rows)

        # Also get drive-linked students
        cursor.execute("""
            SELECT c.company_name, COUNT(*) AS linked_count
            FROM drive_students ds
            JOIN company_drives d ON ds.drive_id = d.drive_id
            JOIN companies c ON d.company_id = c.company_id
            WHERE ds.status = 'Selected'
            GROUP BY c.company_name
        """)
        linked = {r["company_name"]: r["linked_count"] for r in cursor.fetchall()}

        for r in rows:
            r["linked_placed"] = linked.get(r["company_name"], 0)

        cursor.close()
        conn.close()
        return jsonify({"sources": rows})
    except Error as e:
        return jsonify({"sources": [], "error": str(e)}), 500


# ── CDM Student Search (for linking UI) ──────────────────────────────────────
@app.route("/api/cdm/search-students")
def cdm_search_students():
    """Search students for linking to drives."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        like = f"%{q}%"
        cursor.execute(
            "SELECT reg_no, student_name, course, department, status "
            "FROM students WHERE "
            "student_name LIKE %s OR reg_no LIKE %s OR course LIKE %s "
            "ORDER BY student_name LIMIT 15",
            (like, like, like),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"results": rows})
    except Error as e:
        return jsonify({"results": [], "error": str(e)}), 500


@app.route("/versions")
def versions():
    """Show all upload versions."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM upload_versions ORDER BY uploaded_at DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("versions.html", versions=rows)
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return render_template("versions.html", versions=[])


@app.route("/versions/<int:version_id>")
def version_detail(version_id):
    """Show data from a specific upload version."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT v.* FROM version_snapshots v WHERE v.version_id = %s ORDER BY v.sr_no",
            (version_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Error:
        rows = []
    return render_template("version_detail.html", version_id=version_id, snap_json=rows)


@app.route("/api/version/<int:version_id>")
def api_version(version_id):
    """Return snapshot data for a specific version as JSON."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT v.*, uv.filename, uv.uploaded_at "
            "FROM version_snapshots v "
            "JOIN upload_versions uv ON v.version_id = uv.version_id "
            "WHERE v.version_id = %s ORDER BY v.sr_no",
            (version_id,),
        )
        rows = cursor.fetchall()
        for r in rows:
            if r.get("uploaded_at"):
                r["uploaded_at"] = r["uploaded_at"].strftime("%Y-%m-%d %H:%M:%S")
        cursor.close()
        conn.close()
        return jsonify({"data": rows})
    except Error as e:
        return jsonify({"data": [], "error": str(e)}), 500


@app.route("/delete-version/<int:version_id>", methods=["POST"])
def delete_version(version_id):
    """Delete a specific upload version and its snapshot data."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM version_snapshots WHERE version_id = %s", (version_id,))
        cursor.execute("DELETE FROM upload_versions WHERE version_id = %s", (version_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Version #{version_id} deleted.", "success")
    except Error as e:
        flash(f"Database error: {e}", "danger")
    return redirect(url_for("versions"))


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
