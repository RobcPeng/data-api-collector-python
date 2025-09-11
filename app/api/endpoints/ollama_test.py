from fastapi import APIRouter
import httpx
import asyncio
import os

router = APIRouter(prefix="/ollama-test", tags=["ollama-test"])

@router.get("/connectivity")
async def test_ollama_connectivity():
    """Test basic connectivity to Ollama from Docker container"""
    
    base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    
    results = {
        "base_url": base_url,
        "tests": {}
    }
    
    # Test 1: Basic connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            results["tests"]["api_tags"] = {
                "status": "success" if response.status_code == 200 else "failed",
                "status_code": response.status_code,
                "response_size": len(response.content) if response.content else 0
            }
            
            if response.status_code == 200:
                data = response.json()
                results["tests"]["api_tags"]["models"] = data.get("models", [])
                results["tests"]["api_tags"]["model_count"] = len(data.get("models", []))
    except Exception as e:
        results["tests"]["api_tags"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test 2: Version info
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/version")
            results["tests"]["version"] = {
                "status": "success" if response.status_code == 200 else "failed",
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
    except Exception as e:
        results["tests"]["version"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test 3: Simple generation test
    try:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Hello! Just say 'Hi' back.",
                    "stream": False
                }
            )
            results["tests"]["generate"] = {
                "status": "success" if response.status_code == 200 else "failed",
                "status_code": response.status_code,
                "model_used": model
            }
            
            if response.status_code == 200:
                data = response.json()
                results["tests"]["generate"]["response_preview"] = data.get("response", "")[:100]
    except Exception as e:
        results["tests"]["generate"] = {
            "status": "error",
            "error": str(e)
        }
    
    return results

@router.get("/network-debug")
async def network_debug():
    """Debug network connectivity options"""
    
    urls_to_test = [
        "http://host.docker.internal:11434",
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://172.17.0.1:11434",  # Default Docker bridge
        "http://192.168.65.2:11434",  # Docker Desktop on Mac
        "http://10.0.2.2:11434"      # Some virtualization setups
    ]
    
    results = {}
    
    for url in urls_to_test:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/api/tags")
                results[url] = {
                    "status": "reachable",
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
        except httpx.ConnectTimeout:
            results[url] = {"status": "timeout"}
        except httpx.ConnectError:
            results[url] = {"status": "connection_refused"}
        except Exception as e:
            results[url] = {"status": "error", "error": str(e)}
    
    return {
        "tested_urls": urls_to_test,
        "results": results,
        "recommendation": "Use the first URL that shows 'reachable' status"
    }

@router.get("/environment")
async def show_environment():
    """Show relevant environment variables"""
    
    env_vars = {}
    relevant_vars = [
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT",
        "OLLAMA_API_KEY", "HOSTNAME", "HOST"
    ]
    
    for var in relevant_vars:
        env_vars[var] = os.getenv(var, "NOT_SET")
    
    return {
        "environment_variables": env_vars,
        "container_hostname": os.getenv("HOSTNAME", "unknown"),
        "current_working_dir": os.getcwd()
    }
