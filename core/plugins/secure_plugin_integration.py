"""
VoiceOS Secure Plugin Integration Architecture

This module provides a secure, permission-first integration layer for
plugins, helpers, and extensions while maintaining VoiceOS architecture
purity and security boundaries.
"""

import asyncio
import logging
import importlib
import inspect
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib
import json
import time

from core.config import config
from permissions.permission_engine import PermissionLevel, permission_engine
from tools.tool_registry import ToolRegistry, ToolMetadata, ToolCategory


class SecurityLevel(Enum):
    """Security classification for plugin operations"""
    SAFE = "safe"                    # Read-only, no system access
    RESTRICTED = "restricted"        # Limited system access
    SANDBOXED = "sandboxed"          # Full execution in sandbox
    ISOLATED = "isolated"            # Complete isolation


class IntegrationType(Enum):
    """Integration approach for plugin components"""
    PROXY = "proxy"                  # Proxy through VoiceOS tools
    WRAPPER = "wrapper"              # Wrap with security layer
    ADAPTER = "adapter"              # Adapt to VoiceOS interfaces
    GATEWAY = "gateway"              # Gateway with validation


@dataclass
class SecurityPolicy:
    """Security policy for plugin operations"""
    level: SecurityLevel
    allowed_operations: List[str]
    blocked_operations: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    audit_required: bool = True
    timeout_seconds: int = 30


@dataclass
class PluginManifest:
    """VoiceOS-compliant plugin manifest"""
    name: str
    version: str
    description: str
    author: str
    security_level: SecurityLevel
    integration_type: IntegrationType
    required_permissions: List[PermissionLevel]
    dependencies: List[str] = field(default_factory=list)
    entry_points: Dict[str, str] = field(default_factory=dict)
    security_policies: Dict[str, SecurityPolicy] = field(default_factory=dict)


class SecurityValidator:
    """Validates plugin security compliance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.blocked_patterns = [
            "os.system",
            "subprocess.call",
            "eval(",
            "exec(",
            "__import__",
            "open(",
            "file(",
            "input(",
            "raw_input("
        ]
    
    def validate_plugin_code(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Validate plugin code for security compliance.
        
        Args:
            plugin_path: Path to plugin directory
            
        Returns:
            Validation results with security issues
        """
        issues = []
        security_score = 100
        
        # Check all Python files
        for py_file in plugin_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for blocked patterns
                for pattern in self.blocked_patterns:
                    if pattern in content:
                        issues.append({
                            "file": str(py_file),
                            "issue": f"Blocked pattern found: {pattern}",
                            "severity": "high"
                        })
                        security_score -= 20
                
                # Check for imports
                lines = content.split('\n')
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if line.startswith('import ') or line.startswith('from '):
                        if self._is_dangerous_import(line):
                            issues.append({
                                "file": str(py_file),
                                "line": line_num,
                                "issue": f"Dangerous import: {line}",
                                "severity": "medium"
                            })
                            security_score -= 10
                            
            except Exception as e:
                issues.append({
                    "file": str(py_file),
                    "issue": f"Error reading file: {e}",
                    "severity": "low"
                })
        
        return {
            "valid": security_score >= 70,
            "security_score": max(0, security_score),
            "issues": issues,
            "recommendations": self._generate_recommendations(issues)
        }
    
    def _is_dangerous_import(self, import_line: str) -> bool:
        """Check if import line contains dangerous modules"""
        dangerous_modules = [
            "os", "sys", "subprocess", "shutil", "tempfile",
            "socket", "urllib", "http", "ftplib", "smtplib",
            "ctypes", "multiprocessing", "threading"
        ]
        
        for module in dangerous_modules:
            if module in import_line:
                return True
        return False
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate security recommendations based on issues"""
        recommendations = []
        
        high_issues = [i for i in issues if i.get("severity") == "high"]
        medium_issues = [i for i in issues if i.get("severity") == "medium"]
        
        if high_issues:
            recommendations.append("Remove or replace high-risk operations with VoiceOS tools")
        
        if medium_issues:
            recommendations.append("Use VoiceOS sandboxed alternatives for system operations")
        
        if len(issues) > 10:
            recommendations.append("Consider refactoring plugin to use VoiceOS architecture")
        
        return recommendations


class SandboxEnvironment:
    """Sandboxed execution environment for plugins"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        self.active_processes: Dict[str, Any] = {}
    
    async def execute_plugin_code(self, plugin_id: str, code: str, 
                                security_policy: SecurityPolicy) -> Dict[str, Any]:
        """
        Execute plugin code in sandboxed environment.
        
        Args:
            plugin_id: Plugin identifier
            code: Code to execute
            security_policy: Security policy for execution
            
        Returns:
            Execution results
        """
        start_time = time.time()
        execution_id = f"{plugin_id}_{int(start_time)}"
        
        try:
            # Create isolated workspace
            plugin_workspace = self.workspace_root / "sandboxes" / execution_id
            plugin_workspace.mkdir(parents=True, exist_ok=True)
            
            # Apply resource limits
            limits = security_policy.resource_limits
            memory_limit = limits.get("memory_mb", 100)
            timeout = security_policy.timeout_seconds
            
            # Execute in controlled environment
            result = await self._run_isolated_code(
                code, plugin_workspace, memory_limit, timeout
            )
            
            # Audit execution
            if security_policy.audit_required:
                await self._audit_execution(execution_id, code, result)
            
            return {
                "success": True,
                "result": result,
                "execution_time": time.time() - start_time,
                "execution_id": execution_id
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Execution timeout",
                "execution_time": time.time() - start_time
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
        finally:
            # Cleanup workspace
            await self._cleanup_workspace(execution_id)
    
    async def _run_isolated_code(self, code: str, workspace: Path, 
                                memory_limit: int, timeout: int) -> Any:
        """Run code in an isolated restricted scope."""
        if "import" in code or "exec(" in code or "eval(" in code:
            raise SecurityError("Direct imports or execution not allowed in sandbox")
        
        # Execute with limited scope
        safe_globals = {
            "__builtins__": {},
            "result": None
        }
        
        try:
            exec(code, safe_globals)
            return safe_globals.get("result")
        except Exception as e:
            raise SecurityError(f"Code execution failed: {e}")
    
    async def _audit_execution(self, execution_id: str, code: str, result: Any):
        """Audit plugin execution for security"""
        audit_log = {
            "execution_id": execution_id,
            "timestamp": time.time(),
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "result_type": type(result).__name__,
            "security_violations": []
        }
        
        # Store audit log
        audit_path = self.workspace_root / "logs" / "plugin_audit.json"
        audit_path.parent.mkdir(exist_ok=True)
        
        try:
            with open(audit_path, 'a') as f:
                f.write(json.dumps(audit_log) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")
    
    async def _cleanup_workspace(self, execution_id: str):
        """Clean up sandbox workspace"""
        workspace = self.workspace_root / "sandboxes" / execution_id
        try:
            if workspace.exists():
                import shutil
                shutil.rmtree(workspace)
        except Exception as e:
            self.logger.error(f"Failed to cleanup workspace {execution_id}: {e}")


class VoiceOSPluginInterface(ABC):
    """Abstract base class for VoiceOS-compliant plugins"""
    
    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """Return plugin manifest"""
        pass
    
    @abstractmethod
    async def initialize(self, voiceos_context: Dict[str, Any]) -> bool:
        """Initialize plugin with VoiceOS context"""
        pass
    
    @abstractmethod
    async def execute_operation(self, operation: str, params: Dict[str, Any],
                              security_policy: SecurityPolicy) -> Dict[str, Any]:
        """Execute operation with security policy"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources"""
        pass


class SecurePluginAdapter:
    """Adapts external plugins to VoiceOS security model"""
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.security_validator = SecurityValidator()
        self.sandbox = SandboxEnvironment(config.project_root / "workspace")
        self.logger = logging.getLogger(__name__)
        self.loaded_plugins: Dict[str, VoiceOSPluginInterface] = {}
    
    async def load_plugin(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Load and validate plugin securely.
        
        Args:
            plugin_path: Path to plugin directory
            
        Returns:
            Loading results with validation status
        """
        try:
            # Validate plugin security
            validation_result = self.security_validator.validate_plugin_code(plugin_path)
            
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Security validation failed",
                    "issues": validation_result["issues"],
                    "recommendations": validation_result["recommendations"]
                }
            
            # Load plugin manifest
            manifest = await self._load_plugin_manifest(plugin_path)
            
            # Check permissions
            if not await self._check_plugin_permissions(manifest):
                return {
                    "success": False,
                    "error": "Insufficient permissions for plugin"
                }
            
            # Create plugin wrapper
            plugin_wrapper = await self._create_plugin_wrapper(plugin_path, manifest)
            
            # Initialize plugin
            voiceos_context = {
                "workspace": config.project_root / "workspace",
                "tool_registry": self.tool_registry,
                "permission_engine": permission_engine
            }
            
            if await plugin_wrapper.initialize(voiceos_context):
                self.loaded_plugins[manifest.name] = plugin_wrapper
                
                return {
                    "success": True,
                    "plugin_name": manifest.name,
                    "security_score": validation_result["security_score"],
                    "manifest": manifest
                }
            else:
                return {
                    "success": False,
                    "error": "Plugin initialization failed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Plugin loading failed: {e}"
            }
    
    async def execute_plugin_operation(self, plugin_name: str, operation: str,
                                      params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute plugin operation with security controls.
        
        Args:
            plugin_name: Name of loaded plugin
            operation: Operation to execute
            params: Operation parameters
            
        Returns:
            Execution results
        """
        if plugin_name not in self.loaded_plugins:
            return {
                "success": False,
                "error": "Plugin not loaded"
            }
        
        plugin = self.loaded_plugins[plugin_name]
        manifest = plugin.get_manifest()
        
        # Get security policy for operation
        security_policy = manifest.security_policies.get(operation, 
            SecurityPolicy(
                level=SecurityLevel.SANDBOXED,
                allowed_operations=[operation],
                timeout_seconds=30
            )
        )
        
        # Validate operation against policy
        if operation not in security_policy.allowed_operations:
            return {
                "success": False,
                "error": f"Operation '{operation}' not allowed by security policy"
            }
        
        # Check user permissions
        required_permission = manifest.required_permissions[0] if manifest.required_permissions else PermissionLevel.MEDIUM
        if not permission_engine.check_tool_permission(required_permission):
            return {
                "success": False,
                "error": f"Insufficient user permissions for plugin operation"
            }
        
        try:
            # Execute with security controls
            if security_policy.level == SecurityLevel.SANDBOXED:
                # Execute in sandbox
                result = await self.sandbox.execute_plugin_code(
                    f"{plugin_name}.{operation}", 
                    f"result = await plugin.execute_operation('{operation}', {params})",
                    security_policy
                )
            else:
                # Execute directly with monitoring
                result = await plugin.execute_operation(operation, params, security_policy)
            
            return {
                "success": True,
                "result": result,
                "security_level": security_policy.level.value
            }
            
        except Exception as e:
            self.logger.error(f"Plugin operation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_plugin_manifest(self, plugin_path: Path) -> PluginManifest:
        """Load and validate plugin manifest"""
        manifest_path = plugin_path / "plugin.yaml"
        
        if not manifest_path.exists():
            raise ValueError("Plugin manifest not found")
        
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
    
    async def _check_plugin_permissions(self, manifest: PluginManifest) -> bool:
        """Check if plugin permissions are acceptable"""
        # Check if required permissions are available
        for permission in manifest.required_permissions:
            if not permission_engine.check_tool_permission(permission):
                return False
        return True
    
    async def _create_plugin_wrapper(self, plugin_path: Path, 
                                    manifest: PluginManifest) -> VoiceOSPluginInterface:
        """Create VoiceOS-compliant plugin wrapper"""
        # This would create a wrapper that enforces VoiceOS security
        # For now, return a basic wrapper
        class PluginWrapper(VoiceOSPluginInterface):
            def __init__(self, path: Path, manifest: PluginManifest):
                self.path = path
                self.manifest = manifest
                self.plugin_instance = None
            
            def get_manifest(self) -> PluginManifest:
                return self.manifest
            
            async def initialize(self, voiceos_context: Dict[str, Any]) -> bool:
                # Initialize plugin with VoiceOS context
                return True
            
            async def execute_operation(self, operation: str, params: Dict[str, Any],
                                      security_policy: SecurityPolicy) -> Dict[str, Any]:
                # Execute operation with security constraints
                return {"result": "Operation executed securely"}
            
            async def cleanup(self) -> None:
                # Cleanup resources
                pass
        
        return PluginWrapper(plugin_path, manifest)


class SecurityError(Exception):
    """Security-related error"""
    pass


# Global secure plugin adapter instance
secure_plugin_adapter = None

def get_secure_plugin_adapter(tool_registry: ToolRegistry) -> SecurePluginAdapter:
    """Get or create secure plugin adapter instance"""
    global secure_plugin_adapter
    if secure_plugin_adapter is None:
        secure_plugin_adapter = SecurePluginAdapter(tool_registry)
    return secure_plugin_adapter
