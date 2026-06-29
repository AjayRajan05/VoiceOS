"""
Agent Memory Module - Specialized memory management for agents
Handles conversation history, knowledge base, and agent-specific memory
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from collections import defaultdict, deque
import os

logger = logging.getLogger(__name__)

class MemoryType(Enum):
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    WORKSPACE = "workspace"
    AGENT_STATE = "agent_state"
    USER_PREFERENCE = "user_preference"
    TASK_CONTEXT = "task_context"

class MemoryPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class MemoryEntry:
    id: str
    type: MemoryType
    content: Any
    metadata: Dict[str, Any]
    timestamp: float
    priority: MemoryPriority
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

@dataclass
class MemoryConfig:
    max_entries: int = 10000
    max_conversation_history: int = 100
    default_ttl: int = 86400  # 24 hours
    cleanup_interval: int = 3600  # 1 hour
    persistence_enabled: bool = True
    memory_file: str = "memory/agent_memory.json"
    compression_enabled: bool = True
    index_search_enabled: bool = True

class AgentMemory:
    def __init__(self, agent_id: str, config: MemoryConfig = None):
        self.agent_id = agent_id
        self.config = config or MemoryConfig()
        
        # Memory storage
        self.memories: Dict[str, MemoryEntry] = {}
        self.type_index: Dict[MemoryType, List[str]] = defaultdict(list)
        self.tag_index: Dict[str, List[str]] = defaultdict(list)
        self.priority_queue: deque = deque()
        
        # Conversation history
        self.conversation_history: deque = deque(
            maxlen=self.config.max_conversation_history
        )
        
        # Knowledge base
        self.knowledge_base: Dict[str, Any] = {}
        
        # Statistics
        self.stats = {
            "total_memories": 0,
            "memories_by_type": defaultdict(int),
            "cache_hits": 0,
            "cache_misses": 0,
            "expired_memories": 0,
            "cleanup_runs": 0
        }
        
        # Load existing memories
        if self.config.persistence_enabled:
            self._load_memories()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    def store_memory(self, memory_type: MemoryType, content: Any, 
                    priority: MemoryPriority = MemoryPriority.MEDIUM,
                    tags: List[str] = None, metadata: Dict[str, Any] = None,
                    ttl: int = None) -> str:
        """
        Store a memory entry
        """
        try:
            # Generate unique ID
            memory_id = self._generate_memory_id(content)
            
            # Calculate expiration time
            expires_at = None
            if ttl or self.config.default_ttl:
                ttl = ttl or self.config.default_ttl
                expires_at = time.time() + ttl
            
            # Create memory entry
            memory = MemoryEntry(
                id=memory_id,
                type=memory_type,
                content=content,
                metadata=metadata or {},
                timestamp=time.time(),
                priority=priority,
                tags=tags or [],
                expires_at=expires_at
            )
            
            # Store memory
            self.memories[memory_id] = memory
            
            # Update indexes
            self.type_index[memory_type].append(memory_id)
            for tag in tags or []:
                self.tag_index[tag].append(memory_id)
            
            # Add to priority queue
            self._add_to_priority_queue(memory)
            
            # Update conversation history if applicable
            if memory_type == MemoryType.CONVERSATION:
                self.conversation_history.append(memory)
            
            # Update statistics
            self.stats["total_memories"] += 1
            self.stats["memories_by_type"][memory_type.value] += 1
            
            # Enforce memory limits
            self._enforce_memory_limits()
            
            # Persist if enabled
            if self.config.persistence_enabled:
                self._save_memories_async()
            
            logger.debug(f"Stored memory {memory_id} of type {memory_type.value}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None
    
    def retrieve_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        """
        try:
            memory = self.memories.get(memory_id)
            if memory:
                # Check if expired
                if memory.expires_at and time.time() > memory.expires_at:
                    self._remove_memory(memory_id)
                    return None
                
                # Update access stats
                memory.access_count += 1
                memory.last_accessed = time.time()
                self.stats["cache_hits"] += 1
                
                return memory
            else:
                self.stats["cache_misses"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {e}")
            return None
    
    def search_memories(self, query: str, memory_type: MemoryType = None,
                       tags: List[str] = None, limit: int = 50) -> List[MemoryEntry]:
        """
        Search memories by content, type, and tags
        """
        try:
            results = []
            query_lower = query.lower()
            
            # Filter candidates
            candidates = []
            if memory_type:
                candidates = self.type_index.get(memory_type, [])
            else:
                candidates = list(self.memories.keys())
            
            # Filter by tags if specified
            if tags:
                tag_filtered = set()
                for tag in tags:
                    tag_filtered.update(self.tag_index.get(tag, []))
                candidates = list(set(candidates) & tag_filtered)
            
            # Search content
            for memory_id in candidates:
                memory = self.memories.get(memory_id)
                if not memory:
                    continue
                
                # Check if expired
                if memory.expires_at and time.time() > memory.expires_at:
                    continue
                
                # Simple text search
                content_str = str(memory.content).lower()
                if query_lower in content_str:
                    results.append(memory)
                    if len(results) >= limit:
                        break
            
            # Sort by priority and timestamp
            results.sort(key=lambda m: (m.priority.value, m.timestamp), reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []
    
    def get_conversation_history(self, limit: int = None) -> List[MemoryEntry]:
        """
        Get conversation history
        """
        history = list(self.conversation_history)
        if limit:
            history = history[-limit:]
        return history
    
    def add_conversation_turn(self, user_input: str, agent_response: str, 
                            metadata: Dict[str, Any] = None) -> str:
        """
        Add a conversation turn to memory
        """
        content = {
            "user_input": user_input,
            "agent_response": agent_response,
            "turn_number": len(self.conversation_history) + 1
        }
        
        return self.store_memory(
            MemoryType.CONVERSATION,
            content,
            priority=MemoryPriority.MEDIUM,
            tags=["conversation", "turn"],
            metadata=metadata
        )
    
    def store_knowledge(self, key: str, value: Any, category: str = None,
                       confidence: float = 1.0) -> str:
        """
        Store knowledge in the knowledge base
        """
        content = {
            "key": key,
            "value": value,
            "category": category,
            "confidence": confidence
        }
        
        # Also store in knowledge base dict for quick access
        self.knowledge_base[key] = value
        
        return self.store_memory(
            MemoryType.KNOWLEDGE,
            content,
            priority=MemoryPriority.HIGH,
            tags=["knowledge"] + ([category] if category else []),
            metadata={"confidence": confidence}
        )
    
    def retrieve_knowledge(self, key: str) -> Optional[Any]:
        """
        Retrieve knowledge by key
        """
        # Quick lookup from knowledge base
        if key in self.knowledge_base:
            return self.knowledge_base[key]
        
        # Search memories if not in quick lookup
        memories = self.search_memories(key, MemoryType.KNOWLEDGE, limit=1)
        if memories:
            return memories[0].content.get("value")
        
        return None
    
    def store_agent_state(self, state: Dict[str, Any], state_name: str = None) -> str:
        """
        Store agent state
        """
        return self.store_memory(
            MemoryType.AGENT_STATE,
            state,
            priority=MemoryPriority.HIGH,
            tags=["agent_state"] + ([state_name] if state_name else []),
            metadata={"state_name": state_name}
        )
    
    def get_agent_state(self, state_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Get current or specific agent state
        """
        memories = self.search_memories(
            state_name or "current",
            MemoryType.AGENT_STATE,
            limit=1
        )
        
        if memories:
            return memories[0].content
        
        return None
    
    def store_user_preference(self, key: str, value: Any) -> str:
        """
        Store user preference
        """
        content = {"key": key, "value": value}
        return self.store_memory(
            MemoryType.USER_PREFERENCE,
            content,
            priority=MemoryPriority.HIGH,
            tags=["user_preference", key]
        )
    
    def get_user_preference(self, key: str) -> Optional[Any]:
        """
        Get user preference
        """
        memories = self.search_memories(key, MemoryType.USER_PREFERENCE, limit=1)
        if memories:
            return memories[0].content.get("value")
        return None
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """
        Get memory system summary
        """
        return {
            "agent_id": self.agent_id,
            "total_memories": len(self.memories),
            "memories_by_type": {
                mem_type.value: len(self.type_index.get(mem_type, []))
                for mem_type in MemoryType
            },
            "conversation_history_size": len(self.conversation_history),
            "knowledge_base_size": len(self.knowledge_base),
            "statistics": self.stats.copy()
        }
    
    def clear_memories(self, memory_type: MemoryType = None, tags: List[str] = None):
        """
        Clear memories by type or tags
        """
        to_remove = []
        
        if memory_type:
            to_remove.extend(self.type_index.get(memory_type, []))
        
        if tags:
            tag_filtered = set()
            for tag in tags:
                tag_filtered.update(self.tag_index.get(tag, []))
            to_remove.extend(tag_filtered)
        
        # Remove duplicates and actual memories
        for memory_id in set(to_remove):
            self._remove_memory(memory_id)
        
        logger.info(f"Cleared {len(set(to_remove))} memories")
    
    def _generate_memory_id(self, content: Any) -> str:
        """
        Generate unique memory ID
        """
        content_str = json.dumps(content, sort_keys=True, default=str)
        content_hash = hashlib.md5(content_str.encode()).hexdigest()
        timestamp = str(int(time.time()))
        return f"{self.agent_id}_{content_hash[:8]}_{timestamp}"
    
    def _add_to_priority_queue(self, memory: MemoryEntry):
        """
        Add memory to priority queue for LRU eviction
        """
        self.priority_queue.append(memory.id)
        
        # Limit queue size
        if len(self.priority_queue) > self.config.max_entries:
            # Remove oldest (lowest priority) memories
            while len(self.priority_queue) > self.config.max_entries * 0.8:
                oldest_id = self.priority_queue.popleft()
                if oldest_id in self.memories:
                    self._remove_memory(oldest_id)
    
    def _enforce_memory_limits(self):
        """
        Enforce maximum memory limits across all collections
        """
        # Check overall memory count
        if len(self.memories) >= self.config.max_entries:
            # Remove lowest priority memories
            to_remove = len(self.memories) - int(self.config.max_entries * 0.8)
            removed = 0
            for memory_id in sorted(
                self.memories.keys(),
                key=lambda mid: (
                    self.memories[mid].priority.value if mid in self.memories else 0,
                    self.memories[mid].access_count if mid in self.memories else 0
                )
            ):
                if removed >= to_remove:
                    break
                if memory_id in self.memories:
                    self._remove_memory(memory_id)
                    removed += 1
    
    def _remove_memory(self, memory_id: str):
        """
        Remove a memory from all indexes
        """
        if memory_id not in self.memories:
            return
        
        memory = self.memories[memory_id]
        
        # Remove from main storage
        del self.memories[memory_id]
        
        # Remove from type index
        if memory_id in self.type_index.get(memory.type, []):
            self.type_index[memory.type].remove(memory_id)
        
        # Remove from tag indexes
        for tag in memory.tags:
            if memory_id in self.tag_index.get(tag, []):
                self.tag_index[tag].remove(memory_id)
        
        # Remove from priority queue
        if memory_id in self.priority_queue:
            self.priority_queue.remove(memory_id)
        
        # Remove from conversation history if applicable
        if memory in self.conversation_history:
            self.conversation_history.remove(memory)
        
        self.stats["total_memories"] -= 1
    
    async def _cleanup_loop(self):
        """
        Background cleanup task
        """
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                self._cleanup_expired_memories()
                self.stats["cleanup_runs"] += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    def _cleanup_expired_memories(self):
        """
        Remove expired memories
        """
        current_time = time.time()
        expired = []
        
        for memory_id, memory in self.memories.items():
            if memory.expires_at and current_time > memory.expires_at:
                expired.append(memory_id)
        
        for memory_id in expired:
            self._remove_memory(memory_id)
        
        self.stats["expired_memories"] += len(expired)
        
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired memories")
    
    def _save_memories_async(self):
        """
        Save memories asynchronously
        """
        try:
            # Create background task for saving
            asyncio.create_task(self._save_memories())
        except Exception as e:
            logger.error(f"Failed to start save task: {e}")
    
    async def _save_memories(self):
        """
        Save memories to file
        """
        try:
            os.makedirs(os.path.dirname(self.config.memory_file), exist_ok=True)
            
            save_data = {
                "agent_id": self.agent_id,
                "memories": {
                    memory_id: {
                        "type": memory.type.value,
                        "content": memory.content,
                        "metadata": memory.metadata,
                        "timestamp": memory.timestamp,
                        "priority": memory.priority.value,
                        "tags": memory.tags,
                        "expires_at": memory.expires_at,
                        "access_count": memory.access_count,
                        "last_accessed": memory.last_accessed
                    }
                    for memory_id, memory in self.memories.items()
                },
                "knowledge_base": self.knowledge_base,
                "stats": self.stats
            }
            
            with open(self.config.memory_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")
    
    def _load_memories(self):
        """
        Load memories from file
        """
        try:
            if not os.path.exists(self.config.memory_file):
                return
            
            with open(self.config.memory_file, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            # Load memories
            for memory_id, memory_data in save_data.get("memories", {}).items():
                memory = MemoryEntry(
                    id=memory_id,
                    type=MemoryType(memory_data["type"]),
                    content=memory_data["content"],
                    metadata=memory_data["metadata"],
                    timestamp=memory_data["timestamp"],
                    priority=MemoryPriority(memory_data["priority"]),
                    tags=memory_data["tags"],
                    expires_at=memory_data.get("expires_at"),
                    access_count=memory_data.get("access_count", 0),
                    last_accessed=memory_data.get("last_accessed", time.time())
                )
                
                self.memories[memory_id] = memory
                self.type_index[memory.type].append(memory_id)
                for tag in memory.tags:
                    self.tag_index[tag].append(memory_id)
                self._add_to_priority_queue(memory)
            
            # Load knowledge base
            self.knowledge_base = save_data.get("knowledge_base", {})
            
            # Load stats
            self.stats.update(save_data.get("stats", {}))
            self.stats["total_memories"] = len(self.memories)
            
            logger.info(f"Loaded {len(self.memories)} memories for agent {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")
    
    async def shutdown(self):
        """
        Shutdown memory system
        """
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save final state
        if self.config.persistence_enabled:
            await self._save_memories()
        
        logger.info(f"Memory system shutdown for agent {self.agent_id}")
