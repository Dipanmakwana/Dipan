
from pydantic import BaseModel, Field, field_validator, model_validator


class CreateIssueRequest(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=0, max_length=5000)
    building_id: str | None = Field(default=None, max_length=100)
    room: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_text: str | None = Field(default=None, max_length=300)
    photo_urls: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        return self


class IssueListQuery(BaseModel):
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


def _clean(value: str | None, what: str, required: bool = True) -> str | None:
    value = (value or "").strip()
    if required and not value:
        raise ValueError(f"{what} cannot be empty.")
    return value or None


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return _clean(value, "Comment")


class ConfirmRequest(BaseModel):
    """Student confirms a resolved issue is fixed -> closed, with a 1-5 rating."""
    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=1000)

    @field_validator("feedback")
    @classmethod
    def strip_feedback(cls, value: str | None) -> str | None:
        return _clean(value, "Feedback", required=False)


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = _clean(value, "Reason")
        if len(value) < 5:
            raise ValueError("Please describe what is still wrong (at least 5 characters).")
        return value
