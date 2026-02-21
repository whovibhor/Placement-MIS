from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from decimal import Decimal
import statistics
import os
import uuid
import re
import json
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
    'status', 'company_name', 'designation', 'ctc',
    'graduation_ogpa', 'percent_10', 'percent_12', 'backlogs',
    'hometown', 'address', 'reason',
    'resume_status', 'offer_letter_status', 'joining_date', 'joining_status',
    'graduation_course',
]

# Columns that are editable via inline editing
EDITABLE_COLUMNS = set(DB_COLUMNS) - {"sr_no", "reg_no"}

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
    """Convert Decimal values to float for JSON serialization."""
    if row is None:
        return None
    for k, v in row.items():
        if isinstance(v, Decimal):
            row[k] = float(v)
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
        cursor = conn.cursor()

        # Get existing reg_nos in one query for insert/update tracking
        cursor.execute("SELECT reg_no FROM students")
        existing_regs = set(row[0] for row in cursor.fetchall())

        values_list = []
        for _, row in df.iterrows():
            values = tuple(row[c] for c in DB_COLUMNS)
            values_list.append(values)
            if row["reg_no"] in existing_regs:
                updated += 1
            else:
                inserted += 1

        cursor.executemany(upsert_sql, values_list)
        conn.commit()

        # ── Save version snapshot (batch) ────────────────────────────────
        total = inserted + updated
        cursor.execute(
            "INSERT INTO upload_versions (filename, uploaded_at, total_records, inserted, updated) "
            "VALUES (%s, %s, %s, %s, %s)",
            (file.filename, datetime.now(), total, inserted, updated),
        )
        version_id = cursor.lastrowid

        snap_cols = ", ".join(DB_COLUMNS)
        snap_placeholders = ", ".join(["%s"] * (len(DB_COLUMNS) + 1))
        snap_sql = (
            f"INSERT INTO version_snapshots (version_id, {snap_cols}) "
            f"VALUES ({snap_placeholders})"
        )
        snap_values_list = []
        for _, row in df.iterrows():
            values = (version_id,) + tuple(row[c] for c in DB_COLUMNS)
            snap_values_list.append(values)
        cursor.executemany(snap_sql, snap_values_list)

        conn.commit()
        cursor.close()
        conn.close()

        # Invalidate analytics cache after data change
        invalidate_analytics_cache()

        flash(
            f"Upload successful. {total} records processed, "
            f"{inserted} inserted, {updated} updated.",
            "success",
        )
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
