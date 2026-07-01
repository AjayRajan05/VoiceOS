"""
Security Module - Comprehensive security hardening for VoiceOS
Provides input validation, output sanitization, access control, and security monitoring
"""

import asyncio
import logging
import hashlib
import hmac
import time
import re
import json
import os
from typing import Dict, Any, List, Optional, Set, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import secrets
from collections import defaultdict, deque

logger: logging.Logger = logging.getLogger(__name__)

class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SecurityEventType(Enum):
    SUSPICIOUS_INPUT = "suspicious_input"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MALICIOUS_REQUEST = "malicious_request"
    SECURITY_VIOLATION = "security_violation"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    INJECTION_ATTEMPT = "injection_attempt"

@dataclass
class SecurityEvent:
    event_id: str
    event_type: SecurityEventType
    threat_level: ThreatLevel
    source_ip: str
    user_agent: str
    timestamp: float
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = False

@dataclass
class SecurityConfig:
    enable_input_validation: bool = True
    enable_output_sanitization: bool = True
    enable_rate_limiting: bool = True
    enable_access_control: bool = True
    enable_audit_logging: bool = True
    max_input_length: int = 10000
    max_requests_per_minute: int = 60
    max_failed_attempts: int = 5
    block_duration: int = 300  # 5 minutes
    enable_encryption: bool = True
    encryption_key: Optional[str] = None
    allowed_hosts: List[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])
    blocked_ips: Set[str] = field(default_factory=set)
    trusted_ips: Set[str] = field(default_factory=set)

class SecurityValidator:
    """Input and output validation and sanitization"""
    
    def __init__(self) -> None:
        # Dangerous patterns
        self.injection_patterns: List[str] = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript protocol
            r'on\w+\s*=',  # Event handlers
            r'eval\s*\(',  # eval() calls
            r'exec\s*\(',  # exec() calls
            r'system\s*\(',  # system() calls
            r'shell_exec\s*\(',  # shell_exec() calls
            r'passthru\s*\(',  # passthru() calls
            r'file_get_contents\s*\(',  # file operations
            r'fopen\s*\(',  # File operations
            r'unlink\s*\(',  # File deletion
            r'rmdir\s*\(',  # Directory removal
            r'mkdir\s*\(',  # Directory creation
            r'chmod\s*\(',  # Permission changes
            r'\.\.[\\/]',  # Path traversal
            r'[;&|`$()]',  # Command injection chars
            r'union\s+select',  # SQL injection
            r'drop\s+table',  # SQL injection
            r'delete\s+from',  # SQL injection
            r'insert\s+into',  # SQL injection
            r'update\s+set',  # SQL injection
        ]
        
        # Compile regex patterns
        self.compiled_patterns: List[re.Pattern[str]] = [re.compile(pattern, re.IGNORECASE | re.DOTALL)
                                                         for pattern in self.injection_patterns]
        
        # Allowed characters for different contexts
        self.allowed_chars: Dict[str, str] = {
            'text': r'a-zA-Z0-9\s.,!?;:()\[\]{}"-\'',
            'filename': r'a-zA-Z0-9._-',
            'path': r'a-zA-Z0-9/._-\\',
            'json': r'a-zA-Z0-9\s.,!?;:()\[\]{}"\'{}'
        }
    
    def validate_input(self, input_data: str, context: str = "text", 
                      max_length: int = 10000) -> Dict[str, Any]:
        """
        Validate input data for security threats
        """
        result = {
            "valid": True,
            "threats": [],
            "sanitized": input_data,
            "reason": ""
        }
        
        try:
            # Check length
            if len(input_data) > max_length:
                result["valid"] = False
                result["threats"].append("input_too_long")
                result["reason"] = f"Input exceeds maximum length of {max_length}"
                return result
            
            # Check for injection patterns
            for pattern in self.compiled_patterns:
                if pattern.search(input_data):
                    result["valid"] = False
                    result["threats"].append("injection_attempt")
                    result["reason"] = f"Potentially malicious pattern detected: {pattern.pattern}"
                    return result
            
            # Check allowed characters
            if context in self.allowed_chars:
                allowed_pattern: str = f'^[{self.allowed_chars[context]}]*$'
                if not re.match(allowed_pattern, input_data, re.IGNORECASE):
                    result["valid"] = False
                    result["threats"].append("invalid_characters")
                    result["reason"] = f"Input contains invalid characters for context: {context}"
            
            # Sanitize input
            result["sanitized"] = self.sanitize_input(input_data)
            
        except Exception as e:
            logger.error(f"Input validation error: {e}")
            result["valid"] = False
            result["threats"].append("validation_error")
            result["reason"] = f"Validation error: {str(e)}"
        
        return result
    
    def sanitize_input(self, input_data: str) -> str:
        """
        Sanitize input data by removing dangerous elements
        """
        try:
            sanitized: str = input_data
            
            # Remove script tags
            sanitized: str = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            
            # Remove JavaScript protocols
            sanitized: str = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
            
            # Remove event handlers
            sanitized: str = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
            
            # Remove dangerous function calls
            dangerous_functions: List[str] = ['eval', 'exec', 'system', 'shell_exec', 'passthru']
            for func in dangerous_functions:
                sanitized = re.sub(f'{func}\\s*\\(', '', sanitized, flags=re.IGNORECASE)
            
            # Normalize whitespace
            sanitized: str = re.sub(r'\s+', ' ', sanitized)
            
            # Strip leading/trailing whitespace
            sanitized: str = sanitized.strip()
            
            return sanitized
            
        except Exception as e:
            logger.error(f"Input sanitization error: {e}")
            return input_data
    
    def sanitize_output(self, output_data: str, context: str = "text") -> str:
        """
        Sanitize output data to prevent XSS and other attacks
        """
        try:
            if context == "html":
                # HTML context - escape HTML entities
                sanitized: str = (output_data.replace('&', '&amp;')
                                        .replace('<', '&lt;')
                                        .replace('>', '&gt;')
                                        .replace('"', '&quot;')
                                        .replace("'", '&#x27;'))
            else:
                # Text context - just remove dangerous elements
                sanitized: str = self.sanitize_input(output_data)
            
            return sanitized
            
        except Exception as e:
            logger.error(f"Output sanitization error: {e}")
            return output_data
    
    def validate_file_path(self, file_path: str, base_path: str = None) -> Dict[str, Any]:
        """
        Validate file path for security
        """
        result = {
            "valid": True,
            "threats": [],
            "sanitized_path": file_path,
            "reason": ""
        }
        
        try:
            # Normalize path
            normalized_path: str = os.path.normpath(file_path)
            
            # Check for path traversal
            if '..' in normalized_path:
                result["valid"] = False
                result["threats"].append("path_traversal")
                result["reason"] = "Path traversal attempt detected"
                return result
            
            # Check absolute paths
            if os.path.isabs(normalized_path):
                result["valid"] = False
                result["threats"].append("absolute_path")
                result["reason"] = "Absolute paths not allowed"
                return result
            
            # Check against base path if provided
            if base_path:
                full_path: str = os.path.join(base_path, normalized_path)
                full_path: str = os.path.normpath(full_path)
                
                if not full_path.startswith(os.path.normpath(base_path)):
                    result["valid"] = False
                    result["threats"].append("path_escape")
                    result["reason"] = "Path escapes base directory"
                    return result
                
                result["sanitized_path"] = full_path
            else:
                result["sanitized_path"] = normalized_path
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            result["valid"] = False
            result["threats"].append("validation_error")
            result["reason"] = f"Path validation error: {str(e)}"
        
        return result

class RateLimiter:
    """Rate limiting and DDoS protection"""
    
    def __init__(self, max_requests_per_minute: int = 60, block_duration: int = 300) -> None:
        self.max_requests_per_minute: int = max_requests_per_minute
        self.block_duration: int = block_duration
        
        # Request tracking
        self.requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.blocked_ips: Dict[str, float] = {}
        
        # Statistics
        self.stats: Dict[str, int] = {
            "total_requests": 0,
            "blocked_requests": 0,
            "rate_limited_ips": 0
        }
    
    def check_rate_limit(self, ip_address: str) -> Dict[str, Any]:
        """
        Check if IP address is rate limited
        """
        current_time: float = time.time()
        
        # Check if IP is blocked
        if ip_address in self.blocked_ips:
            block_expiry: float = self.blocked_ips[ip_address]
            if current_time < block_expiry:
                remaining_time = int(block_expiry - current_time)
                return {
                    "allowed": False,
                    "reason": "IP blocked",
                    "remaining_time": remaining_time
                }
            else:
                # Block expired, remove it
                del self.blocked_ips[ip_address]
        
        # Check request rate
        requests = self.requests[ip_address]
        
        # Remove old requests (older than 1 minute)
        cutoff_time: float = current_time - 60
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        # Check if limit exceeded
        if len(requests) >= self.max_requests_per_minute:
            # Block the IP
            self.blocked_ips[ip_address] = current_time + self.block_duration
            self.stats["blocked_requests"] += 1
            self.stats["rate_limited_ips"] += 1
            
            return {
                "allowed": False,
                "reason": "Rate limit exceeded",
                "remaining_time": self.block_duration
            }
        
        # Record this request
        requests.append(current_time)
        self.stats["total_requests"] += 1
        
        return {
            "allowed": True,
            "remaining_requests": self.max_requests_per_minute - len(requests)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get rate limiting statistics
        """
        return {
            **self.stats,
            "currently_blocked": len(self.blocked_ips),
            "active_requesters": len(self.requests),
            "requests_per_minute": self.max_requests_per_minute
        }

class AccessController:
    """Access control and authentication"""
    
    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.permissions: Dict[str, Set[str]] = defaultdict(set)
        self.failed_attempts: Dict[str, int] = defaultdict(int)
        
        # Default permissions
        self.default_permissions: Set[str] = {
            "read",
            "execute_safe_tools"
        }
        
        # Admin permissions
        self.admin_permissions: Set[str] = {
            "read",
            "write",
            "execute_all_tools",
            "manage_agents",
            "configure_system",
            "view_logs"
        }
    
    def create_session(self, user_id: str, permissions: Set[str] = None) -> str:
        """
        Create a new user session
        """
        session_id: str = secrets.token_urlsafe(32)
        
        session_data = {
            "user_id": user_id,
            "permissions": permissions or self.default_permissions,
            "created_at": time.time(),
            "last_activity": time.time(),
            "ip_address": None
        }
        
        self.sessions[session_id] = session_data
        self.permissions[user_id] = session_data["permissions"]
        
        return session_id
    
    def validate_session(self, session_id: str, required_permission: str = None) -> Dict[str, Any]:
        """
        Validate session and check permissions
        """
        if session_id not in self.sessions:
            return {
                "valid": False,
                "reason": "Invalid session"
            }
        
        session: Dict[str, Any] = self.sessions[session_id]
        current_time: float = time.time()
        
        # Check session timeout (24 hours)
        if current_time - session["last_activity"] > 86400:
            del self.sessions[session_id]
            return {
                "valid": False,
                "reason": "Session expired"
            }
        
        # Update last activity
        session["last_activity"] = current_time
        
        # Check permissions
        if required_permission and required_permission not in session["permissions"]:
            return {
                "valid": False,
                "reason": f"Insufficient permissions: {required_permission}"
            }
        
        return {
            "valid": True,
            "user_id": session["user_id"],
            "permissions": session["permissions"]
        }
    
    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a session
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """
        Check if user has specific permission
        """
        # Input validation
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")
        
        if not permission or not isinstance(permission, str):
            raise ValueError("permission must be a non-empty string")
        
        # Validate format
        if not user_id.replace('-', '').replace('_', '').isalnum():
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        if not permission.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Invalid permission format: {permission}")
        
        return permission in self.permissions.get(user_id, set())
    
    def grant_permission(self, user_id: str, permission: str) -> None:
        """
        Grant permission to user
        """
        self.permissions[user_id].add(permission)
    
    def revoke_permission(self, user_id: str, permission: str) -> None:
        """
        Revoke permission from user
        """
        self.permissions[user_id].discard(permission)

class SecurityMonitor:
    """Security monitoring and threat detection"""
    
    def __init__(self) -> None:
        self.security_events: List[SecurityEvent] = []
        self.threat_patterns: Dict[str, Callable] = {}
        self.alert_handlers: List[Callable] = []
        
        # Statistics
        self.stats = {
            "total_events": 0,
            "blocked_requests": 0,
            "threats_by_level": defaultdict(int),
            "events_by_type": defaultdict(int)
        }
        
        # Initialize threat detection patterns
        self._initialize_threat_patterns()
    
    def _initialize_threat_patterns(self) -> None:
        """
        Initialize threat detection patterns
        """
        self.threat_patterns = {
            "multiple_failed_attempts": self._detect_multiple_failed_attempts,
            "rapid_requests": self._detect_rapid_requests,
            "suspicious_patterns": self._detect_suspicious_patterns,
            "unusual_access_times": self._detect_unusual_access_times
        }
    
    def log_security_event(self, event_type: SecurityEventType, threat_level: ThreatLevel,
                         source_ip: str, user_agent: str, description: str,
                         details: Dict[str, Any] = None, block: bool = False) -> None:
        """
        Log a security event
        """
        import uuid
        
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            threat_level=threat_level,
            source_ip=source_ip,
            user_agent=user_agent,
            timestamp=time.time(),
            description=description,
            details=details or {},
            blocked=block
        )
        
        self.security_events.append(event)
        self.stats["total_events"] += 1
        self.stats["threats_by_level"][threat_level.value] += 1
        self.stats["events_by_type"][event_type.value] += 1
        
        if block:
            self.stats["blocked_requests"] += 1
        
        # Trigger alert handlers
        for handler in self.alert_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        # Log event
        log_level: int = logging.WARNING if threat_level in [ThreatLevel.LOW, ThreatLevel.MEDIUM] else logging.ERROR
        logger.log(log_level, f"Security Event [{threat_level.value.upper()}]: {description}")
    
    def _detect_multiple_failed_attempts(self, ip_address: str, failed_count: int) -> bool:
        """
        Detect multiple failed attempts from same IP
        """
        return failed_count >= 5
    
    def _detect_rapid_requests(self, request_times: List[float]) -> bool:
        """
        Detect rapid succession of requests
        """
        if len(request_times) < 10:
            return False
        
        # Check if 10 requests came in less than 1 second
        return request_times[-1] - request_times[-10] < 1.0
    
    def _detect_suspicious_patterns(self, user_agent: str, request_data: str) -> bool:
        """
        Detect suspicious patterns in requests
        """
        suspicious_ua_patterns: List[str] = [
            "bot", "crawler", "scanner", "exploit", "hack"
        ]
        
        user_agent_lower: str = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_ua_patterns)
    
    def _detect_unusual_access_times(self, access_times: List[float]) -> bool:
        """
        Detect unusual access patterns (e.g., 3 AM requests)
        """
        if not access_times:
            return False
        
        # Check for access between 2 AM and 4 AM
        for timestamp in access_times[-10:]:  # Last 10 accesses
            hour: int = time.localtime(timestamp).tm_hour
            if 2 <= hour <= 4:
                return True
        
        return False
    
    def analyze_threats(self, ip_address: str, user_agent: str, request_data: str,
                         failed_attempts: int, request_times: List[float]) -> Dict[str, Any]:
        """
        Analyze potential threats
        """
        threats = []
        overall_threat_level: ThreatLevel = ThreatLevel.LOW
        
        # Check various threat patterns
        if self._detect_multiple_failed_attempts(ip_address, failed_attempts):
            threats.append("multiple_failed_attempts")
            overall_threat_level = max(overall_threat_level, ThreatLevel.MEDIUM)
        
        if self._detect_rapid_requests(request_times):
            threats.append("rapid_requests")
            overall_threat_level = max(overall_threat_level, ThreatLevel.HIGH)
        
        if self._detect_suspicious_patterns(user_agent, request_data):
            threats.append("suspicious_patterns")
            overall_threat_level = max(overall_threat_level, ThreatLevel.MEDIUM)
        
        if self._detect_unusual_access_times(request_times):
            threats.append("unusual_access_times")
            overall_threat_level = max(overall_threat_level, ThreatLevel.LOW)
        
        return {
            "threats": threats,
            "threat_level": overall_threat_level,
            "recommendation": self._get_security_recommendation(overall_threat_level)
        }
    
    def _get_security_recommendation(self, threat_level: ThreatLevel) -> str:
        """
        Get security recommendation based on threat level
        """
        recommendations: Dict[ThreatLevel, str] = {
            ThreatLevel.LOW: "Monitor for unusual activity",
            ThreatLevel.MEDIUM: "Increase monitoring and consider rate limiting",
            ThreatLevel.HIGH: "Block temporarily and investigate",
            ThreatLevel.CRITICAL: "Block immediately and alert administrators"
        }
        
        return recommendations.get(threat_level, "Monitor the situation")
    
    def add_alert_handler(self, handler: Callable) -> None:
        """
        Add security alert handler
        """
        self.alert_handlers.append(handler)
    
    def get_security_report(self) -> Dict[str, Any]:
        """
        Get comprehensive security report
        """
        current_time: float = time.time()
        recent_events: List[SecurityEvent] = [
            event for event in self.security_events
            if current_time - event.timestamp < 3600  # Last hour
        ]
        
        return {
            "statistics": self.stats.copy(),
            "recent_events_count": len(recent_events),
            "threat_levels": {
                level.value: len([e for e in recent_events if e.threat_level == level])
                for level in ThreatLevel
            },
            "event_types": {
                event_type.value: len([e for e in recent_events if e.event_type == event_type])
                for event_type in SecurityEventType
            },
            "blocked_requests": len([e for e in recent_events if e.blocked])
        }

class VoiceOSSecurity:
    """Main security coordinator"""
    
    def __init__(self, config: SecurityConfig = None) -> None:
        self.config: SecurityConfig = config or SecurityConfig()
        
        # Initialize components
        self.validator = SecurityValidator()
        self.rate_limiter = RateLimiter(
            self.config.max_requests_per_minute,
            self.config.block_duration
        )
        self.access_controller = AccessController()
        self.monitor = SecurityMonitor()
        
        # Initialize encryption key
        if self.config.enable_encryption:
            self.encryption_key: str = self.config.encryption_key or self._generate_encryption_key()
        
        # Statistics
        self.stats: Dict[str, int] = {
            "total_requests": 0,
            "blocked_requests": 0,
            "validated_inputs": 0,
            "sanitized_outputs": 0
        }
    
    def _generate_encryption_key(self) -> str:
        """
        Generate encryption key
        """
        return secrets.token_urlsafe(32)
    
    def validate_request(self, ip_address: str, user_agent: str, request_data: str,
                        session_id: str = None, required_permission: str = None) -> Dict[str, Any]:
        """
        Comprehensive request validation
        """
        result = {
            "allowed": False,
            "reason": "",
            "threat_level": ThreatLevel.LOW,
            "session_valid": False,
            "rate_limited": False
        }
        
        try:
            self.stats["total_requests"] += 1
            
            # Check IP blocking
            if ip_address in self.config.blocked_ips:
                result["reason"] = "IP address blocked"
                result["threat_level"] = ThreatLevel.HIGH
                return result
            
            # Check rate limiting
            if self.config.enable_rate_limiting:
                rate_check: Dict[str, Any] = self.rate_limiter.check_rate_limit(ip_address)
                if not rate_check["allowed"]:
                    result["rate_limited"] = True
                    result["reason"] = rate_check["reason"]
                    result["threat_level"] = ThreatLevel.MEDIUM
                    return result
            
            # Check session if provided
            if session_id and self.config.enable_access_control:
                session_check: Dict[str, Any] = self.access_controller.validate_session(session_id, required_permission)
                if not session_check["valid"]:
                    result["reason"] = session_check["reason"]
                    result["threat_level"] = ThreatLevel.MEDIUM
                    return result
                else:
                    result["session_valid"] = True
            
            # Validate input
            if self.config.enable_input_validation:
                validation: Dict[str, Any] = self.validator.validate_input(request_data)
                if not validation["valid"]:
                    result["reason"] = f"Input validation failed: {validation['reason']}"
                    result["threat_level"] = ThreatLevel.HIGH
                    
                    # Log security event
                    self.monitor.log_security_event(
                        SecurityEventType.SUSPICIOUS_INPUT,
                        result["threat_level"],
                        ip_address,
                        user_agent,
                        f"Malicious input detected: {validation['reason']}",
                        {"validation_result": validation},
                        block=True
                    )
                    
                    return result
                else:
                    self.stats["validated_inputs"] += 1
            
            # All checks passed
            result["allowed"] = True
            result["reason"] = "Request validated successfully"
            
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            result["reason"] = f"Validation error: {str(e)}"
            result["threat_level"] = ThreatLevel.MEDIUM
        
        return result
    
    def sanitize_response(self, response_data: str, context: str = "text") -> str:
        """
        Sanitize response data
        """
        if self.config.enable_output_sanitization:
            sanitized: str = self.validator.sanitize_output(response_data, context)
            self.stats["sanitized_outputs"] += 1
            return sanitized
        
        return response_data
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data
        """
        if not self.config.enable_encryption:
            return data
        
        try:
            # Simple XOR encryption (in production, use proper encryption)
            key_bytes: bytes = self.encryption_key.encode()
            data_bytes: bytes = data.encode()
            
            encrypted = bytearray()
            for i, byte in enumerate(data_bytes):
                encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
            
            return encrypted.hex()
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return data
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data
        """
        if not self.config.enable_encryption:
            return encrypted_data
        
        try:
            # Simple XOR decryption
            key_bytes: bytes = self.encryption_key.encode()
            encrypted_bytes: bytes = bytes.fromhex(encrypted_data)
            
            decrypted = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
            
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return encrypted_data
    
    def get_security_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive security statistics
        """
        return {
            **self.stats,
            "rate_limiter": self.rate_limiter.get_statistics(),
            "security_monitor": self.monitor.get_security_report(),
            "active_sessions": len(self.access_controller.sessions),
            "blocked_ips": len(self.config.blocked_ips),
            "trusted_ips": len(self.config.trusted_ips)
        }
    
    def block_ip(self, ip_address: str, duration: int = None) -> None:
        """
        Block an IP address
        """
        self.config.blocked_ips.add(ip_address)
        
        if duration:
            # Schedule unblock (in production, use proper scheduling)
            pass
        
        logger.warning(f"Blocked IP address: {ip_address}")
    
    def unblock_ip(self, ip_address: str) -> None:
        """
        Unblock an IP address
        """
        self.config.blocked_ips.discard(ip_address)
        logger.info(f"Unblocked IP address: {ip_address}")
    
    def add_trusted_ip(self, ip_address: str) -> None:
        """
        Add trusted IP address
        """
        self.config.trusted_ips.add(ip_address)
        logger.info(f"Added trusted IP: {ip_address}")
    
    def create_user_session(self, user_id: str, permissions: Set[str] = None) -> str:
        """
        Create user session with permissions
        """
        if not self.config.enable_access_control:
            return "no_session_required"
        
        return self.access_controller.create_session(user_id, permissions)
    
    def add_security_alert_handler(self, handler: Callable) -> None:
        """
        Add security alert handler
        """
        self.monitor.add_alert_handler(handler)
