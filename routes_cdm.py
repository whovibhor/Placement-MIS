# routes_cdm.py — Company Data Management routes
import re
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO

from flask import (
    flash, jsonify, redirect, render_template, request, send_file, url_for,
)
from mysql.connector import Error

from helpers import (
    get_connection, normalize_rows, invalidate_analytics_cache,
)


# ── CDM constants ────────────────────────────────────────────────────────────
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

CDM_EDITABLE_FIELDS = {
    "role", "ctc_text", "jd_received_date", "process_date", "data_shared",
    "process_mode", "location", "received_by", "notes", "status",
}


# ── CDM helpers ──────────────────────────────────────────────────────────────
def generate_company_id(name, cursor):
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


def parse_ctc_value(ctc_text):
    if not ctc_text:
        return None
    text = str(ctc_text).strip()
    parts = re.split(r'\s*[-&,/]\s*', text)
    for part in parts:
        m = re.search(r'(\d+\.?\d*)', part)
        if m:
            val = float(m.group(1))
            if val > 0:
                return val
    return None


def register_cdm_routes(app):
    """Register all CDM routes on the Flask app."""

    # ── CDM main page ────────────────────────────────────────────────────
    @app.route("/cdm")
    def cdm_page():
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

    # ── CDM JSON endpoint ────────────────────────────────────────────────
    @app.route("/api/cdm")
    def api_cdm():
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

    # ── CDM Import ───────────────────────────────────────────────────────
    @app.route("/cdm/import", methods=["GET", "POST"])
    def cdm_import():
        if request.method == "GET":
            return redirect(url_for("upload"))

        import pandas as pd

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

        df.columns = [str(h).strip() for h in df.columns]
        df = df.where(pd.notnull(df), None)

        col_map = {}
        for excel_h, internal in CDM_EXCEL_HEADERS.items():
            for col in df.columns:
                if col.strip().lower() == excel_h.strip().lower():
                    col_map[col] = internal
                    break
        df.rename(columns=col_map, inplace=True)

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

                courses_raw = str(row.get("course", "")).strip() if row.get("course") else ""
                if courses_raw and courses_raw.lower() != "nan":
                    courses = [c.strip() for c in courses_raw.split(",") if c.strip()]
                    if courses:
                        cursor.executemany(
                            "INSERT IGNORE INTO drive_courses (drive_id, course_name) VALUES (%s, %s)",
                            [(drive_id, c) for c in courses],
                        )

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

        return redirect(url_for("upload"))

    # ── Company detail page ──────────────────────────────────────────────
    @app.route("/cdm/company/<company_id>")
    def cdm_company_detail(company_id):
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

            for d in drives:
                cursor.execute(
                    "SELECT course_name FROM drive_courses WHERE drive_id=%s",
                    (d["drive_id"],),
                )
                d["courses"] = ", ".join([r["course_name"] for r in cursor.fetchall()])
                d["data_shared"] = "Yes" if d.get("data_shared") else "No"
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM drive_students WHERE drive_id=%s",
                    (d["drive_id"],),
                )
                d["student_count"] = cursor.fetchone()["cnt"]
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM drive_rounds WHERE drive_id=%s",
                    (d["drive_id"],),
                )
                d["round_count"] = cursor.fetchone()["cnt"]

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

    # ── Drive CRUD ───────────────────────────────────────────────────────
    @app.route("/api/cdm/delete-drive/<int:drive_id>", methods=["POST"])
    def cdm_delete_drive(drive_id):
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

    # ── Drive inline editing ─────────────────────────────────────────────
    @app.route("/api/cdm/drive/<int:drive_id>", methods=["PUT"])
    def cdm_update_drive(drive_id):
        data = request.get_json()
        if not data or "field" not in data:
            return jsonify({"error": "Missing field"}), 400

        field = data["field"]
        value = data.get("value")

        if field not in CDM_EDITABLE_FIELDS:
            return jsonify({"error": f"Field '{field}' is not editable"}), 400

        if value is not None and str(value).strip() == "":
            value = None

        if field in ("jd_received_date", "process_date") and value:
            value = parse_date_field(value)

        if field == "data_shared":
            if isinstance(value, str):
                value = True if value.strip().upper() in ("Y", "YES", "TRUE", "1") else False

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
                "SELECT c.company_name FROM company_drives d "
                "JOIN companies c ON d.company_id = c.company_id WHERE d.drive_id = %s",
                (drive_id,),
            )
            company_row = cursor.fetchone()
            company_name = company_row["company_name"] if company_row else ""

            cursor.execute(
                f"UPDATE company_drives SET `{field}` = %s WHERE drive_id = %s",
                (value, drive_id),
            )

            cursor.execute(
                "INSERT INTO cdm_edit_log (drive_id, company_name, field_name, old_value, new_value, changed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (drive_id, company_name, field,
                 str(old_value) if old_value is not None else None,
                 str(value) if value is not None else None,
                 datetime.now()),
            )

            conn.commit()
            cursor.close()
            conn.close()

            display_value = value
            if field == "data_shared":
                display_value = "Yes" if value else "No"

            return jsonify({"ok": True, "drive_id": drive_id, "field": field, "value": display_value})
        except Error as e:
            return jsonify({"error": str(e)}), 500

    # ── CDM Change Log API ───────────────────────────────────────────────
    @app.route("/api/cdm/edit-log")
    def api_cdm_edit_log():
        limit = request.args.get("limit", 200, type=int)
        page = request.args.get("page", 1, type=int)
        drive_id = request.args.get("drive_id", None, type=int)
        offset = (page - 1) * limit
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            if drive_id:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM cdm_edit_log WHERE drive_id = %s", (drive_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) as cnt FROM cdm_edit_log")
            total_count = cursor.fetchone()["cnt"]

            if drive_id:
                cursor.execute(
                    "SELECT * FROM cdm_edit_log WHERE drive_id = %s ORDER BY changed_at DESC LIMIT %s OFFSET %s",
                    (drive_id, limit, offset),
                )
            else:
                cursor.execute(
                    "SELECT * FROM cdm_edit_log ORDER BY changed_at DESC LIMIT %s OFFSET %s",
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

    # ── HR Management API ────────────────────────────────────────────────
    @app.route("/api/cdm/hr/<int:hr_id>", methods=["PUT"])
    def cdm_update_hr(hr_id):
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

    # ── Company search ───────────────────────────────────────────────────
    @app.route("/api/cdm/search")
    def cdm_search():
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

    # ── Company CRUD ─────────────────────────────────────────────────────
    @app.route("/api/cdm/company", methods=["POST"])
    def cdm_create_company():
        data = request.get_json(silent=True) or {}
        name = (data.get("company_name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Company name is required."}), 400
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
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
        try:
            conn = get_connection()
            cursor = conn.cursor()
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

    # ── CDM Analytics API ────────────────────────────────────────────────
    @app.route("/api/cdm/analytics")
    def cdm_analytics():
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT COUNT(*) AS total_drives FROM company_drives")
            total_drives = cursor.fetchone()["total_drives"]
            cursor.execute("SELECT COUNT(*) AS total_companies FROM companies")
            total_companies = cursor.fetchone()["total_companies"]

            cursor.execute(
                "SELECT IFNULL(status, 'Upcoming') AS status, COUNT(*) AS cnt "
                "FROM company_drives GROUP BY status"
            )
            status_dist = {r["status"]: r["cnt"] for r in cursor.fetchall()}

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

            cursor.execute("""
                SELECT d.received_by, COUNT(ds.reg_no) AS selections
                FROM company_drives d
                JOIN drive_students ds ON d.drive_id = ds.drive_id
                WHERE ds.status = 'Selected'
                  AND d.received_by IS NOT NULL AND d.received_by != ''
                GROUP BY d.received_by
            """)
            team_selections = {r["received_by"]: r["selections"] for r in cursor.fetchall()}

            cursor.execute("""
                SELECT d.received_by, d.ctc_text
                FROM company_drives d
                WHERE d.received_by IS NOT NULL AND d.received_by != ''
                  AND d.ctc_text IS NOT NULL AND d.ctc_text != ''
            """)
            team_ctc_rows = cursor.fetchall()
            team_ctc_map = {}
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

    # ── Student Linking API ──────────────────────────────────────────────
    @app.route("/api/cdm/drive/<int:drive_id>/students", methods=["GET"])
    def cdm_drive_students(drive_id):
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

    # ── Bulk Student Import ──────────────────────────────────────────────
    @app.route("/api/cdm/drive/<int:drive_id>/students/bulk", methods=["POST"])
    def cdm_bulk_link_students(drive_id):
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file uploaded"}), 400
        f = request.files["file"]
        if not f.filename or not f.filename.lower().endswith((".xlsx", ".xls")):
            return jsonify({"ok": False, "error": "Only .xlsx/.xls files accepted"}), 400
        try:
            import openpyxl

            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            header = next(rows_iter, None)
            if header is None:
                return jsonify({"ok": False, "error": "Empty file"}), 400
            header_lower = [str(h).strip().lower() if h else "" for h in header]
            reg_col = None
            for i, h in enumerate(header_lower):
                if h in ("reg number", "reg_number", "reg no", "reg_no", "registration number", "registration_number"):
                    reg_col = i
                    break
            if reg_col is None:
                return jsonify({"ok": False, "error": "Column 'Reg Number' not found in header"}), 400
            file_regs = []
            for row in rows_iter:
                if row[reg_col] is not None:
                    val = str(row[reg_col]).strip()
                    if val:
                        file_regs.append(val)
            wb.close()
            if not file_regs:
                return jsonify({"ok": False, "error": "No registration numbers found in file"}), 400

            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT reg_no, student_name, course, department FROM students")
            all_students = cursor.fetchall()
            lookup = {}
            for s in all_students:
                lookup[s["reg_no"].upper()] = s

            linked = []
            not_found = []
            already = []
            for reg in file_regs:
                student = lookup.get(reg.upper())
                if not student:
                    not_found.append(reg)
                    continue
                try:
                    cursor.execute(
                        "INSERT INTO drive_students (drive_id, reg_no, status, current_round) "
                        "VALUES (%s, %s, %s, %s)",
                        (drive_id, student["reg_no"], "Applied", 0),
                    )
                    linked.append({
                        "reg_no": student["reg_no"],
                        "student_name": student["student_name"],
                        "course": student["course"],
                        "department": student["department"],
                    })
                except Exception:
                    already.append(student["reg_no"])
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({
                "ok": True,
                "linked": len(linked),
                "not_found": not_found,
                "already_linked": already,
                "students": linked,
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/cdm/student-template")
    def cdm_student_template():
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(["Reg Number", "Student Name"])
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 30
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="student_import_template.xlsx",
        )

    # ── Round Management API ─────────────────────────────────────────────
    @app.route("/api/cdm/drive/<int:drive_id>/rounds", methods=["GET"])
    def cdm_drive_rounds(drive_id):
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

    # ── Calendar Data API ────────────────────────────────────────────────
    @app.route("/api/cdm/calendar")
    def cdm_calendar():
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

    # ── Placement Source Analytics ────────────────────────────────────────
    @app.route("/api/cdm/placement-sources")
    def cdm_placement_sources():
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
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

    # ── Student Search (for linking UI) ──────────────────────────────────
    @app.route("/api/cdm/search-students")
    def cdm_search_students():
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
