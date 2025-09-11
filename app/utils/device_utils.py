import torch
from typing import Tuple

def get_device() -> str:
    """
    Automatically detect the best available device for PyTorch operations.
    
    Returns:
        str: Device string - 'cuda', 'mps', or 'cpu'
    """
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():  # Mac M1/M2
        return "mps"
    else:
        return "cpu"

def get_device_and_dtype() -> Tuple[str, torch.dtype]:
    """
    Get device and appropriate dtype for that device.
    
    Returns:
        Tuple[str, torch.dtype]: Device and recommended dtype
    """
    device = get_device()
    
    if device == "cuda":
        dtype = torch.bfloat16
    elif device == "mps":
        dtype = torch.float16  # MPS doesn't support bfloat16
    else:
        dtype = torch.float32  # CPU fallback
    
    return device, dtype

def get_device_info() -> dict:
    """
    Get comprehensive device information.
    
    Returns:
        dict: Device information including capabilities
    """
    device = get_device()
    info = {
        "device": device,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available(),
    }
    
    if device == "cuda":
        info.update({
            "cuda_version": torch.version.cuda,
            "gpu_count": torch.cuda.device_count(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        })
    
    return info