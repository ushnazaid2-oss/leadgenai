"""
WhatsApp Log model — tracks all inbound and outbound WhatsApp messages.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class WhatsAppDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class WhatsAppStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsAppLog(Base):
    __tablename__ = "whatsapp_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    template_name = Column(String(200), nullable=True)
    message_body = Column(Text, nullable=True)
    direction = Column(
        Enum(WhatsAppDirection), default=WhatsAppDirection.OUTBOUND, nullable=False
    )
    status = Column(
        Enum(WhatsAppStatus), default=WhatsAppStatus.QUEUED, nullable=False, index=True
    )
    whatsapp_message_id = Column(String(255), nullable=True)  # Meta's message ID
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="whatsapp_logs")
    campaign = relationship("Campaign", back_populates="whatsapp_logs")

    def __repr__(self):
        return f"<WhatsAppLog(id={self.id}, lead={self.lead_id}, direction='{self.direction}')>"
