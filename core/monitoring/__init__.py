"""
VoiceOS Monitoring System

This module contains components for performance monitoring and error recovery.
"""

from .performance_monitor import PerformanceMonitor
from .error_recovery import ErrorRecovery


def get_performance_monitor():
    return PerformanceMonitor()


def get_error_recovery():
    return ErrorRecovery()


__all__ = [
    'PerformanceMonitor',
    'ErrorRecovery',
    'get_performance_monitor',
    'get_error_recovery',
]
