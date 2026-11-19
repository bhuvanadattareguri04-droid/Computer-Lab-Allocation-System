
import threading
from collections import deque

# Total computer capacity
TOTAL_COMPUTERS = 5

# Counting semaphore
computer_semaphore = threading.Semaphore(TOTAL_COMPUTERS)

# Mutex for shared data protection
allocation_lock = threading.Lock()

# Available workstations
available_workstations = [
    f"PC-{i:02d}" for i in range(1, TOTAL_COMPUTERS + 1)
]

# Student allocation records
allocations = {}

# FIFO waiting queue
waiting_queue = deque()


def request_computer(student_id):

    with allocation_lock:

        # Prevent duplicate requests
        if student_id in allocations:
            return {
                "status": "already_allocated",
                "message": f"{student_id} already has a computer."
            }

        if student_id in waiting_queue:
            return {
                "status": "already_waiting",
                "message": f"{student_id} is already waiting."
            }

        # Check whether a computer is available
        if computer_semaphore.acquire(blocking=False):

            pc_id = available_workstations.pop(0)
            allocations[student_id] = pc_id

            return {
                "status": "allocated",
                "student": student_id,
                "workstation": pc_id,
                "message": f"{student_id} allocated {pc_id}"
            }

        # Add student to FIFO queue
        waiting_queue.append(student_id)

        return {
            "status": "waiting",
            "student": student_id,
            "message": f"{student_id} added to waiting queue."
        }


def logout_student(student_id):

    with allocation_lock:

        if student_id not in allocations:
            return {
                "status": "error",
                "message": f"{student_id} has no allocated computer."
            }

        pc_id = allocations.pop(student_id)

        # Transfer workstation to next waiting student
        if waiting_queue:

            next_student = waiting_queue.popleft()
            allocations[next_student] = pc_id

            return {
                "status": "reassigned",
                "workstation": pc_id,
                "previous_student": student_id,
                "next_student": next_student,
                "message": f"{pc_id} reassigned to {next_student}"
            }

        # Return workstation to available pool
        available_workstations.append(pc_id)
        computer_semaphore.release()

        return {
            "status": "released",
            "workstation": pc_id,
            "message": f"{pc_id} is now available."
        }


def get_system_status():

    with allocation_lock:

        return {
            "total_computers": TOTAL_COMPUTERS,
            "available": list(available_workstations),
            "allocations": dict(allocations),
            "waiting": list(waiting_queue),
            "occupied_count": len(allocations),
            "waiting_count": len(waiting_queue)
        }
