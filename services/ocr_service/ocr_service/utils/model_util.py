import os
import base64
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from PIL import Image
from llama_cpp import Llama
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import hf_hub_download
import logging
from .device_utils import get_device_and_dtype

# This dictionary will store the active model and its type
model_cache = {}

# --- Configuration for GGUF (Quantized) Model ---
GGUF_MODEL_REPO = "huihui-ai/Huihui-MiniCPM-V-4_5-abliterated"
GGUF_MODEL_FILE = "GGUF/ggml-model-Q4_K_M.gguf" 
GGUF_CLIP_REPO = "openbmb/MiniCPM-V-4_5-gguf"
GGUF_CLIP_FILE = "mmproj-model-f16.gguf"

# --- Configuration for Transformers (Full Precision) Model ---
TRANSFORMERS_MODEL_NAME = "openbmb/MiniCPM-V-4_5"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Reads the MODEL_TYPE environment variable and loads the appropriate model on startup.
    Defaults to 'gguf' if the variable is not set.
    """
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
        raise ValueError(f"Unknown MODEL_TYPE: '{model_type}'. Choose 'gguf' or 'transformers'.")

    logging.info(f"✅ {model_type.upper()} model loaded successfully. Service is ready.")
    
    yield # The application runs here

    model_cache.clear()
    logging.info("Model cache cleared on shutdown.")

def initialize_gguf_model():
    """Downloads (if needed) and loads the GGUF model and its CLIP model."""
    logging.info(f"Downloading GGUF model from repo: {GGUF_MODEL_REPO}")
    model_path = hf_hub_download(repo_id=GGUF_MODEL_REPO, filename=GGUF_MODEL_FILE)
    clip_path = hf_hub_download(repo_id=GGUF_CLIP_REPO, filename=GGUF_CLIP_FILE)
    
    logging.info("Loading GGUF model into llama-cpp...")
    return Llama(
        model_path=model_path,
        clip_model_path=clip_path,
        n_ctx=2048,
        verbose=True,
        n_threads=4,
        # For GPU deployment, you would change n_gpu_layers=-1
        # and ensure you have the correct llama-cpp-python build.
        n_gpu_layers=0 
    )

def initialize_transformers_model():
    """Loads the full-precision transformers model and tokenizer."""
    device, dtype = get_device_and_dtype()
    logging.info(f"Loading transformers model '{TRANSFORMERS_MODEL_NAME}' onto device '{device}'...")
    
    model = AutoModel.from_pretrained(
        TRANSFORMERS_MODEL_NAME,
        trust_remote_code=True,
        dtype=dtype
    ).eval().to(device)
    
    tokenizer = AutoTokenizer.from_pretrained(TRANSFORMERS_MODEL_NAME, trust_remote_code=True)
    return model, tokenizer

async def analyze_image(image: Image.Image, question: str) -> str:
    """
    Performs inference by checking the loaded model type from the cache
    and executing the appropriate logic.
    """
    if "model" not in model_cache or "type" not in model_cache:
        raise HTTPException(status_code=503, detail="Model is not loaded or type is unknown.")
    
    prompt = """
You are an OCR assistant. Your task is to identify and extract all visible text from the image provided. Preserve the original formatting as closely as possible, including:

Line breaks and paragraphs
Headings and subheadings
Any tables, lists, bullet points, or numbered items
Special characters, spacing, and alignment
Output strictly the extracted text in Markdown format, reflecting the layout and structure of the original image. Do not add commentary, interpretation, or summarization—only return the raw text content with its formatting.
"""

    model_type = model_cache["type"]
    llm = model_cache["model"]

    if image.mode != 'RGB':
        image = image.convert('RGB')

    # --- Logic for GGUF model ---
    if model_type == "gguf":
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        image_url = f"data:image/png;base64,{base64_image}"
        
        messages = [{
            "role": "user", 
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}}, 
                {"type": "text", "content": f"{prompt}\n\n{question}"}
            ]
        }]
        response = llm.create_chat_completion(messages=messages)
        return response['choices'][0]['message']['content']

    # --- Logic for Transformers model ---
    elif model_type == "transformers":
        tokenizer = model_cache["tokenizer"]
        # Combine prompt and question for the transformers model
        combined_text = f"{prompt}\n\n{question}"
        messages = [{'role': 'user', 'content': [image, combined_text]}]
        
        answer_stream = llm.chat(
            msgs=messages,
            tokenizer=tokenizer,
            stream=True
        )
        return "".join(list(answer_stream))