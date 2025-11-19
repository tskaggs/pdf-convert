"""
Example script demonstrating how to use the PDF to Image Converter API
"""
import requests
import json

# API endpoint
BASE_URL = "http://localhost:8000"

def convert_pdf_to_image(pdf_path: str, output_format: str = "png", pages: str = None, dpi: int = 300):
    """
    Convert a PDF file to images
    
    Args:
        pdf_path: Path to the PDF file
        output_format: Output format (png, jpeg, jpg, gif, webp)
        pages: Page range (e.g., "1-3" or "1,2,3")
        dpi: Resolution in DPI
    """
    url = f"{BASE_URL}/convert"
    
    with open(pdf_path, "rb") as f:
        files = {"file": f}
        data = {
            "output_format": output_format,
            "dpi": dpi
        }
        
        if pages:
            data["pages"] = pages
        
        print(f"Converting {pdf_path} to {output_format}...")
        response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        task_id = result["data"]["id"]
        files = result["data"]["result"]["files"]
        
        print(f"\nConversion successful! Task ID: {task_id}")
        print(f"Converted {len(files)} page(s):")
        
        # Download each converted image
        for idx, file_info in enumerate(files):
            download_url = f"{BASE_URL}{file_info['url']}"
            output_filename = file_info["filename"]
            
            print(f"  - Downloading {output_filename}...")
            img_response = requests.get(download_url)
            
            if img_response.status_code == 200:
                with open(output_filename, "wb") as img_file:
                    img_file.write(img_response.content)
                print(f"    Saved to {output_filename}")
            else:
                print(f"    Failed to download {output_filename}")
        
        return result
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def list_formats():
    """List all supported conversion formats"""
    url = f"{BASE_URL}/convert/formats"
    response = requests.get(url)
    
    if response.status_code == 200:
        formats = response.json()["data"]
        print("Supported formats:")
        for fmt in formats:
            print(f"  - {fmt['input_format']} -> {fmt['output_format']} (engine: {fmt['engine']})")
        return formats
    else:
        print(f"Error: {response.status_code}")
        return None

if __name__ == "__main__":
    # List supported formats
    print("=" * 50)
    list_formats()
    print("\n" + "=" * 50)
    
    # Example: Convert PDF to PNG (all pages)
    # convert_pdf_to_image("example.pdf", output_format="png")
    
    # Example: Convert PDF to JPEG (pages 1-3)
    # convert_pdf_to_image("example.pdf", output_format="jpeg", pages="1-3")
    
    # Example: Convert PDF to WebP (specific pages)
    # convert_pdf_to_image("example.pdf", output_format="webp", pages="1,3,5")
    
    print("\nUncomment the examples above to test with your PDF file!")

