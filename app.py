from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import statistics
import os
import uuid
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

# Columns displayed on dashboard (school_name removed)
DISPLAY_COLUMNS = [c for c in DB_COLUMNS if c != "school_name"]

# Columns that are editable via inline editing
EDITABLE_COLUMNS = set(DB_COLUMNS) - {"sr_no", "reg_no"}


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
    conn.commit()
    cursor.close()
    conn.close()


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

    def to_int_or_none(v):
        if v is None:
            return None
        try:
            return int(float(str(v)))
        except (ValueError, TypeError):
            return None

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

    # ── Upsert into MySQL ────────────────────────────────────────────────
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

        for _, row in df.iterrows():
            values = tuple(row[c] for c in DB_COLUMNS)
            cursor.execute(
                "SELECT 1 FROM students WHERE reg_no = %s", (row["reg_no"],)
            )
            exists = cursor.fetchone()
            cursor.execute(upsert_sql, values)
            if exists:
                updated += 1
            else:
                inserted += 1

        conn.commit()

        # ── Save version snapshot ────────────────────────────────────────
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
        for _, row in df.iterrows():
            values = (version_id,) + tuple(row[c] for c in DB_COLUMNS)
            cursor.execute(snap_sql, values)

        conn.commit()
        cursor.close()
        conn.close()

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
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students ORDER BY sr_no")
        rows = cursor.fetchall()
        analytics = compute_analytics(rows)
        cursor.close()
        conn.close()
    except Error:
        rows = []
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
        analytics = compute_analytics(rows)
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

        student_name = current.get("student_name", "")
        changes = []

        for field, value in fields.items():
            if value is not None and str(value).strip() == "":
                value = None

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

        return jsonify({"ok": True, "reg_no": reg_no, "changed": changes})
    except Error as e:
        return jsonify({"error": str(e)}), 500


# ── Change Log API ───────────────────────────────────────────────────────────
@app.route("/api/edit-log")
def api_edit_log():
    """Return all edit log entries."""
    limit = request.args.get("limit", 200, type=int)
    reg_no = request.args.get("reg_no", None)
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        if reg_no:
            cursor.execute(
                "SELECT * FROM edit_log WHERE reg_no = %s ORDER BY changed_at DESC LIMIT %s",
                (reg_no, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM edit_log ORDER BY changed_at DESC LIMIT %s", (limit,)
            )
        rows = cursor.fetchall()
        for r in rows:
            if r.get("changed_at"):
                r["changed_at"] = r["changed_at"].strftime("%d %b %Y, %I:%M %p")
        cursor.close()
        conn.close()
        return jsonify({"data": rows})
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
        cursor.close()
        conn.close()
        return jsonify({"data": rows})
    except Error as e:
        return jsonify({"data": [], "error": str(e)}), 500


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
