from typing import Any, Optional
from pydantic import BaseModel
from app.errors import ErrorCode


class BaseResponse(BaseModel):
    status: str  # "success" | "failed"
    error_code: Optional[ErrorCode] = None
    data: Optional[Any] = None
