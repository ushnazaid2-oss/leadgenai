"""
Email Account model — stores SMTP/SendGrid sender configurations.
Supports multiple accounts with per-account rate limiting.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from app.database import Base


class EmailProvider(str, enum.Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SENDGRID = "sendgrid"
    CUSTOM_SMTP = "custom_smtp"


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)           # Display name
    email = Column(String(255), unique=True, nullable=False)
    provider = Column(Enum(EmailProvider), nullable=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587)
    username = Column(String(255), nullable=True)
    encrypted_password = Column(String(500), nullable=True)  # Fernet-encrypted
    sendgrid_api_key = Column(String(500), nullable=True)    # For SendGrid accounts
    is_active = Column(Boolean, default=True)
    daily_limit = Column(Integer, default=500)
    hourly_limit = Column(Integer, default=50)
    sent_today = Column(Integer, default=0)
    sent_this_hour = Column(Integer, default=0)
    last_reset_date = Column(DateTime, nullable=True)
    last_hourly_reset = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailAccount(id={self.id}, email='{self.email}', provider='{self.provider}')>"
