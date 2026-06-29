"""
Utility functions for common patterns
Consolidates frequently repeated code patterns into reusable functions
"""

import json
import logging
import yaml
from typing import Any, Dict, Optional, Type, TypeVar, Callable
from pathlib import Path

T = TypeVar('T')

# Logger factory
_loggers: Dict[str, logging.Logger] = {}

def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


# JSON utilities
def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string with fallback.
    
    Args:
        json_str: JSON string to parse
        default: Value to return if parsing fails
        
    Returns:
        Parsed JSON object or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to parse JSON: {e}, returning default")
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely serialize object to JSON string.
    
    Args:
        obj: Object to serialize
        default: Value to return if serialization fails
        
    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(obj, indent=2)
    except (TypeError, ValueError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to serialize to JSON: {e}, returning default")
        return default


def safe_yaml_loads(yaml_str: str, default: Any = None) -> Any:
    """Safely parse YAML string with fallback.
    
    Args:
        yaml_str: YAML string to parse
        default: Value to return if parsing fails
        
    Returns:
        Parsed YAML object or default value
    """
    try:
        return yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to parse YAML: {e}, returning default")
        return default


def safe_yaml_dumps(obj: Any, default: str = "{}") -> str:
    """Safely serialize object to YAML string.
    
    Args:
        obj: Object to serialize
        default: Value to return if serialization fails
        
    Returns:
        YAML string or default value
    """
    try:
        return yaml.dump(obj, default_flow_style=False, indent=2)
    except (TypeError, ValueError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to serialize to YAML: {e}, returning default")
        return default


# Dictionary utilities
def safe_get_nested(obj: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation.
    
    Args:
        obj: Dictionary to query
        path: Dot-separated path (e.g., 'config.logging.level')
        default: Value to return if path doesn't exist
        
    Returns:
        Value at path or default
    """
    try:
        keys = path.split('.')
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current
    except (AttributeError, KeyError, TypeError):
        return default


def safe_set_nested(obj: Dict[str, Any], path: str, value: Any) -> bool:
    """Safely set nested dictionary value using dot notation.
    
    Args:
        obj: Dictionary to update
        path: Dot-separated path (e.g., 'config.logging.level')
        value: Value to set
        
    Returns:
        True if successful, False otherwise
    """
    try:
        keys = path.split('.')
        current = obj
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set value
        current[keys[-1]] = value
        return True
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


# Retry logic
def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    on_error: Optional[Callable] = None,
    **kwargs
) -> Optional[T]:
    """Execute function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        *args: Positional arguments for function
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        on_error: Optional callback on each error
        **kwargs: Keyword arguments for function
        
    Returns:
        Function result or None if all attempts fail
    """
    import time
    
    logger = get_logger(__name__)
    delay = initial_delay
    
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if on_error:
                on_error(attempt, e)
            
            if attempt < max_attempts - 1:
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
            else:
                logger.error(f"All {max_attempts} attempts failed: {e}")
    
    return None


# File utilities
def safe_read_file(path: str, encoding: str = "utf-8", default: str = "") -> str:
    """Safely read file with error handling.
    
    Args:
        path: File path to read
        encoding: Text encoding (default: utf-8)
        default: Value to return if read fails
        
    Returns:
        File content or default value
    """
    try:
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to read file {path}: {e}, returning default")
        return default


def safe_write_file(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Safely write file with error handling.
    
    Args:
        path: File path to write
        content: Content to write
        encoding: Text encoding (default: utf-8)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except (IOError, OSError) as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to write file {path}: {e}")
        return False
