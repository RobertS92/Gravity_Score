"""
API Authentication
Simple API key authentication for protected endpoints
"""

from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# HTTP Bearer token security scheme
security = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Verify API key for protected endpoints
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If API key is invalid
    """
    configured_key = (settings.API_KEY or "").strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY is not configured on this service",
        )
    if credentials.credentials != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
