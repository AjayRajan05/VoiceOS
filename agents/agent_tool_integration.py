"""
Agent Tool Integration - Connects VoiceOS agents with native VoiceOS tools
Provides safe tool access for agents through the tool registry
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from tools.tool_registry import ToolRegistry, ToolCategory
from tools.voiceos_tools_integration import VoiceOSToolsIntegration, initialize_voiceos_tools_integration
from permissions.permission_engine import PermissionLevel, permission_engine

logger = logging.getLogger(__name__)


class AgentToolBridge:
    """
    Bridge between VoiceOS agents and native VoiceOS tools
    Provides safe, permission-checked tool access
    """
    
    def __init__(self, tool_registry: ToolRegistry = None):
        if tool_registry is None:
            tool_registry = ToolRegistry()
            initialize_voiceos_tools_integration(tool_registry)
        self.tool_registry = tool_registry
        self.voiceos_tools_integration = None
        self.logger = logging.getLogger(__name__)
        self._initialize_voiceos_tools()
    
    def set_registry(self, tool_registry: ToolRegistry):
        """Attach a shared registry (called from main.py)."""
        self.tool_registry = tool_registry
        self.voiceos_tools_integration = VoiceOSToolsIntegration(tool_registry)
    
    def _initialize_voiceos_tools(self):
        """Initialize VoiceOS tools integration"""
        if self.tool_registry is None:
            return
        try:
            if not self.voiceos_tools_integration:
                self.voiceos_tools_integration = initialize_voiceos_tools_integration(self.tool_registry)
            self.logger.info("VoiceOS tools initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize VoiceOS tools: {e}")
    
    def get_available_tools_for_agent(self, agent_type: str = "general") -> List[str]:
        """Get list of available tools for specific agent type"""
        if self.tool_registry is None:
            return []
        all_tools = self.tool_registry.list_tools()
        
        # Filter tools based on agent type and permissions
        agent_tools = []
        
        for tool_name in all_tools:
            tool_info = self.tool_registry.get_tool_info(tool_name)
            if not tool_info:
                continue
            
            # Check if tool is appropriate for agent type
            if self._is_tool_suitable_for_agent(tool_name, agent_type):
                agent_tools.append(tool_name)
        
        return agent_tools
    
    def _is_tool_suitable_for_agent(self, tool_name: str, agent_type: str) -> bool:
        """Check if tool is suitable for specific agent type"""
        tool_info = self.tool_registry.get_tool_info(tool_name)
        if not tool_info:
            return False
        
        # Agent type to tool category mapping
        agent_tool_mapping = {
            "autonomous": ["web_tools", "system_tools", "file_operations", "analysis"],
            "researcher": ["web_tools", "analysis"],
            "developer": ["system_tools", "file_operations"],
            "analyst": ["analysis", "web_tools"],
            "general": ["file_operations", "web_tools"]
        }
        
        allowed_categories = agent_tool_mapping.get(agent_type, ["file_operations"])
        
        return tool_info["category"] in allowed_categories
    
    async def execute_tool_for_agent(self, agent_type: str, tool_name: str, 
                                   method_name: str = None, **kwargs) -> Dict[str, Any]:
        """Execute tool for agent with permission checking"""
        try:
            # Check if tool exists and is active
            tool_registration = self.tool_registry.get_tool(tool_name)
            if not tool_registration:
                raise ValueError(f"Tool not found: {tool_name}")
            
            if tool_registration.status.value != "active":
                raise RuntimeError(f"Tool {tool_name} is not active")
            
            # Check if tool is suitable for agent type
            if not self._is_tool_suitable_for_agent(tool_name, agent_type):
                raise PermissionError(f"Tool {tool_name} not suitable for agent type {agent_type}")
            
            # Check permissions for VoiceOS tools
            if self.voiceos_tools_integration and tool_name in self.voiceos_tools_integration.voiceos_tools:
                required_permission = self.voiceos_tools_integration.get_tool_permissions(tool_name).get(method_name or "execute", PermissionLevel.MEDIUM)
                
                if not permission_engine.check_tool_permission(required_permission):
                    raise PermissionError(f"Insufficient permissions for {tool_name}.{method_name or 'execute'}")
            
            # Execute tool
            result = await self.tool_registry.execute_tool(
                tool_name=tool_name,
                parameters={"method_name": method_name, **kwargs}
            )
            
            self.logger.info(f"Agent {agent_type} executed {tool_name}.{method_name or 'execute'} successfully")
            
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
                "method_name": method_name,
                "agent_type": agent_type
            }
            
        except Exception as e:
            self.logger.error(f"Agent {agent_type} failed to execute {tool_name}.{method_name or 'execute'}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "method_name": method_name,
                "agent_type": agent_type
            }
    
    def get_tool_info_for_agent(self, agent_type: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool information for agent"""
        if not self._is_tool_suitable_for_agent(tool_name, agent_type):
            return None
        
        tool_info = self.tool_registry.get_tool_info(tool_name)
        if not tool_info:
            return None
        
        # Add VoiceOS specific info if applicable
        if self.voiceos_tools_integration and tool_name in self.voiceos_tools_integration.voiceos_tools:
            tool_info["voiceos_methods"] = self.voiceos_tools_integration.get_tool_methods(tool_name)
            tool_info["voiceos_permissions"] = {
                method: level.value 
                for method, level in self.voiceos_tools_integration.get_tool_permissions(tool_name).items()
            }
        
        return tool_info
    
    def get_agent_tool_summary(self, agent_type: str) -> Dict[str, Any]:
        """Get summary of available tools for agent type"""
        available_tools = self.get_available_tools_for_agent(agent_type)
        
        tool_summary = {
            "agent_type": agent_type,
            "total_tools": len(available_tools),
            "tools": {},
            "categories": {}
        }
        
        for tool_name in available_tools:
            tool_info = self.get_tool_info_for_agent(agent_type, tool_name)
            if tool_info:
                tool_summary["tools"][tool_name] = {
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "category": tool_info["category"],
                    "safety_level": tool_info["safety_level"],
                    "methods": tool_info.get("runtime_methods", [])
                }
                
                # Count by category
                category = tool_info["category"]
                tool_summary["categories"][category] = tool_summary["categories"].get(category, 0) + 1
        
        return tool_summary


class AgentToolManager:
    """
    High-level manager for agent tool access
    """
    
    def __init__(self, tool_registry: ToolRegistry = None):
        self.tool_bridge = AgentToolBridge(tool_registry)
        self.logger = logging.getLogger(__name__)
        
        # Agent configurations
        self.agent_configurations = {
            "autonomous": {
                "default_permission_level": PermissionLevel.HIGH,
                "allowed_categories": ["web_tools", "system_tools", "file_operations", "analysis"],
                "max_concurrent_tools": 5
            },
            "researcher": {
                "default_permission_level": PermissionLevel.MEDIUM,
                "allowed_categories": ["web_tools", "analysis"],
                "max_concurrent_tools": 3
            },
            "developer": {
                "default_permission_level": PermissionLevel.HIGH,
                "allowed_categories": ["system_tools", "file_operations"],
                "max_concurrent_tools": 4
            },
            "analyst": {
                "default_permission_level": PermissionLevel.MEDIUM,
                "allowed_categories": ["analysis", "web_tools"],
                "max_concurrent_tools": 3
            },
            "general": {
                "default_permission_level": PermissionLevel.MEDIUM,
                "allowed_categories": ["file_operations", "web_tools"],
                "max_concurrent_tools": 2
            }
        }
    
    async def execute_agent_task(self, agent_type: str, task_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task plan for a specific agent type"""
        try:
            # Set appropriate permission level for agent
            agent_config = self.agent_configurations.get(agent_type, self.agent_configurations["general"])
            permission_engine.set_user_permission_level(agent_config["default_permission_level"])
            
            # Execute task steps
            results = []
            
            for step in task_plan.get("steps", []):
                step_result = await self._execute_task_step(agent_type, step)
                results.append(step_result)
                
                # Stop if any step fails
                if not step_result.get("success", False):
                    break
            
            return {
                "success": all(r.get("success", False) for r in results),
                "results": results,
                "agent_type": agent_type,
                "task_plan": task_plan
            }
            
        except Exception as e:
            self.logger.error(f"Agent task execution failed for {agent_type}: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": agent_type
            }
    
    async def _execute_task_step(self, agent_type: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task step"""
        tool_name = step.get("tool")
        method_name = step.get("method")
        parameters = step.get("parameters", {})
        
        if not tool_name:
            return {"success": False, "error": "No tool specified"}
        
        return await self.tool_bridge.execute_tool_for_agent(
            agent_type=agent_type,
            tool_name=tool_name,
            method_name=method_name,
            **parameters
        )
    
    def get_agent_capabilities(self, agent_type: str) -> Dict[str, Any]:
        """Get capabilities summary for agent type"""
        return self.tool_bridge.get_agent_tool_summary(agent_type)


# Global agent tool manager instance (registry injected from main.py)
agent_tool_manager = AgentToolManager()


def configure_agent_tools(tool_registry: ToolRegistry, permission_engine=None) -> AgentToolManager:
    """Wire shared tool registry and permission engine into agent tool manager."""
    from permissions.permission_engine import set_permission_engine

    if permission_engine is not None:
        set_permission_engine(permission_engine)
    agent_tool_manager.tool_bridge.set_registry(tool_registry)
    return agent_tool_manager
