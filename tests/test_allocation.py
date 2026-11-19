import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use isolated DB for test run to preserve production records
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = tmp_db.name
tmp_db.close()
os.environ["LABSPACE_DB_PATH"] = test_db_path

from app.database import init_db
init_db()

from app import semaphore_manager as lab
lab.reset_semaphore()

# Create 10 student requests
students = [f"Student-{i}" for i in range(1, 11)]

print("\n========== SEQUENTIAL FIFO ALLOCATION ==========")

for student in students:
    result = lab.request_computer(student)
    print(f"{student}: {result['message']}")

# Check initial status
status = lab.get_system_status()

print("\n========== INITIAL STATUS ==========")
print("Occupied:", status["occupied_count"])
print("Waiting:", status["waiting_count"])
print("Allocations:", status["allocations"])

# Student-2 logs out
print("\n========== LOGOUT TEST ==========")

result = lab.logout_student("Student-2")
print(result["message"])

# Check updated status
status = lab.get_system_status()

print("\n========== FINAL STATUS ==========")
print("Occupied:", status["occupied_count"])
print("Waiting:", status["waiting_count"])
print("Allocations:", status["allocations"])

# Assertions
assert status["occupied_count"] == 5, f"Expected 5, got {status['occupied_count']}"
assert status["waiting_count"] == 4, f"Expected 4, got {status['waiting_count']}"
assert "Student-6" in status["allocations"], "Student-6 should have been reassigned"
assert status["allocations"]["Student-6"] == "PC-02", f"Expected PC-02, got {status['allocations'].get('Student-6')}"

print("\nALL TESTS PASSED!")

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass
