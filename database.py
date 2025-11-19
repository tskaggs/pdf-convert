import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict, List
import json

import os
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getenv("DATA_DIR", "."), "pdf_convert.db"))

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    
    # API tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Usage tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token_id INTEGER,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            input_format TEXT,
            output_format TEXT,
            pages_converted INTEGER DEFAULT 0,
            file_size INTEGER,
            response_time_ms INTEGER,
            status_code INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (token_id) REFERENCES api_tokens (id)
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == password_hash

def generate_token() -> str:
    """Generate a secure API token"""
    return secrets.token_urlsafe(32)

def create_user(username: str, email: str, password: str, is_admin: bool = False) -> int:
    """Create a new user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    created_at = datetime.utcnow().isoformat() + "Z"
    
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, password_hash, is_admin, created_at))
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        raise ValueError("User already exists")
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def create_api_token(user_id: int, name: str) -> str:
    """Create a new API token for a user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    token = generate_token()
    created_at = datetime.utcnow().isoformat() + "Z"
    
    cursor.execute("""
        INSERT INTO api_tokens (user_id, token, name, created_at, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (user_id, token, name, created_at))
    
    conn.commit()
    conn.close()
    return token

def get_token_info(token: str) -> Optional[Dict]:
    """Get token information including user details"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.*, u.username, u.email, u.is_admin
        FROM api_tokens t
        JOIN users u ON t.user_id = u.id
        WHERE t.token = ? AND t.is_active = 1
    """, (token,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def update_token_last_used(token: str):
    """Update the last_used_at timestamp for a token"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    last_used_at = datetime.utcnow().isoformat() + "Z"
    cursor.execute("""
        UPDATE api_tokens
        SET last_used_at = ?
        WHERE token = ?
    """, (last_used_at, token))
    
    conn.commit()
    conn.close()

def log_usage(
    user_id: Optional[int],
    token_id: Optional[int],
    endpoint: str,
    method: str,
    input_format: Optional[str] = None,
    output_format: Optional[str] = None,
    pages_converted: int = 0,
    file_size: Optional[int] = None,
    response_time_ms: Optional[int] = None,
    status_code: int = 200
):
    """Log API usage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created_at = datetime.utcnow().isoformat() + "Z"
    
    cursor.execute("""
        INSERT INTO usage_logs (
            user_id, token_id, endpoint, method, input_format, output_format,
            pages_converted, file_size, response_time_ms, status_code, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, token_id, endpoint, method, input_format, output_format,
        pages_converted, file_size, response_time_ms, status_code, created_at
    ))
    
    conn.commit()
    conn.close()

def get_usage_stats(user_id: Optional[int] = None, days: int = 30) -> Dict:
    """Get usage statistics"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total requests
    if user_id:
        cursor.execute("""
            SELECT COUNT(*) as total_requests
            FROM usage_logs
            WHERE user_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
        """, (user_id, days))
    else:
        cursor.execute("""
            SELECT COUNT(*) as total_requests
            FROM usage_logs
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        """, (days,))
    
    total_requests = cursor.fetchone()["total_requests"]
    
    # Total pages converted
    if user_id:
        cursor.execute("""
            SELECT COALESCE(SUM(pages_converted), 0) as total_pages
            FROM usage_logs
            WHERE user_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
        """, (user_id, days))
    else:
        cursor.execute("""
            SELECT COALESCE(SUM(pages_converted), 0) as total_pages
            FROM usage_logs
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        """, (days,))
    
    total_pages = cursor.fetchone()["total_pages"]
    
    # Requests by endpoint
    if user_id:
        cursor.execute("""
            SELECT endpoint, COUNT(*) as count
            FROM usage_logs
            WHERE user_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY endpoint
        """, (user_id, days))
    else:
        cursor.execute("""
            SELECT endpoint, COUNT(*) as count
            FROM usage_logs
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY endpoint
        """, (days,))
    
    endpoint_stats = {row["endpoint"]: row["count"] for row in cursor.fetchall()}
    
    # Requests by output format
    if user_id:
        cursor.execute("""
            SELECT output_format, COUNT(*) as count
            FROM usage_logs
            WHERE user_id = ? AND output_format IS NOT NULL 
            AND created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY output_format
        """, (user_id, days))
    else:
        cursor.execute("""
            SELECT output_format, COUNT(*) as count
            FROM usage_logs
            WHERE output_format IS NOT NULL 
            AND created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY output_format
        """, (days,))
    
    format_stats = {row["output_format"]: row["count"] for row in cursor.fetchall()}
    
    # Daily usage (last 7 days)
    if user_id:
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM usage_logs
            WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM usage_logs
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
    
    daily_usage = [{"date": row["date"], "count": row["count"]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_requests": total_requests,
        "total_pages_converted": total_pages,
        "endpoint_stats": endpoint_stats,
        "format_stats": format_stats,
        "daily_usage": daily_usage
    }

def get_all_users() -> List[Dict]:
    """Get all users (admin only)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return users

def get_user_tokens(user_id: int) -> List[Dict]:
    """Get all tokens for a user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM api_tokens
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    tokens = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tokens

def revoke_token(token_id: int, user_id: int):
    """Revoke a token (only owner or admin)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE api_tokens
        SET is_active = 0
        WHERE id = ? AND user_id = ?
    """, (token_id, user_id))
    
    conn.commit()
    conn.close()

