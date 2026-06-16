"""
Agent LLM Module - Specialized LLM integration for agents
Provides streaming responses, model configuration, and token management
"""

import asyncio
import logging
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from dataclasses import dataclass, field
from enum import Enum
from llm.model_paths import get_llm_model_path
from llm.llm_service import LLMService

logger = logging.getLogger(__name__)

class ModelType(Enum):
    LOCAL = "local"
    API = "api"
    HYBRID = "hybrid"

class ResponseFormat(Enum):
    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"

@dataclass
class ModelConfig:
    name: str
    model_type: ModelType
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    context_window: int = 8192
    response_format: ResponseFormat = ResponseFormat.TEXT
    streaming: bool = True
    timeout: float = 30.0
    retry_attempts: int = 3
    api_key: Optional[str] = None
    model_path: Optional[str] = None

@dataclass
class LLMRequest:
    messages: List[Dict[str, str]]
    model_config: ModelConfig
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: str = "auto"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LLMResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    model: str = ""
    response_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float = 0.0

class AgentLLM:
    def __init__(self, default_config: ModelConfig = None, api_base: Optional[str] = None):
        model_path = get_llm_model_path()
        self.api_base = api_base or os.getenv("VOICEOS_LLM_API_BASE") or os.getenv("LLM_ENDPOINT")
        self.default_config = default_config or ModelConfig(
            name="mistral-7b-instruct",
            model_type=ModelType.LOCAL,
            model_path=model_path,
        )

        self.agent_configs = {
            "researcher": ModelConfig(
                name="mistral-7b-instruct",
                model_type=ModelType.LOCAL,
                model_path=model_path,
                temperature=0.3,
                max_tokens=2048,
                response_format=ResponseFormat.STRUCTURED,
            ),
            "developer": ModelConfig(
                name="mistral-7b-instruct",
                model_type=ModelType.LOCAL,
                model_path=model_path,
                temperature=0.1,
                max_tokens=4096,
                response_format=ResponseFormat.TEXT,
            ),
            "analyst": ModelConfig(
                name="mistral-7b-instruct",
                model_type=ModelType.LOCAL,
                model_path=model_path,
                temperature=0.5,
                max_tokens=3072,
                response_format=ResponseFormat.JSON,
            ),
        }
        
        # Token usage tracking
        self.token_usage: Dict[str, TokenUsage] = {}
        self.total_usage = TokenUsage(0, 0, 0)
        
        # Request statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "total_tokens_used": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Response cache
        self.response_cache: Dict[str, LLMResponse] = {}
        self.cache_ttl = 300  # 5 minutes
        self.llm_service = LLMService(
            provider=self.default_config.model_type.value,
            model_name=self.default_config.name,
            model_path=self.default_config.model_path,
            api_base=self.api_base,
            temperature=self.default_config.temperature,
            max_tokens=self.default_config.max_tokens,
            timeout=self.default_config.timeout,
        )

    @classmethod
    def from_voiceos_config(cls, llm_config) -> "AgentLLM":
        """Build AgentLLM from VoiceOS YAML llm section."""
        model_path = get_llm_model_path()
        model_type = (
            ModelType.API
            if getattr(llm_config, "provider", "local") in ("api", "remote")
            else ModelType.LOCAL
        )
        default = ModelConfig(
            name=getattr(llm_config, "model_name", "mistral-7b-instruct"),
            model_type=model_type,
            model_path=model_path,
            temperature=getattr(llm_config, "temperature", 0.7),
            max_tokens=getattr(llm_config, "max_tokens", 4096),
            timeout=getattr(llm_config, "timeout", 30.0),
            api_key=getattr(llm_config, "api_key", None),
        )
        instance = cls(default_config=default, api_base=getattr(llm_config, "api_base", None))
        instance.llm_service = LLMService.from_voiceos_config(llm_config)
        for role in instance.agent_configs:
            cfg = instance.agent_configs[role]
            cfg.name = default.name
            cfg.model_type = model_type
            cfg.model_path = model_path
        return instance
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """
        Generate a complete response from the LLM
        """
        start_time = time.time()
        
        try:
            self.stats["total_requests"] += 1
            
            # Check cache first
            cache_key = self._generate_cache_key(request)
            if cache_key in self.response_cache:
                cached_response = self.response_cache[cache_key]
                if time.time() - cached_response.metadata.get("cached_at", 0) < self.cache_ttl:
                    self.stats["cache_hits"] += 1
                    return cached_response
            
            self.stats["cache_misses"] += 1
            
            # Generate response
            if request.model_config.streaming:
                response = await self._generate_streaming_response(request)
            else:
                response = await self._generate_non_streaming_response(request)
            
            # Update response time
            response.response_time = time.time() - start_time
            
            # Cache response
            response.metadata["cached_at"] = time.time()
            self.response_cache[cache_key] = response
            
            # Update statistics
            self._update_stats(response, success=True)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            self._update_stats(None, success=False)
            
            # Return error response
            return LLMResponse(
                content=f"Error: {str(e)}",
                response_time=time.time() - start_time,
                metadata={"error": str(e)}
            )
    
    async def stream_response(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """
        Stream response chunks from the LLM
        """
        start_time = time.time()
        accumulated_content = ""
        
        try:
            self.stats["total_requests"] += 1
            
            # Check cache first
            cache_key = self._generate_cache_key(request)
            if cache_key in self.response_cache:
                cached_response = self.response_cache[cache_key]
                if time.time() - cached_response.metadata.get("cached_at", 0) < self.cache_ttl:
                    self.stats["cache_hits"] += 1
                    # Stream cached response
                    for chunk in self._chunk_content(cached_response.content):
                        yield chunk
                    return
            
            self.stats["cache_misses"] += 1
            
            # Stream from model
            async for chunk in self._stream_from_model(request):
                accumulated_content += chunk
                yield chunk
            
            # Cache complete response
            response = LLMResponse(
                content=accumulated_content,
                response_time=time.time() - start_time,
                metadata={"cached_at": time.time()}
            )
            self.response_cache[cache_key] = response
            
            # Update statistics
            self._update_stats(response, success=True)
            
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            self._update_stats(None, success=False)
            yield f"Error: {str(e)}"
    
    async def _generate_streaming_response(self, request: LLMRequest) -> LLMResponse:
        """
        Generate streaming response internally
        """
        content = ""
        async for chunk in self.stream_response(request):
            content += chunk
        
        return LLMResponse(
            content=content,
            response_time=0.0,  # Will be updated by caller
            metadata={"streaming": True}
        )
    
    async def _generate_non_streaming_response(self, request: LLMRequest) -> LLMResponse:
        """
        Generate non-streaming response
        """
        # For now, implement as streaming then combine
        return await self._generate_streaming_response(request)
    
    async def _stream_from_model(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """
        Stream response from the actual model
        """
        try:
            if request.model_config.model_type == ModelType.LOCAL:
                async for chunk in self._stream_local_model(request):
                    yield chunk
            elif request.model_config.model_type == ModelType.API:
                async for chunk in self._stream_api_model(request):
                    yield chunk
            else:
                # Hybrid implementation
                async for chunk in self._stream_hybrid_model(request):
                    yield chunk
                    
        except Exception as e:
            logger.error(f"Model streaming failed: {e}")
            yield f"Error: {str(e)}"
    
    async def _stream_local_model(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream from local model via unified LLMService."""
        role = request.metadata.get("agent_role", "general")
        async for chunk in self.llm_service.stream_messages(request.messages, role=role):
            yield chunk
    
    async def _stream_api_model(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """
        Stream from a remote API (Ollama-compatible generate endpoint).
        """
        base = self.api_base or os.getenv("VOICEOS_LLM_API_BASE") or os.getenv("LLM_ENDPOINT")
        if base:
            try:
                async for chunk in self._stream_ollama(request, base):
                    yield chunk
                return
            except Exception as e:
                logger.warning("Remote LLM stream failed, using local fallback: %s", e)
        async for chunk in self._stream_local_model(request):
            yield chunk

    def _ollama_generate_url(self, base_url: str) -> str:
        url = base_url.rstrip("/")
        if url.endswith("/api/generate"):
            return url
        if "/api/" in url:
            return url.split("/api/")[0] + "/api/generate"
        return url + "/api/generate"

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)

    async def _stream_ollama(self, request: LLMRequest, base_url: str) -> AsyncGenerator[str, None]:
        import requests

        url = self._ollama_generate_url(base_url)
        model = request.model_config.name
        prompt = self._messages_to_prompt(request.messages)

        def collect_tokens():
            tokens = []
            response = requests.post(
                url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"temperature": request.model_config.temperature},
                },
                stream=True,
                timeout=request.model_config.timeout or 120,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
                token = data.get("response", "")
                if token:
                    tokens.append(token)
                if data.get("done"):
                    break
            return tokens

        tokens = await asyncio.to_thread(collect_tokens)
        for token in tokens:
            yield token
            await asyncio.sleep(0.005)
    
    async def _stream_hybrid_model(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Try local then API via LLMService hybrid path."""
        saved = self.llm_service.provider
        try:
            from llm.llm_service import LLMProvider
            self.llm_service.provider = LLMProvider.HYBRID
            role = request.metadata.get("agent_role", "general")
            async for chunk in self.llm_service.stream_messages(request.messages, role=role):
                yield chunk
        finally:
            self.llm_service.provider = saved
    
    def _chunk_content(self, content: str, chunk_size: int = 50) -> List[str]:
        """
        Split content into chunks for streaming
        """
        chunks = []
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            chunks.append(chunk)
        return chunks
    
    def _generate_cache_key(self, request: LLMRequest) -> str:
        """
        Generate cache key for request
        """
        import hashlib
        
        # Create a normalized representation of the request
        cache_data = {
            "messages": request.messages,
            "model": request.model_config.name,
            "temperature": request.model_config.temperature,
            "max_tokens": request.model_config.max_tokens
        }
        
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _update_stats(self, response: Optional[LLMResponse], success: bool):
        """
        Update request statistics
        """
        if success:
            self.stats["successful_requests"] += 1
            if response:
                # Update average response time
                total_requests = self.stats["total_requests"]
                current_avg = self.stats["average_response_time"]
                self.stats["average_response_time"] = (
                    (current_avg * (total_requests - 1) + response.response_time) / total_requests
                )
                
                # Update token usage
                if response.usage:
                    self.total_usage.prompt_tokens += response.usage.get("prompt_tokens", 0)
                    self.total_usage.completion_tokens += response.usage.get("completion_tokens", 0)
                    self.total_usage.total_tokens += response.usage.get("total_tokens", 0)
        else:
            self.stats["failed_requests"] += 1
    
    def get_config_for_agent(self, agent_role: str) -> ModelConfig:
        """
        Get model configuration for specific agent role
        """
        return self.agent_configs.get(agent_role, self.default_config)
    
    def set_agent_config(self, agent_role: str, config: ModelConfig):
        """
        Set model configuration for specific agent role
        """
        self.agent_configs[agent_role] = config
        logger.info(f"Set config for agent role: {agent_role}")
    
    def create_request(self, messages: List[Dict[str, str]], agent_role: str = None,
                      tools: List[Dict[str, Any]] = None) -> LLMRequest:
        """
        Create LLM request with appropriate configuration
        """
        config = self.get_config_for_agent(agent_role) if agent_role else self.default_config
        
        return LLMRequest(
            messages=messages,
            model_config=config,
            tools=tools or [],
            metadata={"agent_role": agent_role} if agent_role else {}
        )
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics
        """
        return {
            "token_usage": {
                "prompt_tokens": self.total_usage.prompt_tokens,
                "completion_tokens": self.total_usage.completion_tokens,
                "total_tokens": self.total_usage.total_tokens,
                "estimated_cost": self.total_usage.cost
            },
            "request_stats": self.stats.copy(),
            "cache_stats": {
                "cache_size": len(self.response_cache),
                "cache_hit_rate": self.stats["cache_hits"] / max(1, self.stats["cache_hits"] + self.stats["cache_misses"])
            },
            "agent_configs": {
                role: {
                    "name": config.name,
                    "model_type": config.model_type.value,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens
                }
                for role, config in self.agent_configs.items()
            }
        }
    
    def clear_cache(self):
        """
        Clear response cache
        """
        self.response_cache.clear()
        logger.info("LLM response cache cleared")
    
    def reset_statistics(self):
        """
        Reset usage statistics
        """
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "total_tokens_used": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        self.total_usage = TokenUsage(0, 0, 0)
        logger.info("LLM usage statistics reset")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on LLM system
        """
        try:
            # Test request
            test_request = self.create_request([
                {"role": "user", "content": "Hello, this is a health check."}
            ])
            
            start_time = time.time()
            response = await self.generate_response(test_request)
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if response.content and not response.content.startswith("Error:") else "unhealthy",
                "response_time": response_time,
                "cache_size": len(self.response_cache),
                "total_requests": self.stats["total_requests"],
                "success_rate": self.stats["successful_requests"] / max(1, self.stats["total_requests"]),
                "default_model": self.default_config.name
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time": time.time() - start_time
            }
