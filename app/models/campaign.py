"""
Campaign model — tracks multi-channel outreach campaigns.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.database import Base


class CampaignType(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CALL = "call"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    type = Column(Enum(CampaignType), nullable=False, index=True)
    status = Column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False, index=True
    )
    template_name = Column(String(200), nullable=True)
    niche_filter = Column(String(100), nullable=True)   # To target leads by niche
    subject = Column(String(500), nullable=True)       # For email campaigns
    body = Column(Text, nullable=True)                  # Template body
    target_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    celery_task_id = Column(String(255), nullable=True)  # Track Celery task
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    email_logs = relationship("EmailLog", back_populates="campaign", cascade="all, delete-orphan")
    whatsapp_logs = relationship("WhatsAppLog", back_populates="campaign", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', type='{self.type}')>"
