"""
Lead model — the core entity of the CRM system.
Tracks contacts through the full pipeline from import to conversion.
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    OPENED = "opened"
    REPLIED = "replied"
    CALLED = "called"
    INTERESTED = "interested"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(str, enum.Enum):
    CSV_IMPORT = "csv_import"
    MANUAL = "manual"
    API = "api"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    company = Column(String(200), nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True, index=True)
    niche = Column(String(100), nullable=True, index=True)
    status = Column(
        Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True
    )
    is_hot_lead = Column(Boolean, default=False, index=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    email_logs = relationship("EmailLog", back_populates="lead", cascade="all, delete-orphan")
    whatsapp_logs = relationship("WhatsAppLog", back_populates="lead", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead(id={self.id}, name='{self.name}', status='{self.status}')>"
