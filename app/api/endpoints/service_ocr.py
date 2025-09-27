import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/service_ocr", tags=["service"])

# The URL for our new service. 
# This works because Docker's networking lets containers talk to each other by their service name.
OCR_SERVICE_URL = "http://ocr-service:8002/"

# Define a Pydantic model for the final response to the user
class FinalResponse(BaseModel):
    analysis: str
    model: str
    status: str

@router.post("/analyze", response_model=FinalResponse)
async def analyze_file_with_question(
    question: str = Form(...),
    file: UploadFile = File(...)  # Changed from 'image' to 'file' for clarity
):
    """
    Proxies a request to the ocr-service for both images and PDFs and returns a complete JSON response.
    
    Supports:
    - Image files: JPG, PNG, GIF, BMP, TIFF, WebP
    - PDF files: Processes each page and combines results
    """
    # Prepare files and data for the OCR service
    files = {'file': (file.filename, await file.read(), file.content_type)}
    data = {'question': question}
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # Increased timeout for PDF processing
        try:
            # Send request to OCR service
            response = await client.post(OCR_SERVICE_URL+"analyze", files=files, data=data)
            response.raise_for_status()
            
            # Parse the JSON from the service's response
            service_data = response.json()
            print(f"OCR Service Response: {service_data}")

            # Return a structured JSON object to the end-user
            return FinalResponse(
                analysis=service_data.get("response", "No response received"),
                model=service_data.get("model_type", "Unknown"),
                status="success",
                pages_processed=service_data.get("pages_processed", 1)
            )

        except httpx.RequestError as e:
            print(f"Request error: {e}")
            raise HTTPException(status_code=503, detail="The OCR service is unavailable.")
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            print(f"HTTP error: {e.response.status_code} - {error_detail}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Error from OCR service: {error_detail}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/analyze-image", response_model=FinalResponse)
async def analyze_image_with_question(
    question: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Proxies a request to the ocr-service and returns a complete JSON response.
    """
    files = {'image': (image.filename, await image.read(), image.content_type)}
    data = {'question': question}
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # 🔄 Use a standard 'post' call, not 'stream'
            response = await client.post(OCR_SERVICE_URL+"analyze-image", files=files, data=data)
            response.raise_for_status()
            
            # Parse the JSON from the service's response
            service_data = response.json()
            print(service_data)

            # Return a structured JSON object to the end-user
            return FinalResponse(
                analysis=service_data.get("response"),
                model=service_data.get("model_type"),
                status="success"
            )

        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="The OCR service is unavailable.")
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=f"Error from OCR service: {error_detail}")