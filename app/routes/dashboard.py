from flask import Blueprint, render_template, jsonify
from app import semaphore_manager
from app.database import get_db_connection

dashboard_bp = Blueprint("dashboard", __name__)


# Dashboard page
@dashboard_bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


# Live dashboard & semaphore monitoring board statistics API
@dashboard_bp.route("/api/dashboard-data", methods=["GET"])
def dashboard_data():
    status = semaphore_manager.get_system_status()
    conn = get_db_connection()

    try:
        # Get 10 most recent allocation history events
        history = conn.execute("""
            SELECT student_id, pc_id, action, event_time
            FROM allocation_history
            ORDER BY history_id DESC
            LIMIT 10
        """).fetchall()

        history_data = [
            {
                "student_id": row["student_id"],
                "workstation": row["pc_id"],
                "action": row["action"],
                "time": row["event_time"]
            }
            for row in history
        ]

        return jsonify({
            # Standard statistics
            "total_computers": status["total_computers"],
            "total_capacity": status["total_capacity"],
            "occupied_count": status["occupied_count"],
            "available_count": status["available_count"],
            "waiting_count": status["waiting_count"],
            "waiting_students": status["waiting_students"],
            "available": status["available"],
            "allocations": status["allocations"],
            "waiting": status["waiting"],
            "history": history_data,
            # Concurrency & Semaphore Board metrics
            "available_permits": status["available_permits"],
            "acquired_permits": status["acquired_permits"],
            "mutex_locked": status["mutex_locked"],
            "mutex_status": status["mutex_status"],
            "workstations": status["workstations"]
        })

    finally:
        conn.close()


@dashboard_bp.route("/api/semaphore-status", methods=["GET"])
def semaphore_status():
    """Dedicated endpoint returning live semaphore and mutex metrics."""
    return jsonify(semaphore_manager.get_system_status())
