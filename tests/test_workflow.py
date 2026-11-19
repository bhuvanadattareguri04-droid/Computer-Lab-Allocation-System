"""
Workflow & Semaphore Verification Test Suite
LabSpace – Computer Lab Allocation System
=========================================
Tests the 10 specific workflow scenarios required:
1. Add a new student through the Allocation page.
2. Verify the student is immediately allocated if a workstation is available.
3. Fill all workstations.
4. Add another student and verify FIFO waiting.
5. Add a new workstation.
6. Verify the first waiting student automatically receives it.
7. Log out a student.
8. Verify the next waiting student receives the released workstation.
9. Verify the Semaphore Management page displays correct permit counts.
10. Verify the dashboard statistics update correctly.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_workflow_tests():
    print("=" * 75)
    print("LABSPACE: 10-STEP ALLOCATION WORKFLOW & SEMAPHORE VERIFICATION")
    print("Operating Systems & Computer Networks Subject")
    print("=" * 75)

    # Use isolated test database to preserve production records
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    test_db = tmp_file.name
    tmp_file.close()

    os.environ["LABSPACE_DB_PATH"] = test_db

    try:
        from app import create_app
        import app.database as db_mod
        db_mod.DB_PATH = Path(test_db)
        import app.semaphore_manager as sem_mod

        app = create_app()
        client = app.test_client()
        sem_mod.reset_semaphore()

        # -------------------------------------------------------------
        # Scenario 1: Add a new student through the Allocation page
        # -------------------------------------------------------------
        print("\n[Scenario 1] Adding a new student through the Allocation page...")
        res1 = client.post("/api/allocate", json={
            "student_id": "STU_W1",
            "student_name": "Alice Workflow"
        })
        assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
        data1 = res1.get_json()
        print(f"  -> Allocation Request: student='{data1['student']}', status='{data1['status']}'")

        # -------------------------------------------------------------
        # Scenario 2: Verify student is immediately allocated if PC is available
        # -------------------------------------------------------------
        print("\n[Scenario 2] Verifying immediate workstation allocation...")
        assert data1["status"] == "allocated"
        assert data1["workstation"] == "PC-01"
        assert "allocated workstation PC-01" in data1["message"]

        # Verify auto-registration in students table without prior manual add
        students_res = client.get("/api/students").get_json()
        registered_ids = [s["student_id"] for s in students_res["students"]]
        assert "STU_W1" in registered_ids
        print("  -> PASS: STU_W1 immediately allocated PC-01 and auto-registered in students table.")

        # -------------------------------------------------------------
        # Scenario 3: Fill all workstations
        # -------------------------------------------------------------
        print("\n[Scenario 3] Filling remaining 4 workstations (PC-02 through PC-05)...")
        for i in range(2, 6):
            r = client.post("/api/allocate", json={
                "student_id": f"STU_W{i}",
                "student_name": f"Student {i}"
            }).get_json()
            assert r["status"] == "allocated"
            assert r["workstation"] == f"PC-0{i}"
            print(f"  -> Allocated STU_W{i} to {r['workstation']}")

        status_full = sem_mod.get_system_status()
        assert status_full["occupied_count"] == 5
        assert status_full["available_count"] == 0
        assert status_full["available_permits"] == 0
        print("  -> PASS: All 5 workstations filled. Capacity is 100% utilized.")

        # -------------------------------------------------------------
        # Scenario 4: Add another student and verify FIFO waiting
        # -------------------------------------------------------------
        print("\n[Scenario 4] Adding 6th student (STU_W6) and 7th student (STU_W7)...")
        r6 = client.post("/api/allocate", json={"student_id": "STU_W6", "student_name": "Student Six"}).get_json()
        assert r6["status"] == "waiting"
        assert r6["queue_position"] == 1
        print(f"  -> STU_W6 placed in waiting queue at Position #{r6['queue_position']}")

        r7 = client.post("/api/allocate", json={"student_id": "STU_W7", "student_name": "Student Seven"}).get_json()
        assert r7["status"] == "waiting"
        assert r7["queue_position"] == 2
        print(f"  -> STU_W7 placed in waiting queue at Position #{r7['queue_position']}")

        q_status = client.get("/api/waiting-queue").get_json()
        assert q_status["waiting_count"] == 2
        assert q_status["queue"][0]["student_id"] == "STU_W6"
        assert q_status["queue"][1]["student_id"] == "STU_W7"
        print("  -> PASS: Both students queued in strict FIFO order.")

        # -------------------------------------------------------------
        # Scenario 5: Add a new workstation
        # -------------------------------------------------------------
        print("\n[Scenario 5] Dynamically adding a new workstation (PC-06)...")
        add_ws_res = client.post("/api/workstations/add").get_json()
        assert add_ws_res["status"] == "success"
        assert add_ws_res["workstation"] == "PC-06"
        print(f"  -> Add Result: {add_ws_res['message']}")

        # -------------------------------------------------------------
        # Scenario 6: Verify first waiting student automatically receives it
        # -------------------------------------------------------------
        print("\n[Scenario 6] Verifying STU_W6 automatically received PC-06...")
        assert add_ws_res["action"] == "allocated_to_waiting"
        assert add_ws_res["student"] == "STU_W6"

        # Verify STU_W6 is now allocated and STU_W7 moved to Position #1
        status_after_ws = sem_mod.get_system_status()
        assert status_after_ws["allocations"]["STU_W6"] == "PC-06"
        assert status_after_ws["waiting_count"] == 1
        assert status_after_ws["waiting"][0] == "STU_W7"
        print("  -> PASS: PC-06 automatically given to STU_W6. STU_W7 promoted to Queue Position #1.")

        # -------------------------------------------------------------
        # Scenario 7: Log out a student
        # -------------------------------------------------------------
        print("\n[Scenario 7] Logging out student STU_W1 (releasing PC-01)...")
        logout_res = client.post("/api/logout", json={"student_id": "STU_W1"}).get_json()
        assert logout_res["status"] == "reassigned"
        print(f"  -> Logout Result: {logout_res['message']}")

        # -------------------------------------------------------------
        # Scenario 8: Verify next waiting student receives released workstation
        # -------------------------------------------------------------
        print("\n[Scenario 8] Verifying STU_W7 automatically received PC-01...")
        assert logout_res["next_student"] == "STU_W7"
        assert logout_res["workstation"] == "PC-01"

        status_after_logout = sem_mod.get_system_status()
        assert status_after_logout["allocations"]["STU_W7"] == "PC-01"
        assert status_after_logout["waiting_count"] == 0
        print("  -> PASS: Released PC-01 automatically reassigned to STU_W7. Waiting queue is empty.")

        # -------------------------------------------------------------
        # Scenario 9: Verify Semaphore Management page displays correct permit counts
        # -------------------------------------------------------------
        print("\n[Scenario 9] Verifying Semaphore Management telemetry API (/api/semaphore-data)...")
        sem_res = client.get("/api/semaphore-data")
        assert sem_res.status_code == 200
        sem_data = sem_res.get_json()

        print(f"  -> Total Capacity: {sem_data['total_capacity']}")
        print(f"  -> Available Permits: {sem_data['available_permits']}")
        print(f"  -> Acquired Permits: {sem_data['acquired_permits']}")
        print(f"  -> Active Allocations: {sem_data['active_allocations']}")
        print(f"  -> Waiting Students: {sem_data['waiting_students']}")

        assert sem_data["total_capacity"] == 6
        assert sem_data["available_permits"] == 0
        assert sem_data["acquired_permits"] == 6
        assert sem_data["active_allocations"] == 6
        assert sem_data["waiting_students"] == 0
        assert len(sem_data["workstations"]) == 6

        # Check visual indicator mappings: all 6 must be occupied (red)
        for ws in sem_data["workstations"]:
            assert ws["status"] == "Occupied"

        # Now free one workstation (STU_W2) and re-check permit counts
        client.post("/api/logout", json={"student_id": "STU_W2"})
        sem_data2 = client.get("/api/semaphore-data").get_json()
        assert sem_data2["available_permits"] == 1
        assert sem_data2["acquired_permits"] == 5
        assert sem_data2["active_allocations"] == 5
        print(f"  -> After 1 logout: Available Permits = {sem_data2['available_permits']}, Acquired = {sem_data2['acquired_permits']}")
        print("  -> PASS: Semaphore Management telemetry is 100% accurate and database-grounded.")

        # -------------------------------------------------------------
        # Scenario 10: Verify dashboard statistics update correctly
        # -------------------------------------------------------------
        print("\n[Scenario 10] Verifying Dashboard statistics (/api/dashboard-data)...")
        dash_res = client.get("/api/dashboard-data")
        assert dash_res.status_code == 200
        dash_data = dash_res.get_json()

        print(f"  -> Total Computers: {dash_data['total_computers']}")
        print(f"  -> Occupied Count: {dash_data['occupied_count']}")
        print(f"  -> Available Count: {dash_data['available_count']}")
        print(f"  -> Waiting Count: {dash_data['waiting_count']}")

        assert dash_data["total_computers"] == 6
        assert dash_data["occupied_count"] == 5
        assert dash_data["available_count"] == 1
        assert dash_data["waiting_count"] == 0
        assert dash_data["available_count"] == dash_data["available_permits"]
        print("  -> PASS: Dashboard statistics accurately match live database state.")

        print("\n" + "=" * 75)
        print("ALL 10 WORKFLOW VERIFICATION SCENARIOS COMPLETED AND PASSED!")
        print("=" * 75)

    finally:
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass


if __name__ == "__main__":
    run_workflow_tests()
