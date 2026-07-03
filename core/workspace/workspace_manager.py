"""
Workspace Manager Module - Task isolation and workspace management
Provides isolated environments for agent execution with file management
"""

import os
import shutil
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class WorkspaceConfig:
    workspace_id: str
    agent_name: str
    agent_role: str
    created_at: str
    task_intent: str
    max_size_mb: int = 100
    auto_cleanup: bool = True
    ttl_hours: int = 24

@dataclass
class FileMetadata:
    filename: str
    filepath: str
    size_bytes: int
    created_at: str
    modified_at: str
    file_type: str
    checksum: str

class WorkspaceManager:
    def __init__(self, base_path: str = "workspace"):
        self.base_path = base_path
        self.active_workspaces = {}
        self.workspace_metadata = {}
        
        # Ensure base workspace directory exists
        os.makedirs(self.base_path, exist_ok=True)
        
        # Clean up expired workspaces on startup
        self._cleanup_expired_workspaces()
    
    async def create_workspace(self, workspace_id: str, agent_config: Any) -> 'Workspace':
        """
        Create a new isolated workspace for agent execution
        """
        try:
            # Create workspace directory
            workspace_path = os.path.join(self.base_path, workspace_id)
            os.makedirs(workspace_path, exist_ok=True)
            
            # Create subdirectories
            subdirs = ["files", "output", "temp", "logs", "cache"]
            for subdir in subdirs:
                os.makedirs(os.path.join(workspace_path, subdir), exist_ok=True)
            
            # Create workspace configuration
            config = WorkspaceConfig(
                workspace_id=workspace_id,
                agent_name=getattr(agent_config, 'name', 'unknown'),
                agent_role=getattr(agent_config, 'role', 'unknown'),
                created_at=str(int(time.time())),
                task_intent=getattr(agent_config, 'intent', 'unknown'),
                max_size_mb=getattr(agent_config, 'max_workspace_size_mb', 100),
                auto_cleanup=getattr(agent_config, 'auto_cleanup', True),
                ttl_hours=getattr(agent_config, 'ttl_hours', 24)
            )
            
            # Save workspace metadata
            metadata_path = os.path.join(workspace_path, "workspace.json")
            with open(metadata_path, 'w') as f:
                json.dump(asdict(config), f, indent=2)
            
            # Create workspace object
            workspace = Workspace(
                workspace_id=workspace_id,
                path=workspace_path,
                config=config,
                manager=self
            )
            
            # Track active workspace
            self.active_workspaces[workspace_id] = workspace
            self.workspace_metadata[workspace_id] = config
            
            logger.info(f"Created workspace: {workspace_id}")
            return workspace
            
        except Exception as e:
            logger.error(f"Failed to create workspace {workspace_id}: {e}")
            raise
    
    async def get_workspace(self, workspace_id: str) -> Optional['Workspace']:
        """
        Get existing workspace by ID
        """
        if workspace_id in self.active_workspaces:
            return self.active_workspaces[workspace_id]
        
        # Try to load from disk
        workspace_path = os.path.join(self.base_path, workspace_id)
        if os.path.exists(workspace_path):
            try:
                # Load metadata
                metadata_path = os.path.join(workspace_path, "workspace.json")
                with open(metadata_path, 'r') as f:
                    config_data = json.load(f)
                
                config = WorkspaceConfig(**config_data)
                
                workspace = Workspace(
                    workspace_id=workspace_id,
                    path=workspace_path,
                    config=config,
                    manager=self
                )
                
                self.active_workspaces[workspace_id] = workspace
                self.workspace_metadata[workspace_id] = config
                
                return workspace
                
            except Exception as e:
                logger.error(f"Failed to load workspace {workspace_id}: {e}")
        
        return None
    
    async def cleanup_workspace(self, workspace_id: str):
        """
        Clean up and remove workspace
        """
        try:
            workspace = await self.get_workspace(workspace_id)
            if workspace:
                await workspace.cleanup()
            
            # Remove from active workspaces
            self.active_workspaces.pop(workspace_id, None)
            self.workspace_metadata.pop(workspace_id, None)
            
            # Remove directory if it exists
            workspace_path = os.path.join(self.base_path, workspace_id)
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path)
            
            logger.info(f"Cleaned up workspace: {workspace_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup workspace {workspace_id}: {e}")
    
    def _cleanup_expired_workspaces(self):
        """
        Clean up workspaces that have expired
        """
        try:
            current_time = time.time()
            
            for workspace_name in os.listdir(self.base_path):
                workspace_path = os.path.join(self.base_path, workspace_name)
                
                if not os.path.isdir(workspace_path):
                    continue
                
                # Check metadata
                metadata_path = os.path.join(workspace_path, "workspace.json")
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as f:
                            config_data = json.load(f)
                        
                        created_at = int(config_data.get('created_at', 0))
                        ttl_hours = config_data.get('ttl_hours', 24)
                        
                        # Check if expired
                        if current_time - created_at > ttl_hours * 3600:
                            logger.info(f"Cleaning up expired workspace: {workspace_name}")
                            shutil.rmtree(workspace_path)
                            
                    except Exception as e:
                        logger.warning(f"Failed to check workspace {workspace_name}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to cleanup expired workspaces: {e}")
    
    def get_workspace_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all workspaces
        """
        workspaces = []
        
        for workspace_id, config in self.workspace_metadata.items():
            workspaces.append({
                "workspace_id": workspace_id,
                "agent_name": config.agent_name,
                "agent_role": config.agent_role,
                "created_at": config.created_at,
                "task_intent": config.task_intent,
                "active": workspace_id in self.active_workspaces
            })
        
        return workspaces
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """
        Get workspace statistics
        """
        total_size = 0
        active_count = len(self.active_workspaces)
        
        for workspace_id in self.active_workspaces:
            workspace_path = os.path.join(self.base_path, workspace_id)
            if os.path.exists(workspace_path):
                total_size += self._get_directory_size(workspace_path)
        
        return {
            "active_workspaces": active_count,
            "total_workspaces": len(self.workspace_metadata),
            "total_size_mb": total_size / (1024 * 1024),
            "base_path": self.base_path
        }
    
    def _get_directory_size(self, path: str) -> int:
        """
        Get total size of directory in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception:
            pass
        return total_size

class Workspace:
    def __init__(self, workspace_id: str, path: str, config: WorkspaceConfig, manager: WorkspaceManager):
        self.workspace_id = workspace_id
        self.path = path
        self.config = config
        self.manager = manager
        
        # Subdirectory paths
        self.files_path = os.path.join(path, "files")
        self.output_path = os.path.join(path, "output")
        self.temp_path = os.path.join(path, "temp")
        self.logs_path = os.path.join(path, "logs")
        self.cache_path = os.path.join(path, "cache")
        
        # File tracking
        self.files = {}
        self._load_existing_files()
    
    def _load_existing_files(self):
        """
        Load existing files in workspace
        """
        try:
            for root, dirs, filenames in os.walk(self.files_path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.files_path)
                    
                    stat = os.stat(filepath)
                    file_meta = FileMetadata(
                        filename=filename,
                        filepath=rel_path,
                        size_bytes=stat.st_size,
                        created_at=str(int(stat.st_ctime)),
                        modified_at=str(int(stat.st_mtime)),
                        file_type=self._get_file_type(filename),
                        checksum=self._calculate_checksum(filepath)
                    )
                    
                    self.files[rel_path] = file_meta
                    
        except Exception as e:
            logger.error(f"Failed to load existing files: {e}")
    
    async def write_file(self, filename: str, content: str, directory: str = "files") -> str:
        """
        Write file to workspace
        """
        try:
            target_dir = getattr(self, f"{directory}_path")
            filepath = os.path.join(target_dir, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Write content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update file metadata
            rel_path = os.path.relpath(filepath, self.files_path)
            stat = os.stat(filepath)
            
            self.files[rel_path] = FileMetadata(
                filename=filename,
                filepath=rel_path,
                size_bytes=stat.st_size,
                created_at=str(int(stat.st_ctime)),
                modified_at=str(int(stat.st_mtime)),
                file_type=self._get_file_type(filename),
                checksum=self._calculate_checksum(filepath)
            )
            
            logger.info(f"Wrote file: {filename} to workspace {self.workspace_id}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to write file {filename}: {e}")
            raise
    
    async def read_file(self, filename: str, directory: str = "files") -> str:
        """
        Read file from workspace
        """
        try:
            target_dir = getattr(self, f"{directory}_path")
            filepath = os.path.join(target_dir, filename)
            
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filename}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to read file {filename}: {e}")
            raise
    
    async def delete_file(self, filename: str, directory: str = "files") -> bool:
        """
        Delete file from workspace
        """
        try:
            target_dir = getattr(self, f"{directory}_path")
            filepath = os.path.join(target_dir, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                
                # Remove from tracking
                rel_path = os.path.relpath(filepath, self.files_path)
                self.files.pop(rel_path, None)
                
                logger.info(f"Deleted file: {filename} from workspace {self.workspace_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file {filename}: {e}")
            return False
    
    async def list_files(self, directory: str = "files") -> List[str]:
        """
        List files in workspace directory
        """
        try:
            target_dir = getattr(self, f"{directory}_path")
            files = []
            
            for root, dirs, filenames in os.walk(target_dir):
                for filename in filenames:
                    rel_path = os.path.relpath(os.path.join(root, filename), target_dir)
                    files.append(rel_path)
            
            return sorted(files)
            
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []
    
    async def get_file_info(self, filename: str, directory: str = "files") -> Optional[FileMetadata]:
        """
        Get file metadata
        """
        rel_path = filename if directory == "files" else f"{directory}/{filename}"
        return self.files.get(rel_path)
    
    async def cleanup(self):
        """
        Clean up workspace resources
        """
        try:
            # Clear temp directory
            if os.path.exists(self.temp_path):
                shutil.rmtree(self.temp_path)
                os.makedirs(self.temp_path, exist_ok=True)
            
            # Clear cache directory
            if os.path.exists(self.cache_path):
                shutil.rmtree(self.cache_path)
                os.makedirs(self.cache_path, exist_ok=True)
            
            logger.info(f"Cleaned up workspace: {self.workspace_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup workspace {self.workspace_id}: {e}")
    
    def _get_file_type(self, filename: str) -> str:
        """
        Get file type from extension
        """
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            '.txt': 'text',
            '.py': 'python',
            '.js': 'javascript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.csv': 'csv',
            '.xml': 'xml'
        }
        return type_map.get(ext, 'unknown')
    
    def _calculate_checksum(self, filepath: str) -> str:
        """
        Calculate simple file checksum
        """
        try:
            import hashlib
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return "unknown"
    
    def get_size_info(self) -> Dict[str, Any]:
        """
        Get workspace size information
        """
        total_size = 0
        
        for root, dirs, filenames in os.walk(self.path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        
        return {
            "workspace_id": self.workspace_id,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "file_count": len(self.files),
            "max_size_mb": self.config.max_size_mb,
            "usage_percentage": (total_size / (1024 * 1024)) / self.config.max_size_mb * 100
        }
