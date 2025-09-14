import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/service_ocr", tags=["service"])

# The URL for our new service. 
# This works because Docker's networking lets containers talk to each other by their service name.
OCR_SERVICE_URL = "http://ocr-service:8002/analyze"

# Define a Pydantic model for the final response to the user
class FinalResponse(BaseModel):
    analysis: str
    model: str
    status: str

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
            response = await client.post(OCR_SERVICE_URL, files=files, data=data)
            response.raise_for_status()
            
            # Parse the JSON from the service's response
            service_data = response.json()

            # Return a structured JSON object to the end-user
            return FinalResponse(
                analysis=service_data.get("response_text"),
                model=service_data.get("model_used"),
                status="success"
            )

        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="The OCR service is unavailable.")
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=f"Error from OCR service: {error_detail}")