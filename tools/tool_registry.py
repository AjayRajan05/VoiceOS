"""
Tool Registry Module - Comprehensive tool management system
Provides tool discovery, loading, dependency management, and execution
"""

import asyncio
import logging
import importlib
import inspect
from typing import Dict, Any, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
import time
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ToolStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    LOADING = "loading"

class ToolCategory(Enum):
    OS_CONTROL = "os_control"
    WEB_TOOLS = "web_tools"
    AGENT_TOOLS = "agent_tools"
    FILE_OPERATIONS = "file_operations"
    SYSTEM_TOOLS = "system_tools"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"

@dataclass
class ToolMetadata:
    name: str
    description: str
    category: ToolCategory
    version: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    safety_level: str = "medium"  # low, medium, high, critical
    async_execution: bool = False
    timeout: float = 30.0
    tags: List[str] = field(default_factory=list)

@dataclass
class ToolRegistration:
    tool_class: Type
    instance: Any
    metadata: ToolMetadata
    status: ToolStatus
    registration_time: float
    last_used: float = 0.0
    usage_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

@dataclass
class ToolConfig:
    auto_discover: bool = True
    tool_directories: List[str] = field(default_factory=lambda: ["tools", "tools/agent_tools"])
    enable_caching: bool = True
    cache_timeout: int = 300  # 5 minutes
    enable_metrics: bool = True
    max_concurrent_executions: int = 10
    default_timeout: float = 30.0

class ToolRegistry:
    def __init__(self, config: ToolConfig = None):
        self.config = config or ToolConfig()
        
        # Tool storage
        self.tools: Dict[str, ToolRegistration] = {}
        self.tool_index: Dict[ToolCategory, List[str]] = {cat: [] for cat in ToolCategory}
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Execution tracking
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.execution_semaphore = asyncio.Semaphore(self.config.max_concurrent_executions)
        
        # Metrics
        self.metrics = {
            "total_registrations": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "execution_times": {},
            "tool_usage": {}
        }
        
        # Auto-discover tools if enabled
        if self.config.auto_discover:
            self._discover_tools()
    
    def _discover_tools(self):
        """
        Auto-discover tools from configured directories
        """
        for directory in self.config.tool_directories:
            self._discover_tools_in_directory(directory)
    
    def _discover_tools_in_directory(self, directory: str):
        """
        Discover tools in a specific directory
        """
        try:
            tool_dir = Path(directory)
            if not tool_dir.exists():
                logger.warning(f"Tool directory not found: {directory}")
                return
            
            # Find Python files
            for py_file in tool_dir.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                self._load_tool_from_file(py_file)
                
        except Exception as e:
            logger.error(f"Failed to discover tools in {directory}: {e}")
    
    def _load_tool_from_file(self, file_path: Path):
        """
        Load tool from a Python file
        """
        try:
            # Import module
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find tool classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_tool_class(obj):
                    self.register_tool(obj, module.__file__)
                    
        except Exception as e:
            logger.error(f"Failed to load tool from {file_path}: {e}")
    
    def _is_tool_class(self, cls) -> bool:
        """
        Check if a class is a valid tool
        """
        # Check if it has execute method
        if not hasattr(cls, 'execute'):
            return False
        
        # Check if it's not from built-in modules
        if cls.__module__ in ['builtins']:
            return False
        
        return True
    
    def register_tool(self, tool_class: Type, file_path: str = None) -> bool:
        """
        Register a tool class
        """
        try:
            # Extract metadata
            metadata = self._extract_tool_metadata(tool_class)
            if not metadata:
                logger.warning(f"No metadata found for tool class: {tool_class.__name__}")
                return False
            
            # Create instance
            tool_instance = tool_class()
            
            # Create registration
            registration = ToolRegistration(
                tool_class=tool_class,
                instance=tool_instance,
                metadata=metadata,
                status=ToolStatus.ACTIVE,
                registration_time=time.time()
            )
            
            # Store registration
            self.tools[metadata.name] = registration
            self.tool_index[metadata.category].append(metadata.name)
            
            # Update dependency graph
            self.dependency_graph[metadata.name] = metadata.dependencies
            
            # Update metrics
            self.metrics["total_registrations"] += 1
            self.metrics["tool_usage"][metadata.name] = 0
            
            logger.info(f"Registered tool: {metadata.name} ({metadata.category.value})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register tool {tool_class.__name__}: {e}")
            return False
    
    def _extract_tool_metadata(self, tool_class: Type) -> Optional[ToolMetadata]:
        """
        Extract metadata from tool class
        """
        try:
            # Check for metadata attribute
            if hasattr(tool_class, 'TOOL_METADATA'):
                metadata_value = tool_class.TOOL_METADATA
                if isinstance(metadata_value, ToolMetadata):
                    return metadata_value
                if isinstance(metadata_value, dict):
                    category = metadata_value.get('category', 'system_tools')
                    if isinstance(category, ToolCategory):
                        category_enum = category
                    else:
                        category_enum = ToolCategory(category)
                    return ToolMetadata(
                        name=metadata_value.get('name', tool_class.__name__.lower()),
                        description=metadata_value.get('description', ''),
                        category=category_enum,
                        version=metadata_value.get('version', '1.0.0'),
                        author=metadata_value.get('author', 'Unknown'),
                        dependencies=metadata_value.get('dependencies', []),
                        parameters=metadata_value.get('parameters', {}),
                        safety_level=metadata_value.get('safety_level', 'medium'),
                        async_execution=metadata_value.get('async_execution', False),
                        timeout=metadata_value.get('timeout', self.config.default_timeout),
                        tags=metadata_value.get('tags', [])
                    )
            
            # Extract from docstring
            docstring = tool_class.__doc__ or ""
            lines = [line.strip() for line in docstring.split('\n') if line.strip()]
            
            if lines:
                # Try to parse simple format
                name = tool_class.__name__.lower()
                description = lines[0] if lines else ""
                category = ToolCategory.SYSTEM_TOOLS
                
                # Guess category from name
                if 'web' in name or 'search' in name:
                    category = ToolCategory.WEB_TOOLS
                elif 'file' in name or 'dir' in name:
                    category = ToolCategory.FILE_OPERATIONS
                elif 'os' in name or 'system' in name:
                    category = ToolCategory.OS_CONTROL
                
                return ToolMetadata(
                    name=name,
                    description=description,
                    category=category,
                    version="1.0.0",
                    author="Auto-detected",
                    dependencies=[],
                    parameters={},
                    safety_level="medium",
                    async_execution=inspect.iscoroutinefunction(tool_class.execute),
                    timeout=self.config.default_timeout,
                    tags=[]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract metadata from {tool_class.__name__}: {e}")
            return None
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any], 
                          context: Dict[str, Any] = None) -> Any:
        """
        Execute a tool with parameters
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
        
        registration = self.tools[tool_name]
        
        # Check tool status
        if registration.status != ToolStatus.ACTIVE:
            raise RuntimeError(f"Tool {tool_name} is not active (status: {registration.status.value})")
        
        # Check dependencies
        if not self._check_dependencies(tool_name):
            raise RuntimeError(f"Dependencies not satisfied for tool: {tool_name}")
        
        # Acquire semaphore for concurrency control
        async with self.execution_semaphore:
            try:
                start_time = time.time()
                
                # Update usage stats
                registration.usage_count += 1
                registration.last_used = start_time
                self.metrics["total_executions"] += 1
                self.metrics["tool_usage"][tool_name] += 1
                
                # Execute tool
                if registration.metadata.async_execution:
                    result = await registration.instance.execute(**parameters)
                else:
                    # Run sync tool in thread pool
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, registration.instance.execute, **parameters
                    )
                
                # Update metrics
                execution_time = time.time() - start_time
                self._update_execution_metrics(tool_name, execution_time, True)
                
                return result
                
            except Exception as e:
                # Update error stats
                registration.error_count += 1
                registration.last_error = str(e)
                self.metrics["failed_executions"] += 1
                
                self._update_execution_metrics(tool_name, time.time() - start_time, False)
                
                logger.error(f"Tool execution failed {tool_name}: {e}")
                raise
    
    def _check_dependencies(self, tool_name: str) -> bool:
        """
        Check if tool dependencies are satisfied
        """
        dependencies = self.dependency_graph.get(tool_name, [])
        
        for dep in dependencies:
            if dep not in self.tools:
                logger.warning(f"Dependency {dep} not found for tool {tool_name}")
                return False
            
            if self.tools[dep].status != ToolStatus.ACTIVE:
                logger.warning(f"Dependency {dep} not active for tool {tool_name}")
                return False
        
        return True
    
    def _update_execution_metrics(self, tool_name: str, execution_time: float, success: bool):
        """
        Update execution metrics
        """
        if success:
            self.metrics["successful_executions"] += 1
        
        # Update execution times
        if tool_name not in self.metrics["execution_times"]:
            self.metrics["execution_times"][tool_name] = []
        
        self.metrics["execution_times"][tool_name].append(execution_time)
        
        # Keep only recent times
        if len(self.metrics["execution_times"][tool_name]) > 100:
            self.metrics["execution_times"][tool_name] = \
                self.metrics["execution_times"][tool_name][-50:]
    
    def get_tool(self, tool_name: str) -> Optional[ToolRegistration]:
        """
        Get tool registration by name
        """
        return self.tools.get(tool_name)
    
    def list_tools(self, category: ToolCategory = None, status: ToolStatus = None) -> List[str]:
        """
        List tools with optional filtering
        """
        tools = list(self.tools.keys())
        
        if category:
            tools = [name for name in tools if self.tools[name].metadata.category == category]
        
        if status:
            tools = [name for name in tools if self.tools[name].status == status]
        
        return tools
    
    def get_tools_by_category(self) -> Dict[ToolCategory, List[str]]:
        """
        Get tools grouped by category
        """
        return {cat: tools[:] for cat, tools in self.tool_index.items()}
    
    def search_tools(self, query: str) -> List[str]:
        """
        Search tools by name, description, or tags
        """
        query_lower = query.lower()
        results = []
        
        for tool_name, registration in self.tools.items():
            # Search name
            if query_lower in tool_name.lower():
                results.append(tool_name)
                continue
            
            # Search description
            if query_lower in registration.metadata.description.lower():
                results.append(tool_name)
                continue
            
            # Search tags
            if any(query_lower in tag.lower() for tag in registration.metadata.tags):
                results.append(tool_name)
        
        return results
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed tool information
        """
        registration = self.tools.get(tool_name)
        if not registration:
            return None
        
        # Calculate average execution time
        exec_times = self.metrics["execution_times"].get(tool_name, [])
        avg_time = sum(exec_times) / len(exec_times) if exec_times else 0
        
        return {
            "name": registration.metadata.name,
            "description": registration.metadata.description,
            "category": registration.metadata.category.value,
            "version": registration.metadata.version,
            "author": registration.metadata.author,
            "dependencies": registration.metadata.dependencies,
            "parameters": registration.metadata.parameters,
            "safety_level": registration.metadata.safety_level,
            "async_execution": registration.metadata.async_execution,
            "timeout": registration.metadata.timeout,
            "tags": registration.metadata.tags,
            "status": registration.status.value,
            "usage_count": registration.usage_count,
            "error_count": registration.error_count,
            "last_used": registration.last_used,
            "average_execution_time": avg_time,
            "last_error": registration.last_error
        }
    
    def set_tool_status(self, tool_name: str, status: ToolStatus) -> bool:
        """
        Set tool status
        """
        if tool_name not in self.tools:
            return False
        
        self.tools[tool_name].status = status
        logger.info(f"Set tool {tool_name} status to {status.value}")
        return True
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool
        """
        if tool_name not in self.tools:
            return False
        
        registration = self.tools[tool_name]
        
        # Remove from indexes
        self.tool_index[registration.metadata.category].remove(tool_name)
        
        # Remove from dependency graph
        self.dependency_graph.pop(tool_name, None)
        
        # Remove from tools
        del self.tools[tool_name]
        
        # Update metrics
        self.metrics["tool_usage"].pop(tool_name, None)
        self.metrics["execution_times"].pop(tool_name, None)
        
        logger.info(f"Unregistered tool: {tool_name}")
        return True
    
    def get_registry_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive registry metrics
        """
        # Calculate success rate
        total = self.metrics["total_executions"]
        success_rate = (self.metrics["successful_executions"] / total * 100) if total > 0 else 0
        
        # Calculate average execution times
        avg_times = {}
        for tool_name, times in self.metrics["execution_times"].items():
            if times:
                avg_times[tool_name] = sum(times) / len(times)
        
        return {
            **self.metrics,
            "success_rate": success_rate,
            "average_execution_times": avg_times,
            "registered_tools": len(self.tools),
            "active_executions": len(self.active_executions),
            "tools_by_category": {cat.value: len(tools) for cat, tools in self.tool_index.items()},
            "dependency_graph_size": len(self.dependency_graph)
        }
    
    def export_registry(self, file_path: str) -> bool:
        """
        Export registry configuration to file
        """
        try:
            export_data = {
                "tools": {
                    name: {
                        "metadata": {
                            "name": reg.metadata.name,
                            "description": reg.metadata.description,
                            "category": reg.metadata.category.value,
                            "version": reg.metadata.version,
                            "author": reg.metadata.author,
                            "dependencies": reg.metadata.dependencies,
                            "parameters": reg.metadata.parameters,
                            "safety_level": reg.metadata.safety_level,
                            "async_execution": reg.metadata.async_execution,
                            "timeout": reg.metadata.timeout,
                            "tags": reg.metadata.tags
                        },
                        "status": reg.status.value,
                        "registration_time": reg.registration_time
                    }
                    for name, reg in self.tools.items()
                },
                "dependency_graph": self.dependency_graph,
                "metrics": self.metrics
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported registry to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export registry: {e}")
            return False
    
    async def shutdown(self):
        """
        Shutdown tool registry
        """
        # Cancel active executions
        for execution_id, task in self.active_executions.items():
            task.cancel()
        
        # Wait for tasks to complete
        if self.active_executions:
            await asyncio.gather(*self.active_executions.values(), return_exceptions=True)
        
        self.active_executions.clear()
        logger.info("Tool registry shutdown complete")