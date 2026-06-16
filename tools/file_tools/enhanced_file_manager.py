"""
Enhanced File Manager - Safe workspace file operations for VoiceOS
Maintains VoiceOS security boundaries while leveraging imported capabilities
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

"""
VoiceOS Tools - Native implementation

This module provides native VoiceOS tools for file operations with
workspace isolation and permission-based security.

Classes:
    EnhancedFileManager: Safe file operations within workspace boundaries
"""

import os

from core.config import config
from permissions.permission_engine import PermissionLevel, check_permission
from tools.workspace_paths import resolve_within_workspace, assert_within_workspace


class EnhancedFileManager:
    """
    Safe wrapper for file operations with workspace restrictions and logging.
    
    This class provides secure file operations confined to a specified workspace
    directory, ensuring that all file access remains within approved boundaries.
    All operations are logged for security auditing.
    
    Attributes:
        workspace_root (Path): Root directory for all file operations
        logger (logging.Logger): Logger for operation tracking
        max_file_size_mb (int): Maximum allowed file size in MB
    
    Args:
        workspace_root (Optional[str]): Path to workspace directory.
            Defaults to project_root/workspace if not specified.
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else config.project_root / "workspace"
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve path within workspace bounds.
        
        Ensures that the provided path is safe and within the workspace
        directory to prevent directory traversal attacks.
        
        Args:
            path (str): File path to validate
            
        Returns:
            Path: Resolved absolute path within workspace
            
        Raises:
            PermissionError: If path is outside workspace bounds
            ValueError: If path is invalid or malformed
        """
        try:
            resolved_path = resolve_within_workspace(self.workspace_root, path)
            assert_within_workspace(self.workspace_root, resolved_path)
            return resolved_path
        except PermissionError:
            raise
        except Exception as e:
            self.logger.error(f"Path validation failed for {path}: {e}")
            raise ValueError(f"Invalid path: {e}")
    
    def _log_operation(self, operation: str, path: str, result: Any, error: Optional[str] = None):
        """
        Log all file operations for security auditing.
        
        Creates detailed log entries for all file operations including
        timestamps, operation types, and results.
        
        Args:
            operation (str): Type of operation (read, write, delete, etc.)
            path (str): File path that was operated on
            result (Any): Operation result or status
            error (Optional[str]): Error message if operation failed
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
            "result": str(result)[:200],  # Truncate long results
            "error": error
        }
        
        log_file = self.workspace_root / "logs" / "file_operations.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")
    
    @check_permission(PermissionLevel.LOW)
    def read_file(self, path: str) -> str:
        """
        Safely read file within workspace.
        
        Reads the contents of a file after validating that the path is
        within workspace bounds and the file exists.
        
        Args:
            path (str): Relative path to file within workspace
            
        Returns:
            str: File contents as UTF-8 text
            
        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If user lacks read permissions
            ValueError: If path is outside workspace
        """
        try:
            validated_path = self._validate_path(path)
            
            if not validated_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            # VoiceOS native file operation
            with open(str(validated_path), 'r', encoding='utf-8') as f:
                content = f.read()
            
            self._log_operation("read_file", path, "success")
            return content
            
        except Exception as e:
            self._log_operation("read_file", path, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.MEDIUM)
    def write_file(self, path: str, content: str) -> str:
        """
        Safely write file within workspace.
        
        Writes content to a file after validating the path is within
        workspace bounds. Creates parent directories if needed.
        
        Args:
            path (str): Relative path to file within workspace
            content (str): Content to write to file
            
        Returns:
            str: Success message with file path
            
        Raises:
            PermissionError: If user lacks write permissions
            ValueError: If path is outside workspace
        """
        try:
            validated_path = self._validate_path(path)
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            
            # VoiceOS native file operation
            with open(str(validated_path), 'w', encoding='utf-8') as f:
                f.write(content)
            
            result = f"File written to {validated_path}"
            
            self._log_operation("write_file", path, "success")
            return f"File written to {path}"
            
        except Exception as e:
            self._log_operation("write_file", path, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.MEDIUM)
    def create_file(self, path: str) -> str:
        """
        Create empty file within workspace.
        
        Creates an empty file at the specified path after validating
        that the path is within workspace bounds.
        
        Args:
            path (str): Relative path to file within workspace
            
        Returns:
            str: Success message with file path
            
        Raises:
            PermissionError: If user lacks write permissions
            ValueError: If path is outside workspace
        """
        try:
            validated_path = self._validate_path(path)
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            
            validated_path.touch()
            
            self._log_operation("create_file", path, "success")
            return f"File created at {path}"
            
        except Exception as e:
            self._log_operation("create_file", path, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.HIGH)
    def delete_file(self, path: str) -> str:
        """
        Delete file within workspace (requires high permission).
        
        Deletes a file after validating that the path is within
        workspace bounds and the file exists.
        
        Args:
            path (str): Relative path to file within workspace
            
        Returns:
            str: Success message with file path
            
        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If user lacks delete permissions
            ValueError: If path is outside workspace
        """
        try:
            validated_path = self._validate_path(path)
            
            if not validated_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            validated_path.unlink()
            
            self._log_operation("delete_file", path, "success")
            return f"File deleted: {path}"
            
        except Exception as e:
            self._log_operation("delete_file", path, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def list_directory(self, path: str = ".") -> List[Dict[str, Any]]:
        """
        List directory contents within workspace.
        
        Lists all files and directories in the specified path after
        validating that the path is within workspace bounds.
        
        Args:
            path (str): Relative path to directory within workspace.
                Defaults to workspace root.
            
        Returns:
            List[Dict[str, Any]]: List of directory items with metadata
            
        Raises:
            NotADirectoryError: If path is not a directory
            PermissionError: If user lacks read permissions
            ValueError: If path is outside workspace
        """
        try:
            validated_path = self._validate_path(path)
            
            if not validated_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {path}")
            
            items = []
            for item in validated_path.iterdir():
                if item.name == "logs":
                    continue
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            self._log_operation("list_directory", path, f"found {len(items)} items")
            return items
            
        except Exception as e:
            self._log_operation("list_directory", path, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def file_exists(self, path: str) -> bool:
        """
        Check if file exists within workspace.
        
        Checks if a file exists at the specified path after validating
        that the path is within workspace bounds.
        
        Args:
            path (str): Relative path to file within workspace
            
        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            validated_path = self._validate_path(path)
            return validated_path.exists()
            
        except Exception as e:
            self._log_operation("file_exists", path, "failed", str(e))
            return False


# Global instance for tool registry
enhanced_file_manager = EnhancedFileManager()
