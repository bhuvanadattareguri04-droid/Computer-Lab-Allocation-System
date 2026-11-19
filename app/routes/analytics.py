from flask import Blueprint, render_template, jsonify
from app import semaphore_manager
from app.database import get_db_connection

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics_page():
    return render_template("analytics.html")


@analytics_bp.route("/api/analytics")
def get_analytics():
    conn = get_db_connection()
    try:
        status = semaphore_manager.get_system_status()

        # Total allocations
        total_allocations = conn.execute("""
            SELECT COUNT(*) FROM allocation_history WHERE action IN ('Allocated', 'Reassigned')
        """).fetchone()[0]

        # Total logouts
        total_logouts = conn.execute("""
            SELECT COUNT(*) FROM allocation_history WHERE action = 'Logout'
        """).fetchone()[0]

        # Total reassignments
        total_reassigned = conn.execute("""
            SELECT COUNT(*) FROM allocation_history WHERE action = 'Reassigned'
        """).fetchone()[0]

        # Usage per workstation (dynamically fetched from workstations table)
        ws_rows = conn.execute("SELECT pc_id FROM workstations ORDER BY pc_id ASC").fetchall()
        pc_usage = {row["pc_id"]: 0 for row in ws_rows}

        usage_rows = conn.execute("""
            SELECT pc_id, COUNT(*) as usage_count
            FROM allocation_history
            WHERE action IN ('Allocated', 'Reassigned')
            GROUP BY pc_id
        """).fetchall()

        for row in usage_rows:
            pc_usage[row["pc_id"]] = row["usage_count"]

        # Action breakdown
        action_rows = conn.execute("""
            SELECT action, COUNT(*) as count
            FROM allocation_history
            GROUP BY action
        """).fetchall()

        action_breakdown = {row["action"]: row["count"] for row in action_rows}

        return jsonify({
            "total_computers": status["total_computers"],
            "occupied_count": status["occupied_count"],
            "available_count": len(status["available"]),
            "waiting_count": status["waiting_count"],
            "total_allocations": total_allocations,
            "total_logouts": total_logouts,
            "total_reassigned": total_reassigned,
            "workstation_usage": pc_usage,
            "action_breakdown": action_breakdown
        })

    finally:
        conn.close()
