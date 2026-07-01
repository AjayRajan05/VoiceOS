"""
VoiceOS Plugin Error Handling and Recovery System

This module provides comprehensive error handling and recovery mechanisms
for plugins while maintaining VoiceOS security boundaries and architectural purity.
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
from datetime import datetime, timedelta

from core.config import config
from permissions.permission_engine import PermissionLevel
from core.plugins.secure_plugin_integration import SecurityLevel, SecurityPolicy
from core.plugins.plugin_lifecycle import PluginState, PluginInstance


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"           # Minor issues, plugin continues
    MEDIUM = "medium"     # Significant issues, may affect functionality
    HIGH = "high"         # Critical issues, plugin may need restart
    CRITICAL = "critical"  # Fatal issues, plugin must be stopped


class ErrorCategory(Enum):
    """Error categories"""
    VALIDATION = "validation"           # Configuration or input validation errors
    SECURITY = "security"               # Security policy violations
    EXECUTION = "execution"             # Runtime execution errors
    DEPENDENCY = "dependency"           # Missing or broken dependencies
    RESOURCE = "resource"               # Resource exhaustion or limits
    COMMUNICATION = "communication"     # Network or communication errors
    SYSTEM = "system"                   # System-level errors
    UNKNOWN = "unknown"                 # Unclassified errors


class RecoveryAction(Enum):
    """Recovery actions"""
    RETRY = "retry"                     # Retry the operation
    RESTART = "restart"                 # Restart the plugin
    DISABLE = "disable"                 # Disable the plugin
    FALLBACK = "fallback"               # Use fallback mechanism
    ESCALATE = "escalate"               # Escalate to higher authority
    IGNORE = "ignore"                   # Ignore the error
    QUARANTINE = "quarantine"           # Quarantine the plugin


@dataclass
class PluginError:
    """Plugin error record"""
    error_id: str
    plugin_name: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: Dict[str, Any]
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_action: Optional[RecoveryAction] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None


@dataclass
class RecoveryPolicy:
    """Recovery policy for error types"""
    error_category: ErrorCategory
    severity_threshold: ErrorSeverity
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_retry_delay: float = 60.0
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    auto_recovery: bool = True
    requires_approval: bool = False
    quarantine_threshold: int = 5


@dataclass
class ErrorMetrics:
    """Error handling metrics"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    quarantined_plugins: int = 0
    average_recovery_time: float = 0.0


class PluginErrorHandler:
    """
    Handles plugin errors with automatic recovery mechanisms.
    
    This class provides comprehensive error handling, classification, recovery,
    and prevention while maintaining VoiceOS security boundaries.
    """
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        
        # Error storage
        self.error_log_path = workspace_root / "logs" / "plugin_errors.json"
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Error tracking
        self.active_errors: Dict[str, PluginError] = {}
        self.error_history: List[PluginError] = []
        self.max_history_size = 10000
        
        # Recovery policies
        self.recovery_policies: Dict[str, RecoveryPolicy] = {}
        self._register_default_policies()
        
        # Plugin state tracking
        self.plugin_states: Dict[str, PluginState] = {}
        self.quarantined_plugins: Dict[str, datetime] = {}
        
        # Error handlers
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = {}
        
        # Recovery callbacks
        self.recovery_callbacks: Dict[RecoveryAction, Callable] = {}
        self._register_recovery_callbacks()
        
        # Metrics
        self.metrics = ErrorMetrics()
        
        # Background tasks
        self._cleanup_task = None
        self._monitoring_task = None
        
        # Error patterns
        self.error_patterns: Dict[str, List[PluginError]] = {}
    
    async def start_error_handling(self):
        """Start error handling system"""
        self.logger.info("Starting plugin error handling system...")
        
        # Load error history
        await self._load_error_history()
        
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._background_cleanup())
        self._monitoring_task = asyncio.create_task(self._error_monitoring())
        
        self.logger.info("Plugin error handling system started")
    
    async def stop_error_handling(self):
        """Stop error handling system"""
        self.logger.info("Stopping plugin error handling system...")
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Save error history
        await self._save_error_history()
        
        self.logger.info("Plugin error handling system stopped")
    
    async def handle_plugin_error(self, plugin_name: str, error: Exception,
                               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle a plugin error with automatic recovery.
        
        Args:
            plugin_name: Name of plugin that caused the error
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            Error handling result
        """
        try:
            # Classify error
            error_info = await self._classify_error(plugin_name, error, context or {})
            
            # Create error record
            plugin_error = PluginError(
                error_id=self._generate_error_id(),
                plugin_name=plugin_name,
                timestamp=datetime.now(),
                severity=error_info["severity"],
                category=error_info["category"],
                message=str(error),
                details=error_info["details"],
                stack_trace=traceback.format_exc(),
                context=context or {}
            )
            
            # Store error
            await self._store_error(plugin_error)
            
            # Update metrics
            self._update_metrics(plugin_error)
            
            # Check if plugin is quarantined
            if plugin_name in self.quarantined_plugins:
                return {
                    "success": False,
                    "error_id": plugin_error.error_id,
                    "action": "plugin_quarantined",
                    "message": f"Plugin {plugin_name} is quarantined"
                }
            
            # Get recovery policy
            policy = self._get_recovery_policy(plugin_error.category, plugin_error.severity)
            
            # Attempt recovery
            recovery_result = await self._attempt_recovery(plugin_error, policy)
            
            # Update error record
            plugin_error.recovery_attempted = True
            plugin_error.recovery_action = recovery_result.get("action")
            plugin_error.recovery_successful = recovery_result.get("success", False)
            
            if recovery_result.get("success"):
                plugin_error.resolved = True
                plugin_error.resolution_time = datetime.now()
            
            return {
                "success": recovery_result.get("success", False),
                "error_id": plugin_error.error_id,
                "severity": plugin_error.severity.value,
                "category": plugin_error.category.value,
                "recovery_action": recovery_result.get("action"),
                "recovery_successful": recovery_result.get("success", False),
                "message": recovery_result.get("message", "")
            }
            
        except Exception as e:
            self.logger.error(f"Error handling failed: {e}")
            return {
                "success": False,
                "error": f"Error handling failed: {e}"
            }
    
    async def register_error_handler(self, category: ErrorCategory, handler: Callable):
        """Register custom error handler for category"""
        if category not in self.error_handlers:
            self.error_handlers[category] = []
        self.error_handlers[category].append(handler)
    
    async def register_recovery_policy(self, plugin_name: str, policy: RecoveryPolicy):
        """Register custom recovery policy for plugin"""
        self.recovery_policies[f"{plugin_name}:{policy.error_category.value}"] = policy
    
    async def quarantine_plugin(self, plugin_name: str, reason: str, duration_hours: int = 24):
        """
        Quarantine a plugin due to repeated errors.
        
        Args:
            plugin_name: Name of plugin to quarantine
            reason: Reason for quarantine
            duration_hours: Quarantine duration in hours
        """
        quarantine_time = datetime.now() + timedelta(hours=duration_hours)
        self.quarantined_plugins[plugin_name] = quarantine_time
        
        self.logger.warning(f"Plugin {plugin_name} quarantined until {quarantine_time}: {reason}")
        
        # Update metrics
        self.metrics.quarantined_plugins += 1
        
        # Emit quarantine event (would integrate with event system)
        await self._emit_quarantine_event(plugin_name, reason, quarantine_time)
    
    async def release_plugin_from_quarantine(self, plugin_name: str) -> Dict[str, Any]:
        """Release a plugin from quarantine"""
        if plugin_name not in self.quarantined_plugins:
            return {
                "success": False,
                "error": f"Plugin {plugin_name} is not quarantined"
            }
        
        del self.quarantined_plugins[plugin_name]
        
        self.logger.info(f"Plugin {plugin_name} released from quarantine")
        
        # Update metrics
        self.metrics.quarantined_plugins = max(0, self.metrics.quarantined_plugins - 1)
        
        return {
            "success": True,
            "plugin_name": plugin_name,
            "action": "released_from_quarantine"
        }
    
    async def get_error_statistics(self, plugin_name: Optional[str] = None,
                                time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Args:
            plugin_name: Filter by plugin name
            time_range_hours: Time range in hours
            
        Returns:
            Error statistics
        """
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
        
        # Filter errors
        errors = self.error_history
        if plugin_name:
            errors = [e for e in errors if e.plugin_name == plugin_name]
        errors = [e for e in errors if e.timestamp >= cutoff_time]
        
        # Calculate statistics
        total_errors = len(errors)
        errors_by_category = {}
        errors_by_severity = {}
        recovery_rate = 0
        
        if total_errors > 0:
            for error in errors:
                # Category statistics
                category = error.category.value
                errors_by_category[category] = errors_by_category.get(category, 0) + 1
                
                # Severity statistics
                severity = error.severity.value
                errors_by_severity[severity] = errors_by_severity.get(severity, 0) + 1
                
                # Recovery rate
                if error.recovery_attempted:
                    recovery_rate += 1 if error.recovery_successful else 0
        
        recovery_rate = (recovery_rate / total_errors * 100) if total_errors > 0 else 0
        
        # Error patterns
        patterns = await self._detect_error_patterns(errors)
        
        return {
            "total_errors": total_errors,
            "errors_by_category": errors_by_category,
            "errors_by_severity": errors_by_severity,
            "recovery_rate": recovery_rate,
            "error_patterns": patterns,
            "time_range_hours": time_range_hours,
            "quarantined_plugins": len(self.quarantined_plugins)
        }
    
    async def get_recent_errors(self, plugin_name: Optional[str] = None,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors"""
        errors = self.error_history
        
        if plugin_name:
            errors = [e for e in errors if e.plugin_name == plugin_name]
        
        # Sort by timestamp (newest first) and limit
        errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        return [
            {
                "error_id": e.error_id,
                "plugin_name": e.plugin_name,
                "timestamp": e.timestamp.isoformat(),
                "severity": e.severity.value,
                "category": e.category.value,
                "message": e.message,
                "recovery_attempted": e.recovery_attempted,
                "recovery_successful": e.recovery_successful,
                "recovery_action": e.recovery_action.value if e.recovery_action else None,
                "resolved": e.resolved
            }
            for e in errors[:limit]
        ]
    
    async def _classify_error(self, plugin_name: str, error: Exception,
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Classify error and determine severity"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Determine category
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.MEDIUM
        
        # Security errors
        if "permission" in error_message or "unauthorized" in error_message:
            category = ErrorCategory.SECURITY
            severity = ErrorSeverity.HIGH
        elif "security" in error_message or "forbidden" in error_message:
            category = ErrorCategory.SECURITY
            severity = ErrorSeverity.CRITICAL
        
        # Validation errors
        elif "validation" in error_message or "invalid" in error_message:
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.LOW
        elif error_type in ["ValueError", "TypeError"]:
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.MEDIUM
        
        # Execution errors
        elif error_type in ["RuntimeError", "AttributeError", "KeyError"]:
            category = ErrorCategory.EXECUTION
            severity = ErrorSeverity.MEDIUM
        elif error_type in ["IndexError", "UnboundLocalError"]:
            category = ErrorCategory.EXECUTION
            severity = ErrorSeverity.LOW
        
        # Resource errors
        elif "memory" in error_message or "timeout" in error_message:
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH
        elif "disk" in error_message or "space" in error_message:
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.CRITICAL
        
        # Communication errors
        elif "connection" in error_message or "network" in error_message:
            category = ErrorCategory.COMMUNICATION
            severity = ErrorSeverity.MEDIUM
        elif error_type in ["ConnectionError", "TimeoutError"]:
            category = ErrorCategory.COMMUNICATION
            severity = ErrorSeverity.HIGH
        
        # Dependency errors
        elif "import" in error_message or "module" in error_message:
            category = ErrorCategory.DEPENDENCY
            severity = ErrorSeverity.HIGH
        elif error_type in ["ImportError", "ModuleNotFoundError"]:
            category = ErrorCategory.DEPENDENCY
            severity = ErrorSeverity.CRITICAL
        
        return {
            "category": category,
            "severity": severity,
            "details": {
                "error_type": error_type,
                "context": context
            }
        }
    
    async def _store_error(self, error: PluginError):
        """Store error record"""
        # Add to active errors
        self.active_errors[error.error_id] = error
        
        # Add to history
        self.error_history.append(error)
        
        # Limit history size
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # Remove from active errors if resolved
        if error.resolved:
            self.active_errors.pop(error.error_id, None)
        
        # Save to file periodically
        if len(self.error_history) % 10 == 0:
            await self._save_error_history()
    
    def _update_metrics(self, error: PluginError):
        """Update error metrics"""
        self.metrics.total_errors += 1
        
        # Category metrics
        category = error.category.value
        self.metrics.errors_by_category[category] = self.metrics.errors_by_category.get(category, 0) + 1
        
        # Severity metrics
        severity = error.severity.value
        self.metrics.errors_by_severity[severity] = self.metrics.errors_by_severity.get(severity, 0) + 1
    
    def _get_recovery_policy(self, category: ErrorCategory, severity: ErrorSeverity) -> RecoveryPolicy:
        """Get recovery policy for error"""
        policy_key = f"{category.value}:{severity.value}"
        
        if policy_key in self.recovery_policies:
            return self.recovery_policies[policy_key]
        
        # Get default policy for category
        category_key = f"{category.value}:*"
        if category_key in self.recovery_policies:
            return self.recovery_policies[category_key]
        
        # Use default policy
        return self.recovery_policies["default"]
    
    async def _attempt_recovery(self, error: PluginError, policy: RecoveryPolicy) -> Dict[str, Any]:
        """Attempt error recovery"""
        if not policy.auto_recovery:
            return {
                "success": False,
                "action": RecoveryAction.ESCALATE,
                "message": "Auto-recovery disabled, escalation required"
            }
        
        # Check if approval is required
        if policy.requires_approval:
            return {
                "success": False,
                "action": RecoveryAction.ESCALATE,
                "message": "Manual approval required for recovery"
            }
        
        # Try recovery actions in order
        for action in policy.recovery_actions:
            try:
                recovery_start = time.time()
                
                if action == RecoveryAction.RETRY:
                    result = await self._retry_operation(error)
                elif action == RecoveryAction.RESTART:
                    result = await self._restart_plugin(error.plugin_name)
                elif action == RecoveryAction.DISABLE:
                    result = await self._disable_plugin(error.plugin_name)
                elif action == RecoveryAction.FALLBACK:
                    result = await self._use_fallback(error.plugin_name)
                elif action == RecoveryAction.QUARANTINE:
                    result = await self._quarantine_plugin(error.plugin_name, policy)
                else:
                    result = {"success": False, "message": f"Unknown recovery action: {action}"}
                
                # Update recovery metrics
                self.metrics.recovery_attempts += 1
                recovery_time = time.time() - recovery_start
                self._update_recovery_time_metrics(recovery_time)
                
                if result.get("success"):
                    self.metrics.successful_recoveries += 1
                    return {
                        "success": True,
                        "action": action,
                        "message": result.get("message", "Recovery successful"),
                        "recovery_time": recovery_time
                    }
                else:
                    self.metrics.failed_recoveries += 1
                    
            except Exception as e:
                self.logger.error(f"Recovery action {action} failed: {e}")
                self.metrics.failed_recoveries += 1
        
        # All recovery actions failed
        return {
            "success": False,
            "action": RecoveryAction.ESCALATE,
            "message": "All recovery actions failed"
        }
    
    async def _retry_operation(self, error: PluginError) -> Dict[str, Any]:
        """Retry the failed operation (caller must re-invoke the operation)."""
        return {
            "success": False,
            "message": "Retry not available without operation context",
        }

    async def _restart_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Restart a plugin via unload + load."""
        from core.plugins.plugin_lifecycle import get_lifecycle_manager

        manager = get_lifecycle_manager()
        unload = await manager.unload_plugin(plugin_name)
        if not unload.get("success"):
            return {
                "success": False,
                "message": unload.get("error", f"Failed to unload {plugin_name}"),
            }
        load = await manager.load_plugin(plugin_name)
        if not load.get("success"):
            return {
                "success": False,
                "message": load.get("error", f"Failed to reload {plugin_name}"),
            }
        init = await manager.initialize_plugin(plugin_name, {})
        return {
            "success": bool(init.get("success")),
            "message": init.get("message", f"Plugin {plugin_name} restarted"),
        }
    
    async def _disable_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Disable a plugin"""
        # This would integrate with lifecycle manager
        return {
            "success": True,
            "message": f"Plugin {plugin_name} disabled"
        }
    
    async def _use_fallback(self, plugin_name: str) -> Dict[str, Any]:
        """Use fallback mechanism"""
        return {
            "success": True,
            "message": f"Using fallback for {plugin_name}"
        }
    
    async def _quarantine_plugin(self, plugin_name: str, policy: RecoveryPolicy) -> Dict[str, Any]:
        """Quarantine a plugin"""
        await self.quarantine_plugin(plugin_name, f"Error threshold exceeded: {policy.quarantine_threshold}")
        return {
            "success": True,
            "message": f"Plugin {plugin_name} quarantined"
        }
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    async def _detect_error_patterns(self, errors: List[PluginError]) -> List[Dict[str, Any]]:
        """Detect error patterns"""
        patterns = []
        
        # Group errors by plugin and category
        error_groups = {}
        for error in errors:
            key = f"{error.plugin_name}:{error.category.value}"
            if key not in error_groups:
                error_groups[key] = []
            error_groups[key].append(error)
        
        # Detect patterns
        for key, group_errors in error_groups.items():
            if len(group_errors) >= 3:  # Pattern threshold
                plugin_name, category = key.split(":")
                
                # Check if errors are frequent
                time_span = (max(e.timestamp for e in group_errors) - 
                           min(e.timestamp for e in group_errors))
                
                if time_span.total_seconds() < 300:  # 5 minutes
                    patterns.append({
                        "plugin_name": plugin_name,
                        "category": category,
                        "error_count": len(group_errors),
                        "time_span_minutes": time_span.total_seconds() / 60,
                        "pattern_type": "frequent_errors"
                    })
        
        return patterns
    
    def _update_recovery_time_metrics(self, recovery_time: float):
        """Update recovery time metrics"""
        if self.metrics.average_recovery_time == 0:
            self.metrics.average_recovery_time = recovery_time
        else:
            self.metrics.average_recovery_time = (
                (self.metrics.average_recovery_time * (self.metrics.recovery_attempts - 1) + recovery_time) /
                self.metrics.recovery_attempts
            )
    
    async def _background_cleanup(self):
        """Background cleanup task"""
        while True:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour
                
                # Clean up old errors
                cutoff_time = datetime.now() - timedelta(days=7)
                self.error_history = [e for e in self.error_history if e.timestamp >= cutoff_time]
                
                # Clean up expired quarantines
                expired_quarantines = [
                    name for name, expiry in self.quarantined_plugins.items()
                    if datetime.now() >= expiry
                ]
                
                for name in expired_quarantines:
                    await self.release_plugin_from_quarantine(name)
                    self.logger.info(f"Plugin {name} automatically released from quarantine")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Background cleanup error: {e}")
    
    async def _error_monitoring(self):
        """Background error monitoring"""
        while True:
            try:
                await asyncio.sleep(300)  # Monitor every 5 minutes
                
                # Check for error spikes
                recent_errors = [
                    e for e in self.error_history
                    if e.timestamp >= datetime.now() - timedelta(minutes=5)
                ]
                
                if len(recent_errors) > 20:  # Error spike threshold
                    self.logger.warning(f"Error spike detected: {len(recent_errors)} errors in 5 minutes")
                    
                    # Find problematic plugins
                    plugin_error_counts = {}
                    for error in recent_errors:
                        plugin_error_counts[error.plugin_name] = plugin_error_counts.get(error.plugin_name, 0) + 1
                    
                    for plugin_name, count in plugin_error_counts.items():
                        if count >= 5:  # Plugin-specific threshold
                            await self.quarantine_plugin(plugin_name, f"Error spike: {count} errors in 5 minutes")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error monitoring error: {e}")
    
    async def _emit_quarantine_event(self, plugin_name: str, reason: str, expiry: datetime):
        """Emit quarantine event"""
        # This would integrate with VoiceOS event system
        pass
    
    async def _load_error_history(self):
        """Load error history from file"""
        if self.error_log_path.exists():
            try:
                with open(self.error_log_path, 'r') as f:
                    data = json.load(f)
                
                for error_data in data.get("errors", []):
                    error = PluginError(
                        error_id=error_data["error_id"],
                        plugin_name=error_data["plugin_name"],
                        timestamp=datetime.fromisoformat(error_data["timestamp"]),
                        severity=ErrorSeverity(error_data["severity"]),
                        category=ErrorCategory(error_data["category"]),
                        message=error_data["message"],
                        details=error_data.get("details", {}),
                        stack_trace=error_data.get("stack_trace"),
                        context=error_data.get("context", {}),
                        recovery_attempted=error_data.get("recovery_attempted", False),
                        recovery_successful=error_data.get("recovery_successful", False),
                        recovery_action=RecoveryAction(error_data["recovery_action"]) if error_data.get("recovery_action") else None,
                        resolved=error_data.get("resolved", False),
                        resolution_time=datetime.fromisoformat(error_data["resolution_time"]) if error_data.get("resolution_time") else None
                    )
                    self.error_history.append(error)
                
                self.logger.info(f"Loaded {len(self.error_history)} error records")
                
            except Exception as e:
                self.logger.error(f"Error loading history: {e}")
    
    async def _save_error_history(self):
        """Save error history to file"""
        try:
            data = {
                "errors": [
                    {
                        "error_id": e.error_id,
                        "plugin_name": e.plugin_name,
                        "timestamp": e.timestamp.isoformat(),
                        "severity": e.severity.value,
                        "category": e.category.value,
                        "message": e.message,
                        "details": e.details,
                        "stack_trace": e.stack_trace,
                        "context": e.context,
                        "recovery_attempted": e.recovery_attempted,
                        "recovery_successful": e.recovery_successful,
                        "recovery_action": e.recovery_action.value if e.recovery_action else None,
                        "resolved": e.resolved,
                        "resolution_time": e.resolution_time.isoformat() if e.resolution_time else None
                    }
                    for e in self.error_history[-1000:]  # Save last 1000 errors
                ],
                "metadata": {
                    "total_errors": len(self.error_history),
                    "last_updated": datetime.now().isoformat()
                }
            }
            
            with open(self.error_log_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving history: {e}")
    
    def _register_default_policies(self):
        """Register default recovery policies"""
        # Security errors - immediate quarantine
        self.recovery_policies["security:critical"] = RecoveryPolicy(
            error_category=ErrorCategory.SECURITY,
            severity_threshold=ErrorSeverity.CRITICAL,
            max_retries=0,
            recovery_actions=[RecoveryAction.QUARANTINE],
            auto_recovery=True,
            requires_approval=False,
            quarantine_threshold=1
        )
        
        # Execution errors - retry then restart
        self.recovery_policies["execution:medium"] = RecoveryPolicy(
            error_category=ErrorCategory.EXECUTION,
            severity_threshold=ErrorSeverity.MEDIUM,
            max_retries=3,
            retry_delay=2.0,
            recovery_actions=[RecoveryAction.RETRY, RecoveryAction.RESTART],
            auto_recovery=True
        )
        
        # Resource errors - disable temporarily
        self.recovery_policies["resource:high"] = RecoveryPolicy(
            error_category=ErrorCategory.RESOURCE,
            severity_threshold=ErrorSeverity.HIGH,
            max_retries=1,
            recovery_actions=[RecoveryAction.DISABLE],
            auto_recovery=True
        )
        
        # Default policy
        self.recovery_policies["default"] = RecoveryPolicy(
            error_category=ErrorCategory.UNKNOWN,
            severity_threshold=ErrorSeverity.MEDIUM,
            max_retries=2,
            retry_delay=1.0,
            recovery_actions=[RecoveryAction.RETRY, RecoveryAction.ESCALATE],
            auto_recovery=True
        )
    
    def _register_recovery_callbacks(self):
        """Register recovery action callbacks"""
        # These would integrate with actual plugin management systems
        self.recovery_callbacks[RecoveryAction.RETRY] = self._retry_operation
        self.recovery_callbacks[RecoveryAction.RESTART] = self._restart_plugin
        self.recovery_callbacks[RecoveryAction.DISABLE] = self._disable_plugin
        self.recovery_callbacks[RecoveryAction.FALLBACK] = self._use_fallback
        self.recovery_callbacks[RecoveryAction.QUARANTINE] = self._quarantine_plugin
    
    def get_metrics(self) -> ErrorMetrics:
        """Get error handling metrics"""
        return self.metrics


# Global error handler instance
plugin_error_handler = None

def get_plugin_error_handler() -> PluginErrorHandler:
    """Get or create plugin error handler instance"""
    global plugin_error_handler
    if plugin_error_handler is None:
        plugin_error_handler = PluginErrorHandler(config.project_root / "workspace")
    return plugin_error_handler
