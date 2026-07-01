"""Lifecycle hook names supported by VoiceOS."""

VALID_HOOKS = frozenset(
    {
        "pre_tool_call",
        "post_tool_call",
        "transform_tool_result",
        "transform_llm_output",
        "pre_llm_call",
        "post_llm_call",
        "on_session_start",
        "on_session_end",
        "pre_gateway_dispatch",
        "subagent_start",
        "subagent_stop",
        "tool_verify",
        "gateway:startup",
        "agent:start",
        "agent:end",
    }
)

# Filesystem hooks use event:type strings; map to plugin hook names where useful.
EVENT_ALIASES = {
    "session:start": "on_session_start",
    "session:end": "on_session_end",
    "agent:start": "agent:start",
    "agent:end": "agent:end",
}
