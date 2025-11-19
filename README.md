# PDF to Image Converter API

A FastAPI service that converts PDF files to image formats (PNG, JPEG, GIF, WebP), similar to CloudConvert's conversion API.

## Features

- Convert PDF pages to PNG, JPEG, GIF, or WebP
- Support for page range selection (e.g., "1-3" or "1,2,3")
- Configurable DPI and image quality
- RESTful API matching CloudConvert's structure
- Async file processing
- **API Token Authentication** - Secure access with Bearer tokens
- **Management Dashboard** - Web-based dashboard for usage statistics and token management
- **Usage Tracking** - Monitor API usage, conversions, and performance metrics
- **User Management** - Admin interface for managing users and tokens

## Installation

### Option 1: Local Python Environment

1. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Option 2: Docker (Recommended)

The easiest way to run the service is using Docker Compose, which handles all dependencies and architecture compatibility automatically.

1. Build and start the service:
```bash
docker-compose up --build
```

2. The API will be available at `http://localhost:8000`

3. **Initialize the database and create admin user:**
```bash
# If running locally
python seed.py

# If using Docker, the seed script runs automatically on startup
```

**Docker Commands:**
```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Rebuild after code changes
docker-compose up --build
```

## Usage

### Start the server

```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Authentication

All API endpoints (except `/convert/formats` and `/auth/login`) require authentication using an API token in the `Authorization` header:

```
Authorization: Bearer YOUR_API_TOKEN
```

#### Getting Started

1. **Seed the database** (creates default admin user):
```bash
python seed.py
```

Default admin credentials:
- Username: `admin`
- Password: `admin123`
- An API token will be generated and displayed

2. **Login to get an API token:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}'
```

Response:
```json
{
  "access_token": "your-api-token-here",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_admin": true
  }
}
```

3. **Use the token in API requests:**
```bash
curl -X POST "http://localhost:8000/convert" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -F "file=@document.pdf" \
     -F "output_format=png"
```

#### Management Dashboard

Access the web-based dashboard at:
```
http://localhost:8000/dashboard
```

The dashboard requires authentication - you'll need to provide your API token. It shows:
- Usage statistics (requests, pages converted)
- Format usage breakdown
- API token management
- Example API usage

### API Endpoints

#### 1. Convert PDF to Image

**POST** `/convert` (Requires Authentication)

Convert a PDF file to an image format.

**Request:**
- `Authorization` header: `Bearer YOUR_API_TOKEN` (required)
- `file` (file): PDF file to convert
- `input_format` (string, optional): Input format (default: "pdf")
- `output_format` (string, required): Output format - one of: "png", "jpeg", "jpg", "gif", "webp"
- `pages` (string, optional): Page range (e.g., "1-3" or "1,2,3"). If not specified, all pages are converted.
- `dpi` (integer, optional): Resolution in DPI (default: 300)
- `quality` (integer, optional): Image quality for JPEG/WebP (1-100, default: 95)

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/convert" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -F "file=@document.pdf" \
     -F "output_format=png" \
     -F "pages=1-3" \
     -F "dpi=300"
```

**Example using Python:**
```python
import requests

url = "http://localhost:8000/convert"
headers = {"Authorization": "Bearer YOUR_API_TOKEN"}
files = {"file": open("document.pdf", "rb")}
data = {
    "output_format": "png",
    "pages": "1-3",
    "dpi": 300
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()
print(result)
```

**Response:**
```json
{
  "data": {
    "id": "c85f3ca9-164c-4e89-8ae2-c08192a7cb08",
    "operation": "convert",
    "status": "finished",
    "message": null,
    "created_at": "2018-09-19T14:42:58+00:00",
    "started_at": "2018-09-19T14:42:58+00:00",
    "ended_at": "2018-09-19T14:42:59+00:00",
    "depends_on_tasks": {},
    "engine": "pymupdf",
    "engine_version": "1.23.0",
    "payload": {
      "input_format": "pdf",
      "output_format": "png",
      "pages": "1-3",
      "dpi": 300,
      "quality": 95
    },
    "result": {
      "files": [
        {
          "filename": "page-1.png",
          "url": "/download/c85f3ca9-164c-4e89-8ae2-c08192a7cb08/0",
          "size": 123456
        },
        {
          "filename": "page-2.png",
          "url": "/download/c85f3ca9-164c-4e89-8ae2-c08192a7cb08/1",
          "size": 123789
        }
      ],
      "count": 2
    }
  }
}
```

#### 2. Download Converted Image

**GET** `/download/{task_id}/{page_index}` (Requires Authentication)

Download a converted image file.

**Example:**
```bash
curl "http://localhost:8000/download/c85f3ca9-164c-4e89-8ae2-c08192a7cb08/0" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     --output page-1.png
```

#### 3. List Supported Formats

**GET** `/convert/formats` (Public endpoint, no authentication required)

List all supported conversion formats.

**Example:**
```bash
curl "http://localhost:8000/convert/formats"
```

**Response:**
```json
{
  "data": [
    {
      "operation": "convert",
      "input_format": "pdf",
      "output_format": "png",
      "engine": "pymupdf",
      "credits": 1,
      "deprecated": false,
      "experimental": false
    },
    ...
  ]
}
```

#### 4. Authentication Endpoints

**POST** `/auth/login` - Login and get API token
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}'
```

**POST** `/auth/tokens` - Create a new API token (requires authentication)
```bash
curl -X POST "http://localhost:8000/auth/tokens" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name": "My API Token"}'
```

**GET** `/auth/tokens` - List your API tokens (requires authentication)
```bash
curl "http://localhost:8000/auth/tokens" \
     -H "Authorization: Bearer YOUR_API_TOKEN"
```

**GET** `/auth/me` - Get current user information (requires authentication)
```bash
curl "http://localhost:8000/auth/me" \
     -H "Authorization: Bearer YOUR_API_TOKEN"
```

#### 5. Usage Statistics

**GET** `/usage/stats` - Get your usage statistics (requires authentication)
```bash
curl "http://localhost:8000/usage/stats?days=30" \
     -H "Authorization: Bearer YOUR_API_TOKEN"
```

**GET** `/usage/stats/all` - Get all users' statistics (admin only)
```bash
curl "http://localhost:8000/usage/stats/all?days=30" \
     -H "Authorization: Bearer ADMIN_API_TOKEN"
```

#### 6. Management Dashboard

**GET** `/dashboard` - Web-based management dashboard (requires authentication)
```
http://localhost:8000/dashboard
```

Access the dashboard in your browser. You'll need to provide your API token for authentication.

## API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

## Supported Formats

### Input
- PDF

### Output
- PNG
- JPEG/JPG
- GIF
- WebP

## Configuration

- **DPI**: Default is 300. Higher values produce better quality but larger files.
- **Quality**: For JPEG and WebP formats, quality ranges from 1-100 (default: 95).

## Notes

- Converted files are stored temporarily in memory. For production use, consider implementing persistent storage.
- The service uses PyMuPDF (fitz) for PDF rendering, which provides high-quality conversions.
- Page numbers in the API are 1-indexed (first page is page 1), but internally converted to 0-indexed for processing.

## Deployment

### Docker

The service is containerized and can be deployed anywhere Docker is supported:

```bash
# Build the image
docker build -t pdf-convert .

# Run the container
docker run -p 8000:8000 pdf-convert
```

### DigitalOcean App Platform

This service can be deployed to DigitalOcean App Platform. Create an `app.yaml` file:

```yaml
name: pdf-convert
services:
  - name: api
    github:
      repo: your-username/pdf-convert
      branch: main
    run_command: uvicorn main:app --host 0.0.0.0 --port 8080
    environment_slug: python
    instance_count: 1
    instance_size_slug: basic-xxs
    http_port: 8080
    routes:
      - path: /
```

Or use Docker:

```yaml
name: pdf-convert
services:
  - name: api
    dockerfile_path: Dockerfile
    github:
      repo: your-username/pdf-convert
      branch: main
    http_port: 8000
    routes:
      - path: /
```

## License

MIT

