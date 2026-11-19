from flask import Blueprint, render_template, jsonify
from app import semaphore_manager

semaphore_bp = Blueprint("semaphore", __name__)


@semaphore_bp.route("/semaphore-management")
def semaphore_page():
    """Render the dedicated Semaphore Management page."""
    return render_template("semaphore_management.html")


@semaphore_bp.route("/api/semaphore-data")
def semaphore_data():
    """Return live semaphore telemetry: capacity, permits, allocations, and queue."""
    status = semaphore_manager.get_system_status()
    # Strip any mutex fields to ensure clean separation as requested
    return jsonify({
        "total_capacity": status["total_capacity"],
        "total_computers": status["total_computers"],
        "available_permits": status["available_permits"],
        "acquired_permits": status["acquired_permits"],
        "active_allocations": status["occupied_count"],
        "occupied_count": status["occupied_count"],
        "waiting_students": status["waiting_count"],
        "waiting_count": status["waiting_count"],
        "workstations": status["workstations"],
        "allocations": status["allocations"],
        "waiting": status["waiting"]
    })
