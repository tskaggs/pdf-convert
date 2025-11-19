from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import uuid
import fitz  # PyMuPDF
from PIL import Image
import io
from enum import Enum

app = FastAPI(title="PDF to Image Converter API", version="1.0.0")

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
    file: UploadFile = File(...),
    input_format: str = Form("pdf"),
    output_format: OutputFormat = Form(...),
    pages: Optional[str] = Form(None),
    dpi: Optional[int] = Form(300),
    quality: Optional[int] = Form(95)
):
    """
    Convert PDF file to image format (PNG, JPEG, GIF, or WebP)
    
    - **file**: PDF file to convert
    - **input_format**: Input format (default: pdf)
    - **output_format**: Output format (png, jpeg, jpg, gif, webp)
    - **pages**: Page range (e.g., "1-3" or "1,2,3"). If not specified, all pages are converted.
    - **dpi**: Resolution in DPI (default: 300)
    - **quality**: Image quality for JPEG/WebP (1-100, default: 95)
    """
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
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.get("/download/{task_id}/{page_index}")
async def download_file(task_id: str, page_index: int):
    """Download converted image file as binary"""
    if task_id not in temp_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = temp_storage[task_id]
    if page_index >= len(task_data["images"]):
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
    
    # Return file directly from memory
    return Response(
        content=img_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_info["filename"]}"'}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

