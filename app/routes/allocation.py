from flask import Blueprint, request, jsonify
from app import semaphore_manager

allocation_bp = Blueprint("allocation", __name__)


@allocation_bp.route("/api/allocate", methods=["POST"])
def allocate():
    # Support both JSON payload and standard form data
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    student_id = data.get("student_id", "").strip()
    student_name = data.get("student_name", "").strip() or None

    if not student_id:
        return jsonify({
            "status": "error",
            "message": "Student ID is required."
        }), 400

    result = semaphore_manager.request_computer(student_id, student_name)
    status_code = 400 if result.get("status") == "error" else 200

    return jsonify(result), status_code


@allocation_bp.route("/api/logout", methods=["POST"])
def logout():
    # Support both JSON payload and standard form data
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

    result = semaphore_manager.logout_student(student_id)
    status_code = 400 if result.get("status") == "error" else 200

    return jsonify(result), status_code


@allocation_bp.route("/api/status", methods=["GET"])
def system_status():
    status = semaphore_manager.get_system_status()
    return jsonify(status)
