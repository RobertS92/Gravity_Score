"""Custom exceptions for Feature Testing MCP Server"""


class FeatureTestingError(Exception):
    """Base exception for feature testing operations"""
    pass


class SheetsError(FeatureTestingError):
    """Google Sheets operations error"""
    pass


class TestExecutionError(FeatureTestingError):
    """Test execution error"""
    pass


class ConfigurationError(FeatureTestingError):
    """Configuration error"""
    pass


class ValidationError(FeatureTestingError):
    """Validation error"""
    pass
