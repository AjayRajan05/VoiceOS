"""
VoiceOS Helper Bridge Integration

This module provides a bridge between helper utilities and VoiceOS tools
while maintaining security boundaries and architectural purity.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.config import config
from permissions.permission_engine import PermissionLevel
from core.helpers.secure_helper_integration import get_secure_helper_adapter, HelperCategory
from tools.tool_registry import ToolRegistry, ToolMetadata, ToolCategory


class BridgeMode(Enum):
    """Bridge integration modes"""
    DIRECT = "direct"              # Direct helper execution
    WRAPPED = "wrapped"            # Wrapped through VoiceOS tools
    SANDBOXED = "sandboxed"        # Sandboxed execution
    PROXY = "proxy"                # Proxy through VoiceOS interfaces


@dataclass
class HelperBridge:
    """Helper bridge configuration"""
    helper_name: str
    function_name: str
    voiceos_tool_name: str
    bridge_mode: BridgeMode
    security_level: PermissionLevel
    parameter_mapping: Dict[str, str]
    result_mapping: Dict[str, str]
    description: str
    enabled: bool = True


class HelperBridgeManager:
    """
    Manages bridge between helper utilities and VoiceOS tools.
    
    This class provides secure integration while maintaining VoiceOS
    security boundaries and architectural purity.
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.logger = logging.getLogger(__name__)
        
        # Helper adapter
        self.helper_adapter = get_secure_helper_adapter()
        
        # Bridge configurations
        self.bridges: Dict[str, HelperBridge] = {}
        
        # Bridge execution history
        self.execution_history: List[Dict[str, Any]] = []
        
        # Initialize default bridges
        self._initialize_default_bridges()
    
    async def create_bridge(self, helper_name: str, function_name: str,
                          voiceos_tool_name: str, bridge_mode: BridgeMode,
                          security_level: PermissionLevel = PermissionLevel.MEDIUM,
                          parameter_mapping: Optional[Dict[str, str]] = None,
                          result_mapping: Optional[Dict[str, str]] = None,
                          description: str = "") -> Dict[str, Any]:
        """
        Create a bridge between helper function and VoiceOS tool.
        
        Args:
            helper_name: Name of helper module
            function_name: Name of helper function
            voiceos_tool_name: Name of VoiceOS tool
            bridge_mode: Bridge integration mode
            security_level: Required permission level
            parameter_mapping: Map helper parameters to tool parameters
            result_mapping: Map tool results to helper results
            description: Bridge description
            
        Returns:
            Bridge creation result
        """
        try:
            # Validate helper exists
            registered_helpers = self.helper_adapter.get_registered_helpers()
            helper_found = any(h["name"] == helper_name for h in registered_helpers)
            
            if not helper_found:
                return {
                    "success": False,
                    "error": f"Helper not found: {helper_name}"
                }
            
            # Validate function exists in helper
            helper_functions = self.helper_adapter.get_helper_functions(helper_name)
            function_found = any(f["name"] == function_name for f in helper_functions)
            
            if not function_found:
                return {
                    "success": False,
                    "error": f"Function not found in helper: {function_name}"
                }
            
            # Create bridge
            bridge_id = f"{helper_name}.{function_name}"
            bridge = HelperBridge(
                helper_name=helper_name,
                function_name=function_name,
                voiceos_tool_name=voiceos_tool_name,
                bridge_mode=bridge_mode,
                security_level=security_level,
                parameter_mapping=parameter_mapping or {},
                result_mapping=result_mapping or {},
                description=description or f"Bridge {helper_name}.{function_name} to {voiceos_tool_name}"
            )
            
            self.bridges[bridge_id] = bridge
            
            # Register VoiceOS tool if needed
            await self._register_bridge_tool(bridge)
            
            self.logger.info(f"Created bridge: {bridge_id}")
            
            return {
                "success": True,
                "bridge_id": bridge_id,
                "bridge_mode": bridge_mode.value,
                "security_level": security_level.value
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create bridge: {e}")
            return {
                "success": False,
                "error": f"Bridge creation failed: {e}"
            }
    
    async def execute_bridge(self, bridge_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a bridge operation.
        
        Args:
            bridge_id: Bridge identifier
            params: Operation parameters
            
        Returns:
            Execution result
        """
        if bridge_id not in self.bridges:
            return {
                "success": False,
                "error": f"Bridge not found: {bridge_id}"
            }
        
        bridge = self.bridges[bridge_id]
        
        if not bridge.enabled:
            return {
                "success": False,
                "error": f"Bridge is disabled: {bridge_id}"
            }
        
        try:
            # Execute based on bridge mode
            if bridge.bridge_mode == BridgeMode.DIRECT:
                result = await self._execute_direct_bridge(bridge, params)
            elif bridge.bridge_mode == BridgeMode.WRAPPED:
                result = await self._execute_wrapped_bridge(bridge, params)
            elif bridge.bridge_mode == BridgeMode.SANDBOXED:
                result = await self._execute_sandboxed_bridge(bridge, params)
            elif bridge.bridge_mode == BridgeMode.PROXY:
                result = await self._execute_proxy_bridge(bridge, params)
            else:
                result = {
                    "success": False,
                    "error": f"Unsupported bridge mode: {bridge.bridge_mode}"
                }
            
            # Record execution
            self.execution_history.append({
                "bridge_id": bridge_id,
                "timestamp": asyncio.get_event_loop().time(),
                "success": result.get("success", False),
                "bridge_mode": bridge.bridge_mode.value
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bridge execution failed: {e}")
            
            # Record failed execution
            self.execution_history.append({
                "bridge_id": bridge_id,
                "timestamp": asyncio.get_event_loop().time(),
                "success": False,
                "error": str(e),
                "bridge_mode": bridge.bridge_mode.value
            })
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_direct_bridge(self, bridge: HelperBridge, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bridge in direct mode"""
        # Map parameters
        mapped_params = self._map_parameters(params, bridge.parameter_mapping)
        
        # Execute helper function directly
        result = await self.helper_adapter.execute_helper_function(
            bridge.helper_name, bridge.function_name, mapped_params
        )
        
        if result["success"]:
            # Map results
            mapped_result = self._map_results(result["result"], bridge.result_mapping)
            return {
                "success": True,
                "result": mapped_result,
                "bridge_mode": "direct"
            }
        else:
            return result
    
    async def _execute_wrapped_bridge(self, bridge: HelperBridge, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bridge in wrapped mode"""
        # Map parameters
        mapped_params = self._map_parameters(params, bridge.parameter_mapping)
        
        # Execute through VoiceOS tool wrapper
        tool_result = await self._execute_voiceos_tool(bridge.voiceos_tool_name, mapped_params)
        
        if tool_result["success"]:
            # Map results back to helper format
            mapped_result = self._map_results(tool_result["result"], bridge.result_mapping)
            return {
                "success": True,
                "result": mapped_result,
                "bridge_mode": "wrapped"
            }
        else:
            return tool_result
    
    async def _execute_sandboxed_bridge(self, bridge: HelperBridge, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bridge in sandboxed mode"""
        # This would implement actual sandboxing
        # For now, use wrapped mode
        return await self._execute_wrapped_bridge(bridge, params)
    
    async def _execute_proxy_bridge(self, bridge: HelperBridge, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bridge in proxy mode"""
        # Proxy through VoiceOS interface
        return await self._execute_wrapped_bridge(bridge, params)
    
    async def _execute_voiceos_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute VoiceOS tool"""
        # This would execute actual VoiceOS tool
        # For now, simulate execution
        return {
            "success": True,
            "result": f"Executed {tool_name} with params: {params}"
        }
    
    def _map_parameters(self, params: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Map parameters according to bridge configuration"""
        mapped_params = {}
        
        for key, value in params.items():
            mapped_key = mapping.get(key, key)
            mapped_params[mapped_key] = value
        
        return mapped_params
    
    def _map_results(self, result: Any, mapping: Dict[str, str]) -> Any:
        """Map results according to bridge configuration"""
        if not mapping or not isinstance(result, dict):
            return result
        
        mapped_result = {}
        
        for key, value in result.items():
            mapped_key = mapping.get(key, key)
            mapped_result[mapped_key] = value
        
        return mapped_result
    
    async def _register_bridge_tool(self, bridge: HelperBridge):
        """Register VoiceOS tool for bridge"""
        # Create tool metadata
        tool_metadata = ToolMetadata(
            name=bridge.voiceos_tool_name,
            description=bridge.description,
            category=ToolCategory.HELPER_TOOLS,
            permission_level=bridge.security_level,
            parameters={
                "bridge_id": {"type": "string", "required": True},
                "params": {"type": "object", "required": True}
            }
        )
        
        # Register tool with bridge execution function
        async def bridge_tool(**kwargs):
            bridge_id = kwargs.get("bridge_id")
            params = kwargs.get("params", {})
            return await self.execute_bridge(bridge_id, params)
        
        self.tool_registry.register_tool(tool_metadata, bridge_tool)
    
    def _initialize_default_bridges(self):
        """Initialize default helper bridges"""
        # File operations bridge
        self._create_bridge_sync(
            helper_name="files",
            function_name="read_file",
            voiceos_tool_name="voiceos_file_reader",
            bridge_mode=BridgeMode.WRAPPED,
            security_level=PermissionLevel.MEDIUM,
            parameter_mapping={"path": "file_path"},
            result_mapping={"content": "file_content"},
            description="Bridge helper file reading to VoiceOS file tool"
        )
        
        # Web operations bridge
        self._create_bridge_sync(
            helper_name="browser",
            function_name="search",
            voiceos_tool_name="voiceos_web_search",
            bridge_mode=BridgeMode.WRAPPED,
            security_level=PermissionLevel.MEDIUM,
            parameter_mapping={"query": "search_query"},
            result_mapping={"results": "search_results"},
            description="Bridge helper web search to VoiceOS web tool"
        )
        
        # Data processing bridge
        self._create_bridge_sync(
            helper_name="data_processor",
            function_name="process_data",
            voiceos_tool_name="voiceos_data_processor",
            bridge_mode=BridgeMode.SANDBOXED,
            security_level=PermissionLevel.LOW,
            parameter_mapping={"data": "input_data"},
            result_mapping={"processed": "output_data"},
            description="Bridge helper data processing to VoiceOS data tool"
        )
    
    def get_bridges(self) -> List[Dict[str, Any]]:
        """Get list of all bridges"""
        return [
            {
                "bridge_id": bridge_id,
                "helper_name": bridge.helper_name,
                "function_name": bridge.function_name,
                "voiceos_tool_name": bridge.voiceos_tool_name,
                "bridge_mode": bridge.bridge_mode.value,
                "security_level": bridge.security_level.value,
                "enabled": bridge.enabled,
                "description": bridge.description
            }
            for bridge_id, bridge in self.bridges.items()
        ]
    
    def enable_bridge(self, bridge_id: str) -> Dict[str, Any]:
        """Enable a bridge"""
        if bridge_id not in self.bridges:
            return {
                "success": False,
                "error": f"Bridge not found: {bridge_id}"
            }
        
        self.bridges[bridge_id].enabled = True
        return {
            "success": True,
            "bridge_id": bridge_id,
            "enabled": True
        }
    
    def disable_bridge(self, bridge_id: str) -> Dict[str, Any]:
        """Disable a bridge"""
        if bridge_id not in self.bridges:
            return {
                "success": False,
                "error": f"Bridge not found: {bridge_id}"
            }
        
        self.bridges[bridge_id].enabled = False
        return {
            "success": True,
            "bridge_id": bridge_id,
            "enabled": False
        }
    
    def remove_bridge(self, bridge_id: str) -> Dict[str, Any]:
        """Remove a bridge"""
        if bridge_id not in self.bridges:
            return {
                "success": False,
                "error": f"Bridge not found: {bridge_id}"
            }
        
        bridge = self.bridges[bridge_id]
        
        # Unregister VoiceOS tool
        try:
            self.tool_registry.unregister_tool(bridge.voiceos_tool_name)
        except KeyError as e:
            logger.debug(f"Tool {bridge.voiceos_tool_name} not registered: {e}")
        except Exception as e:
            logger.warning(f"Error unregistering tool {bridge.voiceos_tool_name}: {e}")
        
        # Remove bridge
        del self.bridges[bridge_id]
        
        return {
            "success": True,
            "bridge_id": bridge_id,
            "removed": True
        }
    
    def _create_bridge_sync(self, helper_name: str, function_name: str,
                        voiceos_tool_name: str, bridge_mode: BridgeMode,
                        security_level: PermissionLevel = PermissionLevel.MEDIUM,
                        parameter_mapping: Optional[Dict[str, str]] = None,
                        result_mapping: Optional[Dict[str, str]] = None,
                        description: str = ""):
        """Create a bridge synchronously (non-async version)"""
        bridge_id = f"{helper_name}.{function_name}"
        bridge = HelperBridge(
            helper_name=helper_name,
            function_name=function_name,
            voiceos_tool_name=voiceos_tool_name,
            bridge_mode=bridge_mode,
            security_level=security_level,
            parameter_mapping=parameter_mapping or {},
            result_mapping=result_mapping or {},
            description=description or f"Bridge {helper_name}.{function_name} to {voiceos_tool_name}"
        )
        
        self.bridges[bridge_id] = bridge
        
        # Register VoiceOS tool if needed
        try:
            self._register_bridge_tool(bridge)
        except Exception as e:
            # Tool registration might fail if tool registry is not ready
            pass
    
    def get_bridge_statistics(self) -> Dict[str, Any]:
        """Get bridge execution statistics"""
        total_executions = len(self.execution_history)
        successful_executions = len([e for e in self.execution_history if e["success"]])
        failed_executions = total_executions - successful_executions
        
        # Statistics by bridge mode
        mode_stats = {}
        for bridge in self.bridges.values():
            mode = bridge.bridge_mode.value
            if mode not in mode_stats:
                mode_stats[mode] = {"total": 0, "success": 0, "failed": 0}
            mode_stats[mode]["total"] += 1
        
        for execution in self.execution_history:
            mode = execution["bridge_mode"]
            if mode in mode_stats:
                if execution["success"]:
                    mode_stats[mode]["success"] += 1
                else:
                    mode_stats[mode]["failed"] += 1
        
        return {
            "total_bridges": len(self.bridges),
            "enabled_bridges": len([b for b in self.bridges.values() if b.enabled]),
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": (successful_executions / total_executions * 100) if total_executions > 0 else 0,
            "statistics_by_mode": mode_stats
        }


# Global bridge manager instance
helper_bridge_manager = None

def get_helper_bridge_manager(tool_registry: ToolRegistry) -> HelperBridgeManager:
    """Get or create helper bridge manager instance"""
    global helper_bridge_manager
    if helper_bridge_manager is None:
        helper_bridge_manager = HelperBridgeManager(tool_registry)
    return helper_bridge_manager
