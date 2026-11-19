import threading

from app import semaphore_manager

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