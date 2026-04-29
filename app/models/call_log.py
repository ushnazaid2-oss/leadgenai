"""
Call Log model — tracks AI voice calls with transcripts and outcomes.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class CallOutcome(str, enum.Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    FOLLOW_UP = "follow_up"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    FAILED = "failed"


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    twilio_call_sid = Column(String(255), nullable=True, unique=True)
    from_number = Column(String(50), nullable=False)
    to_number = Column(String(50), nullable=False)
    duration_seconds = Column(Integer, default=0)
    outcome = Column(Enum(CallOutcome), nullable=True, index=True)
    transcript = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    call_script_used = Column(Text, nullable=True)
    is_hot_lead = Column(Boolean, default=False)
    scheduled_meeting = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="call_logs")
    campaign = relationship("Campaign", back_populates="call_logs")

    def __repr__(self):
        return f"<CallLog(id={self.id}, lead={self.lead_id}, outcome='{self.outcome}')>"
