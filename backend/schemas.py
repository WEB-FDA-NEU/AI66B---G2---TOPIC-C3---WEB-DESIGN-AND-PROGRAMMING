"""Validated inputs; response serializers explicitly whitelist public fields."""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
BookingState = Literal["pending", "confirmed", "checked_in", "completed", "cancelled", "rejected"]
Money = Annotated[Decimal, Field(ge=0, le=99999999999, decimal_places=0)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=False)

    @field_validator("*", check_fields=False)
    @classmethod
    def password_utf8(cls, value):
        pending = [value]
        while pending:
            candidate = pending.pop()
            if isinstance(candidate, SecretStr):
                candidate = candidate.get_secret_value()
            if isinstance(candidate, dict):
                pending.extend(candidate.keys())
                pending.extend(candidate.values())
            elif isinstance(candidate, (list, tuple)):
                pending.extend(candidate)
            elif isinstance(candidate, str):
                try:
                    candidate.encode("utf-8")
                except UnicodeEncodeError:
                    raise ValueError("Text must be valid UTF-8") from None
        return value


class ProfileIn(Input):
    display_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    phone: str = Field(default="", max_length=20)
    avatar: str | None = Field(default=None, max_length=500000)

    @field_validator("display_name", "phone", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def email_normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        if value and not re.fullmatch(r"(?:0|\+84)[35789][0-9]{8}", value):
            raise ValueError("Invalid Vietnamese phone number")
        return value


class RegisterIn(ProfileIn):
    password: SecretStr = Field(min_length=8, max_length=128)
    role: Literal["user"] = "user"


class ProfilePatch(ProfileIn):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict) and any(v is None for v in value.values()):
            raise ValueError("Omit unchanged fields instead of null")
        return value


class LoginIn(Input):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def email_normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordIn(Input):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)


class HostApplicationData(Input):
    homestay_name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=5, max_length=300)
    province: str = Field(min_length=2, max_length=120)
    room_count: int = Field(ge=1, le=100)
    description: str = Field(min_length=10, max_length=1000)
    experience: str = Field(default="", max_length=1000)
    phone: str = Field(max_length=20)
    accept_terms: Literal[True]

    @field_validator("homestay_name", "address", "province", "description", "experience", "phone", mode="before")
    @classmethod
    def trim_application_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def valid_application_phone(cls, value):
        if not re.fullmatch(r"(?:0|\+84)[35789][0-9]{8}", value):
            raise ValueError("Invalid Vietnamese phone number")
        return value


class ApplicationIn(Input):
    application_data: HostApplicationData


class ReasonIn(Input):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class PaymentSimulationIn(ReasonIn):
    action: Literal["paid", "refunded"]


class HomestayIn(Input):
    status: Literal["active", "inactive"] = "active"
    id: str | int | None = None
    name: Name
    address: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=5, max_length=20000)
    city: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=500)
    amenities: list[str] = Field(default_factory=list, max_length=40)
    images: list[str] = Field(default_factory=lambda: ["img/placeholder.svg"], max_length=12)
    room_type: str = Field(default="Phòng riêng", min_length=2, max_length=80)

    @field_validator("address", "description", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("amenities")
    @classmethod
    def amenities_valid(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Invalid amenities")
        return list(dict.fromkeys(values))


class RoomIn(Input):
    status: Literal["active", "inactive"] = "active"
    id: str | int | None = None
    homestay_id: int = Field(alias="homestayId", ge=1)
    name: Name
    description: str = Field(min_length=5, max_length=10000)
    capacity: int = Field(ge=1, le=50, strict=True)
    price_per_night: Money = Field(alias="pricePerNight", gt=0)
    inventory: int = Field(default=1, ge=1, le=100, strict=True)
    images: list[str] = Field(default_factory=lambda: ["img/placeholder.svg"], max_length=6)
    blocked_dates: list[date] | None = Field(default=None, alias="blockedDates", max_length=365)


class BlockIn(Input):
    unit: int | None = Field(default=None, ge=1, le=100, strict=True)
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def dates(self):
        if not 0 < (self.end_date - self.start_date).days <= 365:
            raise ValueError("Block must be between 1 and 365 nights")
        return self


class RoomSelection(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    key: str | None = Field(default=None, max_length=80)
    room_id: int | None = Field(default=None, alias="roomId", ge=1)
    qty: int = Field(ge=1, le=100, strict=True)

    @model_validator(mode="after")
    def identifier(self):
        if not self.key and not self.room_id:
            raise ValueError("A real room key or roomId is required")
        return self


class QuoteIn(BaseModel):
    # Existing checkout sends untrusted display/price snapshots. Ignore these, never persist them.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    homestay_id: int = Field(alias="homestayId", ge=1)
    check_in: date = Field(validation_alias=AliasChoices("checkIn", "checkin", "check_in"))
    check_out: date = Field(validation_alias=AliasChoices("checkOut", "checkout", "check_out"))
    adults: int = Field(default=2, ge=1, le=10, strict=True)
    children: int = Field(default=0, ge=0, le=6, strict=True)
    rooms: list[RoomSelection] = Field(min_length=1, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def no_card_data(cls, data):
        forbidden = {"cardnum", "cardnumber", "card_num", "cvv", "cardcvv", "pan", "cvc", "cardexp"}
        if isinstance(data, dict) and any(str(key).lower() in forbidden for key in data):
            raise ValueError("Raw card data is not accepted")
        return data

    @model_validator(mode="after")
    def dates(self):
        if not 0 < (self.check_out - self.check_in).days <= 365:
            raise ValueError("Stay must be between 1 and 365 nights")
        try:
            for value in [getattr(self, "guest_name", ""), *(r.key or "" for r in self.rooms)]:
                value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Booking text must be valid UTF-8") from None
        return self


class BookingIn(QuoteIn):
    guest_name: Name = Field(alias="guestName")
    guest_email: EmailStr = Field(alias="guestEmail")


class StatusIn(Input):
    status: Literal["confirmed", "checked_in", "completed", "rejected"]
    reason: str = Field(default="", max_length=1000)

    @field_validator("reason")
    @classmethod
    def utf8_reason(cls, value):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Reason must be valid UTF-8") from None
        return value


class ReviewIn(Input):
    booking_id: int | None = Field(default=None, alias="bookingId", ge=1)
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str = Field(min_length=5, max_length=3000)
    name: str | None = Field(default=None, max_length=160)  # ignored: author is the authenticated customer

    @field_validator("comment", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class AdminUserIn(Input):
    is_active: bool | None = None
    role: Literal["user", "admin"] | None = (
        None  # host role can only be granted through reviewed applications
    )


class ModerationIn(ReasonIn):
    status: Literal["active", "inactive"]


class UserOut(BaseModel):
    id: int
    display_name: str
    email: str
    phone: str
    role: str
    avatar: str
    createdAt: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
