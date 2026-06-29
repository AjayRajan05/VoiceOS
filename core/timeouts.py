"""
Central timeout configuration
Consolidates all hardcoded timeout values to enable easy tuning and consistency
"""

# Voice pipeline timeouts
VOICE_RECORDING_TIMEOUT = 30.0
VOICE_PROCESSING_TIMEOUT = 60.0
VOICE_RESPONSE_TIMEOUT = 120.0

# CLI timeouts
CLI_INPUT_TIMEOUT = 30.0
CLI_PROCESSING_TIMEOUT = 300.0
CLI_CHECK_INTERVAL = 0.1

# Agent execution timeouts
AGENT_EXECUTION_TIMEOUT = 300.0
AGENT_PLAN_TIMEOUT = 60.0
AGENT_TOOL_TIMEOUT = 120.0
AGENT_STEP_TIMEOUT = 60.0

# HTTP client timeouts
HTTP_REQUEST_TIMEOUT = 10
HTTP_CONNECTION_TIMEOUT = 5
HTTP_READ_TIMEOUT = 30

# LLM service timeouts
LLM_REQUEST_TIMEOUT = 120.0
LLM_STREAMING_TIMEOUT = 300.0
LLM_INFERENCE_TIMEOUT = 600.0

# Worker pool timeouts
WORKER_HEARTBEAT_INTERVAL = 30.0
WORKER_TASK_TIMEOUT = 300.0
WORKER_SHUTDOWN_TIMEOUT = 60.0

# Task queue timeouts
TASK_QUEUE_TIMEOUT = 300.0
TASK_POLLING_INTERVAL = 1.0

# Permission/approval timeouts
APPROVAL_TIMEOUT = 30.0
PERMISSION_CHECK_TIMEOUT = 5.0

# Event processing timeouts
EVENT_PROCESSING_TIMEOUT = 10.0
EVENT_HANDLER_TIMEOUT = 30.0

# Database connection timeouts
DATABASE_CONNECT_TIMEOUT = 5.0
DATABASE_QUERY_TIMEOUT = 30.0

# Distributed system timeouts
REDIS_CONNECT_TIMEOUT = 5.0
REDIS_OPERATION_TIMEOUT = 10.0

# Default retry policy
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 30.0
RETRY_BACKOFF_MULTIPLIER = 2.0

def get_timeout(name: str, default: float = 30.0) -> float:
    """Get timeout value by name with fallback to default.
    
    Args:
        name: Timeout configuration name (e.g., 'AGENT_EXECUTION_TIMEOUT')
        default: Default value if name not found
        
    Returns:
        Timeout value in seconds
    """
    import sys
    module = sys.modules[__name__]
    return getattr(module, name, default)
