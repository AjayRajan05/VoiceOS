"""
Error Recovery Module - Comprehensive error handling and recovery system
Provides graceful degradation, retry mechanisms, and system recovery
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    SYSTEM = "system"
    NETWORK = "network"
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    MEMORY = "memory"
    CONFIGURATION = "configuration"
    USER_INPUT = "user_input"

class RecoveryAction(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    RESTART_COMPONENT = "restart_component"
    DEGRADE_SERVICE = "degrade_service"

@dataclass
class ErrorInfo:
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    traceback: str
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)
    component: str = ""
    recovery_attempts: int = 0
    resolved: bool = False

@dataclass
class RecoveryStrategy:
    category: ErrorCategory
    severity: ErrorSeverity
    action: RecoveryAction
    max_attempts: int = 3
    backoff_factor: float = 2.0
    timeout: float = 30.0
    fallback_handler: Optional[Callable] = None

@dataclass
class RecoveryConfig:
    enable_auto_recovery: bool = True
    max_concurrent_recoveries: int = 5
    recovery_timeout: float = 60.0
    error_log_retention: int = 1000
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 300.0

class ErrorRecovery:
    def __init__(self, config: RecoveryConfig = None):
        self.config = config or RecoveryConfig()
        
        # Error tracking
        self.error_history: List[ErrorInfo] = []
        self.active_recoveries: Dict[str, asyncio.Task] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Recovery strategies
        self.recovery_strategies = self._initialize_recovery_strategies()
        
        # Statistics
        self.stats = {
            "total_errors": 0,
            "resolved_errors": 0,
            "failed_recoveries": 0,
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "errors_by_category": {},
            "errors_by_severity": {}
        }
        
        # Recovery handlers
        self.fallback_handlers: Dict[str, Callable] = {}
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    def _initialize_recovery_strategies(self) -> List[RecoveryStrategy]:
        """
        Initialize default recovery strategies
        """
        strategies = [
            # Network errors - retry with backoff
            RecoveryStrategy(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.RETRY,
                max_attempts=3,
                backoff_factor=2.0
            ),
            RecoveryStrategy(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.RETRY,
                max_attempts=2,
                backoff_factor=2.0
            ),
            
            # LLM errors - fallback to alternative model
            RecoveryStrategy(
                category=ErrorCategory.LLM,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.FALLBACK,
                max_attempts=2,
                fallback_handler=self._llm_fallback_handler
            ),
            
            # Tool errors - retry with fallback
            RecoveryStrategy(
                category=ErrorCategory.TOOL,
                severity=ErrorSeverity.LOW,
                action=RecoveryAction.RETRY,
                max_attempts=3
            ),
            RecoveryStrategy(
                category=ErrorCategory.TOOL,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.FALLBACK,
                fallback_handler=self._tool_fallback_handler
            ),
            
            # Agent errors - restart agent
            RecoveryStrategy(
                category=ErrorCategory.AGENT,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.RESTART_COMPONENT,
                max_attempts=1
            ),
            
            # System errors - degrade service
            RecoveryStrategy(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                action=RecoveryAction.DEGRADE_SERVICE,
                max_attempts=1
            ),
            RecoveryStrategy(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                action=RecoveryAction.ABORT,
                max_attempts=1
            ),
            
            # Memory errors - cleanup and retry
            RecoveryStrategy(
                category=ErrorCategory.MEMORY,
                severity=ErrorSeverity.MEDIUM,
                action=RecoveryAction.RETRY,
                max_attempts=2,
                fallback_handler=self._memory_cleanup_handler
            )
        ]
        
        return strategies
    
    async def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Handle an error and attempt recovery
        """
        try:
            # Create error info
            error_info = self._create_error_info(error, context or {})
            
            # Log error
            logger.error(f"Error occurred: {error_info.message} (ID: {error_info.error_id})")
            
            # Check circuit breaker
            if self._is_circuit_breaker_open(error_info.component):
                logger.warning(f"Circuit breaker open for {error_info.component}")
                error_info.resolved = False
                return error_info
            
            # Find recovery strategy
            strategy = self._find_recovery_strategy(error_info)
            if not strategy:
                logger.warning(f"No recovery strategy found for error: {error_info.error_id}")
                return error_info
            
            # Attempt recovery
            if self.config.enable_auto_recovery:
                success = await self._attempt_recovery(error_info, strategy)
                error_info.resolved = success
            
            # Update statistics
            self._update_stats(error_info)
            
            return error_info
            
        except Exception as e:
            logger.error(f"Error in error handling: {e}")
            return self._create_error_info(e, {"original_error": str(error)})
    
    def _create_error_info(self, error: Exception, context: Dict[str, Any]) -> ErrorInfo:
        """
        Create error information object
        """
        import uuid
        
        # Determine category and severity
        category = self._categorize_error(error)
        severity = self._assess_severity(error)
        
        error_info = ErrorInfo(
            error_id=str(uuid.uuid4()),
            category=category,
            severity=severity,
            message=str(error),
            traceback=traceback.format_exc(),
            timestamp=time.time(),
            context=context,
            component=context.get("component", "unknown")
        )
        
        # Add to history
        self.error_history.append(error_info)
        
        # Limit history size
        if len(self.error_history) > self.config.error_log_retention:
            self.error_history = self.error_history[-self.config.error_log_retention//2:]
        
        return error_info
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Categorize error based on type and message
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Network errors
        if any(term in error_message for term in ["connection", "timeout", "network", "http"]):
            return ErrorCategory.NETWORK
        
        # LLM errors
        if any(term in error_message for term in ["model", "llm", "generation", "token"]):
            return ErrorCategory.LLM
        
        # Tool errors
        if any(term in error_message for term in ["tool", "execution", "parameter"]):
            return ErrorCategory.TOOL
        
        # Agent errors
        if any(term in error_message for term in ["agent", "planner", "router"]):
            return ErrorCategory.AGENT
        
        # Memory errors
        if any(term in error_message for term in ["memory", "storage", "cache"]):
            return ErrorCategory.MEMORY
        
        # Configuration errors
        if any(term in error_message for term in ["config", "setting", "parameter"]):
            return ErrorCategory.CONFIGURATION
        
        # Default to system
        return ErrorCategory.SYSTEM
    
    def _assess_severity(self, error: Exception) -> ErrorSeverity:
        """
        Assess error severity
        """
        error_type = type(error).__name__
        
        # Critical errors
        if error_type in ["SystemExit", "KeyboardInterrupt", "MemoryError"]:
            return ErrorSeverity.CRITICAL
        
        # High severity
        if error_type in ["ImportError", "AttributeError", "TypeError"]:
            return ErrorSeverity.HIGH
        
        # Medium severity
        if error_type in ["ValueError", "KeyError", "IndexError"]:
            return ErrorSeverity.MEDIUM
        
        # Low severity
        return ErrorSeverity.LOW
    
    def _find_recovery_strategy(self, error_info: ErrorInfo) -> Optional[RecoveryStrategy]:
        """
        Find appropriate recovery strategy for error
        """
        for strategy in self.recovery_strategies:
            if (strategy.category == error_info.category and 
                strategy.severity == error_info.severity):
                return strategy
        
        # Try to find less specific strategy
        for strategy in self.recovery_strategies:
            if (strategy.category == error_info.category and 
                strategy.severity.value in ["low", "medium"] and 
                error_info.severity.value in ["high", "critical"]):
                return strategy
        
        return None
    
    async def _attempt_recovery(self, error_info: ErrorInfo, strategy: RecoveryStrategy) -> bool:
        """
        Attempt to recover from error using strategy
        """
        if error_info.recovery_attempts >= strategy.max_attempts:
            logger.warning(f"Max recovery attempts reached for error {error_info.error_id}")
            return False
        
        try:
            # Check if recovery is already in progress
            if error_info.error_id in self.active_recoveries:
                logger.info(f"Recovery already in progress for {error_info.error_id}")
                return False
            
            # Start recovery task
            recovery_task = asyncio.create_task(
                self._execute_recovery(error_info, strategy)
            )
            self.active_recoveries[error_info.error_id] = recovery_task
            
            # Wait for recovery with timeout
            try:
                result = await asyncio.wait_for(
                    recovery_task, 
                    timeout=strategy.timeout
                )
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"Recovery timeout for error {error_info.error_id}")
                recovery_task.cancel()
                return False
                
        except Exception as e:
            logger.error(f"Recovery failed for error {error_info.error_id}: {e}")
            return False
        
        finally:
            # Clean up active recovery
            self.active_recoveries.pop(error_info.error_id, None)
    
    async def _execute_recovery(self, error_info: ErrorInfo, strategy: RecoveryStrategy) -> bool:
        """
        Execute recovery action
        """
        error_info.recovery_attempts += 1
        self.stats["recovery_attempts"] += 1
        
        try:
            if strategy.action == RecoveryAction.RETRY:
                return await self._retry_recovery(error_info, strategy)
            
            elif strategy.action == RecoveryAction.FALLBACK:
                return await self._fallback_recovery(error_info, strategy)
            
            elif strategy.action == RecoveryAction.SKIP:
                logger.info(f"Skipping error {error_info.error_id}")
                return True
            
            elif strategy.action == RecoveryAction.ABORT:
                logger.error(f"Aborting due to error {error_info.error_id}")
                return False
            
            elif strategy.action == RecoveryAction.RESTART_COMPONENT:
                return await self._restart_component_recovery(error_info, strategy)
            
            elif strategy.action == RecoveryAction.DEGRADE_SERVICE:
                return await self._degrade_service_recovery(error_info, strategy)
            
            else:
                logger.warning(f"Unknown recovery action: {strategy.action}")
                return False
                
        except Exception as e:
            logger.error(f"Recovery execution failed: {e}")
            return False
    
    async def _retry_recovery(self, error_info: ErrorInfo, strategy: RecoveryStrategy) -> bool:
        """
        Retry recovery with exponential backoff
        """
        backoff = strategy.backoff_factor ** (error_info.recovery_attempts - 1)
        
        logger.info(f"Retrying operation for error {error_info.error_id} (attempt {error_info.recovery_attempts})")
        
        # Wait before retry
        await asyncio.sleep(backoff)
        
        # Retry is coordinated by the caller; backoff only applies here.
        return False
    
    async def _fallback_recovery(self, error_info: ErrorInfo, strategy: RecoveryAction) -> bool:
        """
        Fallback recovery using alternative method
        """
        logger.info(f"Attempting fallback recovery for error {error_info.error_id}")
        
        if strategy.fallback_handler:
            try:
                result = await strategy.fallback_handler(error_info)
                self.stats["successful_recoveries"] += 1
                return result
            except Exception as e:
                logger.error(f"Fallback handler failed: {e}")
        
        return False
    
    async def _restart_component_recovery(self, error_info: ErrorInfo, strategy: RecoveryStrategy) -> bool:
        """
        Restart component recovery
        """
        logger.info(f"Restarting component {error_info.component} for error {error_info.error_id}")
        return False
    
    async def _degrade_service_recovery(self, error_info: ErrorInfo, strategy: RecoveryStrategy) -> bool:
        """
        Degrade service recovery
        """
        logger.info(f"Degrading service for error {error_info.error_id}")
        return False
    
    async def _llm_fallback_handler(self, error_info: ErrorInfo) -> bool:
        """
        Fallback handler for LLM errors
        """
        logger.info("Using LLM fallback handler")
        return False
    
    async def _tool_fallback_handler(self, error_info: ErrorInfo) -> bool:
        """
        Fallback handler for tool errors
        """
        logger.info("Using tool fallback handler")
        return False
    
    async def _memory_cleanup_handler(self, error_info: ErrorInfo) -> bool:
        """
        Memory cleanup handler
        """
        logger.info("Performing memory cleanup")
        import gc

        gc.collect()
        return True
    
    def _is_circuit_breaker_open(self, component: str) -> bool:
        """
        Check if circuit breaker is open for component
        """
        if not self.config.enable_circuit_breaker:
            return False
        
        breaker = self.circuit_breakers.get(component, {})
        
        if breaker.get("open", False):
            # Check if timeout has passed
            if time.time() - breaker.get("opened_at", 0) > self.config.circuit_breaker_timeout:
                # Reset circuit breaker
                self.circuit_breakers[component] = {
                    "open": False,
                    "failures": 0,
                    "last_failure": 0
                }
                return False
            else:
                return True
        
        return False
    
    def _update_circuit_breaker(self, component: str, success: bool):
        """
        Update circuit breaker state
        """
        if not self.config.enable_circuit_breaker:
            return
        
        breaker = self.circuit_breakers.get(component, {
            "open": False,
            "failures": 0,
            "last_failure": 0
        })
        
        if success:
            # Reset on success
            breaker["failures"] = 0
            breaker["open"] = False
        else:
            # Increment failures
            breaker["failures"] += 1
            breaker["last_failure"] = time.time()
            
            # Open circuit breaker if threshold reached
            if breaker["failures"] >= self.config.circuit_breaker_threshold:
                breaker["open"] = True
                breaker["opened_at"] = time.time()
                logger.warning(f"Circuit breaker opened for {component}")
        
        self.circuit_breakers[component] = breaker
    
    def _update_stats(self, error_info: ErrorInfo):
        """
        Update error statistics
        """
        self.stats["total_errors"] += 1
        
        if error_info.resolved:
            self.stats["resolved_errors"] += 1
            self.stats["successful_recoveries"] += 1
        else:
            self.stats["failed_recoveries"] += 1
        
        # Update by category
        category = error_info.category.value
        self.stats["errors_by_category"][category] = self.stats["errors_by_category"].get(category, 0) + 1
        
        # Update by severity
        severity = error_info.severity.value
        self.stats["errors_by_severity"][severity] = self.stats["errors_by_severity"].get(severity, 0) + 1
    
    def register_fallback_handler(self, category: ErrorCategory, handler: Callable):
        """
        Register custom fallback handler
        """
        self.fallback_handlers[category.value] = handler
        logger.info(f"Registered fallback handler for {category.value}")
    
    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """
        Add custom recovery strategy
        """
        self.recovery_strategies.append(strategy)
        logger.info(f"Added recovery strategy for {strategy.category.value}/{strategy.severity.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive error statistics
        """
        return {
            **self.stats,
            "active_recoveries": len(self.active_recoveries),
            "circuit_breakers": {
                component: breaker for component, breaker in self.circuit_breakers.items()
                if breaker.get("open", False)
            },
            "error_history_size": len(self.error_history),
            "recovery_strategies": len(self.recovery_strategies)
        }
    
    def get_recent_errors(self, limit: int = 50, category: ErrorCategory = None, 
                         severity: ErrorSeverity = None) -> List[ErrorInfo]:
        """
        Get recent errors with optional filtering
        """
        errors = self.error_history.copy()
        
        # Filter by category
        if category:
            errors = [e for e in errors if e.category == category]
        
        # Filter by severity
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        # Sort by timestamp and limit
        errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        return errors[:limit]
    
    def clear_error_history(self):
        """
        Clear error history
        """
        self.error_history.clear()
        logger.info("Error history cleared")
    
    async def _cleanup_loop(self):
        """
        Background cleanup task
        """
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                self._cleanup_old_errors()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    def _cleanup_old_errors(self):
        """
        Clean up old errors and expired circuit breakers
        """
        current_time = time.time()
        
        # Clean up old errors
        cutoff_time = current_time - (24 * 3600)  # 24 hours
        self.error_history = [
            e for e in self.error_history 
            if e.timestamp > cutoff_time
        ]
        
        # Clean up expired circuit breakers
        for component, breaker in list(self.circuit_breakers.items()):
            if (breaker.get("open", False) and 
                current_time - breaker.get("opened_at", 0) > self.config.circuit_breaker_timeout):
                del self.circuit_breakers[component]
                logger.info(f"Reset expired circuit breaker for {component}")
    
    async def shutdown(self):
        """
        Shutdown error recovery system
        """
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active recoveries
        for recovery_id, task in self.active_recoveries.items():
            task.cancel()
        
        # Wait for tasks to complete
        if self.active_recoveries:
            await asyncio.gather(*self.active_recoveries.values(), return_exceptions=True)
        
        self.active_recoveries.clear()
        logger.info("Error recovery system shutdown complete")
