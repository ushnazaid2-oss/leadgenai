"""
Lead schemas — request/response models for lead management.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import phonenumbers


class LeadCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    niche: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        try:
            parsed = phonenumbers.parse(v, "US")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            raise ValueError(f"Cannot parse phone number: {v}")


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    niche: Optional[str] = None
    status: Optional[str] = None
    is_hot_lead: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        try:
            parsed = phonenumbers.parse(v, "US")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            raise ValueError(f"Cannot parse phone number: {v}")


class LeadResponse(BaseModel):
    id: int
    name: str
    company: Optional[str] = None
    email: str
    phone: Optional[str] = None
    niche: Optional[str] = None
    status: str
    is_hot_lead: bool
    source: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    leads: List[LeadResponse]


class CSVImportResponse(BaseModel):
    total_rows: int
    imported: int
    skipped: int
    duplicates: int
    errors: List[str]
