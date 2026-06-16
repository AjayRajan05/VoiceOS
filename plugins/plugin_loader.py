"""
Plugin Loader - Dynamic loading and management of VoiceOS bundled plugins.
Enforces permission levels and safe import boundaries.
"""

import os
import yaml
import logging
import importlib
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass

from core.config import config
from permissions.permission_engine import PermissionLevel


@dataclass
class PluginInfo:
    """Plugin metadata structure"""
    name: str
    version: str
    description: str
    author: str
    permission_level: PermissionLevel
    entry_point: str
    dependencies: List[str]
    enabled: bool = True


class PluginLoader:
    """Safe plugin loader that validates and manages VoiceOS bundled plugins."""
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else config.project_root / "workspace"
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Plugin directories
        self.plugin_dirs = [
            self.workspace_root / "plugins",
            Path("agent-zero-main/agent-zero-main/plugins"),
            Path("plugins")
        ]
        
        # Loaded plugins registry
        self.loaded_plugins: Dict[str, PluginInfo] = {}
        self.plugin_instances: Dict[str, Any] = {}
        
    def _validate_plugin_config(self, config_path: Path) -> PluginInfo:
        """Validate plugin configuration file"""
        try:
            if not config_path.exists():
                raise FileNotFoundError(f"Plugin config not found: {config_path}")
            
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Required fields
            required_fields = ['name', 'version', 'description', 'author', 'permission_level', 'entry_point']
            for field in required_fields:
                if field not in config_data:
                    raise ValueError(f"Missing required field in plugin config: {field}")
            
            # Validate permission level
            permission_str = config_data['permission_level'].upper()
            try:
                permission_level = PermissionLevel[permission_str]
            except KeyError:
                raise ValueError(f"Invalid permission level: {permission_str}")
            
            # Validate entry point
            entry_point = config_data['entry_point']
            if not entry_point or not isinstance(entry_point, str):
                raise ValueError("Invalid entry point")
            
            # Validate dependencies
            dependencies = config_data.get('dependencies', [])
            if not isinstance(dependencies, list):
                raise ValueError("Dependencies must be a list")
            
            plugin_info = PluginInfo(
                name=config_data['name'],
                version=config_data['version'],
                description=config_data['description'],
                author=config_data['author'],
                permission_level=permission_level,
                entry_point=entry_point,
                dependencies=dependencies,
                enabled=config_data.get('enabled', True)
            )
            
            return plugin_info
            
        except Exception as e:
            self.logger.error(f"Plugin config validation failed for {config_path}: {e}")
            raise ValueError(f"Invalid plugin config: {e}")
    
    def _validate_plugin_code(self, plugin_path: Path) -> bool:
        """Validate plugin code for security"""
        try:
            # Check for dangerous patterns
            dangerous_patterns = [
                'import os.system',
                'subprocess.call',
                'eval(',
                'exec(',
                '__import__',
                'open(',
                'file(',
                'input(',
                'raw_input(',
                'rm -rf',
                'sudo',
                'chmod',
                'chown',
                'system(',
                'popen(',
            ]
            
            # Check Python files
            for py_file in plugin_path.rglob('*.py'):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    content_lower = content.lower()
                    for pattern in dangerous_patterns:
                        if pattern in content_lower:
                            self.logger.warning(f"Dangerous pattern found in {py_file}: {pattern}")
                            return False
                            
                except Exception as e:
                    self.logger.warning(f"Could not read {py_file}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Plugin code validation failed for {plugin_path}: {e}")
            return False
    
    def _log_operation(self, operation: str, plugin_name: str, result: Any, error: Optional[str] = None):
        """Log all plugin operations"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "plugin_name": plugin_name,
            "result": str(result)[:200],  # Truncate long results
            "error": error
        }
        
        log_file = self.workspace_root / "logs" / "plugin_operations.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")
    
    def discover_plugins(self) -> List[PluginInfo]:
        """Discover available plugins in plugin directories"""
        discovered_plugins = []
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            
            for plugin_path in plugin_dir.iterdir():
                if not plugin_path.is_dir():
                    continue
                
                config_file = plugin_path / "plugin.yaml"
                if not config_file.exists():
                    continue
                
                try:
                    plugin_info = self._validate_plugin_config(config_file)
                    
                    # Validate plugin code
                    if self._validate_plugin_code(plugin_path):
                        discovered_plugins.append(plugin_info)
                        self.logger.info(f"Discovered plugin: {plugin_info.name}")
                    else:
                        self.logger.warning(f"Plugin {plugin_info.name} failed code validation")
                        
                except Exception as e:
                    self.logger.error(f"Failed to load plugin config from {config_file}: {e}")
        
        return discovered_plugins
    
    def load_plugin(self, plugin_info: PluginInfo) -> bool:
        """Load a specific plugin"""
        try:
            if plugin_info.name in self.loaded_plugins:
                self.logger.warning(f"Plugin {plugin_info.name} already loaded")
                return True
            
            # Find plugin directory
            plugin_dir = None
            for search_dir in self.plugin_dirs:
                potential_dir = search_dir / plugin_info.name
                if potential_dir.exists():
                    plugin_dir = potential_dir
                    break
            
            if not plugin_dir:
                raise FileNotFoundError(f"Plugin directory not found for {plugin_info.name}")
            
            # Add plugin directory to Python path
            plugin_path = str(plugin_dir.parent)
            if plugin_path not in os.sys.path:
                os.sys.path.insert(0, plugin_path)
            
            # Import plugin module
            module_name = plugin_info.entry_point.replace('.py', '').replace('/', '.')
            plugin_module = importlib.import_module(module_name)
            
            # Get plugin class (expecting 'Plugin' class)
            if not hasattr(plugin_module, 'Plugin'):
                raise AttributeError(f"Plugin {plugin_info.name} missing 'Plugin' class")
            
            plugin_class = getattr(plugin_module, 'Plugin')
            plugin_instance = plugin_class()
            
            # Store plugin info and instance
            self.loaded_plugins[plugin_info.name] = plugin_info
            self.plugin_instances[plugin_info.name] = plugin_instance
            
            self._log_operation("load_plugin", plugin_info.name, "success")
            self.logger.info(f"Successfully loaded plugin: {plugin_info.name}")
            return True
            
        except Exception as e:
            self._log_operation("load_plugin", plugin_info.name, "failed", str(e))
            self.logger.error(f"Failed to load plugin {plugin_info.name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin"""
        try:
            if plugin_name not in self.loaded_plugins:
                self.logger.warning(f"Plugin {plugin_name} not loaded")
                return True
            
            # Remove from registry
            del self.loaded_plugins[plugin_name]
            if plugin_name in self.plugin_instances:
                del self.plugin_instances[plugin_name]
            
            self._log_operation("unload_plugin", plugin_name, "success")
            self.logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self._log_operation("unload_plugin", plugin_name, "failed", str(e))
            self.logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """Get loaded plugin instance"""
        return self.plugin_instances.get(plugin_name)
    
    def list_plugins(self) -> Dict[str, PluginInfo]:
        """List all loaded plugins"""
        return self.loaded_plugins.copy()
    
    def initialize_plugins(self) -> int:
        """Initialize all discovered plugins"""
        discovered_plugins = self.discover_plugins()
        loaded_count = 0
        
        for plugin_info in discovered_plugins:
            if plugin_info.enabled:
                if self.load_plugin(plugin_info):
                    loaded_count += 1
        
        self.logger.info(f"Initialized {loaded_count} out of {len(discovered_plugins)} discovered plugins")
        return loaded_count
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a specific plugin"""
        try:
            # Unload first
            self.unload_plugin(plugin_name)
            
            # Rediscover and reload
            discovered_plugins = self.discover_plugins()
            for plugin_info in discovered_plugins:
                if plugin_info.name == plugin_name:
                    return self.load_plugin(plugin_info)
            
            raise ValueError(f"Plugin {plugin_name} not found during rediscovery")
            
        except Exception as e:
            self.logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            return False


# Global plugin loader instance
plugin_loader = PluginLoader()
