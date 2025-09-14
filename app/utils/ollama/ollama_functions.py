from .ollama_config import client

def call_model(msg: str, role:str ="user" ,model: str = "gpt-oss:20b"):
    response = client.chat.completions.create(
        model=model,
        messages=[
             {"role": role,"content": msg}]
    )
    return response