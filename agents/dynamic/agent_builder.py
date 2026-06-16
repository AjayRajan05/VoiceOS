"""
Dynamic Agent Builder Module
Constructs agents at runtime from YAML configuration and prompt templates
"""

import yaml
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    name: str
    description: str
    role: str
    tools: List[str]
    style: str
    max_steps: int
    timeout: float
    system_prompt: str

@dataclass
class DynamicAgent:
    config: AgentConfig
    tools: Dict[str, Any]
    workspace_id: str
    created_at: str

class AgentBuilder:
    def __init__(self, tool_registry=None):
        self.roles_path = "agents/roles"
        self.prompt_loader = PromptLoader()
        self.tool_registry = tool_registry
        self._agent_cache = {}
        
    async def build_agent(self, role: str, intent: str, context: Dict[str, Any]) -> Optional[DynamicAgent]:
        """
        Build a dynamic agent for the specified role
        """
        try:
            # Load agent configuration
            config = await self._load_agent_config(role)
            if not config:
                logger.error(f"No configuration found for role: {role}")
                return None
            
            # Load system prompt
            system_prompt = await self.prompt_loader.load_prompt(role)
            if not system_prompt:
                logger.error(f"No prompt found for role: {role}")
                return None
            
            # Update config with loaded prompt
            config.system_prompt = system_prompt
            
            # Customize config based on intent and context
            config = self._customize_config(config, intent, context)
            
            # Load tools for this agent
            tools = await self._load_tools(config.tools)
            
            # Generate workspace ID
            workspace_id = self._generate_workspace_id(role, intent)
            
            # Create agent
            agent = DynamicAgent(
                config=config,
                tools=tools,
                workspace_id=workspace_id,
                created_at=self._get_timestamp()
            )
            
            # Cache agent
            cache_key = f"{role}_{intent}"
            self._agent_cache[cache_key] = agent
            
            logger.info(f"Built dynamic agent: {config.name} for role: {role}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to build agent for role {role}: {e}")
            return None
    
    async def _load_agent_config(self, role: str) -> Optional[AgentConfig]:
        """
        Load agent configuration from YAML file
        """
        config_path = os.path.join(self.roles_path, role, "agent.yaml")
        
        try:
            if not os.path.exists(config_path):
                logger.error(f"Agent config not found: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            return AgentConfig(
                name=config_data.get('name', role),
                description=config_data.get('description', ''),
                role=role,
                tools=config_data.get('tools', []),
                style=config_data.get('style', 'professional'),
                max_steps=config_data.get('max_steps', 10),
                timeout=config_data.get('timeout', 60.0),
                system_prompt=""  # Will be loaded separately
            )
            
        except Exception as e:
            logger.error(f"Failed to load agent config from {config_path}: {e}")
            return None
    
    async def _load_tools(self, tool_names: List[str]) -> Dict[str, Any]:
        """Resolve tools from the central registry only."""
        tools: Dict[str, Any] = {}
        if not self.tool_registry:
            logger.warning("No tool registry attached to AgentBuilder")
            return tools

        for tool_name in tool_names:
            registration = self.tool_registry.get_tool(tool_name)
            if registration:
                tools[tool_name] = registration
            else:
                logger.warning("Tool not registered: %s", tool_name)
        return tools
    
    def _customize_config(self, config: AgentConfig, intent: str, context: Dict[str, Any]) -> AgentConfig:
        """
        Customize agent configuration based on intent and context
        """
        # Adjust max steps based on intent complexity
        if 'research' in intent:
            config.max_steps = max(config.max_steps, 8)
        elif 'develop' in intent or 'code' in intent:
            config.max_steps = max(config.max_steps, 12)
        elif 'analyze' in intent:
            config.max_steps = max(config.max_steps, 6)
        
        # Adjust timeout based on complexity
        config.timeout = config.max_steps * 5.0  # 5 seconds per step
        
        # Add context to description
        if context and 'parameters' in context:
            params = context['parameters']
            if params:
                config.description += f" (Target: {params[0] if len(params) == 1 else params})"
        
        return config
    
    def _generate_workspace_id(self, role: str, intent: str) -> str:
        """
        Generate unique workspace ID for the agent
        """
        import uuid
        import time
        
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        return f"{role}_{intent}_{timestamp}_{unique_id}"
    
    def _get_timestamp(self) -> str:
        """
        Get current timestamp
        """
        import time
        return str(int(time.time()))
    
    def get_cached_agent(self, role: str, intent: str) -> Optional[DynamicAgent]:
        """
        Get cached agent if available
        """
        cache_key = f"{role}_{intent}"
        return self._agent_cache.get(cache_key)
    
    def clear_cache(self):
        """
        Clear agent cache
        """
        self._agent_cache.clear()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information
        """
        return {
            "cached_agents": len(self._agent_cache),
            "cache_keys": list(self._agent_cache.keys())
        }

class PromptLoader:
    def __init__(self):
        self.roles_path = "agents/roles"
        self._prompt_cache = {}
    
    async def load_prompt(self, role: str) -> Optional[str]:
        """
        Load system prompt for the specified role
        """
        # Check cache first
        if role in self._prompt_cache:
            return self._prompt_cache[role]
        
        prompt_path = os.path.join(self.roles_path, role, "prompt.txt")
        
        try:
            if not os.path.exists(prompt_path):
                logger.error(f"Prompt file not found: {prompt_path}")
                return None
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()
            
            # Cache the prompt
            self._prompt_cache[role] = prompt
            
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to load prompt from {prompt_path}: {e}")
            return None
    
    def clear_cache(self):
        """
        Clear prompt cache
        """
        self._prompt_cache.clear()
