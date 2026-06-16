"""
VoiceOS Event System

This module provides the base Event class for the VoiceOS event system.
Events are used for communication between components in the system.
"""

import time


class Event:
    """
    Base event class for VoiceOS event system.
    
    Events are used to communicate information between different components
    of the VoiceOS system, enabling loose coupling and asynchronous communication.
    
    Attributes:
        type: Event type identifier
        payload: Event data/content
        source: Event source identifier
        timestamp: Event creation timestamp
    """

    def __init__(self, type, payload=None, source=None):
        """
        Initialize an event.
        
        Args:
            type: Event type identifier
            payload (optional): Event data/content
            source (optional): Event source identifier
        """
        self.type = type
        self.payload = payload or {}
        self.source = source
        self.timestamp = time.time()

    @property
    def data(self):
        """Backward-compatible alias for payload."""
        return self.payload