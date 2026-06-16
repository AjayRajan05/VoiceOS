"""
Safety Module - Permission validation and risk assessment
Provides comprehensive safety checks before tool execution
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SafetyAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_PERMISSION = "require_permission"
    REQUIRE_CONFIRMATION = "require_confirmation"

@dataclass
class SafetyRule:
    name: str
    pattern: str
    risk_level: RiskLevel
    action: SafetyAction
    description: str
    tools_affected: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SafetyCheck:
    tool_name: str
    parameters: Dict[str, Any]
    risk_level: RiskLevel
    action: SafetyAction
    confidence: float
    reasons: List[str]
    rule_matches: List[str]
    timestamp: float
    user_context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SafetyConfig:
    enable_risk_assessment: bool = True
    enable_pattern_matching: bool = True
    enable_parameter_validation: bool = True
    enable_context_analysis: bool = True
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    auto_approve_safe: bool = True
    require_permission_for_high_risk: bool = True
    block_critical_risk: bool = True
    session_timeout: int = 3600  # 1 hour
    max_concurrent_requests: int = 10

class SafetyModule:
    def __init__(self, config: SafetyConfig = None, permission_engine=None):
        self.config = config or SafetyConfig()
        self.permission_engine = permission_engine
        self.safety_rules = self._initialize_safety_rules()
        self.blocked_patterns = self._initialize_blocked_patterns()
        self.risky_operations = self._initialize_risky_operations()
        
        # Safety state
        self.session_history: List[SafetyCheck] = []
        self.risk_scores: Dict[str, float] = {}
        self.permission_cache: Dict[str, Any] = {}
        self.blocked_operations: Set[str] = set()
        
        # Statistics
        self.stats = {
            "total_checks": 0,
            "allowed": 0,
            "denied": 0,
            "required_permission": 0,
            "risk_levels": defaultdict(int)
        }
    
    def _initialize_safety_rules(self) -> List[SafetyRule]:
        """
        Initialize comprehensive safety rules
        """
        return [
            # System modification rules
            SafetyRule(
                name="system_file_modification",
                pattern=r"(delete|remove|format|erase|wipe).*\.(sys|dll|exe|bat|cmd)",
                risk_level=RiskLevel.HIGH,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="System file modification detected",
                tools_affected=["os_file_manager", "os_command"]
            ),
            
            # Network operations
            SafetyRule(
                name="network_download",
                pattern=r"(download|fetch|get|pull).*(exe|bat|cmd|scr|msi)",
                risk_level=RiskLevel.MEDIUM,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Executable download detected",
                tools_affected=["web_downloader", "network_tools"]
            ),
            
            # Data access rules
            SafetyRule(
                name="sensitive_data_access",
                pattern=r"(password|credential|token|key|secret|private)",
                risk_level=RiskLevel.HIGH,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Sensitive data access detected",
                tools_affected=["file_reader", "data_extractor"]
            ),
            
            # Command injection patterns
            SafetyRule(
                name="command_injection",
                pattern=r"[;&|`$(){}[\]\\]",
                risk_level=RiskLevel.CRITICAL,
                action=SafetyAction.DENY,
                description="Command injection pattern detected",
                tools_affected=["os_command", "shell_executor"]
            ),
            
            # Path traversal
            SafetyRule(
                name="path_traversal",
                pattern=r"\.\.[\\/]",
                risk_level=RiskLevel.HIGH,
                action=SafetyAction.DENY,
                description="Path traversal attempt detected",
                tools_affected=["file_reader", "file_writer", "os_command"]
            ),
            
            # Code execution
            SafetyRule(
                name="code_execution",
                pattern=r"(eval|exec|system|shell|powershell|bash)",
                risk_level=RiskLevel.MEDIUM,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Code execution detected",
                tools_affected=["code_executor", "script_runner"]
            ),
            
            # Registry modification
            SafetyRule(
                name="registry_modification",
                pattern=r"(regedit|registry|reg\.exe)",
                risk_level=RiskLevel.HIGH,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Registry modification detected",
                tools_affected=["os_command", "system_tools"]
            ),
            
            # Service management
            SafetyRule(
                name="service_management",
                pattern=r"(service|daemon|start|stop|restart).*\.(exe|msc)",
                risk_level=RiskLevel.MEDIUM,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Service management detected",
                tools_affected=["os_command", "system_tools"]
            ),
            
            # Network configuration
            SafetyRule(
                name="network_config",
                pattern=r"(firewall|port|network|ipconfig|netstat)",
                risk_level=RiskLevel.LOW,
                action=SafetyAction.REQUIRE_PERMISSION,
                description="Network configuration detected",
                tools_affected=["network_tools", "os_command"]
            )
        ]
    
    def _initialize_blocked_patterns(self) -> List[str]:
        """
        Initialize patterns that are always blocked
        """
        return [
            r"rm\s+-rf\s+/",
            r"format\s+c:",
            r"del\s+/s",
            r"shutdown\s+/s",
            r"reboot",
            r"halt",
            r"poweroff"
        ]
    
    def _initialize_risky_operations(self) -> Dict[str, RiskLevel]:
        """
        Initialize risky operation mappings
        """
        return {
            "os_delete_file": RiskLevel.MEDIUM,
            "os_format_disk": RiskLevel.CRITICAL,
            "os_modify_registry": RiskLevel.HIGH,
            "os_install_software": RiskLevel.MEDIUM,
            "network_download": RiskLevel.MEDIUM,
            "code_execute": RiskLevel.MEDIUM,
            "system_restart": RiskLevel.HIGH,
            "system_shutdown": RiskLevel.CRITICAL,
            "user_management": RiskLevel.HIGH,
            "permission_change": RiskLevel.HIGH
        }
    
    async def check_safety(self, tool_name: str, parameters: Dict[str, Any], 
                          user_context: Dict[str, Any] = None) -> SafetyCheck:
        """
        Perform comprehensive safety check
        """
        start_time = time.time()
        self.stats["total_checks"] += 1
        
        try:
            # Initialize safety check
            safety_check = SafetyCheck(
                tool_name=tool_name,
                parameters=parameters,
                risk_level=RiskLevel.SAFE,
                action=SafetyAction.ALLOW,
                confidence=0.0,
                reasons=[],
                rule_matches=[],
                timestamp=start_time,
                user_context=user_context or {}
            )
            
            # 1. Check blocked patterns
            if self._check_blocked_patterns(parameters, safety_check):
                return safety_check
            
            # 2. Check safety rules
            if self.config.enable_pattern_matching:
                self._check_safety_rules(tool_name, parameters, safety_check)
            
            # 3. Check tool-specific risk
            if self.config.enable_risk_assessment:
                self._check_tool_risk(tool_name, parameters, safety_check)
            
            # 4. Parameter validation
            if self.config.enable_parameter_validation:
                self._validate_parameters(tool_name, parameters, safety_check)
            
            # 5. Context analysis
            if self.config.enable_context_analysis:
                self._analyze_context(user_context, safety_check)
            
            # 6. Determine final action
            self._determine_action(safety_check)
            
            # Update statistics
            self.stats["allowed"] += 1 if safety_check.action == SafetyAction.ALLOW else 0
            self.stats["denied"] += 1 if safety_check.action == SafetyAction.DENY else 0
            self.stats["required_permission"] += 1 if safety_check.action == SafetyAction.REQUIRE_PERMISSION else 0
            self.stats["risk_levels"][safety_check.risk_level.value] += 1
            
            # Store in history
            self.session_history.append(safety_check)
            
            # Limit history size
            if len(self.session_history) > 1000:
                self.session_history = self.session_history[-500:]
            
            return safety_check
            
        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return SafetyCheck(
                tool_name=tool_name,
                parameters=parameters,
                risk_level=RiskLevel.HIGH,
                action=SafetyAction.DENY,
                confidence=0.0,
                reasons=[f"Safety check error: {str(e)}"],
                rule_matches=[],
                timestamp=start_time
            )
    
    def _check_blocked_patterns(self, parameters: Dict[str, Any], safety_check: SafetyCheck) -> bool:
        """
        Check for blocked patterns
        """
        param_text = str(parameters).lower()
        
        for pattern in self.blocked_patterns:
            if re.search(pattern, param_text, re.IGNORECASE):
                safety_check.risk_level = RiskLevel.CRITICAL
                safety_check.action = SafetyAction.DENY
                safety_check.reasons.append(f"Blocked pattern detected: {pattern}")
                safety_check.rule_matches.append(pattern)
                safety_check.confidence = 1.0
                return True
        
        return False
    
    def _check_safety_rules(self, tool_name: str, parameters: Dict[str, Any], safety_check: SafetyCheck):
        """
        Check against safety rules
        """
        param_text = str(parameters).lower()
        
        for rule in self.safety_rules:
            # Check if rule applies to this tool
            if rule.tools_affected and tool_name not in rule.tools_affected:
                continue
            
            # Check pattern match
            if re.search(rule.pattern, param_text, re.IGNORECASE):
                safety_check.rule_matches.append(rule.name)
                safety_check.reasons.append(rule.description)
                
                # Update risk level if higher
                if rule.risk_level.value > safety_check.risk_level.value:
                    safety_check.risk_level = rule.risk_level
                
                # Update action based on rule
                if rule.action.value > safety_check.action.value:
                    safety_check.action = rule.action
    
    def _check_tool_risk(self, tool_name: str, parameters: Dict[str, Any], safety_check: SafetyCheck):
        """
        Check tool-specific risk
        """
        base_risk = self.risky_operations.get(tool_name, RiskLevel.SAFE)
        
        if base_risk.value > safety_check.risk_level.value:
            safety_check.risk_level = base_risk
            safety_check.reasons.append(f"Tool {tool_name} has {base_risk.value} risk level")
        
        # Check for risky parameters
        risky_params = self._identify_risky_parameters(tool_name, parameters)
        if risky_params:
            safety_check.reasons.extend([f"Risky parameter: {param}" for param in risky_params])
            if safety_check.risk_level == RiskLevel.SAFE:
                safety_check.risk_level = RiskLevel.LOW
    
    def _validate_parameters(self, tool_name: str, parameters: Dict[str, Any], safety_check: SafetyCheck):
        """
        Validate parameters for safety
        """
        for param_name, param_value in parameters.items():
            # Check for suspicious values
            if isinstance(param_value, str):
                # Check for command injection
                if any(char in param_value for char in [';', '&', '|', '`', '$', '(', ')']):
                    safety_check.reasons.append(f"Suspicious characters in parameter {param_name}")
                    safety_check.risk_level = RiskLevel.HIGH
                    safety_check.action = SafetyAction.DENY
                
                # Check for path traversal
                if '..' in param_value or '\\' in param_value or '/' in param_value:
                    safety_check.reasons.append(f"Path traversal attempt in parameter {param_name}")
                    safety_check.risk_level = RiskLevel.HIGH
                
                # Check for extremely long values (potential buffer overflow)
                if len(param_value) > 10000:
                    safety_check.reasons.append(f"Extremely long parameter {param_name}")
                    safety_check.risk_level = RiskLevel.MEDIUM
    
    def _analyze_context(self, user_context: Dict[str, Any], safety_check: SafetyCheck):
        """
        Analyze user context for safety
        """
        if not user_context:
            return
        
        # Check user trust level
        trust_level = user_context.get('trust_level', 'medium')
        if trust_level == 'low':
            safety_check.reasons.append("Low trust user context")
            if safety_check.risk_level == RiskLevel.SAFE:
                safety_check.risk_level = RiskLevel.LOW
        
        # Check session history
        recent_checks = [c for c in self.session_history[-10:] 
                         if c.timestamp > time.time() - 300]  # Last 5 minutes
        
        denied_count = sum(1 for c in recent_checks if c.action == SafetyAction.DENY)
        if denied_count > 3:
            safety_check.reasons.append("Multiple recent denied operations")
            safety_check.risk_level = RiskLevel.HIGH
        
        # Check frequency of operations
        tool_checks = [c for c in recent_checks if c.tool_name == safety_check.tool_name]
        if len(tool_checks) > 5:
            safety_check.reasons.append(f"High frequency operations for {safety_check.tool_name}")
            if safety_check.risk_level == RiskLevel.SAFE:
                safety_check.risk_level = RiskLevel.LOW
    
    def _determine_action(self, safety_check: SafetyCheck):
        """
        Determine final safety action
        """
        # Calculate confidence based on rule matches and risk level
        if safety_check.rule_matches:
            safety_check.confidence = min(1.0, len(safety_check.rule_matches) * 0.3 + 0.4)
        else:
            safety_check.confidence = 0.8  # High confidence for safe operations
        
        # Apply configuration rules
        if safety_check.risk_level == RiskLevel.CRITICAL and self.config.block_critical_risk:
            safety_check.action = SafetyAction.DENY
        elif safety_check.risk_level == RiskLevel.HIGH and self.config.require_permission_for_high_risk:
            safety_check.action = SafetyAction.REQUIRE_PERMISSION
        elif safety_check.risk_level == RiskLevel.SAFE and self.config.auto_approve_safe:
            safety_check.action = SafetyAction.ALLOW
        
        # Check against max risk level
        if safety_check.risk_level.value > self.config.max_risk_level.value:
            safety_check.action = SafetyAction.REQUIRE_PERMISSION
    
    def _identify_risky_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> List[str]:
        """
        Identify risky parameters for a tool
        """
        risky_params = []
        
        for param_name, param_value in parameters.items():
            if isinstance(param_value, str):
                # Check for risky keywords
                risky_keywords = ['delete', 'remove', 'format', 'shutdown', 'restart', 'kill']
                if any(keyword in param_value.lower() for keyword in risky_keywords):
                    risky_params.append(param_name)
        
        return risky_params
    
    async def request_permission(self, safety_check: SafetyCheck) -> bool:
        """
        Request user permission for operation
        """
        # Check permission cache
        cache_key = self._generate_permission_cache_key(safety_check)
        if cache_key in self.permission_cache:
            cached = self.permission_cache[cache_key]
            if time.time() - cached['timestamp'] < self.config.session_timeout:
                return cached['allowed']
        
        if self.permission_engine:
            approved = await self.permission_engine.prompt_for_approval(
                safety_check.tool_name,
                [safety_check.tool_name],
                str(safety_check.parameters)[:200],
            )
            self.permission_cache[cache_key] = {
                "allowed": approved,
                "timestamp": time.time(),
            }
            return approved

        logger.warning(f"Permission required for {safety_check.tool_name}: {safety_check.reasons}")
        
        # Cache the permission (default to denied for safety)
        self.permission_cache[cache_key] = {
            'allowed': False,
            'timestamp': time.time()
        }
        
        return False
    
    def _generate_permission_cache_key(self, safety_check: SafetyCheck) -> str:
        """
        Generate cache key for permission
        """
        key_data = f"{safety_check.tool_name}:{hash(str(safety_check.parameters))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_safety_statistics(self) -> Dict[str, Any]:
        """
        Get safety statistics
        """
        return {
            **self.stats,
            "session_history_size": len(self.session_history),
            "permission_cache_size": len(self.permission_cache),
            "blocked_operations": len(self.blocked_operations),
            "active_rules": len(self.safety_rules)
        }
    
    def clear_session_history(self):
        """
        Clear session history
        """
        self.session_history.clear()
    
    def clear_permission_cache(self):
        """
        Clear permission cache
        """
        self.permission_cache.clear()
    
    def add_safety_rule(self, rule: SafetyRule):
        """
        Add new safety rule
        """
        self.safety_rules.append(rule)
        logger.info(f"Added safety rule: {rule.name}")
    
    def remove_safety_rule(self, rule_name: str) -> bool:
        """
        Remove safety rule by name
        """
        for i, rule in enumerate(self.safety_rules):
            if rule.name == rule_name:
                del self.safety_rules[i]
                logger.info(f"Removed safety rule: {rule_name}")
                return True
        return False
    
    def update_config(self, config: SafetyConfig):
        """
        Update safety configuration
        """
        self.config = config
        logger.info("Safety configuration updated")
