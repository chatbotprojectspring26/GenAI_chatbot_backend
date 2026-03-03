from typing import List, Tuple, Dict, Any
import requests
import json

from openai import OpenAI

from .config import get_settings


settings = get_settings()
_client = OpenAI(api_key=settings.openai_api_key)


ChatMessageDict = Dict[str, str]


def generate_completion(
    messages: List[ChatMessageDict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, Dict[str, Any]]:
    """
    Call the LLM API and return text plus basic usage metadata.
    Supports both OpenAI and LLAMA APIs.
    """
    # Check if we should use LLAMA API (when configured and model starts with "llama")
    if (settings.llama_api_key and settings.llama_api_url and 
        model.startswith("llama")):
        return _generate_llama_completion(messages, model, temperature, max_tokens)
    
    # Check if we're using a dummy API key for testing
    if settings.openai_api_key.startswith("sk-dummy"):
        # Mock response for testing
        user_message = messages[-1].get("content", "") if messages else ""
        text = f"This is a mock response to: '{user_message}'. The API is working but using a dummy key for testing."
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25,
            "id": "mock-response-id",
        }
        return text, usage
    
    # Use OpenAI API
    response = _client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    choice = response.choices[0]
    text = choice.message.content or ""

    usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
        "total_tokens": response.usage.total_tokens if response.usage else None,
        "id": response.id,
    }

    return text, usage


def _generate_llama_completion(
    messages: List[ChatMessageDict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, Dict[str, Any]]:
    """
    Call the Binghamton University LLAMA API through VPN.
    """
    headers = {
        "Authorization": f"Bearer {settings.llama_api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    try:
        response = requests.post(
            f"{settings.llama_api_url}/api/chat/completions",
            headers=headers,
            json=data,
            timeout=60  # Increased timeout for university API
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result["choices"][0]
        text = choice.get("message", {}).get("content", "")
        
        # Handle Binghamton API usage format
        usage_info = result.get("usage", {})
        usage = {
            "prompt_tokens": usage_info.get("prompt_tokens"),
            "completion_tokens": usage_info.get("completion_tokens"),
            "total_tokens": usage_info.get("total_tokens"),
            "id": result.get("id"),
        }
        
        return text, usage
        
    except requests.exceptions.RequestException as e:
        # Fallback to mock response if LLAMA API fails
        user_message = messages[-1].get("content", "") if messages else ""
        text = f"Binghamton API error: {str(e)}. Mock response to: '{user_message}'. Check VPN connection and API key."
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "id": "binghamton-error-fallback",
        }
        return text, usage

