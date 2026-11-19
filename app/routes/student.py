import re
from flask import Blueprint, render_template, request, jsonify
from app import semaphore_manager
from app.database import get_db_connection

student_bp = Blueprint("student", __name__)


@student_bp.route("/students")
def students_page():
    """Render Student Management page."""
    return render_template("students.html")


@student_bp.route("/api/students", methods=["GET"])
def get_students():
    """Retrieve all students with their actual real-time status."""
    conn = get_db_connection()
    try:
        students = conn.execute("""
            SELECT
                s.student_id,
                s.created_at,
                a.pc_id as active_pc,
                q.queue_id as waiting_id
            FROM students s
            LEFT JOIN allocations a ON s.student_id = a.student_id
            LEFT JOIN waiting_queue q ON s.student_id = q.student_id
            ORDER BY s.student_id ASC
        """).fetchall()

        student_list = []
        for s in students:
            if s["active_pc"]:
                current_status = f"Using {s['active_pc']}"
                status_type = "active"
            elif s["waiting_id"]:
                current_status = "Waiting"
                status_type = "waiting"
            else:
                current_status = "Logged Out"
                status_type = "idle"

            student_list.append({
                "student_id": s["student_id"],
                "created_at": s["created_at"],
                "current_status": current_status,
                "status_type": status_type,
                "active_pc": s["active_pc"]
            })

        return jsonify({
            "total_students": len(student_list),
            "students": student_list
        })

    finally:
        conn.close()


@student_bp.route("/api/students", methods=["POST"])
def add_student():
    """
    Register a student using Student ID and immediately trigger automatic allocation.
    If workstations are available, student is allocated.
    Otherwise, student enters the FIFO waiting queue.
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    student_id = data.get("student_id", "").strip()

    if not student_id:
        return jsonify({
            "status": "error",
            "message": "Student ID is required."
        }), 400

    conn = get_db_connection()
    try:
        # Check duplicate active allocation or waiting queue entry
        active = conn.execute("SELECT pc_id FROM allocations WHERE student_id = ?", (student_id,)).fetchone()
        if active:
            return jsonify({
                "status": "error",
                "message": f"Student '{student_id}' already has an active allocation on {active['pc_id']}."
            }), 400

        waiting = conn.execute("SELECT queue_id FROM waiting_queue WHERE student_id = ?", (student_id,)).fetchone()
        if waiting:
            return jsonify({
                "status": "error",
                "message": f"Student '{student_id}' is already in the FIFO waiting queue."
            }), 400

        # Check existing registration
        existing = conn.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if existing:
            return jsonify({
                "status": "error",
                "message": f"Student with ID '{student_id}' already exists in database."
            }), 400

        # Save student in SQLite
        conn.execute(
            "INSERT INTO students (student_id, student_name) VALUES (?, ?)",
            (student_id, student_id)
        )
        conn.commit()

    finally:
        conn.close()

    # Automatically trigger workstation allocation request immediately
    alloc_result = semaphore_manager.request_computer(student_id)

    if alloc_result.get("status") == "allocated":
        msg = f"Student {student_id} registered and immediately allocated {alloc_result['workstation']}."
    elif alloc_result.get("status") == "waiting":
        msg = f"Student {student_id} registered. All workstations are occupied, added to FIFO waiting queue at position #{alloc_result['queue_position']}."
    else:
        msg = alloc_result.get("message", "Processed registration request.")

    return jsonify({
        "status": "success",
        "student_id": student_id,
        "allocation_status": alloc_result.get("status"),
        "workstation": alloc_result.get("workstation"),
        "queue_position": alloc_result.get("queue_position"),
        "message": msg
    }), 201


@student_bp.route("/api/students/<student_id>", methods=["DELETE"])
def delete_student(student_id):
    """
    Remove an individual student record immediately without browser popup.
    Blocks removal if student has an active allocation or waiting queue entry.
    """
    conn = get_db_connection()
    try:
        # 1. Check if student exists
        student = conn.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if not student:
            return jsonify({
                "status": "error",
                "message": f"Student '{student_id}' not found."
            }), 404

        # 2. Block removal if student currently holds a workstation
        active = conn.execute("SELECT pc_id FROM allocations WHERE student_id = ?", (student_id,)).fetchone()
        if active:
            return jsonify({
                "status": "error",
                "message": f"Cannot remove student {student_id}: currently using workstation {active['pc_id']}. Log out the student before removing."
            }), 400

        # 3. Block removal if student is currently in the waiting queue
        waiting = conn.execute("SELECT queue_id FROM waiting_queue WHERE student_id = ?", (student_id,)).fetchone()
        if waiting:
            pos = conn.execute(
                "SELECT COUNT(*) FROM waiting_queue WHERE queue_id <= ?",
                (waiting["queue_id"],)
            ).fetchone()[0]
            return jsonify({
                "status": "error",
                "message": f"Cannot remove student {student_id}: currently waiting in queue at position #{pos}."
            }), 400

        # 4. Eligible for removal
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Student {student_id} removed successfully."
        })

    finally:
        conn.close()


@student_bp.route("/api/students/bulk", methods=["POST"])
def bulk_add_students():
    """
    Bulk-register multiple students in one operation.

    Workflow for each student:
      1. Generate unique sequential Student IDs (e.g. STU-001, STU-002 ...).
      2. Save each student in SQLite.
      3. Immediately trigger automatic workstation allocation (semaphore.acquire).
      4. If a workstation is available → allocate it.
         If all workstations are occupied → place student in FIFO waiting queue.
      5. Return per-student results and overall summary.
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    # --- Validate count -------------------------------------------------------
    raw_count = data.get("count", "")
    try:
        if isinstance(raw_count, bool):
            raise ValueError()
        # Reject floats (e.g. 2.5 sent as JSON number) or strings with decimals
        if isinstance(raw_count, float) and not raw_count.is_integer():
            raise ValueError()
        count = int(float(raw_count)) if isinstance(raw_count, float) else int(raw_count)
        # Guard against decimal strings like "3.5"
        raw_str = str(raw_count).strip()
        if "." in raw_str or "," in raw_str:
            # Allow only if it is effectively an integer (e.g. "5.0")
            if float(raw_str) != int(float(raw_str)):
                raise ValueError()
        if count <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Invalid quantity. Please enter a positive whole number greater than 0."
        }), 400

    conn = get_db_connection()
    try:
        # --- Determine next sequential ID prefix and number -------------------
        # Inspect all existing student IDs to find the highest trailing integer.
        # Supported formats: STU001, STU-001, STU_001, S001, 001, etc.
        all_ids = [row["student_id"] for row in
                   conn.execute("SELECT student_id FROM students").fetchall()]

        max_num = 0
        prefix = "STU-"
        num_width = 3

        for sid in all_ids:
            # Extract trailing digits from the ID
            m = re.search(r"(\d+)$", sid)
            if m:
                n = int(m.group(1))
                if n > max_num:
                    max_num = n
                    # Derive prefix and width from this ID
                    prefix_candidate = sid[: len(sid) - len(m.group(1))]
                    if prefix_candidate:
                        prefix = prefix_candidate
                    num_width = max(len(m.group(1)), 3)

        # Also scan existing IDs to avoid any collision
        existing_ids_set = set(all_ids)

    finally:
        conn.close()

    # --- Register each student and trigger allocation -------------------------
    results = []
    allocated_count = 0
    waiting_count = 0
    skipped_count = 0

    current_num = max_num
    generated = 0

    while generated < count:
        current_num += 1
        new_id = f"{prefix}{current_num:0{num_width}d}"

        # Skip if ID already exists (edge case from non-sequential existing IDs)
        if new_id in existing_ids_set:
            skipped_count += 1
            continue

        # Save student
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO students (student_id, student_name) VALUES (?, ?)",
                (new_id, new_id)
            )
            conn.commit()
            existing_ids_set.add(new_id)
        finally:
            conn.close()

        # Trigger automatic allocation
        alloc = semaphore_manager.request_computer(new_id)

        status = alloc.get("status")
        if status == "allocated":
            allocated_count += 1
            results.append({
                "student_id": new_id,
                "allocation_status": "allocated",
                "workstation": alloc.get("workstation"),
                "current_status": f"Using {alloc.get('workstation')}"
            })
        elif status == "waiting":
            waiting_count += 1
            results.append({
                "student_id": new_id,
                "allocation_status": "waiting",
                "queue_position": alloc.get("queue_position"),
                "current_status": "Waiting"
            })
        else:
            results.append({
                "student_id": new_id,
                "allocation_status": status,
                "current_status": "Unknown"
            })

        generated += 1

    summary = (
        f"Bulk registration complete: {count} student(s) registered. "
        f"{allocated_count} allocated to workstations, "
        f"{waiting_count} placed in FIFO waiting queue."
    )

    return jsonify({
        "status": "success",
        "registered_count": generated,
        "allocated_count": allocated_count,
        "waiting_count": waiting_count,
        "results": results,
        "message": summary
    }), 201


@student_bp.route("/api/students/remove-all", methods=["POST", "DELETE"])
def remove_all_eligible_students():
    """
    Remove all eligible students in one operation.
    Protects students with active allocations or waiting queue entries.
    """
    conn = get_db_connection()
    try:
        all_students = conn.execute("SELECT student_id FROM students").fetchall()

        removed_count = 0
        skipped_count = 0

        for row in all_students:
            sid = row["student_id"]
            active = conn.execute("SELECT pc_id FROM allocations WHERE student_id = ?", (sid,)).fetchone()
            waiting = conn.execute("SELECT queue_id FROM waiting_queue WHERE student_id = ?", (sid,)).fetchone()

            if active or waiting:
                skipped_count += 1
            else:
                conn.execute("DELETE FROM students WHERE student_id = ?", (sid,))
                removed_count += 1

        conn.commit()

        return jsonify({
            "status": "success",
            "removed_count": removed_count,
            "skipped_count": skipped_count,
            "message": f"Successfully removed {removed_count} eligible student record(s). Skipped {skipped_count} student(s) with active allocations or waiting queue entries."
        })

    finally:
        conn.close()
