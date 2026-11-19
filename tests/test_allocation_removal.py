"""
Verification suite for Allocation page removal and preservation of core OS features.
"""
import sys
import os
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestAllocationPageRemoval(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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

        self.sem_mod.reset_semaphore()

    def test_01_allocation_page_removed_from_sidebar_and_returns_404(self):
        """Verify Allocation link is gone from sidebar and /allocation returns 404."""
        # 1. /allocation should return 404 Not Found
        res_alloc = self.client.get("/allocation")
        self.assertEqual(res_alloc.status_code, 404)

        # 2. Sidebar should not have /allocation in any page
        pages = [
            "/dashboard",
            "/workstations",
            "/students",
            "/waiting-queue",
            "/semaphore-management",
            "/history",
            "/analytics",
        ]
        for url in pages:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")
            self.assertNotIn('href="/allocation"', html)
            self.assertNotIn("Allocation</a>", html)

    def test_02_all_seven_remaining_sidebar_pages_render_successfully(self):
        """Verify all 7 remaining sidebar items render with 200 OK."""
        pages = [
            "/dashboard",
            "/workstations",
            "/students",
            "/waiting-queue",
            "/semaphore-management",
            "/history",
            "/analytics",
        ]
        for url in pages:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)

    def test_03_automatic_allocation_upon_student_registration(self):
        """Registering a student automatically allocates available PC."""
        res = self.client.post("/api/students", json={"student_id": "STU_AUTO_TEST1"})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["allocation_status"], "allocated")
        self.assertEqual(data["workstation"], "PC-01")

        # Verify system status
        status = self.sem_mod.get_system_status()
        self.assertEqual(status["allocations"]["STU_AUTO_TEST1"], "PC-01")

    def test_04_automatic_queue_when_all_workstations_occupied(self):
        """Registering when capacity is full queues student in FIFO waiting queue."""
        # Fill 5 PCs
        for i in range(1, 6):
            self.client.post("/api/students", json={"student_id": f"STU_OCC_{i}"})

        # 6th student
        res = self.client.post("/api/students", json={"student_id": "STU_WAIT_TEST1"})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["allocation_status"], "waiting")
        self.assertEqual(data["queue_position"], 1)

        # Verify waiting queue
        status = self.sem_mod.get_system_status()
        self.assertIn("STU_WAIT_TEST1", status["waiting"])
        self.assertEqual(status["waiting_count"], 1)

    def test_05_release_workstation_reassigns_to_first_waiting_student(self):
        """Workstation release via /api/logout automatically reassigns PC to FIFO waiting student."""
        # Fill 5 PCs
        for i in range(1, 6):
            self.client.post("/api/students", json={"student_id": f"STU_FIFO_{i}"})
        # Add 6th student into waiting queue
        self.client.post("/api/students", json={"student_id": "STU_FIFO_WAIT"})

        # Release PC-01 held by STU_FIFO_1
        logout_res = self.client.post("/api/logout", json={"student_id": "STU_FIFO_1"})
        self.assertEqual(logout_res.status_code, 200)
        data = logout_res.get_json()
        self.assertEqual(data["status"], "reassigned")
        self.assertEqual(data["workstation"], "PC-01")
        self.assertEqual(data["next_student"], "STU_FIFO_WAIT")

        # Verify STU_FIFO_WAIT now has PC-01 and waiting queue is 0
        status = self.sem_mod.get_system_status()
        self.assertEqual(status["allocations"]["STU_FIFO_WAIT"], "PC-01")
        self.assertEqual(status["waiting_count"], 0)

    def test_06_workstations_page_has_release_controls(self):
        """Verify the Workstations page HTML contains the Release Workstation / Logout section."""
        res = self.client.get("/workstations")
        html = res.data.decode("utf-8")
        self.assertIn("Release Workstation / Logout", html)
        self.assertIn("releaseStudentSelect", html)
        self.assertIn("handleReleaseWorkstationFromSelect", html)


if __name__ == "__main__":
    unittest.main()
