from enum import Enum


class ErrorCode(str, Enum):
    unauthorized = "unauthorized"
    bad_request = "bad_request"
    source_unavailable = "source_unavailable"
    blocked_or_captcha = "blocked_or_captcha"
    timeout = "timeout"
    internal_error = "internal_error"


class ScraperError(Exception):
    error_code: ErrorCode = ErrorCode.internal_error


class BrightDataSourceUnavailable(ScraperError):
    error_code = ErrorCode.source_unavailable


class BrightDataTimeoutError(ScraperError):
    error_code = ErrorCode.timeout


class BrightDataInternalError(ScraperError):
    error_code = ErrorCode.internal_error


class YandexCaptchaError(ScraperError):
    error_code = ErrorCode.blocked_or_captcha


class YandexTimeoutError(ScraperError):
    error_code = ErrorCode.timeout


class YandexSourceUnavailableError(ScraperError):
    error_code = ErrorCode.source_unavailable
