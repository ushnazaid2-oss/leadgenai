"""
Activity model — unified timeline of all actions across all channels per lead.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class ActivityChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CALL = "call"
    MANUAL = "manual"
    SYSTEM = "system"


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    channel = Column(Enum(ActivityChannel), nullable=False, index=True)
    action = Column(String(100), nullable=False)   # e.g., "email_sent", "call_completed"
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)          # Flexible metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    lead = relationship("Lead", back_populates="activities")

    def __repr__(self):
        return f"<Activity(id={self.id}, lead={self.lead_id}, action='{self.action}')>"
