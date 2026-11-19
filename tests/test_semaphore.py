import os
import sys
import tempfile
import threading
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use isolated DB for testing
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = tmp_db.name
tmp_db.close()
os.environ["LABSPACE_DB_PATH"] = test_db_path

from app.database import init_db
init_db()

from app import semaphore_manager
semaphore_manager.reset_semaphore()

students = [f"Student-{i}" for i in range(1, 11)]

threads = []

for student in students:
    thread = threading.Thread(
        target=semaphore_manager.use_computer,
        args=(student,)
    )
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

print("\n========== TEST RESULTS ==========")
print("Total students:", len(students))
print("Maximum simultaneous users:",
      semaphore_manager.maximum_active_students)
print("Computer capacity:",
      semaphore_manager.TOTAL_COMPUTERS)
print("All students completed successfully!")

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass
