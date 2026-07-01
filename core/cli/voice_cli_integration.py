"""
Voice + CLI Integration Module - Unified interface for VoiceOS
Provides seamless switching between voice and CLI interaction modes
"""

import asyncio
import logging
import queue
import threading
from asyncio import Future
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import time

from core.events.event_bus import EventBus
from core.events.events import Events
from core.event import Event
from core.orchestrator import Orchestrator
from core.cli.console import VoiceConsole

logger: logging.Logger = logging.getLogger(__name__)

class InteractionMode(Enum):
    VOICE = "voice"
    CLI = "cli"
    HYBRID = "hybrid"

@dataclass
class InteractionConfig:
    default_mode: InteractionMode = InteractionMode.HYBRID
    enable_voice_interrupts: bool = True
    enable_cli_interrupts: bool = True
    voice_timeout: float = 30.0
    cli_prompt: str = ""  # set at runtime via VoiceConsole.PROMPT
    show_voice_indicators: bool = True
    auto_switch_to_voice: bool = False

class VoiceCLIIntegration:
    def __init__(self, event_bus: EventBus, orchestrator: Orchestrator, 
                 config: InteractionConfig = None) -> None:
        self.event_bus: EventBus = event_bus
        self.orchestrator: Orchestrator = orchestrator
        self.config: InteractionConfig = config or InteractionConfig()
        
        # Interaction state
        self.current_mode: InteractionMode = self.config.default_mode
        self.voice_active = False
        self.cli_active = False
        self.current_input: str = ""
        
        # Control flags
        self.running = False
        self.interrupt_requested = False
        self._input_queue: queue.Queue[str] = queue.Queue()
        self._input_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.mode_change_callbacks: List[Callable] = []
        
        # Statistics
        self.stats: Dict[str, int] = {
            "voice_interactions": 0,
            "cli_interactions": 0,
            "interrupts": 0,
            "mode_switches": 0,
            "total_interactions": 0
        }
    
    async def start(self) -> None:
        """
        Start the unified interaction system
        """
        self.running = True
        logger.info(f"Starting Voice+CLI Integration in {self.current_mode.value} mode")
        
        # Setup event handlers
        self._setup_event_handlers()
        
        # Start interaction loop
        await self._interaction_loop()
    
    def _setup_event_handlers(self) -> None:
        """
        Setup event bus subscriptions
        """
        self.event_bus.subscribe(Events.INTERRUPT_REQUESTED, self._handle_interrupt)
    
    async def _interaction_loop(self) -> None:
        """
        Main interaction loop handling both voice and CLI
        """
        try:
            while self.running:
                if self.current_mode == InteractionMode.VOICE:
                    await self._voice_interaction_loop()
                elif self.current_mode == InteractionMode.CLI:
                    await self._cli_interaction_loop()
                else:  # HYBRID
                    await self._hybrid_interaction_loop()
                
                await asyncio.sleep(0.1)  # Prevent busy waiting
                
        except asyncio.CancelledError:
            logger.info("Interaction loop cancelled")
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Connection error in interaction loop: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in interaction loop: {e}")
        finally:
            self.running = False
    
    async def _voice_interaction_loop(self) -> None:
        """
        Voice-only interaction loop
        """
        if not self.voice_active:
            logger.info("Voice mode activated")
            self.voice_active = True
            self._notify_mode_change(InteractionMode.VOICE)
        
        # In voice mode, we wait for voice input events
        # The actual voice processing is handled by the STT system
        await asyncio.sleep(0.1)
    
    async def _cli_interaction_loop(self) -> None:
        """
        CLI-only interaction loop
        """
        if not self.cli_active:
            VoiceConsole.info("CLI mode active")
            self.cli_active = True
            self._notify_mode_change(InteractionMode.CLI)
        
        try:
            user_input = await self._get_cli_input_nonblocking()
            if user_input:
                await self._process_cli_input(user_input)
                self.stats["cli_interactions"] += 1
                self.stats["total_interactions"] += 1
        except EOFError:
            logger.info("CLI input ended")
            self.running = False
        except KeyboardInterrupt:
            logger.info("CLI interrupt received")
            await self._handle_keyboard_interrupt()
    
    async def _hybrid_interaction_loop(self) -> None:
        """
        Hybrid interaction loop supporting both voice and CLI
        """
        if not (self.voice_active and self.cli_active):
            VoiceConsole.info("Hybrid mode: voice + CLI")
            self.voice_active = True
            self.cli_active = True
            self._notify_mode_change(InteractionMode.HYBRID)
        
        # In hybrid mode, we check for CLI input while also listening for voice
        try:
            # Non-blocking CLI input check
            user_input: str | None = await self._get_cli_input_nonblocking()
            
            if user_input:
                await self._process_cli_input(user_input)
                self.stats["cli_interactions"] += 1
                self.stats["total_interactions"] += 1
            
        except (ValueError, KeyError) as e:
            logger.debug(f"Invalid CLI input: {e}")
        except Exception as e:
            logger.debug(f"CLI input processing error: {e}")
        
        # Voice input is handled via events
        await asyncio.sleep(0.1)
    
    async def _get_cli_input_nonblocking(self) -> Optional[str]:
        """
        Get CLI input without blocking
        """
        self._ensure_input_thread()
        try:
            user_input = self._input_queue.get_nowait()
            if user_input is None:
                self.running = False
                return None
            return user_input.strip() if user_input else None
        except queue.Empty:
            return None

    def _ensure_input_thread(self) -> None:
        if self._input_thread and self._input_thread.is_alive():
            return
        self._input_thread = threading.Thread(target=self._cli_input_thread, daemon=True)
        self._input_thread.start()

    def _cli_input_thread(self) -> None:
        while self.running:
            try:
                user_input = VoiceConsole.prompt(self.config.cli_prompt or None)
                self._input_queue.put(user_input)
                if user_input is None:
                    break
            except EOFError:
                self._input_queue.put(None)
                break
            except Exception as e:
                logger.error(f"CLI input thread error: {e}")
                break
    
    async def _process_cli_input(self, user_input: str) -> None | str:
        """
        Process CLI input through the orchestrator
        """
        # Handle special CLI commands
        if user_input.lower() in ['quit', 'exit']:
            self.running = False
            return
        elif user_input.lower() == 'voice':
            await self.switch_mode(InteractionMode.VOICE)
            return
        elif user_input.lower() == 'cli':
            await self.switch_mode(InteractionMode.CLI)
            return
        elif user_input.lower() == 'hybrid':
            await self.switch_mode(InteractionMode.HYBRID)
            return
        elif user_input.lower() == 'help':
            self._show_help()
            return
        elif user_input.lower() == 'status':
            await self._show_status()
            return
        elif user_input.lower() == 'mode':
            VoiceConsole.info(f"Current mode: {self.current_mode.value}")
            return
        
        VoiceConsole.flow("Processing", user_input[:80])
        try:
            result = await self.orchestrator.process_user_input(user_input)
            response_text = self._format_result(result)
            VoiceConsole.response(response_text)
            await self.event_bus.publish(Event(
                Events.ORCHESTRATOR_RESPONSE,
                {"text": response_text, "source": "cli"},
                "voice_cli_integration"
            ))
            return response_text
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Invalid CLI input structure: {e}")
            VoiceConsole.error(f"Input error: {e}")
            return ""
        except asyncio.TimeoutError as e:
            logger.warning(f"CLI processing timeout: {e}")
            VoiceConsole.error("Processing timeout")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error in CLI processing: {e}")
            return ""
    
    async def _handle_voice_input(self, event: Event) -> None:
        """Track voice stats only; orchestrator handles SPEECH_TRANSCRIBED."""
        user_input = event.payload.get("text", "")
        if not user_input.strip():
            return
        if self.config.show_voice_indicators:
            VoiceConsole.voice(user_input)
        self.stats["voice_interactions"] += 1
        self.stats["total_interactions"] += 1
    
    async def _handle_interrupt(self, event: Event) -> None:
        """
        Handle interrupt requests
        """
        reason = event.payload.get("reason", "User interrupt")
        logger.info(f"Interrupt received: {reason}")
        
        self.interrupt_requested = True
        self.stats["interrupts"] += 1
        
        # Cancel current operations
        if self.orchestrator.current_execution:
            await self.orchestrator._handle_interrupt(event)
    
    async def _handle_keyboard_interrupt(self) -> None:
        """
        Handle keyboard interrupt (Ctrl+C)
        """
        logger.info("Keyboard interrupt received")
        
        if self.current_mode == InteractionMode.HYBRID:
            # In hybrid mode, switch to CLI mode
            await self.switch_mode(InteractionMode.CLI)
        else:
            # In single mode, handle as interrupt
            await self._handle_interrupt(Event(
                Events.INTERRUPT_REQUESTED,
                {"reason": "Keyboard interrupt"},
                "voice_cli_integration"
            ))
    
    async def switch_mode(self, new_mode: InteractionMode) -> None:
        """
        Switch interaction mode
        """
        if new_mode == self.current_mode:
            return
        
        old_mode: InteractionMode = self.current_mode
        self.current_mode: InteractionMode = new_mode
        self.stats["mode_switches"] += 1
        
        logger.info(f"Switched from {old_mode.value} to {new_mode.value} mode")
        self._notify_mode_change(new_mode)
        
        # Update active states
        if new_mode == InteractionMode.VOICE:
            self.cli_active = False
        elif new_mode == InteractionMode.CLI:
            self.voice_active = False
        else:  # HYBRID
            self.voice_active = True
            self.cli_active = True
    
    def _notify_mode_change(self, new_mode: InteractionMode) -> None:
        """
        Notify callbacks of mode change
        """
        for callback in self.mode_change_callbacks:
            try:
                callback(self.current_mode, new_mode)
            except TypeError as e:
                logger.error(f"Invalid callback signature: {e}")
            except Exception as e:
                logger.warning(f"Mode change callback error: {e}")
    
    def _show_help(self) -> None:
        VoiceConsole.section("VoiceOS CLI Help")
        help_lines: List[str] = [
            f"Mode: {self.current_mode.value}",
            "",
            "Commands:",
            "  help     - this screen",
            "  status   - system metrics",
            "  mode     - show interaction mode",
            "  voice    - voice-only mode",
            "  cli      - terminal-only mode",
            "  hybrid   - voice + terminal",
            "  quit     - exit VoiceOS",
            "",
            "Examples:",
            '  open chrome',
            '  type hello in notepad',
            '  research reinforcement learning',
            "",
            "Interrupt: Ctrl+C or say stop/cancel",
            "",
            "Session shell (when enabled):",
            "  Say wake phrase before commands (default: hey voiceos)",
            "  continue what we were doing - resume last session",
            "  new conversation - reset session history",
        ]
        for line in help_lines:
            if line.startswith("  ") and not line.startswith("  help"):
                VoiceConsole.dim(line)
            elif line.endswith(":"):
                VoiceConsole.info(line)
            else:
                print(line)
    
    async def _show_status(self) -> None:
        try:
            health: Dict[str, Any] = await self.orchestrator.health_check()
            metrics: Dict[str, Any] = self.orchestrator.get_metrics()
            VoiceConsole.section("VoiceOS Status")
            VoiceConsole.info(f"Mode: {self.current_mode.value}")
            VoiceConsole.info(f"Health: {health['status']}")
            VoiceConsole.dim(f"Requests: {metrics['total_requests']} | Success: {metrics['success_rate']:.1%}")
            VoiceConsole.dim(
                f"Interactions - total: {self.stats['total_interactions']} | "
                f"voice: {self.stats['voice_interactions']} | cli: {self.stats['cli_interactions']}"
            )
        except (KeyError, AttributeError) as e:
            VoiceConsole.error(f"Status data error: {e}")
        except Exception as e:
            VoiceConsole.error(f"Status display error: {e}")
    
    def _format_result(self, result: Any) -> str:
        if hasattr(result, "result"):
            return str(result.result)
        if hasattr(result, "final_result"):
            return str(result.final_result)
        return str(result)

    def add_mode_change_callback(self, callback: Callable) -> None:
        """
        Add callback for mode changes
        """
        self.mode_change_callbacks.append(callback)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get interaction statistics
        """
        return {
            **self.stats,
            "current_mode": self.current_mode.value,
            "voice_active": self.voice_active,
            "cli_active": self.cli_active,
            "running": self.running
        }
    
    def reset_statistics(self) -> None:
        """
        Reset interaction statistics
        """
        self.stats: Dict[str, int] = {
            "voice_interactions": 0,
            "cli_interactions": 0,
            "interrupts": 0,
            "mode_switches": 0,
            "total_interactions": 0
        }
    
    async def stop(self) -> None:
        """
        Stop the interaction system
        """
        self.running = False
        self.voice_active = False
        self.cli_active = False
        logger.info("Voice+CLI Integration stopped")


def get_voice_cli(event_bus, orchestrator, config=None) -> VoiceCLIIntegration:
    return VoiceCLIIntegration(event_bus, orchestrator, config)
