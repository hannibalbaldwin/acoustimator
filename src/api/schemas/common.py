"""Common shared Pydantic schemas."""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    """Wrapper for paginated list responses."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str
