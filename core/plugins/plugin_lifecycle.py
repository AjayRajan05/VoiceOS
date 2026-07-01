"""
VoiceOS Plugin Lifecycle Management

This module provides comprehensive plugin lifecycle management including
loading, initialization, execution, monitoring, and cleanup while maintaining
security boundaries and architectural purity.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import hashlib

from core.config import config
from permissions.permission_engine import PermissionLevel
from core.plugins.secure_plugin_integration import (
    PluginManifest, SecurityPolicy, SecurityLevel, VoiceOSPluginInterface
)
from core.integration.controlled_execution import ExecutionMode, ExecutionLimits


class PluginState(Enum):
    """Plugin lifecycle states"""
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ERROR = "error"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"


class LifecycleEvent(Enum):
    """Plugin lifecycle events"""
    DISCOVERED = "plugin_discovered"
    LOADING_STARTED = "plugin_loading_started"
    LOADING_COMPLETED = "plugin_loading_completed"
    INITIALIZATION_STARTED = "plugin_initialization_started"
    INITIALIZATION_COMPLETED = "plugin_initialization_completed"
    ACTIVATION = "plugin_activated"
    SUSPENSION = "plugin_suspended"
    ERROR_OCCURRED = "plugin_error"
    UNLOADING_STARTED = "plugin_unloading_started"
    UNLOADING_COMPLETED = "plugin_unloading_completed"


@dataclass
class PluginInstance:
    """Plugin instance with lifecycle state"""
    manifest: PluginManifest
    state: PluginState
    instance: Optional[VoiceOSPluginInterface] = None
    load_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    error_count: int = 0
    execution_count: int = 0
    security_violations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleMetrics:
    """Plugin lifecycle metrics"""
    total_plugins: int = 0
    active_plugins: int = 0
    error_plugins: int = 0
    total_executions: int = 0
    total_errors: int = 0
    average_load_time: float = 0.0
    uptime_percentage: float = 0.0


class PluginLifecycleManager:
    """
    Manages complete plugin lifecycle with security and monitoring.
    
    This class handles plugin discovery, loading, initialization, execution,
    monitoring, and cleanup while maintaining VoiceOS security boundaries.
    """
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        
        # Plugin registry
        self.plugins: Dict[str, PluginInstance] = {}
        self.plugin_states: Dict[str, PluginState] = {}
        
        # Lifecycle event handlers
        self.event_handlers: Dict[LifecycleEvent, List[Callable]] = {}
        
        # Lifecycle configuration
        self.max_load_time = 30.0  # Maximum time to load a plugin
        self.max_error_count = 5   # Maximum errors before suspension
        self.health_check_interval = 60.0  # Health check interval
        
        # Metrics
        self.metrics = LifecycleMetrics()
        self.lifecycle_events: List[Dict[str, Any]] = []
        
        # Start health monitoring
        self._health_monitor_task = None
        
    async def start_lifecycle_management(self):
        """Start plugin lifecycle management"""
        self.logger.info("Starting plugin lifecycle management...")
        self._health_monitor_task = asyncio.create_task(self._health_monitor())
        
    async def stop_lifecycle_management(self):
        """Stop plugin lifecycle management"""
        self.logger.info("Stopping plugin lifecycle management...")
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Unload all plugins
        await self.unload_all_plugins()
    
    async def discover_plugins(self, plugin_directories: List[Path]) -> Dict[str, Any]:
        """
        Discover plugins in specified directories.
        
        Args:
            plugin_directories: List of directories to search for plugins
            
        Returns:
            Discovery results
        """
        self.logger.info(f"Discovering plugins in {len(plugin_directories)} directories...")
        discovered_plugins = []
        
        for directory in plugin_directories:
            if not directory.exists():
                self.logger.warning(f"Plugin directory not found: {directory}")
                continue
            
            # Look for plugin.yaml files
            for plugin_path in directory.iterdir():
                if plugin_path.is_dir() and (plugin_path / "plugin.yaml").exists():
                    try:
                        manifest = await self._load_plugin_manifest(plugin_path)
                        if manifest:
                            plugin_instance = PluginInstance(
                                manifest=manifest,
                                state=PluginState.DISCOVERED
                            )
                            self.plugins[manifest.name] = plugin_instance
                            discovered_plugins.append(manifest.name)
                            
                            # Emit discovery event
                            await self._emit_lifecycle_event(
                                LifecycleEvent.DISCOVERED,
                                plugin_name=manifest.name,
                                manifest=manifest
                            )
                            
                    except Exception as e:
                        self.logger.error(f"Error discovering plugin {plugin_path}: {e}")
        
        self.metrics.total_plugins = len(self.plugins)
        
        return {
            "success": True,
            "discovered_count": len(discovered_plugins),
            "plugins": discovered_plugins
        }
    
    async def load_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load a plugin into memory.
        
        Args:
            plugin_name: Name of plugin to load
            
        Returns:
            Loading result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state != PluginState.DISCOVERED:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not in discovered state"
            }
        
        start_time = time.time()
        
        try:
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.LOADING)
            
            # Emit loading started event
            await self._emit_lifecycle_event(
                LifecycleEvent.LOADING_STARTED,
                plugin_name=plugin_name
            )
            
            # Load plugin code (this would use the secure adapter)
            plugin_path = self.workspace_root / "plugins" / plugin_name
            
            # Validate plugin security
            from core.plugins.secure_plugin_integration import SecurityValidator
            validator = SecurityValidator()
            validation_result = validator.validate_plugin_code(plugin_path)
            
            if not validation_result["valid"]:
                await self._update_plugin_state(plugin_name, PluginState.ERROR)
                return {
                    "success": False,
                    "error": "Security validation failed",
                    "issues": validation_result["issues"]
                }
            
            # Create plugin instance (simplified for now)
            # In real implementation, this would use the secure adapter
            plugin_instance.instance = self._create_plugin_instance(plugin_instance.manifest)
            
            # Update metrics
            load_time = time.time() - start_time
            plugin_instance.load_time = load_time
            self._update_load_time_metrics(load_time)
            
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.LOADED)
            
            # Emit loading completed event
            await self._emit_lifecycle_event(
                LifecycleEvent.LOADING_COMPLETED,
                plugin_name=plugin_name,
                load_time=load_time
            )
            
            return {
                "success": True,
                "plugin_name": plugin_name,
                "load_time": load_time,
                "security_score": validation_result["security_score"]
            }
            
        except Exception as e:
            await self._update_plugin_state(plugin_name, PluginState.ERROR)
            plugin_instance.error_count += 1
            self.metrics.total_errors += 1
            
            return {
                "success": False,
                "error": f"Plugin loading failed: {e}"
            }
    
    async def initialize_plugin(self, plugin_name: str, 
                             voiceos_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize a plugin.
        
        Args:
            plugin_name: Name of plugin to initialize
            voiceos_context: VoiceOS context for initialization
            
        Returns:
            Initialization result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state != PluginState.LOADED:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not loaded"
            }
        
        if not plugin_instance.instance:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} has no instance"
            }
        
        try:
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.INITIALIZING)
            
            # Emit initialization started event
            await self._emit_lifecycle_event(
                LifecycleEvent.INITIALIZATION_STARTED,
                plugin_name=plugin_name
            )
            
            # Initialize plugin
            init_success = await plugin_instance.instance.initialize(voiceos_context)
            
            if init_success:
                # Update state to active
                await self._update_plugin_state(plugin_name, PluginState.ACTIVE)
                
                # Emit initialization completed event
                await self._emit_lifecycle_event(
                    LifecycleEvent.INITIALIZATION_COMPLETED,
                    plugin_name=plugin_name
                )
                
                # Emit activation event
                await self._emit_lifecycle_event(
                    LifecycleEvent.ACTIVATION,
                    plugin_name=plugin_name
                )
                
                return {
                    "success": True,
                    "plugin_name": plugin_name,
                    "state": "active"
                }
            else:
                await self._update_plugin_state(plugin_name, PluginState.ERROR)
                plugin_instance.error_count += 1
                
                return {
                    "success": False,
                    "error": "Plugin initialization failed"
                }
                
        except Exception as e:
            await self._update_plugin_state(plugin_name, PluginState.ERROR)
            plugin_instance.error_count += 1
            self.metrics.total_errors += 1
            
            return {
                "success": False,
                "error": f"Plugin initialization failed: {e}"
            }
    
    async def execute_plugin_operation(self, plugin_name: str, operation: str,
                                    params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute plugin operation with lifecycle tracking.
        
        Args:
            plugin_name: Name of plugin
            operation: Operation to execute
            params: Operation parameters
            
        Returns:
            Execution result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state != PluginState.ACTIVE:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not active"
            }
        
        try:
            # Update activity
            plugin_instance.last_activity = time.time()
            plugin_instance.execution_count += 1
            self.metrics.total_executions += 1
            
            # Execute operation (through secure adapter in real implementation)
            if plugin_instance.instance:
                # Create security policy for operation
                security_policy = SecurityPolicy(
                    level=plugin_instance.manifest.security_level,
                    allowed_operations=[operation],
                    timeout_seconds=30
                )
                
                result = await plugin_instance.instance.execute_operation(
                    operation, params, security_policy
                )
                
                return result
            else:
                return {
                    "success": False,
                    "error": "Plugin instance not available"
                }
                
        except Exception as e:
            plugin_instance.error_count += 1
            self.metrics.total_errors += 1
            
            # Check if plugin should be suspended
            if plugin_instance.error_count >= self.max_error_count:
                await self.suspend_plugin(plugin_name, f"Too many errors: {e}")
            
            return {
                "success": False,
                "error": f"Plugin operation failed: {e}"
            }
    
    async def suspend_plugin(self, plugin_name: str, reason: str) -> Dict[str, Any]:
        """
        Suspend a plugin.
        
        Args:
            plugin_name: Name of plugin to suspend
            reason: Reason for suspension
            
        Returns:
            Suspension result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state != PluginState.ACTIVE:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not active"
            }
        
        try:
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.SUSPENDED)
            
            # Emit suspension event
            await self._emit_lifecycle_event(
                LifecycleEvent.SUSPENSION,
                plugin_name=plugin_name,
                reason=reason
            )
            
            plugin_instance.metadata["suspension_reason"] = reason
            plugin_instance.metadata["suspension_time"] = time.time()
            
            return {
                "success": True,
                "plugin_name": plugin_name,
                "reason": reason
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Plugin suspension failed: {e}"
            }
    
    async def resume_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Resume a suspended plugin.
        
        Args:
            plugin_name: Name of plugin to resume
            
        Returns:
            Resume result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state != PluginState.SUSPENDED:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not suspended"
            }
        
        try:
            # Reset error count
            plugin_instance.error_count = 0
            
            # Update state to active
            await self._update_plugin_state(plugin_name, PluginState.ACTIVE)
            
            # Clear suspension metadata
            plugin_instance.metadata.pop("suspension_reason", None)
            plugin_instance.metadata.pop("suspension_time", None)
            
            return {
                "success": True,
                "plugin_name": plugin_name,
                "state": "active"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Plugin resume failed: {e}"
            }
    
    async def unload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Unload a plugin from memory.
        
        Args:
            plugin_name: Name of plugin to unload
            
        Returns:
            Unload result
        """
        if plugin_name not in self.plugins:
            return {
                "success": False,
                "error": f"Plugin not found: {plugin_name}"
            }
        
        plugin_instance = self.plugins[plugin_name]
        
        if plugin_instance.state in [PluginState.UNLOADING, PluginState.UNLOADED]:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is already unloading or unloaded"
            }
        
        try:
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.UNLOADING)
            
            # Emit unloading started event
            await self._emit_lifecycle_event(
                LifecycleEvent.UNLOADING_STARTED,
                plugin_name=plugin_name
            )
            
            # Cleanup plugin instance
            if plugin_instance.instance:
                await plugin_instance.instance.cleanup()
                plugin_instance.instance = None
            
            # Update state
            await self._update_plugin_state(plugin_name, PluginState.UNLOADED)
            
            # Emit unloading completed event
            await self._emit_lifecycle_event(
                LifecycleEvent.UNLOADING_COMPLETED,
                plugin_name=plugin_name
            )
            
            return {
                "success": True,
                "plugin_name": plugin_name
            }
            
        except Exception as e:
            await self._update_plugin_state(plugin_name, PluginState.ERROR)
            return {
                "success": False,
                "error": f"Plugin unloading failed: {e}"
            }
    
    async def unload_all_plugins(self) -> Dict[str, Any]:
        """Unload all plugins"""
        results = {}
        
        for plugin_name in list(self.plugins.keys()):
            result = await self.unload_plugin(plugin_name)
            results[plugin_name] = result
        
        return {
            "success": True,
            "results": results,
            "total_unloaded": len([r for r in results.values() if r["success"]])
        }
    
    async def _update_plugin_state(self, plugin_name: str, new_state: PluginState):
        """Update plugin state and metrics"""
        old_state = self.plugins[plugin_name].state
        self.plugins[plugin_name].state = new_state
        self.plugin_states[plugin_name] = new_state
        
        # Update metrics
        self._update_state_metrics()
        
        self.logger.debug(f"Plugin {plugin_name} state: {old_state.value} -> {new_state.value}")
    
    def _update_state_metrics(self):
        """Update state-based metrics"""
        self.metrics.active_plugins = len([
            p for p in self.plugins.values() if p.state == PluginState.ACTIVE
        ])
        self.metrics.error_plugins = len([
            p for p in self.plugins.values() if p.state == PluginState.ERROR
        ])
    
    def _update_load_time_metrics(self, load_time: float):
        """Update load time metrics"""
        if self.metrics.total_plugins == 0:
            self.metrics.average_load_time = load_time
        else:
            self.metrics.average_load_time = (
                (self.metrics.average_load_time * (self.metrics.total_plugins - 1) + load_time) /
                self.metrics.total_plugins
            )
    
    async def _emit_lifecycle_event(self, event: LifecycleEvent, **kwargs):
        """Emit lifecycle event"""
        event_data = {
            "event": event.value,
            "timestamp": time.time(),
            **kwargs
        }
        
        self.lifecycle_events.append(event_data)
        
        # Call event handlers
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    await handler(event_data)
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")
    
    async def _load_plugin_manifest(self, plugin_path: Path) -> Optional[PluginManifest]:
        """Load plugin manifest from path"""
        manifest_path = plugin_path / "plugin.yaml"
        
        if not manifest_path.exists():
            return None
        
        try:
            with open(manifest_path, 'r') as f:
                import yaml
                manifest_data = yaml.safe_load(f)
            
            return PluginManifest(
                name=manifest_data["name"],
                version=manifest_data["version"],
                description=manifest_data["description"],
                author=manifest_data.get("author", "Unknown"),
                security_level=SecurityLevel(manifest_data.get("security_level", "sandboxed")),
                integration_type=IntegrationType(manifest_data.get("integration_type", "wrapper")),
                required_permissions=[PermissionLevel(p) for p in manifest_data.get("required_permissions", ["medium"])],
                dependencies=manifest_data.get("dependencies", []),
                entry_points=manifest_data.get("entry_points", {}),
                security_policies={}
            )
        except Exception as e:
            self.logger.error(f"Error loading manifest from {manifest_path}: {e}")
            return None
    
    def _create_plugin_instance(self, manifest: PluginManifest) -> VoiceOSPluginInterface:
        """Create plugin instance (simplified)"""
        # In real implementation, this would create the actual plugin instance
        class ManifestOnlyPlugin(VoiceOSPluginInterface):
            """Placeholder when a plugin entry has no loadable implementation."""

            def __init__(self, manifest: PluginManifest):
                self.manifest = manifest

            def get_manifest(self) -> PluginManifest:
                return self.manifest

            async def initialize(self, voiceos_context: Dict[str, Any]) -> bool:
                return True

            async def execute_operation(self, operation: str, params: Dict[str, Any],
                                      security_policy: SecurityPolicy) -> Dict[str, Any]:
                return {
                    "success": False,
                    "error": f"Plugin {self.manifest.name} has no executable implementation loaded",
                }

            async def cleanup(self) -> None:
                pass

        return ManifestOnlyPlugin(manifest)
    
    async def _health_monitor(self):
        """Monitor plugin health"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_plugin_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    async def _check_plugin_health(self):
        """Check health of active plugins"""
        current_time = time.time()
        
        for plugin_name, plugin_instance in self.plugins.items():
            if plugin_instance.state == PluginState.ACTIVE:
                # Check for inactivity
                inactive_time = current_time - plugin_instance.last_activity
                if inactive_time > 300:  # 5 minutes
                    self.logger.warning(f"Plugin {plugin_name} inactive for {inactive_time:.1f}s")
                
                # Check error count
                if plugin_instance.error_count >= self.max_error_count:
                    await self.suspend_plugin(plugin_name, "High error count")
    
    def register_event_handler(self, event: LifecycleEvent, handler: Callable):
        """Register lifecycle event handler"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def get_lifecycle_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics"""
        return self.metrics
    
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed plugin status"""
        if plugin_name not in self.plugins:
            return None
        
        plugin_instance = self.plugins[plugin_name]
        
        return {
            "name": plugin_instance.manifest.name,
            "version": plugin_instance.manifest.version,
            "state": plugin_instance.state.value,
            "load_time": plugin_instance.load_time,
            "last_activity": plugin_instance.last_activity,
            "error_count": plugin_instance.error_count,
            "execution_count": plugin_instance.execution_count,
            "security_violations": plugin_instance.security_violations,
            "metadata": plugin_instance.metadata
        }
    
    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all plugins"""
        return {
            name: self.get_plugin_status(name)
            for name in self.plugins.keys()
        }


# Global lifecycle manager instance
lifecycle_manager = None

def get_lifecycle_manager() -> PluginLifecycleManager:
    """Get or create lifecycle manager instance"""
    global lifecycle_manager
    if lifecycle_manager is None:
        lifecycle_manager = PluginLifecycleManager(config.project_root / "workspace")
    return lifecycle_manager
