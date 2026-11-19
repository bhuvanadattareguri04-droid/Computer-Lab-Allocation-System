from flask import Blueprint, render_template, jsonify
from app.database import get_db_connection

history_bp = Blueprint("history", __name__)


@history_bp.route("/history")
def history_page():
    return render_template("history.html")


@history_bp.route("/api/history")
def get_history():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                h.history_id,
                h.student_id,
                h.pc_id,
                h.action,
                h.event_time,
                s.student_name
            FROM allocation_history h
            LEFT JOIN students s ON h.student_id = s.student_id
            ORDER BY h.history_id DESC
        """).fetchall()

        history_list = [
            {
                "history_id": row["history_id"],
                "student_id": row["student_id"],
                "student_name": row["student_name"] or row["student_id"],
                "workstation": row["pc_id"],
                "action": row["action"],
                "event_time": row["event_time"]
            }
            for row in rows
        ]

        return jsonify({
            "total_records": len(history_list),
            "history": history_list
        })

    finally:
        conn.close()
