"""
Data Models for Computer Lab Allocation System
===============================================
Simple data representations and queries for lab entities:
- Workstation
- Student
- Allocation
- WaitingQueue
- AllocationHistory
"""

from app.database import get_db_connection


class WorkstationModel:
    """Manages workstation records."""

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT w.pc_id, w.status, a.student_id, a.login_time
                FROM workstations w
                LEFT JOIN allocations a ON w.pc_id = a.pc_id
                ORDER BY w.pc_id ASC
            """).fetchall()
        finally:
            conn.close()


class StudentModel:
    """Manages student records."""

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT student_id, student_name, created_at
                FROM students
                ORDER BY student_id ASC
            """).fetchall()
        finally:
            conn.close()


class WaitingQueueModel:
    """Manages FIFO waiting queue records."""

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT q.queue_id, q.student_id, q.request_time, s.student_name
                FROM waiting_queue q
                LEFT JOIN students s ON q.student_id = s.student_id
                ORDER BY q.queue_id ASC
            """).fetchall()
        finally:
            conn.close()


class HistoryModel:
    """Manages allocation audit history."""

    @staticmethod
    def get_all(limit=None):
        conn = get_db_connection()
        try:
            query = """
                SELECT h.history_id, h.student_id, h.pc_id, h.action, h.event_time, s.student_name
                FROM allocation_history h
                LEFT JOIN students s ON h.student_id = s.student_id
                ORDER BY h.history_id DESC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            return conn.execute(query).fetchall()
        finally:
            conn.close()


class AnalyticsModel:
    """Computes lab usage analytics and statistics."""

    @staticmethod
    def get_stats():
        conn = get_db_connection()
        try:
            total_allocations = conn.execute("""
                SELECT COUNT(*) FROM allocation_history WHERE action IN ('Allocated', 'Reassigned')
            """).fetchone()[0]

            total_logouts = conn.execute("""
                SELECT COUNT(*) FROM allocation_history WHERE action = 'Logout'
            """).fetchone()[0]

            pc_usage = conn.execute("""
                SELECT pc_id, COUNT(*) as count
                FROM allocation_history
                WHERE action IN ('Allocated', 'Reassigned')
                GROUP BY pc_id
                ORDER BY pc_id ASC
            """).fetchall()

            action_counts = conn.execute("""
                SELECT action, COUNT(*) as count
                FROM allocation_history
                GROUP BY action
            """).fetchall()

            return {
                "total_allocations": total_allocations,
                "total_logouts": total_logouts,
                "pc_usage": {row["pc_id"]: row["count"] for row in pc_usage},
                "action_counts": {row["action"]: row["count"] for row in action_counts}
            }
        finally:
            conn.close()
