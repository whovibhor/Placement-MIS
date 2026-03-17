# routes_data.py — Student data routes
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal

from flask import (
    flash, jsonify, redirect, render_template, request,
    send_from_directory, url_for,
)
from mysql.connector import Error

from helpers import (
    EDITABLE_COLUMNS, NUMERIC_FLOAT_COLS, NUMERIC_INT_COLS,
    get_connection, normalize_row, normalize_rows, to_float_or_none,
    to_int_or_none, compute_analytics, get_cached_analytics,
    save_analytics_cache, invalidate_analytics_cache,
)


def register_data_routes(app):
    """Register all student-data routes on the Flask app."""

    # ── Data page ────────────────────────────────────────────────────────
    @app.route("/students")
    def data_page():
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
        return render_template("students.html", students_json=rows, analytics=analytics)

    @app.route("/data")
    def data_page_legacy_redirect():
        return redirect(url_for("data_page"), code=301)

    # ── Inline Editing API ───────────────────────────────────────────────
    @app.route("/api/student/<reg_no>", methods=["PUT"])
    def update_student(reg_no):
        data = request.get_json()
        if not data or "field" not in data:
            return jsonify({"error": "Missing field"}), 400

        field = data["field"]
        value = data.get("value")

        if field not in EDITABLE_COLUMNS:
            return jsonify({"error": f"Field '{field}' is not editable"}), 400

        if value is not None and str(value).strip() == "":
            value = None

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

            if str(old_value or "") == str(value or ""):
                cursor.close()
                conn.close()
                return jsonify({"ok": True, "reg_no": reg_no, "field": field, "value": value, "unchanged": True})

            cursor.execute(
                f"UPDATE students SET `{field}` = %s WHERE reg_no = %s",
                (value, reg_no),
            )

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

    # ── Delete student ───────────────────────────────────────────────────
    @app.route("/api/student/<reg_no>", methods=["DELETE"])
    def delete_student(reg_no):
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

    # ── Student Profile ──────────────────────────────────────────────────
    @app.route("/student/<reg_no>")
    def student_profile(reg_no):
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM students WHERE reg_no = %s", (reg_no,))
            student = cursor.fetchone()
            if not student:
                flash("Student not found.", "danger")
                return redirect(url_for("dashboard"))
            normalize_row(student)

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

    # ── File upload / serve / delete ─────────────────────────────────────
    @app.route("/student/<reg_no>/upload-file", methods=["POST"])
    def upload_student_file(reg_no):
        file = request.files.get("file")
        file_type = request.form.get("file_type", "resume")

        if not file or file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("student_profile", reg_no=reg_no))

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
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.route("/student/<reg_no>/delete-file/<int:file_id>", methods=["POST"])
    def delete_student_file(reg_no, file_id):
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT stored_name FROM student_files WHERE id = %s AND reg_no = %s", (file_id, reg_no))
            row = cursor.fetchone()
            if row:
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

    # ── Bulk update (student profile) ────────────────────────────────────
    @app.route("/api/student/<reg_no>/bulk-update", methods=["PUT"])
    def bulk_update_student(reg_no):
        data = request.get_json()
        if not data or "fields" not in data:
            return jsonify({"error": "Missing fields"}), 400

        fields = data["fields"]
        invalid = [f for f in fields if f not in EDITABLE_COLUMNS]
        if invalid:
            return jsonify({"error": f"Non-editable fields: {invalid}"}), 400

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

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

                if value is not None:
                    if field in NUMERIC_FLOAT_COLS:
                        value = to_float_or_none(value)
                    elif field in NUMERIC_INT_COLS:
                        value = to_int_or_none(value)

                old_val = current.get(field)
                if str(old_val or "") == str(value or ""):
                    continue

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

    # ── Change Log API ───────────────────────────────────────────────────
    @app.route("/api/edit-log")
    def api_edit_log():
        limit = request.args.get("limit", 200, type=int)
        page = request.args.get("page", 1, type=int)
        reg_no = request.args.get("reg_no", None)
        offset = (page - 1) * limit
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

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
                    r["changed_at"] = r["changed_at"].strftime("%d %B %Y, %I:%M %p")
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

    # ── API: all students / search ───────────────────────────────────────
    @app.route("/api/students")
    def api_students():
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
