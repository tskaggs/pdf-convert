from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import time
from database import get_token_info, update_token_last_used

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify API token from Authorization header
    Returns user information if token is valid
    """
    token = credentials.credentials
    
    token_info = get_token_info(token)
    if not token_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API token"
        )
    
    # Update last used timestamp
    update_token_last_used(token)
    
    return {
        "user_id": token_info["user_id"],
        "username": token_info["username"],
        "email": token_info["email"],
        "is_admin": bool(token_info["is_admin"]),
        "token_id": token_info["id"]
    }

async def get_current_user(auth: dict = Depends(verify_token)) -> dict:
    """Get current authenticated user"""
    return auth

async def get_admin_user(auth: dict = Depends(verify_token)) -> dict:
    """Get current user and verify admin status"""
    if not auth.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return auth

def log_request_time(func):
    """Decorator to log request processing time"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            response_time_ms = int((time.time() - start_time) * 1000)
            # Store response time in kwargs for logging
            if hasattr(result, '__dict__'):
                result._response_time_ms = response_time_ms
            return result
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            e._response_time_ms = response_time_ms
            raise
    return wrapper

