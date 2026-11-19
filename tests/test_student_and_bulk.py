"""
Verification Suite for Student Management, Automatic Allocation, and Bulk Workstation Operations
LabSpace - Computer Lab Allocation System
"""
import sys
import os
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestStudentAndBulkOperations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary SQLite DB to preserve user's database records
        cls.tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.test_db = cls.tmp_file.name
        cls.tmp_file.close()

        os.environ["LABSPACE_DB_PATH"] = cls.test_db

        import app.database as db_mod
        db_mod.DB_PATH = Path(cls.test_db)
        db_mod.init_db()

        from app import create_app
        import app.semaphore_manager as sem_mod

        cls.sem_mod = sem_mod
        cls.db_mod = db_mod
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except OSError:
                pass

    def setUp(self):
        # Reset tables in the temporary database to clean state for each test
        conn = self.db_mod.get_db_connection()
        conn.execute("DELETE FROM allocations")
        conn.execute("DELETE FROM waiting_queue")
        conn.execute("DELETE FROM allocation_history")
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM workstations")
        for i in range(1, 6):
            conn.execute("INSERT INTO workstations (pc_id, status) VALUES (?, 'Available')", (f"PC-0{i}",))
        conn.commit()
        conn.close()

        # Re-sync semaphore permits with the clean database
        self.sem_mod.reset_semaphore()

    def test_01_student_registration_auto_allocation(self):
        """Student registers with Student ID only and is immediately allocated an available PC."""
        res = self.client.post("/api/students", json={"student_id": "STU_AUTO_1"})
        data = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["allocation_status"], "allocated")
        self.assertEqual(data["workstation"], "PC-01")

        # Verify in GET /api/students
        list_res = self.client.get("/api/students").get_json()
        student = next((s for s in list_res["students"] if s["student_id"] == "STU_AUTO_1"), None)
        self.assertIsNotNone(student)
        self.assertEqual(student["current_status"], "Using PC-01")
        self.assertNotIn("Registered", student["current_status"])

    def test_02_duplicate_student_id_rejection(self):
        """Prevent registering duplicate Student IDs."""
        self.client.post("/api/students", json={"student_id": "STU_DUP_1"})
        res = self.client.post("/api/students", json={"student_id": "STU_DUP_1"})
        data = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertTrue("already" in data["message"].lower())

    def test_03_auto_queue_when_workstations_full(self):
        """When 5 PCs are occupied, registering a 6th student queues them into FIFO."""
        for i in range(1, 6):
            self.client.post("/api/students", json={"student_id": f"STU_FILL_{i}"})

        # Register 6th student
        res = self.client.post("/api/students", json={"student_id": "STU_OVERFLOW_1"})
        data = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["allocation_status"], "waiting")
        self.assertEqual(data["queue_position"], 1)

        # Verify GET /api/students status
        list_res = self.client.get("/api/students").get_json()
        student = next((s for s in list_res["students"] if s["student_id"] == "STU_OVERFLOW_1"), None)
        self.assertEqual(student["current_status"], "Waiting")

    def test_04_individual_remove_blocked_for_active_and_waiting(self):
        """Individual remove must be blocked if student is using PC or in queue."""
        # 1. Active student
        self.client.post("/api/students", json={"student_id": "STU_ACT_1"})
        del_act = self.client.delete("/api/students/STU_ACT_1")
        self.assertEqual(del_act.status_code, 400)
        self.assertIn("currently using workstation", del_act.get_json()["message"])

        # 2. Fill all PCs so next goes to queue
        for i in range(2, 6):
            self.client.post("/api/students", json={"student_id": f"STU_FILL2_{i}"})
        self.client.post("/api/students", json={"student_id": "STU_WAIT_1"})

        del_wait = self.client.delete("/api/students/STU_WAIT_1")
        self.assertEqual(del_wait.status_code, 400)
        self.assertIn("waiting in queue", del_wait.get_json()["message"].lower())

    def test_05_individual_remove_eligible_student(self):
        """Individual remove succeeds for eligible (logged out/idle) student and preserves history."""
        # Allocate then logout
        self.client.post("/api/students", json={"student_id": "STU_IDLE_1"})
        self.client.post("/api/logout", json={"student_id": "STU_IDLE_1"})

        # Student status should now be Logged Out
        res_del = self.client.delete("/api/students/STU_IDLE_1")
        self.assertEqual(res_del.status_code, 200)
        self.assertIn("removed successfully", res_del.get_json()["message"])

        # Check history still exists
        hist = self.client.get("/api/history").get_json()
        student_history = [h for h in hist["history"] if h["student_id"] == "STU_IDLE_1"]
        self.assertGreaterEqual(len(student_history), 2)  # Allocated and Logout

    def test_06_remove_all_eligible_students(self):
        """Remove All removes idle students while protecting active/waiting students."""
        # Active student
        self.client.post("/api/students", json={"student_id": "STU_REM_ACT"})
        # Idle student 1
        self.client.post("/api/students", json={"student_id": "STU_REM_IDLE1"})
        self.client.post("/api/logout", json={"student_id": "STU_REM_IDLE1"})
        # Idle student 2
        self.client.post("/api/students", json={"student_id": "STU_REM_IDLE2"})
        self.client.post("/api/logout", json={"student_id": "STU_REM_IDLE2"})

        res_all = self.client.post("/api/students/remove-all")
        data = res_all.get_json()
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(data["removed_count"], 2)
        self.assertGreaterEqual(data["skipped_count"], 1)

        # Active student remains
        students = self.client.get("/api/students").get_json()["students"]
        remaining_ids = [s["student_id"] for s in students]
        self.assertIn("STU_REM_ACT", remaining_ids)
        self.assertNotIn("STU_REM_IDLE1", remaining_ids)
        self.assertNotIn("STU_REM_IDLE2", remaining_ids)

    def test_07_bulk_workstation_addition_and_validation(self):
        """Bulk addition adds sequential PCs, rejects invalid quantities, auto-dispatches to waiting queue."""
        # 1. Invalid input tests
        for bad_val in [0, -1, -5, 2.5, "abc", ""]:
            bad_res = self.client.post("/api/workstations/add", json={"count": bad_val})
            self.assertEqual(bad_res.status_code, 400)
            self.assertIn("positive whole number", bad_res.get_json()["message"])

        # 2. Fill 5 PCs and add 2 waiting students
        for i in range(1, 6):
            self.client.post("/api/students", json={"student_id": f"STU_BULK_{i}"})
        self.client.post("/api/students", json={"student_id": "STU_WAIT_A"})
        self.client.post("/api/students", json={"student_id": "STU_WAIT_B"})

        # Initial queue count = 2
        queue_res = self.client.get("/api/waiting-queue").get_json()
        self.assertEqual(queue_res["waiting_count"], 2)
        self.assertEqual(queue_res["total_capacity"], 5)
        self.assertEqual(queue_res["occupied_count"], 5)

        # 3. Bulk add 5 workstations (PC-06 to PC-10)
        bulk_res = self.client.post("/api/workstations/add", json={"count": 5})
        bdata = bulk_res.get_json()
        self.assertEqual(bulk_res.status_code, 200)
        self.assertEqual(bdata["count"], 5)
        self.assertEqual(bdata["added_workstations"], ["PC-06", "PC-07", "PC-08", "PC-09", "PC-10"])

        # STU_WAIT_A should receive PC-06, STU_WAIT_B should receive PC-07
        status = self.sem_mod.get_system_status()
        self.assertEqual(status["total_capacity"], 10)
        self.assertEqual(status["allocations"]["STU_WAIT_A"], "PC-06")
        self.assertEqual(status["allocations"]["STU_WAIT_B"], "PC-07")
        self.assertEqual(status["waiting_count"], 0)
        self.assertEqual(status["available_count"], 3)  # PC-08, PC-09, PC-10 are available
        self.assertEqual(status["available_permits"], 3)

    def test_08_workstation_removal_rules(self):
        """Available PC can be removed; Occupied PC cannot be removed."""
        # Workstations PC-01 to PC-05 are available initially
        rem_avail = self.client.post("/api/workstations/remove", json={"pc_id": "PC-05"})
        self.assertEqual(rem_avail.status_code, 200)

        # Now allocate PC-01 and try to remove it
        self.client.post("/api/students", json={"student_id": "STU_OCC_PC1"})
        rem_occ = self.client.post("/api/workstations/remove", json={"pc_id": "PC-01"})
        self.assertEqual(rem_occ.status_code, 400)
        self.assertIn("currently Occupied", rem_occ.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
