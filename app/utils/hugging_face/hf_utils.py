from transformers import AutoModel, AutoTokenizer
from PIL import Image
from fastapi import HTTPException
from app.utils.device_utils import get_device_and_dtype


device, dtype = get_device_and_dtype()

def initialize_model():
    global MODEL, TOKENIZER, DEVICE
    if MODEL is None:
        device, dtype = get_device_and_dtype()
        DEVICE = device
        
        MODEL = AutoModel.from_pretrained(
            'openbmb/MiniCPM-V-4_5',
            trust_remote_code=True,
            dtype=dtype,
            attn_implementation='sdpa'
        ).eval().to(device)
        
        TOKENIZER = AutoTokenizer.from_pretrained(
            'openbmb/MiniCPM-V-4_5',
            trust_remote_code=True
        )
        
def analyze_image(image: Image.Image, question: str) -> str:
    """Placeholder function - implement with your actual model"""
    try:
        initialize_model()
        
        if not isinstance(image, Image.Image):
            raise ValueError("Expected PIL Image object")
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        msgs = [{'role': 'user', 'content': [image, question]}]

        answer = MODEL.chat(
            msgs=msgs,
            tokenizer=TOKENIZER,
            enable_thinking=False,
            stream=True
        )
        
        generated_text = ""
        for new_text in answer:
            generated_text += new_text
        
        return generated_text
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing image: {str(e)}")
