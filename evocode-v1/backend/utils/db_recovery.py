import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def get_db_path() -> str:
    """Helper to get the correct database path."""
    # Assuming the app is run from the backend directory
    default_db = "evocode.db"
    return os.getenv("DATABASE_URL", default_db).replace("sqlite:///", "")

def reset_stuck_features() -> Dict[str, Any]:
    """
    Find and reset all features stuck in processing state for more than 5 minutes.
    """
    db_path = get_db_path()
    result = {
        "reset_count": 0,
        "reset_ids": [],
        "message": "No stuck features found"
    }
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Calculate the threshold time (5 minutes ago)
        # Using string comparison for SQLite datetime (assuming stored in ISO format or similar)
        # SQLAlchemy default datetime.utcnow generates things like '2026-04-24 14:18:40.123456'
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        five_mins_ago_str = five_mins_ago.strftime('%Y-%m-%d %H:%M:%S')

        # Find stuck features
        c.execute(
            "SELECT id FROM issue_reports WHERE status = 'processing' AND updated_at < ?",
            (five_mins_ago_str,)
        )
        stuck_rows = c.fetchall()
        stuck_ids = [row["id"] for row in stuck_rows]
        
        if not stuck_ids:
            logger.info("[DB Recovery] No stuck features found.")
            return result
            
        # Reset them
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        for fid in stuck_ids:
            c.execute(
                """
                UPDATE issue_reports 
                SET status = 'failed', 
                    error_message = 'Process interrupted - ready for retry', 
                    current_step = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now_str, fid)
            )
            
        conn.commit()
        
        result["reset_count"] = len(stuck_ids)
        result["reset_ids"] = stuck_ids
        result["message"] = f"Reset {len(stuck_ids)} stuck features"
        
        logger.info(f"[DB Recovery] {result['message']} (IDs: {stuck_ids})")
        
    except sqlite3.Error as e:
        logger.error(f"[DB Recovery] Database error in reset_stuck_features: {e}")
        result["message"] = f"Database error: {e}"
    except Exception as e:
        logger.error(f"[DB Recovery] Unexpected error in reset_stuck_features: {e}")
        result["message"] = f"Unexpected error: {e}"
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
    return result

def reset_specific_feature(feature_id: int) -> Dict[str, Any]:
    """
    Reset a specific feature by ID regardless of how long it has been stuck.
    """
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Check if it exists and is processing
        c.execute("SELECT status FROM issue_reports WHERE id = ?", (feature_id,))
        row = c.fetchone()
        
        if not row:
            return {"success": False, "message": f"Feature ID {feature_id} not found."}
            
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute(
            """
            UPDATE issue_reports 
            SET status = 'failed', 
                error_message = 'Process interrupted - ready for retry', 
                current_step = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now_str, feature_id)
        )
        conn.commit()
        
        logger.info(f"[DB Recovery] Manually reset feature ID {feature_id}")
        return {"success": True, "message": f"Feature {feature_id} reset successfully"}
        
    except sqlite3.Error as e:
        logger.error(f"[DB Recovery] Database error in reset_specific_feature: {e}")
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def get_stuck_features() -> List[Dict[str, Any]]:
    """
    Query and return all stuck features without modifying them.
    A feature is stuck if it has been 'processing' for more than 5 minutes.
    """
    db_path = get_db_path()
    stuck_features = []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        five_mins_ago_str = five_mins_ago.strftime('%Y-%m-%d %H:%M:%S')

        c.execute(
            """
            SELECT id, bug_text as title, status, updated_at as stuck_since, current_step 
            FROM issue_reports 
            WHERE status = 'processing' AND updated_at < ?
            """,
            (five_mins_ago_str,)
        )
        
        rows = c.fetchall()
        for row in rows:
            stuck_features.append({
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "stuck_since": row["stuck_since"],
                "current_step": row["current_step"]
            })
            
        logger.info(f"[DB Recovery] Found {len(stuck_features)} stuck features")
        
    except sqlite3.Error as e:
        logger.error(f"[DB Recovery] Database error in get_stuck_features: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
    return stuck_features
