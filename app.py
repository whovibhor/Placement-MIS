from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

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
    """Create the database and students table if they don't exist."""
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
    conn.commit()
    cursor.close()
    conn.close()


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("upload"))


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
    # Pandas may read "10%" / "12%" as 0.1 / 0.12 — fix that
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

    # Keep only the 26 required columns (drop any extras)
    df = df[EXPECTED_HEADERS]

    # ── Rename columns to DB-friendly names ──────────────────────────────
    df.rename(columns=HEADER_TO_COL, inplace=True)

    # Replace NaN with None so MySQL gets NULL
    df = df.where(pd.notnull(df), None)

    # Convert sr_no to int (pandas reads it as float like 1.0 → 1)
    def to_int_or_none(v):
        if v is None:
            return None
        try:
            return int(float(str(v)))
        except (ValueError, TypeError):
            return None

    df["sr_no"] = df["sr_no"].apply(to_int_or_none)

    # Convert remaining columns to strings (except None) to avoid type issues
    for col in DB_COLUMNS:
        if col == "sr_no":
            continue
        df[col] = df[col].apply(lambda v: str(v).strip() if v is not None else None)

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

            # Check existence to count inserts vs updates
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

        # Snapshot: copy the uploaded data into version_snapshots
        snap_cols = ", ".join(DB_COLUMNS)
        snap_placeholders = ", ".join(["%s"] * (len(DB_COLUMNS) + 1))  # +1 for version_id
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
        cursor.close()
        conn.close()
    except Error:
        rows = []
    return render_template("dashboard.html", students_json=rows)


@app.route("/api/students")
def api_students():
    """Return all student records as JSON for DataTables AJAX source."""
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
        cursor.execute(
            "SELECT * FROM upload_versions ORDER BY uploaded_at DESC"
        )
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
            "SELECT v.* "
            "FROM version_snapshots v "
            "WHERE v.version_id = %s ORDER BY v.sr_no",
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
        # Convert datetime to string for JSON
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
