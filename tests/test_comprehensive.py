"""
Comprehensive Academic Test Suite
LabSpace – Computer Lab Allocation System
=========================================
Tests all 12 scenarios required for academic evaluation:
1. Start the Flask application.
2. Confirm that five workstations are displayed.
3. Allocate five students.
4. Verify that all five workstations become occupied.
5. Request another workstation.
6. Verify that the sixth student enters the waiting queue.
7. Release one workstation.
8. Verify that the first waiting student receives it.
9. Verify FIFO ordering.
10. Test two or more simultaneous allocation requests using Python threads.
11. Confirm that the same workstation is not allocated to two students.
12. Restart the application and verify database persistence.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_all_tests():
    print("=" * 70)
    print("LABSPACE: 12-SCENARIO ACADEMIC VERIFICATION SUITE")
    print("Operating Systems & Computer Networks Subject")
    print("=" * 70)

    # Use an isolated test database to protect production/existing records
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        test_db_path = tmp_db.name

    os.environ["LABSPACE_DB_PATH"] = test_db_path

    try:
        from app import create_app
        import app.database as db_mod
        db_mod.DB_PATH = Path(test_db_path)
        import app.semaphore_manager as sem_mod

        # -------------------------------------------------------------
        # Scenario 1: Start the Flask application
        # -------------------------------------------------------------
        print("\n[Scenario 1] Starting Flask application...")
        app = create_app()
        client = app.test_client()
        sem_mod.reset_semaphore()
        home_res = client.get("/")
        assert home_res.status_code == 302, "Root should redirect to /dashboard"
        print("  -> PASS: Flask application initialized and running.")

        # -------------------------------------------------------------
        # Scenario 2: Confirm that five workstations are displayed
        # -------------------------------------------------------------
        print("\n[Scenario 2] Confirming 5 workstations exist in database...")
        ws_res = client.get("/api/workstations")
        assert ws_res.status_code == 200
        ws_data = ws_res.get_json()["workstations"]
        assert len(ws_data) == 5, f"Expected 5 workstations, found {len(ws_data)}"
        pc_ids = [w["pc_id"] for w in ws_data]
        assert pc_ids == ["PC-01", "PC-02", "PC-03", "PC-04", "PC-05"]
        for w in ws_data:
            assert w["status"] == "Available", f"{w['pc_id']} should be Available initially"
        print(f"  -> PASS: All 5 workstations verified: {pc_ids}")

        # -------------------------------------------------------------
        # Scenario 3: Allocate five students
        # -------------------------------------------------------------
        print("\n[Scenario 3] Allocating 5 students (S1 through S5)...")
        allocated_pcs = []
        for i in range(1, 6):
            res = client.post("/api/allocate", json={"student_id": f"TEST_S{i}"})
            data = res.get_json()
            assert res.status_code == 200
            assert data["status"] == "allocated", f"TEST_S{i} failed to allocate"
            allocated_pcs.append(data["workstation"])
            print(f"  -> Allocated TEST_S{i} to {data['workstation']}")
        print("  -> PASS: 5 students successfully requested and allocated.")

        # -------------------------------------------------------------
        # Scenario 4: Verify that all five workstations become occupied
        # -------------------------------------------------------------
        print("\n[Scenario 4] Verifying all 5 workstations are 'Occupied'...")
        status = sem_mod.get_system_status()
        assert status["occupied_count"] == 5, f"Expected 5 occupied, got {status['occupied_count']}"
        assert len(status["available"]) == 0, f"Expected 0 available, got {len(status['available'])}"
        print(f"  -> PASS: Occupied Count = 5, Available Count = 0. Capacity full.")

        # -------------------------------------------------------------
        # Scenario 5: Request another workstation (6th student)
        # -------------------------------------------------------------
        print("\n[Scenario 5] Requesting workstation for 6th student (TEST_S6)...")
        res_s6 = client.post("/api/allocate", json={"student_id": "TEST_S6"})
        data_s6 = res_s6.get_json()
        assert res_s6.status_code == 200
        print(f"  -> S6 Response: status='{data_s6['status']}', message='{data_s6['message']}'")

        # -------------------------------------------------------------
        # Scenario 6: Verify that the 6th student enters the waiting queue
        # -------------------------------------------------------------
        print("\n[Scenario 6] Verifying 6th student is in FIFO waiting queue...")
        assert data_s6["status"] == "waiting"
        assert data_s6["queue_position"] == 1
        queue_res = client.get("/api/waiting-queue")
        q_data = queue_res.get_json()
        assert q_data["waiting_count"] == 1
        assert q_data["queue"][0]["student_id"] == "TEST_S6"
        assert q_data["queue"][0]["position"] == 1
        print("  -> PASS: TEST_S6 successfully queued at FIFO Position #1.")

        # Also add a 7th student to test multi-item FIFO ordering
        client.post("/api/allocate", json={"student_id": "TEST_S7"})
        print("  -> Enqueued 7th student (TEST_S7) at Position #2 for FIFO test.")

        # -------------------------------------------------------------
        # Scenario 7: Release one workstation
        # -------------------------------------------------------------
        print("\n[Scenario 7] Releasing workstation occupied by TEST_S1...")
        logout_res = client.post("/api/logout", json={"student_id": "TEST_S1"})
        logout_data = logout_res.get_json()
        assert logout_res.status_code == 200
        print(f"  -> Logout Result: status='{logout_data['status']}', msg='{logout_data['message']}'")
        print("  -> PASS: Workstation released by TEST_S1.")

        # -------------------------------------------------------------
        # Scenario 8: Verify that the first waiting student receives it
        # -------------------------------------------------------------
        print("\n[Scenario 8] Verifying first waiting student (TEST_S6) received released PC...")
        assert logout_data["status"] == "reassigned"
        assert logout_data["next_student"] == "TEST_S6"
        freed_pc = logout_data["workstation"]
        # Verify in status
        curr_status = sem_mod.get_system_status()
        assert curr_status["allocations"].get("TEST_S6") == freed_pc
        print(f"  -> PASS: Workstation {freed_pc} automatically reassigned to TEST_S6.")

        # -------------------------------------------------------------
        # Scenario 9: Verify FIFO ordering
        # -------------------------------------------------------------
        print("\n[Scenario 9] Verifying FIFO ordering (TEST_S7 should now be at Head of line)...")
        q_data_after = client.get("/api/waiting-queue").get_json()
        assert q_data_after["waiting_count"] == 1
        assert q_data_after["queue"][0]["student_id"] == "TEST_S7"
        assert q_data_after["queue"][0]["position"] == 1

        # Now logout another student (TEST_S2), verify TEST_S7 gets it
        logout_s2 = client.post("/api/logout", json={"student_id": "TEST_S2"}).get_json()
        assert logout_s2["status"] == "reassigned"
        assert logout_s2["next_student"] == "TEST_S7"
        print("  -> TEST_S7 received PC upon next logout. Queue is now empty.")
        q_empty = client.get("/api/waiting-queue").get_json()
        assert q_empty["waiting_count"] == 0
        print("  -> PASS: First-In, First-Out (FIFO) queue ordering strictly maintained.")

        # -------------------------------------------------------------
        # Scenario 10: Test simultaneous allocation requests using Python threads
        # -------------------------------------------------------------
        print("\n[Scenario 10] Testing concurrent allocation requests with 10 Python threads...")
        # Free all PCs first
        for st in ["TEST_S3", "TEST_S4", "TEST_S5", "TEST_S6", "TEST_S7"]:
            client.post("/api/logout", json={"student_id": st})

        # Confirm all 5 are Available
        clean_status = sem_mod.get_system_status()
        assert clean_status["occupied_count"] == 0
        assert len(clean_status["available"]) == 5

        concurrent_results = []
        threads = []

        def worker_allocate(sid):
            res = client.post("/api/allocate", json={"student_id": sid})
            concurrent_results.append((sid, res.get_json()))

        # Spawn 10 simultaneous threads competing for 5 workstations
        for i in range(1, 11):
            t = threading.Thread(target=worker_allocate, args=(f"RACE_STUDENT_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        allocated_results = [r for r in concurrent_results if r[1]["status"] == "allocated"]
        waiting_results = [r for r in concurrent_results if r[1]["status"] == "waiting"]

        print(f"  -> Allocated count: {len(allocated_results)}")
        print(f"  -> Waiting count: {len(waiting_results)}")
        assert len(allocated_results) == 5, f"Expected exactly 5 allocations, got {len(allocated_results)}"
        assert len(waiting_results) == 5, f"Expected exactly 5 waiting, got {len(waiting_results)}"
        print("  -> PASS: Exactly 5 allocations granted, remaining 5 safely queued.")

        # -------------------------------------------------------------
        # Scenario 11: Confirm that the same workstation is not allocated to two students
        # -------------------------------------------------------------
        print("\n[Scenario 11] Confirming mutual exclusion (no two students hold same PC)...")
        allocated_pcs_concurrent = [r[1]["workstation"] for r in allocated_results]
        unique_pcs = set(allocated_pcs_concurrent)
        assert len(allocated_pcs_concurrent) == len(unique_pcs), "Collision detected! Duplicate PC allocated!"
        assert unique_pcs == {"PC-01", "PC-02", "PC-03", "PC-04", "PC-05"}
        print(f"  -> Allocated PCs: {sorted(list(unique_pcs))}")
        print("  -> PASS: Zero collisions detected. Mutex guaranteed Mutual Exclusion.")

        # -------------------------------------------------------------
        # Scenario 12: Restart the application and verify database persistence
        # -------------------------------------------------------------
        print("\n[Scenario 12] Simulating server restart and verifying persistence...")
        # Re-create app and reset semaphore from database state
        app_restarted = create_app()
        client_restarted = app_restarted.test_client()
        sem_mod.reset_semaphore()

        restarted_status = sem_mod.get_system_status()
        assert restarted_status["occupied_count"] == 5, "Occupied count lost after restart"
        assert restarted_status["waiting_count"] == 5, "Waiting queue lost after restart"
        assert len(restarted_status["available"]) == 0, "Available count incorrect after restart"

        # Check analytics and history persistence
        hist_res = client_restarted.get("/api/history").get_json()
        assert hist_res["total_records"] > 0, "History records lost after restart"
        print(f"  -> Total persisted history records: {hist_res['total_records']}")
        print("  -> PASS: All allocations, waiting queue, and history survived server restart.")

        print("\n" + "=" * 70)
        print("ALL 12 ACADEMIC EVALUATION SCENARIOS COMPLETED AND PASSED!")
        print("=" * 70)

    finally:
        # Clean up temporary test database
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_all_tests()
