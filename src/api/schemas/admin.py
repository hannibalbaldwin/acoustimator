"""Pydantic schemas for the admin user management API."""

from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    created_at: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = "user"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
