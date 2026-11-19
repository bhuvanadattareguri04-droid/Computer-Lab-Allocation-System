
import threading
from app import semaphore_manager as lab

# Create 10 student requests
students = [f"Student-{i}" for i in range(1, 11)]

threads = []

print("\n========== CONCURRENT ALLOCATION ==========")

def allocate_student(student):
    result = lab.request_computer(student)
    print(result["message"])

for student in students:
    thread = threading.Thread(
        target=allocate_student,
        args=(student,)
    )
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

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
assert status["occupied_count"] == 5
assert status["waiting_count"] == 4
assert "Student-6" in status["allocations"]
assert status["allocations"]["Student-6"] == "PC-02"

print("\nALL TESTS PASSED!")
