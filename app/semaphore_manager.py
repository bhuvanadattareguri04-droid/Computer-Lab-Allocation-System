"""
Operating System Synchronization & Dynamic Concurrency Module
=============================================================
This module demonstrates core Operating Systems concepts:
1. Dynamic Counting Semaphore: Regulates access to physical workstations.
   Permit capacity dynamically mirrors the number of physical workstations
   configured in SQLite.
2. Mutex (threading.Lock): Protects critical sections to prevent race conditions
   and guarantees atomic operations during allocation, logout, queue updates,
   and dynamic capacity resizing.
3. FIFO Waiting Queue: Guarantees First-In, First-Out fairness without starvation.
"""

import threading
import time
import re
from app.database import get_db_connection

# ============================================================================
# OPERATING SYSTEM CONCEPT 1: MUTEX (MUTUAL EXCLUSION LOCK)
# ============================================================================
# A Mutex (threading.Lock) ensures that only ONE thread executes a critical section
# at any given time.
# Why is a Mutex required here?
# 1. Race Condition Prevention: If two concurrent HTTP requests arrive at the exact
#    same microsecond, without a mutex both could read PC-01 as 'Available' and allocate
#    it to two different students simultaneously.
# 2. Dynamic Capacity Atomicity: Adding or removing a computer involves both database
#    updates and semaphore permit adjustments. The mutex guarantees that this entire
#    sequence executes atomically without interference.
allocation_lock = threading.Lock()

# Variable to track maximum concurrent active users (used in OS simulation tests)
maximum_active_students = 0

# Backward compatibility alias for legacy test scripts
TOTAL_COMPUTERS = 5


# ============================================================================
# OPERATING SYSTEM CONCEPT 2: DYNAMIC COUNTING SEMAPHORE
# ============================================================================
# In standard Python, `threading.Semaphore` does not provide a `.resize()` method.
# To support dynamic computer management in a clean, robust, and viva-explainable manner:
#
# 1. Invariant: At all times, the available permits in `computer_semaphore` match
#    the count of workstations with status = 'Available'.
#
# 2. When an administrator ADDS workstations (single or bulk):
#    - Sequential IDs are generated (e.g. PC-06, PC-07...).
#    - For each new machine:
#      - If students are waiting in the FIFO queue, the new workstation is immediately
#        dispatched to the first waiting student. The semaphore permits remain unchanged
#        because the new capacity is immediately consumed.
#      - If no students are waiting, the new workstation is marked 'Available' and we call
#        `computer_semaphore.release()`. This increments the semaphore's permit count by 1.
#
# 3. When an administrator REMOVES a workstation:
#    - Workstations can ONLY be removed if they are 'Available' (not occupied).
#    - Before removing, we call `computer_semaphore.acquire(blocking=False)`.
#      This consumes 1 permit from the semaphore, safely reducing its available capacity.
#    - Then the workstation record is deleted from SQLite.
#
# 4. On Server Startup or Restart:
#    - The semaphore is initialized with the exact count of 'Available' workstations
#      found in the database. Active allocations are completely preserved.
# ============================================================================

def get_initial_available_count():
    """
    Restore semaphore capacity based on current database state.
    Ensures that after a server restart, the semaphore accurately reflects
    the number of currently free workstations.
    """
    conn = get_db_connection()
    try:
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='workstations'"
        ).fetchone()
        if not table_check:
            return 5

        available = conn.execute(
            "SELECT COUNT(*) FROM workstations WHERE status = 'Available'"
        ).fetchone()[0]
        return max(0, available)
    except Exception:
        return 5
    finally:
        conn.close()


def get_total_workstations_count():
    """Return total number of workstations currently configured in database."""
    conn = get_db_connection()
    try:
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='workstations'"
        ).fetchone()
        if not table_check:
            return 5
        return conn.execute("SELECT COUNT(*) FROM workstations").fetchone()[0]
    except Exception:
        return 5
    finally:
        conn.close()


# Initialize the Counting Semaphore with available computer capacity
computer_semaphore = threading.Semaphore(get_initial_available_count())


def reset_semaphore():
    """Re-synchronize the semaphore to match current database state."""
    global computer_semaphore
    computer_semaphore = threading.Semaphore(get_initial_available_count())


# ============================================================================
# DYNAMIC WORKSTATION MANAGEMENT (ADMIN ACTIONS)
# ============================================================================

def add_workstations(count=1):
    """
    Dynamically add 'count' workstations to the computer lab in bulk.
    
    Operating Systems Principle:
    - Mutex is held to prevent race conditions during capacity modification.
    - Generates sequential IDs (e.g., PC-09 to PC-13).
    - For each added workstation:
      - If students are waiting in the FIFO queue, immediately allocates the workstation
        to the waiting student (permits unchanged).
      - If no students are waiting, marks PC 'Available' and calls semaphore.release()
        to increase available semaphore permits by 1.
    """
    try:
        if isinstance(count, bool):
            raise ValueError()
        count_int = int(count)
        if count_int != float(count) or count_int <= 0:
            return {
                "status": "error",
                "message": "Number of workstations to add must be a positive whole number (e.g. 1, 2, 5)."
            }
        count = count_int
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": "Invalid quantity provided. Please enter a positive whole number."
        }

    with allocation_lock:
        conn = get_db_connection()
        try:
            # 1. Determine current maximum workstation number
            existing_rows = conn.execute("SELECT pc_id FROM workstations").fetchall()
            existing_ids = [row["pc_id"] for row in existing_rows]

            max_num = 0
            for pc in existing_ids:
                match = re.search(r"(\d+)", pc)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num

            added_pcs = []
            allocated_to_queue = []

            for i in range(1, count + 1):
                pc_id = f"PC-{(max_num + i):02d}"
                added_pcs.append(pc_id)

                # Check FIFO waiting queue
                next_student = conn.execute("""
                    SELECT student_id FROM waiting_queue
                    ORDER BY queue_id ASC
                    LIMIT 1
                """).fetchone()

                if next_student:
                    sid = next_student["student_id"]
                    # Mark PC Occupied
                    conn.execute("INSERT INTO workstations (pc_id, status) VALUES (?, 'Occupied')", (pc_id,))
                    # Dequeue student
                    conn.execute("DELETE FROM waiting_queue WHERE student_id = ?", (sid,))
                    # Record allocation
                    conn.execute("INSERT INTO allocations (student_id, pc_id) VALUES (?, ?)", (sid, pc_id))
                    # Record history
                    conn.execute("INSERT INTO allocation_history (student_id, pc_id, action) VALUES (?, ?, 'Allocated')", (sid, pc_id))
                    allocated_to_queue.append((pc_id, sid))
                else:
                    # Mark PC Available and increment Counting Semaphore permit
                    conn.execute("INSERT INTO workstations (pc_id, status) VALUES (?, 'Available')", (pc_id,))
                    computer_semaphore.release()

            conn.commit()

            total = conn.execute("SELECT COUNT(*) FROM workstations").fetchone()[0]
            available = conn.execute("SELECT COUNT(*) FROM workstations WHERE status = 'Available'").fetchone()[0]
            occupied = total - available

            if count == 1:
                summary_msg = f"Workstation {added_pcs[0]} added successfully."
            else:
                summary_msg = f"{count} workstations ({added_pcs[0]} to {added_pcs[-1]}) added successfully."

            if allocated_to_queue:
                summary_msg += f" {len(allocated_to_queue)} workstation(s) automatically assigned to waiting students (FIFO)."

            res = {
                "status": "success",
                "count": count,
                "workstation": added_pcs[0] if added_pcs else None,
                "added_workstations": added_pcs,
                "allocated_to_queue_count": len(allocated_to_queue),
                "message": summary_msg,
                "total_workstations": total,
                "available_workstations": available,
                "occupied_workstations": occupied
            }
            if allocated_to_queue:
                res["action"] = "allocated_to_waiting"
                res["student"] = allocated_to_queue[0][1]
            return res

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


def add_workstation():
    """Backward compatibility alias for adding 1 workstation."""
    return add_workstations(1)


def remove_workstation(pc_id=None):
    """
    Remove a workstation dynamically.
    
    Operating Systems Principle:
    - Mutex is held to ensure consistency.
    - An occupied workstation CANNOT be removed.
    - If available, one semaphore permit is consumed via `acquire(blocking=False)`
      to safely decrement the semaphore count before deleting the record.
    """
    with allocation_lock:
        conn = get_db_connection()
        try:
            # 1. Determine target workstation
            if pc_id:
                ws = conn.execute(
                    "SELECT pc_id, status FROM workstations WHERE pc_id = ?",
                    (pc_id,)
                ).fetchone()

                if not ws:
                    return {
                        "status": "error",
                        "message": f"Workstation '{pc_id}' does not exist."
                    }

                if ws["status"] == "Occupied":
                    alloc = conn.execute("SELECT student_id FROM allocations WHERE pc_id = ?", (pc_id,)).fetchone()
                    student_info = f" by {alloc['student_id']}" if alloc else ""
                    return {
                        "status": "error",
                        "message": f"Cannot remove workstation {pc_id} because it is currently Occupied{student_info}. Release or log out the student first."
                    }

                target_id = pc_id
            else:
                available_ws = conn.execute("""
                    SELECT pc_id FROM workstations
                    WHERE status = 'Available'
                    ORDER BY pc_id DESC
                    LIMIT 1
                """).fetchone()

                if not available_ws:
                    return {
                        "status": "error",
                        "message": "Cannot remove workstation: all workstations are currently occupied."
                    }

                target_id = available_ws["pc_id"]

            # 2. Decrement Counting Semaphore to match reduced physical capacity
            computer_semaphore.acquire(blocking=False)

            # 3. Delete workstation record
            conn.execute("DELETE FROM workstations WHERE pc_id = ?", (target_id,))
            conn.commit()

            total = conn.execute("SELECT COUNT(*) FROM workstations").fetchone()[0]
            available = conn.execute("SELECT COUNT(*) FROM workstations WHERE status = 'Available'").fetchone()[0]

            return {
                "status": "success",
                "workstation": target_id,
                "message": f"Workstation {target_id} removed successfully. Total capacity is now {total}.",
                "total_workstations": total,
                "available_workstations": available
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


# ============================================================================
# ALLOCATION & LOGOUT (STUDENT ACTIONS)
# ============================================================================

def request_computer(student_id, student_name=None):
    """
    Request a computer workstation for a student with automatic queue processing.

    Operating Systems Principles Applied:
    - Mutex Lock (threading.Lock): Acquired first to enter critical section.
    - Validation & Duplicate Prevention:
        - Rejects duplicate active allocations (student already using a PC).
        - Rejects duplicate waiting requests (student already in FIFO queue).
    - Auto-Registration: Registers or updates student in `students` table.
    - FIFO Queue Workflow:
        1. Add the student to the FIFO waiting queue.
        2. Check if a workstation is available AND this student is at the head of the queue.
        3. If available:
           - Acquire counting semaphore permit non-blocking.
           - Remove student from the FIFO queue.
           - Allocate the lowest available workstation to the student.
           - Record in active allocations and audit history.
        4. If not available:
           - Keep student in the FIFO queue.
           - Return queue position and waiting status.
    """
    global maximum_active_students

    # Acquire MUTEX to protect critical section from concurrent race conditions
    with allocation_lock:
        conn = get_db_connection()
        semaphore_acquired = False

        try:
            student_id = str(student_id).strip()
            if not student_id:
                return {
                    "status": "error",
                    "message": "Student ID is required."
                }

            # 1. Check if student already has an active allocation
            existing = conn.execute(
                "SELECT pc_id FROM allocations WHERE student_id = ?",
                (student_id,)
            ).fetchone()

            if existing:
                return {
                    "status": "already_allocated",
                    "student": student_id,
                    "workstation": existing["pc_id"],
                    "message": f"Student {student_id} is already using workstation {existing['pc_id']}."
                }

            # 2. Check if student is already in the FIFO waiting queue
            waiting = conn.execute(
                "SELECT queue_id FROM waiting_queue WHERE student_id = ?",
                (student_id,)
            ).fetchone()

            if waiting:
                return {
                    "status": "already_waiting",
                    "student": student_id,
                    "message": f"Student {student_id} is already in the waiting queue."
                }

            # 3. Register student record in database if not already present
            conn.execute(
                "INSERT OR IGNORE INTO students (student_id, student_name) VALUES (?, ?)",
                (student_id, student_name or student_id)
            )
            if student_name:
                conn.execute(
                    "UPDATE students SET student_name = ? WHERE student_id = ?",
                    (student_name, student_id)
                )

            # 4. Add the student to the FIFO waiting queue automatically
            conn.execute(
                "INSERT INTO waiting_queue (student_id) VALUES (?)",
                (student_id,)
            )
            conn.commit()

            # 5. Check if any workstation is available AND this student is first in queue
            first_in_line = conn.execute("""
                SELECT student_id FROM waiting_queue
                ORDER BY queue_id ASC
                LIMIT 1
            """).fetchone()

            available_pc = conn.execute("""
                SELECT pc_id FROM workstations
                WHERE status = 'Available'
                ORDER BY pc_id ASC
                LIMIT 1
            """).fetchone()

            if available_pc and first_in_line and first_in_line["student_id"] == student_id:
                # Workstation is available and this student is at the head of the FIFO queue!
                semaphore_acquired = computer_semaphore.acquire(blocking=False)
                if semaphore_acquired:
                    pc_id = available_pc["pc_id"]

                    # Remove from waiting queue
                    conn.execute(
                        "DELETE FROM waiting_queue WHERE student_id = ?",
                        (student_id,)
                    )

                    # Mark workstation Occupied
                    conn.execute(
                        "UPDATE workstations SET status = 'Occupied' WHERE pc_id = ?",
                        (pc_id,)
                    )

                    # Insert active allocation
                    conn.execute(
                        "INSERT INTO allocations (student_id, pc_id) VALUES (?, ?)",
                        (student_id, pc_id)
                    )

                    # Record history
                    conn.execute(
                        "INSERT INTO allocation_history (student_id, pc_id, action) VALUES (?, ?, 'Allocated')",
                        (student_id, pc_id)
                    )

                    conn.commit()

                    # Track peak concurrent allocations
                    occupied_count = conn.execute("SELECT COUNT(*) FROM allocations").fetchone()[0]
                    if occupied_count > maximum_active_students:
                        maximum_active_students = occupied_count

                    return {
                        "status": "allocated",
                        "student": student_id,
                        "workstation": pc_id,
                        "message": f"Successfully allocated workstation {pc_id} to student {student_id}."
                    }

            # 6. Otherwise: No workstation is available, or earlier students are waiting ahead.
            # Student remains in the FIFO queue.
            pos = conn.execute("""
                SELECT COUNT(*) FROM waiting_queue
                WHERE queue_id <= (SELECT queue_id FROM waiting_queue WHERE student_id = ?)
            """, (student_id,)).fetchone()[0]

            return {
                "status": "waiting",
                "student": student_id,
                "queue_position": pos,
                "message": f"All workstations are occupied. Student {student_id} added to FIFO waiting queue at position #{pos}."
            }

        except Exception as e:
            conn.rollback()
            if semaphore_acquired:
                computer_semaphore.release()
            raise e

        finally:
            conn.close()


def logout_student(student_id):
    """
    Log out a student and release their workstation.

    Operating Systems Principles Applied:
    - Mutex Lock: Acquired to safely update allocation records and queue.
    - FIFO Dispatching: If students are waiting, pops the first in queue and
      reassigns the workstation. Semaphore count remains unchanged.
    - Semaphore Release: If waiting queue is empty, marks workstation Available
      and releases the semaphore.
    """
    with allocation_lock:
        conn = get_db_connection()

        try:
            student_id = str(student_id).strip()

            # 1. Find student's active allocation
            allocation = conn.execute("""
                SELECT pc_id FROM allocations
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            if not allocation:
                return {
                    "status": "error",
                    "message": f"Student {student_id} has no currently allocated workstation."
                }

            pc_id = allocation["pc_id"]

            # 2. Record logout in allocation history
            conn.execute("""
                INSERT INTO allocation_history (student_id, pc_id, action)
                VALUES (?, ?, 'Logout')
            """, (student_id, pc_id))

            # 3. Remove student from active allocations
            conn.execute(
                "DELETE FROM allocations WHERE student_id = ?",
                (student_id,)
            )

            # 4. Check FIFO waiting queue for next student in line
            next_student = conn.execute("""
                SELECT student_id FROM waiting_queue
                ORDER BY queue_id ASC
                LIMIT 1
            """).fetchone()

            if next_student:
                next_id = next_student["student_id"]

                # Dequeue next student (FIFO head)
                conn.execute("""
                    DELETE FROM waiting_queue
                    WHERE student_id = ?
                """, (next_id,))

                # Reassign released workstation to the waiting student
                conn.execute("""
                    INSERT INTO allocations (student_id, pc_id)
                    VALUES (?, ?)
                """, (next_id, pc_id))

                # Record reassignment in history
                conn.execute("""
                    INSERT INTO allocation_history (student_id, pc_id, action)
                    VALUES (?, ?, 'Reassigned')
                """, (next_id, pc_id))

                conn.commit()

                return {
                    "status": "reassigned",
                    "workstation": pc_id,
                    "previous_student": student_id,
                    "next_student": next_id,
                    "message": f"Workstation {pc_id} released by {student_id} and automatically reassigned to waiting student {next_id} (FIFO)."
                }

            # 5. No waiting students -> Mark workstation Available and release Semaphore
            conn.execute("""
                UPDATE workstations
                SET status = 'Available'
                WHERE pc_id = ?
            """, (pc_id,))

            conn.commit()

            # Increment counting semaphore permit
            computer_semaphore.release()

            return {
                "status": "released",
                "workstation": pc_id,
                "student": student_id,
                "message": f"Workstation {pc_id} successfully released. It is now Available."
            }

        except Exception as e:
            conn.rollback()
            raise e

        finally:
            conn.close()


def get_system_status():
    """
    Retrieve live system state: total capacity, semaphore permits,
    active allocations, and waiting queue.
    """
    conn = get_db_connection()

    try:
        workstations = conn.execute("""
            SELECT w.pc_id, w.status, a.student_id
            FROM workstations w
            LEFT JOIN allocations a ON w.pc_id = a.pc_id
            ORDER BY w.pc_id ASC
        """).fetchall()

        available = [row["pc_id"] for row in workstations if row["status"] == "Available"]
        allocations = {row["student_id"]: row["pc_id"] for row in workstations if row["student_id"]}

        waiting = conn.execute("""
            SELECT student_id FROM waiting_queue
            ORDER BY queue_id ASC
        """).fetchall()

        total = len(workstations)
        occupied = len(allocations)
        available_count = len(available)

        # Actual semaphore permit count from internal counter
        sem_value = getattr(computer_semaphore, "_value", available_count)
        mutex_locked = allocation_lock.locked()

        return {
            "total_computers": total,
            "total_capacity": total,
            "available": available,
            "available_count": available_count,
            "available_permits": sem_value,
            "acquired_permits": max(0, total - sem_value),
            "allocations": allocations,
            "occupied_count": occupied,
            "waiting": [row["student_id"] for row in waiting],
            "waiting_count": len(waiting),
            "waiting_students": len(waiting),
            "mutex_locked": mutex_locked,
            "mutex_status": "LOCKED" if mutex_locked else "UNLOCKED",
            "workstations": [
                {
                    "pc_id": row["pc_id"],
                    "status": row["status"],
                    "student_id": row["student_id"]
                }
                for row in workstations
            ]
        }

    finally:
        conn.close()


def use_computer(student_id, duration=0.1):
    """
    Academic simulation helper for OS concurrency tests.
    A student requests a computer, uses it for `duration` seconds, and then logs out.
    """
    res = request_computer(student_id)
    if res["status"] == "allocated":
        time.sleep(duration)
        logout_student(student_id)
    return res
