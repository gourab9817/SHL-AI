from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class RecommendationItem(BaseModel):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    test_type: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("messages")
    @classmethod
    def must_include_user_message(cls, value: list[Message]) -> list[Message]:
        if not any(message.role == "user" for message in value):
            raise ValueError("messages must include at least one user message")
        return value


class ChatResponse(BaseModel):
    reply: str = Field(min_length=1)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    end_of_conversation: bool

    model_config = ConfigDict(extra="forbid")
