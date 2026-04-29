"""
CSV Import Service — parse, clean, validate, deduplicate, and import leads from CSV files.
"""

import io
import re
import logging
from typing import Tuple, List

import pandas as pd
import phonenumbers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadSource

logger = logging.getLogger(__name__)

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class CSVImporter:
    """Handles CSV parsing, cleaning, validation, and import."""

    REQUIRED_COLUMNS = {"name", "email"}
    OPTIONAL_COLUMNS = {"company", "phone", "niche"}

    def __init__(self, db: AsyncSession):
        self.db = db
        self.errors: List[str] = []
        self.imported = 0
        self.skipped = 0
        self.duplicates = 0

    async def import_csv(self, file_content: bytes, filename: str = "upload.csv") -> dict:
        """
        Import leads from CSV file content.
        """
        logger.info(f"Starting CSV import: {filename}")
        self.errors = []
        self.imported = 0
        self.skipped = 0
        self.duplicates = 0

        try:
            # Parse CSV
            df = pd.read_csv(io.BytesIO(file_content))
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            return self._report(0, error=f"Failed to parse CSV: {str(e)}")

        # Flexible Column Mapping
        col_map = {}
        for col in df.columns:
            clean_col = col.strip().lower().replace(" ", "_")
            if clean_col in ["name", "full_name", "contact"]: col_map[col] = "name"
            elif clean_col in ["email", "e-mail", "email_address"]: col_map[col] = "email"
            elif clean_col in ["company", "business_name", "agency"]: col_map[col] = "company"
            elif clean_col in ["phone", "mobile", "telephone"]: col_map[col] = "phone"
            elif clean_col in ["niche", "category", "industry"]: col_map[col] = "niche"
        
        df = df.rename(columns=col_map)

        # Validate required columns (now only email is strictly required)
        if "email" not in df.columns:
            return self._report(len(df), error="Missing 'email' column in CSV")

        total_rows = len(df)
        logger.info(f"CSV loaded: {total_rows} rows, columns: {list(df.columns)}")

        # Process each row
        for idx, row in df.iterrows():
            await self._process_row(idx + 2, row)

        return self._report(total_rows)

    async def _process_row(self, row_num: int, row: pd.Series):
        """Process a single CSV row with fallbacks."""
        # Extract and clean fields
        email = self._clean_string(row.get("email"))
        
        # Skip empty or N/A emails
        if not email or email.lower() in ["n/a", "none", "nan"]:
            self.skipped += 1
            return

        if not EMAIL_REGEX.match(email):
            self.errors.append(f"Row {row_num}: Invalid email '{email}'")
            self.skipped += 1
            return

        email = email.lower()

        # Name Logic: Use Name, then Company, then a default
        name = self._clean_string(row.get("name"))
        company = self._clean_string(row.get("company"))
        
        if not name:
            name = company or "Valued Client"

        phone = self._clean_string(row.get("phone"))
        niche = self._clean_string(row.get("niche"))

        # Normalize phone (optional)
        if phone and phone.lower() not in ["n/a", "none"]:
            phone = self._normalize_phone(phone, row_num)

        # Check for duplicate
        existing = await self.db.execute(
            select(Lead).where(Lead.email == email)
        )
        if existing.scalar_one_or_none():
            self.duplicates += 1
            return

        # Create lead
        lead = Lead(
            name=name,
            email=email,
            company=company,
            phone=phone,
            niche=niche,
            source=LeadSource.CSV_IMPORT,
        )
        self.db.add(lead)
        self.imported += 1

    def _clean_string(self, value) -> str:
        """Clean and normalize a string value."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    def _normalize_phone(self, phone: str, row_num: int) -> str:
        """Normalize phone number to E.164 format."""
        try:
            parsed = phonenumbers.parse(phone, "US")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
            else:
                self.errors.append(f"Row {row_num}: Invalid phone '{phone}'")
                return ""
        except phonenumbers.NumberParseException:
            self.errors.append(f"Row {row_num}: Cannot parse phone '{phone}'")
            return ""

    def _report(self, total: int, error: str = None) -> dict:
        """Generate import report."""
        if error:
            self.errors.insert(0, error)
        return {
            "total_rows": total,
            "imported": self.imported,
            "skipped": self.skipped,
            "duplicates": self.duplicates,
            "errors": self.errors[:50],  # Limit error messages
        }
