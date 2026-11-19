# LabSpace – Computer Lab Allocation System

> **Subject:** Operating Systems and Computer Networks  
> **Course Project:** Concurrency Synchronization, Mutex Locks, Dynamic Counting Semaphores, and FIFO Process Scheduling

---

## 1. Project Introduction

**LabSpace** is a web-based Computer Lab Allocation System designed to simulate and manage student access to a dynamically scalable set of laboratory workstations. In real-world educational institutions, computer labs frequently adjust workstation availability based on hardware maintenance, lab expansions, and fluctuating student demand.

LabSpace models this real-world constraint using fundamental Operating System concurrency primitives: **Mutual Exclusion (Mutex)**, **Dynamic Counting Semaphores**, and **First-In, First-Out (FIFO) Waiting Queue Scheduling**.

---

## 2. Problem Statement

When multiple students attempt to access lab computers simultaneously:
1. **Resource Contention:** Workstation capacity is finite; student demand often exceeds available machines.
2. **Dynamic Lab Capacity:** Labs periodically add new machines or temporarily decommission hardware. Concurrency primitives must dynamically scale without data loss or race conditions.
3. **Race Conditions:** Without synchronization, multiple concurrent allocation requests might query the system at the exact same millisecond and assign the same workstation to more than one student.
4. **Starvation & Unfair Scheduling:** Without strict queuing, students arriving later could bypass waiting peers.

---

## 3. Main Operating System Concepts Used

### A. Dynamic Counting Semaphore (`threading.Semaphore`)
- **Role:** Controls access to the pool of physical lab workstations.
- **Why Semaphores Cannot Be Resized Directly in Python:**
  - Python's standard `threading.Semaphore` does not provide a `.resize()` method.
  - Simply replacing the semaphore object during runtime risks desynchronization and race conditions.
- **LabSpace Dynamic Resizing Strategy:**
  - **Invariant:** At all times, the available permits in `computer_semaphore` match the count of workstations with status = `'Available'`.
  - **Adding a Workstation:**
    - If students are waiting in the FIFO queue: The new workstation is immediately dispatched to the first waiting student. The semaphore permit count remains unchanged (new capacity is instantly consumed).
    - If no students are waiting: The workstation is marked `'Available'` and we invoke `computer_semaphore.release()`. This increments the available permit counter by 1.
  - **Removing a Workstation:**
    - Only `'Available'` (unoccupied) workstations can be removed. Attempting to remove an occupied workstation is rejected.
    - We consume 1 permit via `computer_semaphore.acquire(blocking=False)`.
    - The workstation record is safely deleted from SQLite.
  - **Server Restarts:** The semaphore is dynamically initialized with `SELECT COUNT(*) FROM workstations WHERE status = 'Available'`, preserving all active allocations.

### B. Mutex Lock (`threading.Lock()`)
- **Role:** Guarantees Mutual Exclusion during critical sections (allocations, logouts, queue operations, and dynamic workstation resizing).
- **Why it is required:**
  - Ensures atomicity: Checking availability, acquiring permits, updating SQLite records, and queue operations execute as an indivisible unit.
  - Exposes real-time telemetry: The dashboard actively tracks whether the mutex is currently `LOCKED` or `UNLOCKED` via `allocation_lock.locked()`.

### C. First-In, First-Out (FIFO) Waiting Queue
- **Role:** Fair process scheduling when capacity is fully saturated.
- **Mechanism:**
  - When all workstations are occupied, incoming requests join the tail of the `waiting_queue`.
  - When an active workstation is freed, the student at the head of the queue (`ORDER BY queue_id ASC LIMIT 1`) is immediately reassigned the machine.

---

## 4. Key System Features

1. **🚦 Dedicated Semaphore & Concurrency Monitoring Board:**
   - Real-time telemetry board on the Dashboard refreshed every 3 seconds.
   - **Total Semaphore Capacity:** Live count of physical workstations configured.
   - **Available Permits:** Live internal counter from `computer_semaphore._value` (`acquire()` ready).
   - **Acquired Permits:** Permits currently held by active students.
   - **Active Allocations:** Number of students currently logged in.
   - **FIFO Waiting Queue Depth:** Number of students waiting in line.
   - **Mutex Status Badge:** Live visual indicator (**GREEN** for `UNLOCKED`, **RED** for `LOCKED`).
   - **Workstation Concurrency Rack:** Interactive visual rack showing individual workstation nodes with real-time status.

2. **⚙️ Dynamic Computer Management (Lab Configuration):**
   - Admin can dynamically **Add New Workstations** (`PC-01`, `PC-02`... auto-generated sequentially).
   - If students are waiting, newly added machines automatically allocate to the head of the FIFO queue.
   - Admin can **Remove Workstations** (strictly permitted only when the workstation is `Available`; occupied removal is rejected).
   - Live lab utilization rate indicator.

3. **👨‍🎓 Student Management:**
   - Dedicated Admin Student Directory (`/students`).
   - Add new student records (Student ID & Full Name).
   - Strict duplicate student ID prevention.
   - Real-time status tracking for each student: `Using PC-xx` (Occupied), `Waiting in Queue`, or `Idle`.
   - Search and filter students by ID or Name.

4. **⚡ Computer Allocation & Workstation Release:**
   - Instant student request form with immediate feedback (Allocated vs. Queued).
   - One-click workstation release with clickable active student quick-select chips.

5. **⏳ FIFO Waiting Queue Monitor:**
   - Real-time queue table displaying exact FIFO positions (`#1 Next in Line`, `#2`, etc.).

6. **📜 Allocation Audit History & 📈 Analytics:**
   - Persistent SQLite history log with search and action badges (`Allocated`, `Logout`, `Reassigned`).
   - Chart.js visualizations for occupancy breakdown and workstation usage distribution.

---

## 5. Technology Stack

- **Backend:** Python 3, Flask
- **Concurrency & OS Primitives:** Python `threading.Semaphore`, `threading.Lock`
- **Database:** SQLite 3 (native Python standard library)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript (Fetch API)
- **Data Visualization:** Chart.js (CDN)
- **Architecture:** Modular Flask Blueprints (MVC-inspired)

---

## 6. Project Folder Structure

```
Computer-Lab-Allocation-System/
├── app/
│   ├── instance/
│   │   └── computer_lab.db         # Persistent SQLite database
│   ├── routes/
│   │   ├── allocation.py           # Allocation & release endpoints
│   │   ├── analytics.py            # Analytics views & chart API
│   │   ├── dashboard.py            # Dashboard & Semaphore telemetry API
│   │   ├── history.py              # Audit history views & API
│   │   ├── student.py              # Student management views & API
│   │   ├── waiting_queue.py        # FIFO queue views & API
│   │   └── workstation.py          # Dynamic workstation management API
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css           # LabSpace theme styling & Semaphore Board CSS
│   │   └── js/
│   │       └── dashboard.js        # Dashboard client scripts
│   ├── templates/
│   │   ├── analytics.html          # Usage statistics & charts page
│   │   ├── base.html               # Shared layout & navigation sidebar
│   │   ├── dashboard.html          # Dashboard & Semaphore Monitoring Board
│   │   ├── history.html            # Complete audit history log page
│   │   ├── semaphore_management.html # Dedicated Semaphore Monitoring Board
│   │   ├── students.html           # Student management & directory page
│   │   ├── waiting_queue.html      # FIFO waiting queue monitor
│   │   └── workstations.html       # Dynamic workstation management page
│   ├── __init__.py                 # Application factory & blueprint registration
│   ├── database.py                 # SQLite connection & schema initialization
│   ├── models.py                   # Data access query models
│   └── semaphore_manager.py        # Core OS Semaphore, Mutex & Dynamic Queue logic
├── tests/
│   ├── test_allocation.py          # Sequential allocation & logout test
│   ├── test_comprehensive.py       # Full 12-scenario academic verification suite
│   ├── test_dynamic_management.py  # 11-step dynamic workstation & semaphore test
│   └── test_semaphore.py           # Concurrency stress simulation test
├── requirements.txt                # Python package dependencies (Flask)
├── run.py                          # Application entry point
└── README.md                       # Comprehensive documentation
```

---

## 7. Installation & Running the Application

### 1. Activate the Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```

### 2. Start the Flask Server
```bash
python run.py
```

### 3. Open the Web Application
Open your browser and navigate to:
```
http://127.0.0.1:5000/
```
You will be automatically redirected to the **LabSpace Dashboard**.

---

## 8. Automated Academic Verification Tests

Execute the comprehensive test suites in terminal:

### A. Dynamic Workstation & Semaphore Test (11 Scenarios)
```bash
python tests/test_dynamic_management.py
```
**Tests executed:**
1. Start with 5 workstations.
2. Dynamically add 3 workstations (`PC-06`, `PC-07`, `PC-08`).
3. Verify total capacity becomes 8.
4. Allocate 8 students.
5. Verify all 8 workstations are occupied.
6. Submit 9th request and verify it enters FIFO queue.
7. Release one workstation and verify first waiting student receives it.
8. Remove an available workstation.
9. Attempt to remove an occupied workstation and verify operation is rejected.
10. Verify semaphore counts match actual workstation availability.
11. Test simultaneous allocation requests using 10 Python threads.

### B. Student Management, Automatic Allocation & Bulk Addition Suite
```bash
python tests/test_student_and_bulk.py
```
This suite verifies:
1. Student registration with Student ID only and immediate automatic workstation allocation.
2. Duplicate Student ID rejection.
3. Overflow placement in the FIFO waiting queue when all workstations are occupied.
4. Blocked removal of students with active allocations or waiting queue entries with explanatory notices.
5. Successful removal of eligible (logged-out) students while strictly preserving audit history.
6. Bulk removal of all eligible students in one operation without browser popups.
7. Bulk workstation addition with sequential IDs, input validation, and automatic FIFO dispatch.
8. Workstation removal rules (available allowed, occupied strictly blocked).

### C. Standard 12-Scenario Academic Suite
```bash
python tests/test_comprehensive.py
```

### D. 10-Scenario End-to-End Workflow Suite
```bash
python tests/test_workflow.py
```

---

## 9. Viva / Faculty Demonstration Guide

Follow these steps during your project presentation:

1. **Student Registration & Automatic Allocation:**
   - Navigate to `/students`.
   - Register a student using **Student ID only** (e.g. `STU201`).
   - Notice that registration immediately and automatically allocates an available workstation (status becomes `Using PC-01`). No separate allocation step required.
   - Show that duplicate Student IDs are strictly rejected.

2. **Bulk Workstation Scaling:**
   - Navigate to `/workstations`.
   - Use the **Bulk Addition** control: enter `5` and click **Add Workstations**.
   - Watch sequential workstations (`PC-06` through `PC-10`) get created in a single atomic transaction.
   - Notice that if students are waiting in the queue, newly added workstations are immediately dispatched to them in FIFO order.
   - Demonstrate that invalid inputs (0, negative, decimals, text) are safely rejected with informative messages.

3. **Dynamic Waiting Queue:**
   - Navigate to `/waiting-queue`.
   - Highlight the dynamic capacity card showing `X / Y Occupied` calculated directly from SQLite (no hardcoded limits).
   - Point to the live FIFO table displaying `Position | Student ID | Request Time | Status`.

4. **Dedicated Semaphore Management Board:**
   - Navigate to `/semaphore-management`.
   - Point out real-time telemetry: Total Semaphore Capacity, Available Permits, Acquired Permits, and the Visual Permit Rack.

5. **Safe Student Removal:**
   - On `/students`, demonstrate clicking **Remove** on an active student: the system cleanly blocks deletion and explains why.
   - Demonstrate **Remove All Eligible**: removes only idle students in one operation without browser confirmation popups, displaying count removed and skipped.
