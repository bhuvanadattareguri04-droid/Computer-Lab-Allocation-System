"""
Dynamic Workstation Management & Semaphore Board Test Suite
LabSpace – Computer Lab Allocation System
===========================================================
Tests all 11 required scenarios:
1. Start with five workstations.
2. Add three more workstations.
3. Verify total capacity becomes eight.
4. Allocate eight students.
5. Verify all eight workstations are occupied.
6. Submit another request and verify it enters the FIFO queue.
7. Release one workstation and verify the first waiting student receives it.
8. Remove an available workstation.
9. Attempt to remove an occupied workstation and verify the operation is rejected.
10. Verify semaphore counts match actual workstation availability.
11. Test simultaneous allocation requests using Python threads.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_dynamic_tests():
    print("=" * 75)
    print("LABSPACE: DYNAMIC WORKSTATION & SEMAPHORE VERIFICATION SUITE")
    print("Operating Systems & Computer Networks Subject")
    print("=" * 75)

    # Use an isolated test database to protect existing records
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
        # Step 1: Start with five workstations
        # -------------------------------------------------------------
        print("\n[Step 1] Starting with initial 5 workstations...")
        ws_res = client.get("/api/workstations").get_json()
        assert ws_res["total_computers"] == 5, f"Expected 5 workstations, found {ws_res['total_computers']}"
        pc_names = [w["pc_id"] for w in ws_res["workstations"]]
        assert pc_names == ["PC-01", "PC-02", "PC-03", "PC-04", "PC-05"]
        print(f"  -> PASS: 5 workstations verified: {pc_names}")

        # -------------------------------------------------------------
        # Step 2: Add three more workstations
        # -------------------------------------------------------------
        print("\n[Step 2] Dynamically adding 3 workstations (PC-06, PC-07, PC-08)...")
        for i in range(6, 9):
            add_res = client.post("/api/workstations/add").get_json()
            assert add_res["status"] == "success"
            assert add_res["workstation"] == f"PC-0{i}"
            print(f"  -> Added {add_res['workstation']}: {add_res['message']}")
        print("  -> PASS: 3 workstations successfully added.")

        # -------------------------------------------------------------
        # Step 3: Verify total capacity becomes eight
        # -------------------------------------------------------------
        print("\n[Step 3] Verifying total capacity is now 8...")
        status_after_add = sem_mod.get_system_status()
        assert status_after_add["total_computers"] == 8, f"Expected 8, got {status_after_add['total_computers']}"
        assert status_after_add["total_capacity"] == 8
        assert status_after_add["available_count"] == 8
        # Semaphore count must equal 8
        assert status_after_add["available_permits"] == 8
        print(f"  -> PASS: Total Capacity = 8, Available Permits = 8.")

        # -------------------------------------------------------------
        # Step 4: Allocate eight students
        # -------------------------------------------------------------
        print("\n[Step 4] Requesting workstations for 8 students (STU101 to STU108)...")
        allocated_pcs = []
        for i in range(1, 9):
            sid = f"STU10{i}"
            alloc_res = client.post("/api/allocate", json={"student_id": sid}).get_json()
            assert alloc_res["status"] == "allocated", f"Failed to allocate {sid}: {alloc_res}"
            allocated_pcs.append(alloc_res["workstation"])
            print(f"  -> Allocated {sid} to {alloc_res['workstation']}")
        print("  -> PASS: All 8 students successfully allocated.")

        # -------------------------------------------------------------
        # Step 5: Verify all eight workstations are occupied
        # -------------------------------------------------------------
        print("\n[Step 5] Verifying all 8 workstations are 'Occupied'...")
        status_occupied = sem_mod.get_system_status()
        assert status_occupied["occupied_count"] == 8
        assert status_occupied["available_count"] == 0
        assert status_occupied["available_permits"] == 0
        print(f"  -> PASS: Occupied Count = 8, Available Permits = 0. All 8 workstations in use.")

        # -------------------------------------------------------------
        # Step 6: Submit another request and verify it enters the FIFO queue
        # -------------------------------------------------------------
        print("\n[Step 6] Submitting 9th student request (STU109) when capacity is full...")
        q_res = client.post("/api/allocate", json={"student_id": "STU109"}).get_json()
        assert q_res["status"] == "waiting"
        assert q_res["queue_position"] == 1
        print(f"  -> STU109 Result: status='{q_res['status']}', queue_position={q_res['queue_position']}")

        # Submit 10th student request to verify multi-student FIFO ordering
        q10_res = client.post("/api/allocate", json={"student_id": "STU110"}).get_json()
        assert q10_res["status"] == "waiting"
        assert q10_res["queue_position"] == 2
        print(f"  -> STU110 Result: status='{q10_res['status']}', queue_position={q10_res['queue_position']}")
        print("  -> PASS: Overflow requests successfully placed in FIFO queue.")

        # -------------------------------------------------------------
        # Step 7: Release one workstation and verify first waiting student receives it
        # -------------------------------------------------------------
        print("\n[Step 7] Releasing workstation occupied by STU101...")
        logout_res = client.post("/api/logout", json={"student_id": "STU101"}).get_json()
        assert logout_res["status"] == "reassigned"
        assert logout_res["next_student"] == "STU109", f"Expected STU109, got {logout_res['next_student']}"
        freed_pc = logout_res["workstation"]
        print(f"  -> Workstation {freed_pc} automatically reassigned to {logout_res['next_student']} (FIFO Head).")

        # Verify STU110 is now at head of queue (Position #1)
        queue_check = client.get("/api/waiting-queue").get_json()
        assert queue_check["waiting_count"] == 1
        assert queue_check["queue"][0]["student_id"] == "STU110"
        assert queue_check["queue"][0]["position"] == 1
        print("  -> PASS: Automatic FIFO handoff verified. STU110 moved to Position #1.")

        # -------------------------------------------------------------
        # Step 8: Remove an available workstation
        # -------------------------------------------------------------
        print("\n[Step 8] Freeing one PC (by logging out STU110 after allocation) to test removal of an available workstation...")
        # Free STU102 so STU110 gets it, then queue becomes empty
        logout_s2 = client.post("/api/logout", json={"student_id": "STU102"}).get_json()
        assert logout_s2["next_student"] == "STU110"

        # Now log out STU103 so PC becomes Available (no waiting students)
        logout_s3 = client.post("/api/logout", json={"student_id": "STU103"}).get_json()
        assert logout_s3["status"] == "released"
        available_pc = logout_s3["workstation"]
        print(f"  -> Workstation {available_pc} is now Available.")

        # Remove this available workstation
        rem_res = client.post("/api/workstations/remove", json={"pc_id": available_pc}).get_json()
        assert rem_res["status"] == "success"
        print(f"  -> Removed {available_pc}: {rem_res['message']}")
        new_total = client.get("/api/workstations").get_json()["total_computers"]
        assert new_total == 7, f"Expected 7 workstations after removal, got {new_total}"
        print(f"  -> PASS: Available workstation {available_pc} successfully removed. Total capacity = 7.")

        # -------------------------------------------------------------
        # Step 9: Attempt to remove an occupied workstation and verify rejection
        # -------------------------------------------------------------
        print("\n[Step 9] Attempting to remove an OCCUPIED workstation (held by STU104)...")
        status_now = sem_mod.get_system_status()
        occupied_pc = status_now["allocations"]["STU104"]
        rem_fail_res = client.post("/api/workstations/remove", json={"pc_id": occupied_pc})
        assert rem_fail_res.status_code == 400
        rem_fail_data = rem_fail_res.get_json()
        assert rem_fail_data["status"] == "error"
        assert "Cannot remove workstation" in rem_fail_data["message"]
        print(f"  -> Rejection correctly enforced: '{rem_fail_data['message']}'")
        print("  -> PASS: Removal of occupied workstation was strictly rejected.")

        # -------------------------------------------------------------
        # Step 10: Verify semaphore counts match actual workstation availability
        # -------------------------------------------------------------
        print("\n[Step 10] Verifying Counting Semaphore permits match actual physical availability...")
        status_sync = sem_mod.get_system_status()
        db_available = status_sync["available_count"]
        sem_permits = status_sync["available_permits"]
        print(f"  -> Database Available Workstations: {db_available}")
        print(f"  -> Counting Semaphore _value: {sem_permits}")
        assert db_available == sem_permits, f"Desynchronization! DB has {db_available} but Semaphore has {sem_permits}"
        print("  -> PASS: Semaphore permits exactly match database availability (1-to-1 sync).")

        # -------------------------------------------------------------
        # Step 11: Test simultaneous allocation requests using Python threads
        # -------------------------------------------------------------
        print("\n[Step 11] Testing concurrent allocation requests with 10 simultaneous Python threads...")
        # Free all active workstations first
        current_allocs = list(sem_mod.get_system_status()["allocations"].keys())
        for sid in current_allocs:
            client.post("/api/logout", json={"student_id": sid})

        # Confirm all 7 workstations are Available
        clean_status = sem_mod.get_system_status()
        assert clean_status["total_computers"] == 7
        assert clean_status["available_count"] == 7
        assert clean_status["available_permits"] == 7

        concurrent_outcomes = []
        threads = []

        def race_allocator(student_id):
            res = client.post("/api/allocate", json={"student_id": student_id}).get_json()
            concurrent_outcomes.append((student_id, res))

        # Launch 10 simultaneous threads competing for 7 workstations
        for i in range(1, 11):
            t = threading.Thread(target=race_allocator, args=(f"THREAD_STUDENT_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        allocs = [o for o in concurrent_outcomes if o[1]["status"] == "allocated"]
        queued = [o for o in concurrent_outcomes if o[1]["status"] == "waiting"]

        print(f"  -> Successfully Allocated: {len(allocs)} (Capacity: 7)")
        print(f"  -> Placed in FIFO Queue: {len(queued)} (Overflow: 3)")

        assert len(allocs) == 7, f"Expected 7 allocations, got {len(allocs)}"
        assert len(queued) == 3, f"Expected 3 in queue, got {len(queued)}"

        # Verify no two threads received the same workstation
        allocated_pcs_concurrent = [o[1]["workstation"] for o in allocs]
        unique_allocated_pcs = set(allocated_pcs_concurrent)
        assert len(allocated_pcs_concurrent) == len(unique_allocated_pcs), "Collision detected! Mutex failed!"
        print(f"  -> Allocated Workstations: {sorted(list(unique_allocated_pcs))}")
        print("  -> PASS: Mutex guaranteed mutual exclusion under concurrency with zero collisions.")

        print("\n" + "=" * 75)
        print("ALL 11 DYNAMIC WORKSTATION & SEMAPHORE TESTS COMPLETED AND PASSED!")
        print("=" * 75)

    finally:
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass


if __name__ == "__main__":
    run_dynamic_tests()
