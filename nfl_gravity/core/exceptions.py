"""Custom exceptions for NFL Gravity package."""


class NFLGravityError(Exception):
    """Base exception class for NFL Gravity package."""
    pass


class ValidationError(NFLGravityError):
    """Raised when data validation fails."""
    pass


class ExtractionError(NFLGravityError):
    """Raised when data extraction fails."""
    pass


class ScrapingError(NFLGravityError):
    """Raised when web scraping fails."""
    pass


class LLMError(NFLGravityError):
    """Raised when LLM processing fails."""
    pass


class StorageError(NFLGravityError):
    """Raised when data storage fails."""
    pass


class ConfigurationError(NFLGravityError):
    """Raised when configuration is invalid."""
    pass


class RateLimitError(NFLGravityError):
    """Raised when rate limits are exceeded."""
    pass


class AuthenticationError(NFLGravityError):
    """Raised when authentication fails."""
    pass
