"""Request models for routers/admin.py (PHO admin side)."""
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

IssueStatus = Literal["open", "assigned", "in_progress", "resolved", "closed", "rejected"]
Priority = Literal["low", "normal", "high", "urgent"]
Availability = Literal["available", "on_leave", "inactive"]


class StatusUpdate(BaseModel):
    status: IssueStatus
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def note_required(self):
        if self.status in ("rejected", "closed") and not (self.note or "").strip():
            raise ValueError("A note is required when rejecting or closing a complaint.")
        return self


class BulkStatusUpdate(StatusUpdate):
    ids: list[int] = Field(min_length=1, max_length=100)


class PriorityUpdate(BaseModel):
    priority: Priority


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note cannot be empty.")
        return value


class AssignRequest(BaseModel):
    worker_id: int
    note: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)   # required when reassigning (checked in router)


class UnassignRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


def _clean_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10:
        raise ValueError("Phone must be a 10-digit mobile number.")
    return digits


class WorkerBase(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = None
    skills: list[str] | None = None
    primary_skill: str | None = None
    zones: list[str] | None = None
    building_ids: list[str] | None = None
    shift_start: time | None = None
    shift_end: time | None = None
    work_days: list[int] | None = None
    max_active: int | None = Field(default=None, ge=1, le=10)

    @field_validator("phone")
    @classmethod
    def phone_digits(cls, value):
        return None if value is None else _clean_phone(value)

    @field_validator("work_days")
    @classmethod
    def valid_days(cls, value):
        if value is None:
            return value
        if not value or any(day < 1 or day > 7 for day in value):
            raise ValueError("Work days must be 1 (Mon) .. 7 (Sun), at least one.")
        return sorted(set(value))

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, value):
        if value is None:
            return value
        value = sorted({s.strip().lower() for s in value if s and s.strip()})
        if not value:
            raise ValueError("Pick at least one skill.")
        return value

    @model_validator(mode="after")
    def primary_in_skills(self):
        if self.primary_skill:
            self.primary_skill = self.primary_skill.strip().lower()
            if self.skills is not None and self.primary_skill not in self.skills:
                raise ValueError("Primary skill must be one of the skills.")
        if self.shift_start and self.shift_end and self.shift_start >= self.shift_end:
            raise ValueError("Shift end must be after shift start.")
        return self


class WorkerCreate(WorkerBase):
    name: str = Field(min_length=1, max_length=120)
    phone: str
    skills: list[str]


class WorkerUpdate(WorkerBase):
    """All fields optional; only the given ones change."""


class AvailabilityUpdate(BaseModel):
    status: Availability
    leave_from: date | None = None
    leave_to: date | None = None
    force: bool = False      # deactivate even with active jobs

    @model_validator(mode="after")
    def leave_dates(self):
        if self.status == "on_leave":
            if not self.leave_from or not self.leave_to:
                raise ValueError("Leave needs a from and to date.")
            if self.leave_from > self.leave_to:
                raise ValueError("Leave 'from' must be on or before 'to'.")
        else:
            self.leave_from = self.leave_to = None
        return self
