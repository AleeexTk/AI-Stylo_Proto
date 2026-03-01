from sqlalchemy.orm import Session
from ..models import Event
from typing import Any, Dict, List

class EventService:
    def __init__(self, db: Session):
        self.db = db

    def log(self, merchant_id: str, user_id: str, event_type: str, payload: Dict[str, Any] = None) -> Event:
        event = Event(
            merchant_id=merchant_id,
            user_id=user_id,
            type=event_type,
            payload=payload or {}
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_history(self, merchant_id: str, user_id: str = None, limit: int = 100) -> List[Event]:
        query = self.db.query(Event).filter(Event.merchant_id == merchant_id)
        if user_id:
            query = query.filter(Event.user_id == user_id)
        return query.order_by(Event.ts.desc()).limit(limit).all()
