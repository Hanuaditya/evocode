import os
import sqlite3
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

def get_db_path() -> str:
    default_db = "evocode.db"
    return os.getenv("DATABASE_URL", default_db).replace("sqlite:///", "")

class HeartbeatMonitor:
    """
    Monitors process health by updating a last_heartbeat timestamp in the database.
    This allows the frontend to detect dead processes.
    """
    def __init__(self, feature_id: int, interval_seconds: int = 5):
        self.feature_id = feature_id
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None
        self.db_path = get_db_path()

    def start_heartbeat(self) -> None:
        """Starts the background thread to send regular heartbeats."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning(f"[Heartbeat] Already running for feature {self.feature_id}")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"HeartbeatThread-{self.feature_id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[Heartbeat] Started monitoring for feature {self.feature_id}")

    def stop_heartbeat(self) -> None:
        """Stops the heartbeat thread gracefully."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 1)
        logger.info(f"[Heartbeat] Stopped monitoring for feature {self.feature_id}")

    def _heartbeat_loop(self) -> None:
        """The loop that runs in the background thread."""
        while not self._stop_event.is_set():
            self._update_heartbeat()
            # Sleep in small chunks so we can exit quickly when stopped
            for _ in range(self.interval_seconds * 10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def _update_heartbeat(self) -> None:
        """Directly update the SQLite database to avoid SQLAlchemy session conflicts."""
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "UPDATE issue_reports SET last_heartbeat = ? WHERE id = ?",
                (now_str, self.feature_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[Heartbeat] Failed to update heartbeat for feature {self.feature_id}: {e}")
