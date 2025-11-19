from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr
import uuid
import fitz  # PyMuPDF
from PIL import Image
import io
from enum import Enum
import time
import os

# Import database and auth modules
from database import (
    init_db, create_user, get_user_by_username, create_api_token,
    get_user_tokens, log_usage, get_usage_stats, get_all_users,
    revoke_token, get_user_by_id
)
from auth import verify_token, get_current_user, get_admin_user

app = FastAPI(title="PDF to Image Converter API", version="1.0.0")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supported output formats
class OutputFormat(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"
    GIF = "gif"
    WEBP = "webp"

# Request model
class ConvertRequest(BaseModel):
    input_format: Optional[str] = "pdf"
    output_format: OutputFormat
    pages: Optional[str] = None  # e.g., "1-3" or "1,2,3"
    dpi: Optional[int] = 300
    quality: Optional[int] = 95  # For JPEG/WebP

# Response models
class TaskPayload(BaseModel):
    input_format: str
    output_format: str
    pages: Optional[str] = None
    dpi: Optional[int] = None
    quality: Optional[int] = None

class TaskResult(BaseModel):
    files: List[dict]
    count: int

class TaskResponse(BaseModel):
    id: str
    operation: str
    status: str
    message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    depends_on_tasks: dict = {}
    engine: str = "pymupdf"
    engine_version: str = "1.23.0"
    payload: TaskPayload
    result: Optional[TaskResult] = None

class ConvertResponse(BaseModel):
    data: TaskResponse

# Temporary storage for converted files
temp_storage = {}

def parse_pages(pages_str: str, total_pages: int) -> List[int]:
    """Parse page range string like '1-3' or '1,2,3' into list of page numbers (0-indexed)"""
    if not pages_str:
        return list(range(total_pages))
    
    page_nums = []
    parts = pages_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            start = int(start.strip()) - 1  # Convert to 0-indexed
            end = int(end.strip())  # Keep 1-indexed for range
            page_nums.extend(range(start, min(end, total_pages)))
        else:
            page_num = int(part.strip()) - 1  # Convert to 0-indexed
            if 0 <= page_num < total_pages:
                page_nums.append(page_num)
    
    return sorted(set(page_nums))

def convert_pdf_to_images(
    pdf_bytes: bytes,
    output_format: str,
    pages: Optional[str] = None,
    dpi: int = 300,
    quality: int = 95
) -> List[bytes]:
    """Convert PDF pages to images"""
    # Open PDF from bytes
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    
    # Parse which pages to convert
    page_indices = parse_pages(pages, total_pages) if pages else list(range(total_pages))
    
    images = []
    for page_num in page_indices:
        page = pdf_doc[page_num]
        
        # Render page to pixmap (image)
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # Scale factor for DPI
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Convert to requested format
        output_buffer = io.BytesIO()
        
        if output_format.lower() in ["jpeg", "jpg"]:
            # Convert RGBA to RGB if needed
            if img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img
            img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
        elif output_format.lower() == "webp":
            img.save(output_buffer, format="WEBP", quality=quality, method=6)
        elif output_format.lower() == "gif":
            # Convert to RGB if needed
            if img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img
            img.save(output_buffer, format="GIF")
        else:  # PNG (default)
            img.save(output_buffer, format="PNG", optimize=True)
        
        images.append(output_buffer.getvalue())
        output_buffer.close()
    
    pdf_doc.close()
    return images

@app.get("/")
async def root():
    return {
        "message": "PDF to Image Converter API",
        "version": "1.0.0",
        "endpoints": {
            "convert": "/convert",
            "formats": "/convert/formats"
        }
    }

@app.get("/convert/formats")
async def list_formats():
    """List supported conversion formats"""
    return {
        "data": [
            {
                "operation": "convert",
                "input_format": "pdf",
                "output_format": "png",
                "engine": "pymupdf",
                "credits": 1,
                "deprecated": False,
                "experimental": False
            },
            {
                "operation": "convert",
                "input_format": "pdf",
                "output_format": "jpeg",
                "engine": "pymupdf",
                "credits": 1,
                "deprecated": False,
                "experimental": False
            },
            {
                "operation": "convert",
                "input_format": "pdf",
                "output_format": "gif",
                "engine": "pymupdf",
                "credits": 1,
                "deprecated": False,
                "experimental": False
            },
            {
                "operation": "convert",
                "input_format": "pdf",
                "output_format": "webp",
                "engine": "pymupdf",
                "credits": 1,
                "deprecated": False,
                "experimental": False
            }
        ]
    }

@app.post("/convert", response_model=ConvertResponse)
async def convert_pdf(
    request: Request,
    file: UploadFile = File(...),
    input_format: str = Form("pdf"),
    output_format: OutputFormat = Form(...),
    pages: Optional[str] = Form(None),
    dpi: Optional[int] = Form(300),
    quality: Optional[int] = Form(95),
    auth: dict = Depends(verify_token)
):
    """
    Convert PDF file to image format (PNG, JPEG, GIF, or WebP)
    Requires API token in Authorization header: Bearer <token>
    
    - **file**: PDF file to convert
    - **input_format**: Input format (default: pdf)
    - **output_format**: Output format (png, jpeg, jpg, gif, webp)
    - **pages**: Page range (e.g., "1-3" or "1,2,3"). If not specified, all pages are converted.
    - **dpi**: Resolution in DPI (default: 300)
    - **quality**: Image quality for JPEG/WebP (1-100, default: 95)
    """
    start_time = time.time()
    user_id = auth.get("user_id")
    token_id = auth.get("token_id")
    status_code = 200
    
    try:
        # Validate input format
        if input_format.lower() != "pdf":
            raise HTTPException(status_code=400, detail=f"Input format '{input_format}' is not supported. Only PDF is supported.")
        
        # Read PDF file
        pdf_bytes = await file.read()
        
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Validate it's a PDF
        if not pdf_bytes.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat() + "Z"
        
        # Convert PDF to images
        started_at = datetime.utcnow().isoformat() + "Z"
        images = convert_pdf_to_images(
            pdf_bytes,
            output_format.value,
            pages,
            dpi,
            quality
        )
        ended_at = datetime.utcnow().isoformat() + "Z"
        
        # Store converted images temporarily
        file_paths = []
        for idx, img_bytes in enumerate(images):
            # Determine file extension
            suffix = f".{output_format.value}"
            if output_format.value == "jpg":
                suffix = ".jpg"
            
            file_paths.append({
                "filename": f"page-{idx + 1}{suffix}",
                "url": f"/download/{task_id}/{idx}",
                "size": len(img_bytes)
            })
        
        # Store task info
        temp_storage[task_id] = {
            "files": file_paths,
            "images": images
        }
        
        # Build response
        response = ConvertResponse(
            data=TaskResponse(
                id=task_id,
                operation="convert",
                status="finished",
                message=None,
                created_at=created_at,
                started_at=started_at,
                ended_at=ended_at,
                depends_on_tasks={},
                engine="pymupdf",
                engine_version="1.23.0",
                payload=TaskPayload(
                    input_format=input_format,
                    output_format=output_format.value,
                    pages=pages,
                    dpi=dpi,
                    quality=quality
                ),
                result=TaskResult(
                    files=file_paths,
                    count=len(file_paths)
                )
            )
        )
        
        # Log usage
        response_time_ms = int((time.time() - start_time) * 1000)
        log_usage(
            user_id=user_id,
            token_id=token_id,
            endpoint="/convert",
            method="POST",
            input_format=input_format,
            output_format=output_format.value,
            pages_converted=len(images),
            file_size=len(pdf_bytes),
            response_time_ms=response_time_ms,
            status_code=status_code
        )
        
        return response
        
    except HTTPException as e:
        status_code = e.status_code
        response_time_ms = int((time.time() - start_time) * 1000)
        log_usage(
            user_id=user_id,
            token_id=token_id,
            endpoint="/convert",
            method="POST",
            input_format=input_format,
            output_format=output_format.value if output_format else None,
            response_time_ms=response_time_ms,
            status_code=status_code
        )
        raise
    except Exception as e:
        status_code = 500
        response_time_ms = int((time.time() - start_time) * 1000)
        log_usage(
            user_id=user_id,
            token_id=token_id,
            endpoint="/convert",
            method="POST",
            response_time_ms=response_time_ms,
            status_code=status_code
        )
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.get("/download/{task_id}/{page_index}")
async def download_file(
    task_id: str,
    page_index: int,
    auth: dict = Depends(verify_token)
):
    """Download converted image file as binary. Requires API token."""
    start_time = time.time()
    user_id = auth.get("user_id")
    token_id = auth.get("token_id")
    
    if task_id not in temp_storage:
        status_code = 404
        response_time_ms = int((time.time() - start_time) * 1000)
        log_usage(
            user_id=user_id,
            token_id=token_id,
            endpoint=f"/download/{task_id}/{page_index}",
            method="GET",
            response_time_ms=response_time_ms,
            status_code=status_code
        )
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = temp_storage[task_id]
    if page_index >= len(task_data["images"]):
        status_code = 404
        response_time_ms = int((time.time() - start_time) * 1000)
        log_usage(
            user_id=user_id,
            token_id=token_id,
            endpoint=f"/download/{task_id}/{page_index}",
            method="GET",
            response_time_ms=response_time_ms,
            status_code=status_code
        )
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Get image bytes
    img_bytes = task_data["images"][page_index]
    file_info = task_data["files"][page_index]
    
    # Determine media type
    output_format = file_info["filename"].split(".")[-1].lower()
    media_type_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    media_type = media_type_map.get(output_format, "application/octet-stream")
    
    # Log usage
    response_time_ms = int((time.time() - start_time) * 1000)
    log_usage(
        user_id=user_id,
        token_id=token_id,
        endpoint=f"/download/{task_id}/{page_index}",
        method="GET",
        file_size=len(img_bytes),
        response_time_ms=response_time_ms,
        status_code=200
    )
    
    # Return file directly from memory
    return Response(
        content=img_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_info["filename"]}"'}
    )

# Authentication and User Management Endpoints

class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_admin: bool = False

class CreateTokenRequest(BaseModel):
    name: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/register")
async def register_user(user_data: CreateUserRequest, admin: dict = Depends(get_admin_user)):
    """Register a new user (admin only)"""
    try:
        user_id = create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            is_admin=user_data.is_admin
        )
        return {
            "message": "User created successfully",
            "user_id": user_id,
            "username": user_data.username
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
async def login(login_data: LoginRequest):
    """Login and get API token"""
    from database import verify_password
    
    user = get_user_by_username(login_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create a new token
    token = create_api_token(user["id"], "Login Token")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user["is_admin"])
        }
    }

@app.post("/auth/tokens")
async def create_token(token_data: CreateTokenRequest, auth: dict = Depends(get_current_user)):
    """Create a new API token"""
    token = create_api_token(auth["user_id"], token_data.name)
    return {
        "token": token,
        "name": token_data.name,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/auth/tokens")
async def list_tokens(auth: dict = Depends(get_current_user)):
    """List all API tokens for the current user"""
    tokens = get_user_tokens(auth["user_id"])
    # Don't return full token, only last 8 characters
    for token in tokens:
        if token["token"]:
            token["token_preview"] = "..." + token["token"][-8:]
            token["token"] = None  # Don't expose full token
    return {"tokens": tokens}

@app.delete("/auth/tokens/{token_id}")
async def delete_token(token_id: int, auth: dict = Depends(get_current_user)):
    """Revoke an API token"""
    revoke_token(token_id, auth["user_id"])
    return {"message": "Token revoked successfully"}

@app.get("/auth/me")
async def get_current_user_info(auth: dict = Depends(get_current_user)):
    """Get current user information"""
    user = get_user_by_id(auth["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
        "created_at": user["created_at"]
    }

# Usage Statistics Endpoints

@app.get("/usage/stats")
async def get_stats(auth: dict = Depends(get_current_user), days: int = 30):
    """Get usage statistics for the current user"""
    stats = get_usage_stats(user_id=auth["user_id"], days=days)
    return stats

@app.get("/usage/stats/all")
async def get_all_stats(admin: dict = Depends(get_admin_user), days: int = 30):
    """Get usage statistics for all users (admin only)"""
    stats = get_usage_stats(user_id=None, days=days)
    return stats

# Admin Endpoints

@app.get("/admin/users")
async def list_users(admin: dict = Depends(get_admin_user)):
    """List all users (admin only)"""
    users = get_all_users()
    # Remove password hashes
    for user in users:
        user.pop("password_hash", None)
    return {"users": users}

# Dashboard Endpoint

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, token: Optional[str] = None):
    """Management dashboard"""
    # Try to get token from query parameter or Authorization header
    auth_token = token
    if not auth_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]
    
    # If no token provided, show login form
    if not auth_token:
        return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Converter - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 100%;
        }
        h1 { color: #333; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 20px; }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            margin-bottom: 15px;
        }
        button {
            width: 100%;
            background: #667eea;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover { background: #5568d3; }
        .error { color: #e74c3c; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>PDF Converter Dashboard</h1>
        <p>Enter your API token to access the dashboard</p>
        <input type="text" id="token" placeholder="API Token" />
        <button onclick="login()">Access Dashboard</button>
        <p style="margin-top: 20px; font-size: 12px; color: #999;">
            Don't have a token? Use <code>/auth/login</code> endpoint first.
        </p>
        <div id="error" class="error"></div>
    </div>
    <script>
        function login() {
            const token = document.getElementById('token').value;
            if (token) {
                window.location.href = '/dashboard?token=' + encodeURIComponent(token);
            } else {
                document.getElementById('error').textContent = 'Please enter a token';
            }
        }
        // Allow Enter key
        document.getElementById('token').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') login();
        });
    </script>
</body>
</html>
        """)
    
    # Verify token
    from database import get_token_info, update_token_last_used
    try:
        token_info = get_token_info(auth_token)
        if not token_info:
            raise ValueError("Invalid token")
        
        # Update last used timestamp
        update_token_last_used(auth_token)
        
        auth = {
            "user_id": token_info["user_id"],
            "username": token_info["username"],
            "email": token_info["email"],
            "is_admin": bool(token_info["is_admin"]),
            "token_id": token_info["id"]
        }
        
        user = get_user_by_id(auth["user_id"])
        tokens = get_user_tokens(auth["user_id"])
        stats = get_usage_stats(user_id=auth["user_id"], days=30)
    except Exception as e:
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body style="font-family: sans-serif; padding: 40px; text-align: center;">
    <h1>Authentication Failed</h1>
    <p>Invalid or expired API token.</p>
    <a href="/dashboard">Try again</a>
</body>
</html>
        """)
    
    # Generate dashboard HTML
    dashboard_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Converter - Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        .stat {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        .stat:last-child {{
            border-bottom: none;
        }}
        .stat-label {{
            color: #666;
        }}
        .stat-value {{
            color: #333;
            font-weight: bold;
        }}
        .token-list {{
            list-style: none;
        }}
        .token-item {{
            padding: 15px;
            background: #f5f5f5;
            border-radius: 5px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .token-name {{
            font-weight: bold;
            color: #333;
        }}
        .token-preview {{
            font-family: monospace;
            color: #666;
            font-size: 0.9em;
        }}
        .btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
        }}
        .btn:hover {{
            background: #5568d3;
        }}
        .btn-danger {{
            background: #e74c3c;
        }}
        .btn-danger:hover {{
            background: #c0392b;
        }}
        .form-group {{
            margin-bottom: 15px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: 500;
        }}
        .form-group input {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }}
        .api-info {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
            border-left: 4px solid #667eea;
        }}
        .api-info code {{
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PDF Converter Management Dashboard</h1>
            <p>Welcome, <strong>{user['username']}</strong> ({user['email']})</p>
            {'<span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; margin-left: 10px;">Admin</span>' if auth.get('is_admin') else ''}
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Usage Statistics (Last 30 Days)</h2>
                <div class="stat">
                    <span class="stat-label">Total Requests</span>
                    <span class="stat-value">{stats['total_requests']}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Pages Converted</span>
                    <span class="stat-value">{stats['total_pages_converted']}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Avg per Request</span>
                    <span class="stat-value">{round(stats['total_pages_converted'] / max(stats['total_requests'], 1), 1)}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Format Usage</h2>
                {''.join([f'<div class="stat"><span class="stat-label">{format}</span><span class="stat-value">{count}</span></div>' for format, count in stats.get('format_stats', {}).items()])}
                {'<p style="color: #999;">No conversions yet</p>' if not stats.get('format_stats') else ''}
            </div>
            
            <div class="card">
                <h2>API Tokens</h2>
                <ul class="token-list">
                    {''.join([f'<li class="token-item"><div><div class="token-name">{t["name"]}</div><div class="token-preview">{t.get("token_preview", "...")}</div></div><div>Created: {t["created_at"][:10]}</div></li>' for t in tokens[:5]])}
                    {'<li style="color: #999; padding: 15px;">No tokens yet</li>' if not tokens else ''}
                </ul>
                <button class="btn" onclick="showCreateToken()">Create New Token</button>
            </div>
        </div>
        
        <div class="card">
            <h2>API Usage</h2>
            <div class="api-info">
                <p><strong>Example Request:</strong></p>
                <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; margin-top: 10px;"><code>curl -X POST "http://localhost:8000/convert" \\
     -H "Authorization: Bearer YOUR_API_TOKEN" \\
     -F "file=@document.pdf" \\
     -F "output_format=png"</code></pre>
            </div>
        </div>
    </div>
    
    <script>
        // Store token in localStorage for future use
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        if (token) {{
            localStorage.setItem('api_token', token);
        }}
        
        function showCreateToken() {{
            const name = prompt("Enter token name:");
            if (name) {{
                const token = localStorage.getItem('api_token') || urlParams.get('token');
                fetch('/auth/tokens', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + token
                    }},
                    body: JSON.stringify({{name: name}})
                }})
                .then(r => r.json())
                .then(data => {{
                    alert('Token created: ' + data.token);
                    location.reload();
                }})
                .catch(err => alert('Error: ' + err));
            }}
        }}
    </script>
</body>
</html>
    """
    return dashboard_html

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

