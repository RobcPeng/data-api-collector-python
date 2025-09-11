from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import base64
from io import BytesIO
from PIL import Image
from app.utils.hugging_face.hf_utils import analyze_image



router = APIRouter(prefix="/multimodal_ocr", tags=["multimodal"])

class ImageAnalysisRequest(BaseModel):
    question: str
    image_base64: Optional[str] = None

class ImageAnalysisResponse(BaseModel):
    response: str
    model_used: str
    status: str

@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image_with_question(
    question: str,
    image: UploadFile = File(...)
):
    """Upload an image and ask a question about it"""
    # Load image
    image_data = await image.read()
    pil_image = Image.open(BytesIO(image_data))
    
    # Call your model (implement in utils)
    response = analyze_image(pil_image, question)
    
    return ImageAnalysisResponse(
        response=response,
        model_used="MiniCPM-V-4_5",
        status="success"
    )

@router.post("/ocr")
async def extract_text_from_image(image: UploadFile = File(...)):
    """Extract text from an image using OCR"""
    image_data = await image.read()
    pil_image = Image.open(BytesIO(image_data))
    
    # OCR-specific prompt
    response = analyze_image(pil_image, "Extract all text from this image")
    
    return {"extracted_text": response, "status": "success"}

@router.post("/chart-analysis")
async def analyze_chart(
    image: UploadFile = File(...),
    analysis_type: str = "summary"
):
    """Analyze charts, graphs, or data visualizations"""
    prompts = {
        "summary": "Describe what this chart shows",
        "data": "Extract the key data points from this chart",
        "insights": "What insights can you derive from this chart?"
    }
    
    image_data = await image.read()
    pil_image = Image.open(BytesIO(image_data))
    
    prompt = prompts.get(analysis_type, prompts["summary"])
    response = analyze_image(pil_image, prompt)
    
    return {"analysis": response, "type": analysis_type, "status": "success"}