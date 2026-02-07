import os
import logging
from typing import Optional, Dict, Any

from langgraph.graph.state import BaseModel


logger = logging.getLogger(__name__)

def get_llm(provider: str, model_name: str, config: Optional[Dict[str, Any]] = None) -> BaseModel:
    """
    Factory to get a LangChain Chat Model based on provider.
    
    Args:
        provider: 'openai', 'anthropic', 'google', 'ollama', 'azure', etc.
        model_name: The specific model string (e.g. 'gpt-4o', 'claude-3-opus')
        config: Extra config like api_key, base_url, temperature.
    """
    config = config or {}
    api_key = config.get("api_key") or os.environ.get("API_KEY")
    base_url = config.get("base_url") or os.environ.get("BASE_URL")
    temperature = config.get("temperature", 0.0)
    max_tokens = config.get("max_tokens", 4000)
    
    provider = provider.lower()
    
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens
            )
        

        elif provider == 'together':
            from langchain_together import ChatTogether
            kwargs = {
                "model": model_name,
                "api_key": api_key,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if base_url:
                kwargs["base_url"] = base_url
                kwargs['reasoning'] = {"enabled": True}
                
            return ChatTogether(**kwargs)
            
        elif provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=model_name,
                api_version=config.get("api_version", "2023-05-15"),
                api_key=api_key,
                azure_endpoint=base_url,
                temperature=temperature
            )

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=model_name,
                api_key=api_key,
                base_url=base_url, # Anthropic usually doesn't need this unless proxied
                temperature=temperature
            )
            
        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=temperature
            )
            
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_name,
                base_url=base_url or "http://localhost:11434",
                temperature=temperature
            )
            
        elif provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name=model_name,
                api_key=api_key,
                temperature=temperature
            )

        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model_name,
                api_key=api_key,
                temperature=temperature
            )
            
        elif provider == "deepseek":
            # DeepSeek is OpenAI compatible
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url or "https://api.deepseek.com",
                temperature=temperature
            )

        elif provider == "xai":
             from langchain_xai import ChatXAI
             return ChatXAI(
                 model=model_name,
                 api_key=api_key,
                 temperature=temperature
             )

        elif provider == "nvidia":
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
            return ChatNVIDIA(
                model=model_name,
                api_key=api_key,
                temperature=temperature
            )

        else:
            # Fallback or strict error? 
            # Trying OpenAI compatible fallback if unknown but base_url exists
            if base_url:
                logger.warning(f"Unknown provider '{provider}', attempting generic OpenAI compatibility.")
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model_name,
                    api_key=api_key or "dummy",
                    base_url=base_url,
                    temperature=temperature
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

    except ImportError as e:
        logger.error(f"Missing dependency for provider '{provider}': {e}")
        raise ImportError(f"To use provider '{provider}', you need to install its package. Details: {e}")
