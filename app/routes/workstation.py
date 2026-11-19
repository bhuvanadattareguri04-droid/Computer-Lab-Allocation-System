from flask import Blueprint, render_template, jsonify, request
from app import semaphore_manager
from app.database import get_db_connection

workstation_bp = Blueprint("workstation", __name__)


@workstation_bp.route("/workstations")
def workstations_page():
    return render_template("workstations.html")


@workstation_bp.route("/api/workstations")
def get_workstations():
    conn = get_db_connection()

    try:
        workstations = conn.execute("""
            SELECT
                w.pc_id,
                w.status,
                a.student_id,
                a.login_time,
                s.student_name
            FROM workstations w
            LEFT JOIN allocations a ON w.pc_id = a.pc_id
            LEFT JOIN students s ON a.student_id = s.student_id
            ORDER BY w.pc_id ASC
        """).fetchall()

        ws_list = [
            {
                "pc_id": row["pc_id"],
                "status": row["status"],
                "student_id": row["student_id"],
                "student_name": row["student_name"],
                "login_time": row["login_time"]
            }
            for row in workstations
        ]

        total = len(ws_list)
        available = sum(1 for w in ws_list if w["status"] == "Available")
        occupied = total - available

        return jsonify({
            "total_computers": total,
            "total_capacity": total,
            "available_count": available,
            "occupied_count": occupied,
            "workstations": ws_list
        })

    finally:
        conn.close()


@workstation_bp.route("/api/workstations/add", methods=["POST"])
def add_workstation():
    """Admin endpoint to dynamically add workstations (supports bulk count)."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    raw_count = data.get("count", 1)
    result = semaphore_manager.add_workstations(raw_count)
    status_code = 400 if result.get("status") == "error" else 200
    return jsonify(result), status_code


@workstation_bp.route("/api/workstations/remove", methods=["POST"])
def remove_workstation():
    """Admin endpoint to dynamically remove an available workstation."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    pc_id = data.get("pc_id")
    result = semaphore_manager.remove_workstation(pc_id)
    status_code = 400 if result.get("status") == "error" else 200
    return jsonify(result), status_code
