from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime


class ImagePayload(BaseModel):
    media_type: str
    data: str  # base64-encoded image bytes


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=2000)
    image: ImagePayload | None = None


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    created_at: datetime
