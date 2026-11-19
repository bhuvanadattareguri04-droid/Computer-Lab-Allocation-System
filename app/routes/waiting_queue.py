from flask import Blueprint, render_template, jsonify
from app.database import get_db_connection

waiting_queue_bp = Blueprint("waiting_queue", __name__)


@waiting_queue_bp.route("/waiting-queue")
def waiting_queue_page():
    return render_template("waiting_queue.html")


@waiting_queue_bp.route("/api/waiting-queue")
def get_waiting_queue():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                queue_id,
                student_id,
                request_time
            FROM waiting_queue
            ORDER BY queue_id ASC
        """).fetchall()

        queue_data = [
            {
                "position": idx + 1,
                "queue_id": row["queue_id"],
                "student_id": row["student_id"],
                "request_time": row["request_time"]
            }
            for idx, row in enumerate(rows)
        ]

        # Calculate actual dynamic lab capacity from database records
        total_workstations = conn.execute("SELECT COUNT(*) FROM workstations").fetchone()[0]
        available_workstations = conn.execute("SELECT COUNT(*) FROM workstations WHERE status = 'Available'").fetchone()[0]
        occupied_workstations = total_workstations - available_workstations

        return jsonify({
            "waiting_count": len(queue_data),
            "total_capacity": total_workstations,
            "occupied_count": occupied_workstations,
            "available_count": available_workstations,
            "queue": queue_data
        })

    finally:
        conn.close()
