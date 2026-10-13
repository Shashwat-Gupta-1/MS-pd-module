import logging
from typing import List
from sqlalchemy.orm import Session
from app.models.customer_consistency_flag import CustomerConsistencyFlag

logger = logging.getLogger(__name__)


def finalize_consistency_flags(session_id: str, db: Session) -> List[CustomerConsistencyFlag]:
    """
    End-of-Session Rollup (Section 8):
    Returns all customer consistency flags accumulated during live LangGraph batch execution.
    No new detection occurs here (Node 4 already identified discrepancies live).
    Surfaces the flags for officer end-of-visit review and report assembly.
    """
    flags = db.query(CustomerConsistencyFlag).filter(
        CustomerConsistencyFlag.pd_session_id == session_id
    ).order_by(CustomerConsistencyFlag.created_at.asc()).all()

    logger.info(f"Retrieved {len(flags)} customer consistency flags for session {session_id}")
    return flags
