# Application exception hierarchy.

from __future__ import annotations

from typing import Any

# Base class for all application-level exceptions.
class AppException(Exception):
    status_code: int = 500
    error_code: str = "internal_error"
    default_message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

# 4xx Client errors
class BadRequestError(AppException):
    status_code = 400
    error_code = "bad_request"
    default_message = "Bad request"

class AuthenticationError(AppException):
    status_code = 401
    error_code = "unauthenticated"
    default_message = "Authentication required"

class InvalidCredentialsError(AuthenticationError):
    error_code = "invalid_credentials"
    default_message = "Invalid email or password"

class TokenExpiredError(AuthenticationError):
    error_code = "token_expired"
    default_message = "Token has expired"

class PermissionDeniedError(AppException):
    status_code = 403
    error_code = "permission_denied"
    default_message = "You do not have permission to perform this action"

class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"
    default_message = "Resource not found"

class ConflictError(AppException):
    status_code = 409
    error_code = "conflict"
    default_message = "Resource already exists"

class ValidationError(AppException):
    status_code = 422
    error_code = "validation_error"
    default_message = "Validation failed"

class RateLimitError(AppException):
    status_code = 429
    error_code = "rate_limited"
    default_message = "Too many requests"

# 5xx Server errors
class ServiceUnavailableError(AppException):
    status_code = 503
    error_code = "service_unavailable"
    default_message = "Service is temporarily unavailable"
