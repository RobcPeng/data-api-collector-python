import pymupdf
import io
from typing import List
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
    pages_processed: int = 1  # Added for PDF support


def is_pdf_file(file_content: bytes) -> bool:
    """Check if the uploaded file is a PDF"""
    return file_content.startswith(b'%PDF')


def is_image_file(filename: str) -> bool:
    """Check if the uploaded file is an image based on extension"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    return any(filename.lower().endswith(ext) for ext in image_extensions)


def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[Image.Image]:
    """Convert PDF pages to PIL Images"""
    try:
        pdf_document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            # Convert page to pixmap (image)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi/72, dpi/72))
            img_data = pix.tobytes("ppm")
            
            # Convert to PIL Image
            pil_image = Image.open(io.BytesIO(img_data))
            images.append(pil_image)
        
        pdf_document.close()
        return images
        
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")


async def process_file_to_images(file: UploadFile) -> List[Image.Image]:
    """Process uploaded file and return list of PIL Images"""
    file_content = await file.read()
    
    if is_pdf_file(file_content):
        logger.info(f"Processing PDF file: {file.filename}")
        return pdf_to_images(file_content)
    
    elif is_image_file(file.filename or ""):
        logger.info(f"Processing image file: {file.filename}")
        try:
            pil_image = Image.open(io.BytesIO(file_content))
            return [pil_image]  # Return as list for consistency
        except Exception as e:
            logger.error(f"Error opening image: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Please upload an image (jpg, png, etc.) or PDF file. Got: {file.filename}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint for the service."""
    return {"status": "healthy", "service": "OCR Service"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(
    question: str = Form(...),
    file: UploadFile = File(...)  # Changed from 'image' to 'file' for clarity
):
    """
    Analyzes an image or PDF with a question by calling the appropriate model
    backend (GGUF or Transformers).
    
    Supports:
    - Image files: JPG, PNG, GIF, BMP, TIFF, WebP
    - PDF files: Converts each page to an image and analyzes
    """
    try:
        # Process file to get list of images
        images = await process_file_to_images(file)
        
        if not images:
            raise HTTPException(status_code=400, detail="No images found in the uploaded file")
        
        # Get the currently active model type for a more dynamic response
        model_type = os.getenv("MODEL_TYPE", "gguf").upper()
        
        # If PDF with multiple pages, analyze each page
        if len(images) > 1:
            logger.info(f"Processing {len(images)} pages from PDF")
            all_responses = []
            
            for i, pil_image in enumerate(images):
                try:
                    page_response = await analyze_image(pil_image, f"Page {i+1}: {question}")
                    all_responses.append(f"**Page {i+1}:**\n{page_response}")
                except Exception as page_error:
                    logger.error(f"Error analyzing page {i+1}: {page_error}")
                    all_responses.append(f"**Page {i+1}:** Error - {str(page_error)}")
            
            generated_text = "\n\n".join(all_responses)
            
        else:
            # Single image (either uploaded image or single-page PDF)
            generated_text = await analyze_image(images[0], question)
        
        logger.info(f"Analysis completed for {len(images)} page(s)")
        
        return AnalysisResponse(
            response=generated_text,
            model_type=model_type,
            pages_processed=len(images)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during analysis endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backward compatibility (images only)
@app.post("/analyze-image", response_model=AnalysisResponse)
async def analyze_image_endpoint(
    question: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Legacy endpoint - analyzes images only.
    Use /analyze for both images and PDFs.
    """
    try:
        image_data = await image.read()
        pil_image = Image.open(BytesIO(image_data))

        generated_text = await analyze_image(pil_image, question)
        model_type = os.getenv("MODEL_TYPE", "gguf").upper()
        
        return AnalysisResponse(
            response=generated_text,
            model_type=model_type,
            pages_processed=1
        )
    except Exception as e:
        logger.error(f"Error during image analysis endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))