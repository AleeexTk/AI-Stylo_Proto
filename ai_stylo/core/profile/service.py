from sqlalchemy.orm import Session
from ..models import Profile
from typing import Optional

class ProfileService:
    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, merchant_id: str, user_id: str) -> Profile:
        profile = self.db.query(Profile).filter(
            Profile.merchant_id == merchant_id, 
            Profile.user_id == user_id
        ).first()
        
        if not profile:
            profile = Profile(merchant_id=merchant_id, user_id=user_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_profile(self, profile: Profile):
        self.db.add(profile)
        self.db.commit()
