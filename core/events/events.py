class Events:

    MIC_AUDIO = "mic_audio"

    SPEECH_TRANSCRIBED = "speech_transcribed"

    USER_MESSAGE = "user_message"
    SHELL_STATE_CHANGED = "shell_state_changed"

    LLM_DECISION = "llm_decision"

    PERMISSION_REQUEST = "permission_request"

    PERMISSION_GRANTED = "permission_granted"

    PERMISSION_DENIED = "permission_denied"

    TOOL_EXECUTE = "tool_execute"

    TOOL_RESULT = "tool_result"

    ASSISTANT_RESPONSE = "assistant_response"

    TTS_SPEAK = "tts_speak"

    INTERRUPT = "interrupt"

    BACKCHANNEL = "backchannel"

    # New orchestrator events
    ORCHESTRATOR_RESPONSE = "orchestrator_response"
    ORCHESTRATOR_ERROR = "orchestrator_error"
    PERMISSION_REQUESTED = "permission_requested"
    INTERRUPT_REQUESTED = "interrupt_requested"

    # Agent lifecycle events
    AGENT_CREATED = "agent_created"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    # Workspace events
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_CLEANUP = "workspace_cleanup"

    # Task events
    TASK_PLANNED = "task_planned"
    TASK_ROUTED = "task_routed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    EXECUTION_CANCELLED = "execution_cancelled"

    # Subagent delegation events
    SUBAGENT_STARTED = "subagent_started"
    SUBAGENT_PROGRESS = "subagent_progress"
    SUBAGENT_COMPLETED = "subagent_completed"