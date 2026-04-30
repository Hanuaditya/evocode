import os
import signal
import logging
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Any

# Ensure we can import db config/utilities
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

logger = logging.getLogger(__name__)

def get_db_path() -> str:
    default_db = "evocode.db"
    return os.getenv("DATABASE_URL", default_db).replace("sqlite:///", "")

class ProcessManager:
    """
    Singleton class to track running background processes and handle 
    graceful shutdown when the server is restarted/killed.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProcessManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.active_tasks: Dict[int, Dict[str, Any]] = {}
        self._register_signal_handlers()

    def _register_signal_handlers(self):
        """Sets up signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            # SIGBREAK is useful on Windows
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, self.handle_shutdown)
        except Exception as e:
            logger.warning(f"[ProcessManager] Could not register signal handlers: {e}")

    def register_task(self, feature_id: int, task_name: str) -> None:
        """Register that a background task started."""
        self.active_tasks[feature_id] = {
            "name": task_name,
            "started_at": datetime.utcnow(),
            "pid": os.getpid()
        }
        logger.info(f"[ProcessManager] Registered task {task_name} for feature {feature_id}")

    def unregister_task(self, feature_id: int) -> None:
        """Mark task as completed."""
        if feature_id in self.active_tasks:
            del self.active_tasks[feature_id]
            logger.info(f"[ProcessManager] Unregistered task for feature {feature_id}")

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Returns list of currently running tasks."""
        tasks = []
        for fid, info in self.active_tasks.items():
            task_info = {"feature_id": fid}
            task_info.update(info)
            tasks.append(task_info)
        return tasks

    def handle_shutdown(self, signum, frame) -> None:
        """Called when process is killed (SIGTERM, SIGINT)."""
        logger.warning(f"[ProcessManager] Shutdown signal ({signum}) received, cleaning up...")
        
        if not self.active_tasks:
            logger.info("[ProcessManager] No active tasks to clean up.")
            sys.exit(0)

        db_path = get_db_path()
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()

            for feature_id, info in self.active_tasks.items():
                logger.info(f"[ProcessManager] Cleaning up aborted feature {feature_id}...")
                c.execute(
                    """
                    UPDATE issue_reports 
                    SET status = 'failed', 
                        error_message = 'Server restarted - process was interrupted', 
                        current_step = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now_str, feature_id)
                )
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ProcessManager] Database cleanup failed during shutdown: {e}")
        
        logger.info("[ProcessManager] Cleanup complete. Exiting gracefully.")
        sys.exit(0)

# Export a singleton instance
process_manager = ProcessManager()
