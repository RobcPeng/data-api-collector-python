import os
import base64
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI
from PIL import Image
from llama_cpp import Llama
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import hf_hub_download
import logging
from .device_utils import get_device_and_dtype

model_cache = {}

# --- GGUF Config ---
GGUF_MODEL_REPO = "huihui-ai/Huihui-MiniCPM-V-4_5-abliterated"
GGUF_MODEL_FILE = "GGUF/ggml-model-Q4_K_M.gguf" 
GGUF_CLIP_REPO = "openbmb/MiniCPM-V-4_5-gguf"
GGUF_CLIP_FILE = "mmproj-model-f16.gguf"

# --- Transformers Config ---
TRANSFORMERS_MODEL_NAME = "openbmb/MiniCPM-V-4_5"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Reads MODEL_TYPE and loads the appropriate model."""
    model_type = os.getenv("MODEL_TYPE", "gguf").lower()
    logging.info(f"Model type set to: '{model_type}'")

    if model_type == "gguf":
        model_cache["model"] = initialize_gguf_model()
        model_cache["type"] = "gguf"
    elif model_type == "transformers":
        model, tokenizer = initialize_transformers_model()
        model_cache["model"] = model
        model_cache["tokenizer"] = tokenizer
        model_cache["type"] = "transformers"
    else:
        raise ValueError(f"Unknown MODEL_TYPE: {model_type}")

    logging.info(f"✅ {model_type} model loaded successfully.")
    yield
    model_cache.clear()
           
async def analyze_image(image: Image.Image, question: str) -> str:
    """Analyzes an image using the loaded GGUF model."""
    if "model" not in model_cache:
        raise HTTPException(status_code=503, detail="GGUF model not ready.")
    
    if image.mode != 'RGB':
        image = image.convert('RGB')

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
    image_data_uri = f"data:image/png;base64,{base64_image}"
    
    llm = model_cache["model"]
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_uri}},
                {"type": "text", "content": question}
            ]
        }
    ]
    
    response = llm.create_chat_completion(messages=messages)
    print(response)
    return response['choices'][0]['message']['content']