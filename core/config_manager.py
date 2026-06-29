"""
Configuration Manager Module - Centralized configuration management
Handles environment-specific settings, validation, and agent configuration
"""

from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
import time
from enum import Enum

logger: logging.Logger = logging.getLogger(__name__)

class Environment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    STAGING = "staging"

@dataclass
class DistributedConfig:
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "voiceos_tasks"
    task_timeout: float = 120.0
    auto_detect_redis: bool = True

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "voiceos"
    username: str = "voiceos"
    password: str = ""
    ssl_mode: str = "prefer"

@dataclass
class LLMConfig:
    provider: str = "local"
    model_name: str = "mistral-7b-instruct"
    model_path: str = "models/mistral-7b-instruct.gguf"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 30.0
    context_window: int = 8192

@dataclass
class AgentConfig:
    max_concurrent_agents: int = 5
    default_timeout: float = 120.0
    workspace_ttl: int = 3600
    memory_ttl: int = 86400
    enable_caching: bool = True
    cache_size: int = 1000
    safety_level: str = "medium"

@dataclass
class VoiceConfig:
    stt_model: str = "whisper-tiny"
    tts_model: str = "coqui-tts"
    tts_engine: str = "auto"
    sample_rate: int = 16000
    chunk_size: int = 1024
    enable_backchannel: bool = True
    enable_interrupts: bool = True
    max_recording_duration: int = 30

@dataclass
class SecurityConfig:
    enable_authentication: bool = False
    session_timeout: int = 3600
    max_login_attempts: int = 3
    encryption_key: Optional[str] = None
    enable_audit_logging: bool = True
    allowed_hosts: List[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])

@dataclass
class PerformanceConfig:
    enable_monitoring: bool = True
    metrics_retention_days: int = 7
    enable_profiling: bool = False
    max_memory_usage_mb: int = 2048
    cpu_threshold: float = 80.0
    response_time_threshold_ms: float = 1000.0

@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = "logs/voiceos.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    enable_console: bool = True

@dataclass
class VoiceOSConfig:
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    version: str = "1.0.0"
    
    # Component configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    distributed: DistributedConfig = field(default_factory=DistributedConfig)
    
    # Paths
    models_path: str = "models"
    workspace_path: str = "workspace"
    memory_path: str = "memory"
    logs_path: str = "logs"
    config_path: str = "config"
    
    # Feature flags
    enable_workspace_isolation: bool = True
    enable_agent_memory: bool = True
    enable_tool_registry: bool = True
    enable_event_handlers: bool = True
    enable_safety_checks: bool = True
    execution_mode: str = "local"

class ConfigManager:
    def __init__(self, config_file: str = None, environment: Environment = None) -> None:
        self.config_file: str = config_file or "config/voiceos.yaml"
        self.environment: Environment = environment or self._detect_environment()
        self.config = VoiceOSConfig()
        
        # Load configuration
        self._load_configuration()
        
        # Validate configuration
        self._validate_configuration()
        
        # Apply environment overrides
        self._apply_environment_overrides()
        
        # Setup logging
        self._setup_logging()
    
    def _detect_environment(self) -> Environment:
        """
        Detect current environment from environment variables
        """
        env_var: str = os.getenv("VOICEOS_ENV", "").lower()
        
        if env_var == "production":
            return Environment.PRODUCTION
        elif env_var == "testing":
            return Environment.TESTING
        elif env_var == "staging":
            return Environment.STAGING
        else:
            return Environment.DEVELOPMENT
    
    def _load_configuration(self) -> None:
        """
        Load configuration from file
        """
        try:
            config_path = Path(self.config_file)
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    if config_path.suffix.lower() == '.yaml' or config_path.suffix.lower() == '.yml':
                        config_data = yaml.safe_load(f)
                    else:
                        config_data = json.load(f)
                
                # Update config with loaded data
                self._update_config_from_dict(config_data)
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                logger.warning(f"Configuration file not found: {self.config_file}")
                self._create_default_config()
                
        except (IOError, OSError) as e:
            logger.error(f"Failed to read configuration file: {e}")
            self._create_default_config()
        except (yaml.YAMLError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid configuration format: {e}")
            self._create_default_config()
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            self._create_default_config()
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]) -> None:
        """
        Update configuration object from dictionary
        """
        try:
            # Update main config
            if "environment" in config_data:
                self.config.environment = Environment(config_data["environment"])
            
            if "debug" in config_data:
                self.config.debug = config_data["debug"]
            
            if "version" in config_data:
                self.config.version = config_data["version"]
            
            # Update component configs
            if "database" in config_data:
                self._update_dataclass(self.config.database, config_data["database"])
            
            if "llm" in config_data:
                self._update_dataclass(self.config.llm, config_data["llm"])
            
            if "agents" in config_data:
                self._update_dataclass(self.config.agents, config_data["agents"])
            
            if "voice" in config_data:
                self._update_dataclass(self.config.voice, config_data["voice"])
            
            if "security" in config_data:
                self._update_dataclass(self.config.security, config_data["security"])
            
            if "performance" in config_data:
                self._update_dataclass(self.config.performance, config_data["performance"])
            
            if "logging" in config_data:
                self._update_dataclass(self.config.logging, config_data["logging"])

            if "distributed" in config_data:
                self._update_dataclass(self.config.distributed, config_data["distributed"])
            
            # Update paths
            path_keys: List[str] = ["models_path", "workspace_path", "memory_path", "logs_path", "config_path"]
            for key in path_keys:
                if key in config_data:
                    setattr(self.config, key, config_data[key])
            
            # Update feature flags
            feature_keys: List[str] = [
                "enable_workspace_isolation", "enable_agent_memory", 
                "enable_tool_registry", "enable_event_handlers", "enable_safety_checks",
                "execution_mode",
            ]
            for key in feature_keys:
                if key in config_data:
                    setattr(self.config, key, config_data[key])
                    
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Invalid configuration structure: {e}")
        except ValueError as e:
            logger.error(f"Invalid configuration value: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating config: {e}")
    
    def _update_dataclass(self, dataclass_instance, data: Dict[str, Any]) -> None:
        """
        Update dataclass instance from dictionary
        """
        for key, value in data.items():
            if hasattr(dataclass_instance, key):
                setattr(dataclass_instance, key, value)
    
    def _create_default_config(self) -> None:
        """
        Create default configuration file
        """
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            default_config: Dict[str, Any] = asdict(self.config)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(default_config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(default_config, f, indent=2)
            
            logger.info(f"Created default configuration file: {self.config_file}")
            
        except (IOError, OSError) as e:
            logger.error(f"Failed to write configuration file: {e}")
        except (yaml.YAMLError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to serialize configuration: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating default config: {e}")
    
    def _validate_configuration(self) -> None:
        """
        Validate configuration values
        """
        try:
            # Validate paths
            paths_to_validate: List[str] = [
                self.config.models_path,
                self.config.workspace_path,
                self.config.memory_path,
                self.config.logs_path,
                self.config.config_path
            ]
            
            for path in paths_to_validate:
                path_obj = Path(path)
                if not path_obj.exists():
                    path_obj.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path}")
            
            # Validate LLM config
            if self.config.llm.provider == "local" and not self.config.llm.model_path:
                logger.warning("Local LLM provider specified but no model path configured")
            
            # Validate agent config
            if self.config.agents.max_concurrent_agents < 1:
                self.config.agents.max_concurrent_agents = 5
                logger.warning("Invalid max_concurrent_agents, setting to 5")
            
            # Validate voice config
            if self.config.voice.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
                logger.warning(f"Unusual sample rate: {self.config.voice.sample_rate}")
            
            # Validate security config
            if self.config.security.enable_authentication and not self.config.security.encryption_key:
                logger.warning("Authentication enabled but no encryption key configured")
            
        except (IOError, OSError) as e:
            logger.error(f"Failed to create required directories: {e}")
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Invalid configuration attribute: {e}")
        except Exception as e:
            logger.error(f"Unexpected error validating configuration: {e}")
    
    def _apply_environment_overrides(self) -> None:
        """
        Apply environment-specific overrides
        """
        try:
            # Environment-specific settings
            if self.environment == Environment.PRODUCTION:
                self.config.debug = False
                self.config.logging.level = "WARNING"
                self.config.performance.enable_monitoring = True
                self.config.security.enable_authentication = True
                
            elif self.environment == Environment.DEVELOPMENT:
                self.config.debug = True
                self.config.logging.level = "DEBUG"
                self.config.performance.enable_profiling = True
                
            elif self.environment == Environment.TESTING:
                self.config.debug = True
                self.config.logging.level = "INFO"
                self.config.agents.max_concurrent_agents = 2
            
            # Apply environment variable overrides
            env_overrides = {
                "VOICEOS_DEBUG": ("debug", bool),
                "VOICEOS_LOG_LEVEL": ("logging.level", str),
                "VOICEOS_MAX_AGENTS": ("agents.max_concurrent_agents", int),
                "VOICEOS_LLM_MODEL": ("llm.model_name", str),
                "VOICEOS_LLM_PATH": ("llm.model_path", str),
                "VOICEOS_LLM_API_BASE": ("llm.api_base", str),
                "VOICEOS_DB_HOST": ("database.host", str),
                "VOICEOS_DB_PORT": ("database.port", int),
                "VOICEOS_ENABLE_AUTH": ("security.enable_authentication", bool),
                "REDIS_URL": ("distributed.redis_url", str),
                "EXECUTION_MODE": ("execution_mode", str),
            }
            
            for env_var, (config_path, value_type) in env_overrides.items():
                env_value: str | None = os.getenv(env_var)
                if env_value:
                    self._set_nested_value(config_path, self._convert_value(env_value, value_type))
            
            logger.info(f"Applied environment overrides for {self.environment.value}")
            
        except Exception as e:
            logger.error(f"Failed to apply environment overrides: {e}")
    
    def _set_nested_value(self, path: str, value: Any) -> None:
        """
        Set nested configuration value with depth validation
        """
        if not path or not isinstance(path, str):
            raise ValueError("path must be a non-empty string")
        
        keys: List[str] = path.split('.')
        
        if len(keys) > 10:
            raise ValueError(f"Config path too deep (max 10 levels): {len(keys)}")
        
        current: VoiceOSConfig = self.config
        
        try:
            for key in keys[:-1]:
                if not isinstance(key, str) or not key.isidentifier():
                    raise ValueError(f"Invalid config key: {key}")
                current = getattr(current, key)
            
            final_key: str = keys[-1]
            if not isinstance(final_key, str) or not final_key.isidentifier():
                raise ValueError(f"Invalid config key: {final_key}")
            setattr(current, final_key, value)
        except AttributeError as e:
            raise ValueError(f"Invalid config path {path}: {e}")
    
    def _convert_value(self, value: str, value_type: type) -> Any:
        """
        Convert string value to appropriate type
        """
        if value_type == bool:
            return value.lower() in ['true', '1', 'yes', 'on']
        elif value_type == int:
            return int(value)
        elif value_type == float:
            return float(value)
        else:
            return value
    
    def _setup_logging(self) -> None:
        """
        Setup logging based on configuration
        """
        try:
            import logging.config
            
            log_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": self.config.logging.format
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": self.config.logging.level,
                        "formatter": "default",
                        "stream": "ext://sys.stdout"
                    }
                },
                "root": {
                    "level": self.config.logging.level,
                    "handlers": ["console"] if self.config.logging.enable_console else []
                }
            }
            
            # Add file handler if configured
            if self.config.logging.file_path:
                log_path = Path(self.config.logging.file_path)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                log_config["handlers"]["file"] = {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.config.logging.level,
                    "formatter": "default",
                    "filename": str(log_path),
                    "maxBytes": self.config.logging.max_file_size_mb * 1024 * 1024,
                    "backupCount": self.config.logging.backup_count
                }
                
                if "file" not in log_config["root"]["handlers"]:
                    log_config["root"]["handlers"].append("file")
            
            logging.config.dictConfig(log_config)
            logger.info(f"Logging configured with level: {self.config.logging.level}")
            
        except (IOError, OSError) as e:
            logging.basicConfig(level=logging.INFO)
            logger.error(f"Failed to setup logging - file access error: {e}")
        except (KeyError, TypeError, ValueError) as e:
            logging.basicConfig(level=logging.INFO)
            logger.error(f"Invalid logging configuration: {e}")
        except Exception as e:
            logging.basicConfig(level=logging.INFO)
            logger.error(f"Unexpected error setting up logging: {e}")
    
    def get_config(self) -> VoiceOSConfig:
        """
        Get current configuration
        """
        return self.config
    
    def get_agent_config(self, agent_role: str) -> Dict[str, Any]:
        """
        Get configuration for specific agent role
        """
        base_config = {
            "max_steps": 10,
            "timeout": self.config.agents.default_timeout,
            "workspace_ttl": self.config.agents.workspace_ttl,
            "memory_ttl": self.config.agents.memory_ttl,
            "enable_caching": self.config.agents.enable_caching,
            "safety_level": self.config.agents.safety_level
        }
        
        # Role-specific overrides
        role_configs = {
            "researcher": {
                "max_steps": 8,
                "timeout": 180.0,
                "tools": ["web_search", "content_extractor", "summarizer"]
            },
            "developer": {
                "max_steps": 12,
                "timeout": 300.0,
                "tools": ["code_editor", "file_manager", "test_runner"]
            },
            "analyst": {
                "max_steps": 6,
                "timeout": 120.0,
                "tools": ["data_processor", "comparison_engine"]
            }
        }
        
        if agent_role in role_configs:
            base_config.update(role_configs[agent_role])
        
        return base_config
    
    def update_config(self, updates: Dict[str, Any], save: bool = True) -> None:
        """
        Update configuration with new values
        """
        try:
            self._update_config_from_dict(updates)
            self._validate_configuration()
            
            if save:
                self._save_configuration()
            
            logger.info("Configuration updated successfully")
            
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.error(f"Invalid configuration update - invalid structure or value: {e}")
            raise
        except (IOError, OSError) as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating configuration: {e}")
            raise
    
    def _save_configuration(self) -> None:
        """
        Save current configuration to file
        """
        try:
            config_path = Path(self.config_file)
            config_data: Dict[str, Any] = asdict(self.config)
            
            # Convert enum to string
            config_data["environment"] = self.config.environment.value
            
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def reload_configuration(self) -> None:
        """
        Reload configuration from file
        """
        logger.info("Reloading configuration...")
        self._load_configuration()
        self._validate_configuration()
        self._apply_environment_overrides()
        self._setup_logging()
        logger.info("Configuration reloaded successfully")
    
    def export_configuration(self, export_path: str, include_sensitive: bool = False) -> None:
        """
        Export configuration to file
        """
        try:
            config_data: Dict[str, Any] = asdict(self.config)
            
            # Remove sensitive information if requested
            if not include_sensitive:
                sensitive_keys: List[str] = [
                    "database.password",
                    "llm.api_key",
                    "security.encryption_key"
                ]
                
                for key in sensitive_keys:
                    keys: List[str] = key.split('.')
                    self._remove_nested_key(config_data, keys)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                if export_path.endswith('.yaml') or export_path.endswith('.yml'):
                    yaml.dump(config_data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration exported to {export_path}")
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            raise
    
    def _remove_nested_key(self, data: Dict, keys: List[str]) -> None:
        """
        Remove nested key from dictionary
        """
        current = data
        for key in keys[:-1]:
            if key in current:
                current = current[key]
            else:
                return
        
        if keys[-1] in current:
            del current[keys[-1]]
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get environment information
        """
        return {
            "environment": self.environment.value,
            "debug": self.config.debug,
            "version": self.config.version,
            "config_file": self.config_file,
            "feature_flags": {
                "workspace_isolation": self.config.enable_workspace_isolation,
                "agent_memory": self.config.enable_agent_memory,
                "tool_registry": self.config.enable_tool_registry,
                "event_handlers": self.config.enable_event_handlers,
                "safety_checks": self.config.enable_safety_checks
            }
        }
