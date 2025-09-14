from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from PIL import Image
from io import BytesIO
import logging
import os

# 🔄 CORRECTED IMPORT
# Import from the unified model_util.py. This file acts as the router.
from .utils.model_util import lifespan, analyze_image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastAPI app with the lifespan manager from our utility file.
app = FastAPI(lifespan=lifespan)


class AnalysisResponse(BaseModel):
    response: str
    model_type: str


@app.get("/health")
async def health_check():
    """Health check endpoint for the service."""
    return {"status": "healthy", "service": "OCR Service"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(
    question: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Analyzes an image with a question by calling the appropriate model
    backend (GGUF or Transformers).
    """
    try:
        image_data = await image.read()
        pil_image = Image.open(BytesIO(image_data))

        # This call now works for either model type automatically
        generated_text = await analyze_image(pil_image, question)
        
        # Get the currently active model type for a more dynamic response
        model_type = os.getenv("MODEL_TYPE", "gguf").upper()
        
        return AnalysisResponse(
            response=generated_text,
            model_type=model_type
        )
    except Exception as e:
        logger.error(f"Error during analysis endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))