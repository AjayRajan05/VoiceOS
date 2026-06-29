"""
Prompt Loader Module - Centralized prompt template management
Handles loading, caching, and processing of prompt templates for agents
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PromptTemplate:
    name: str
    content: str
    variables: List[str]
    metadata: Dict[str, Any]
    file_path: str
    last_modified: float
    version: str = "1.0"

@dataclass
class PromptConfig:
    template_dir: str = "agents/roles"
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    auto_reload: bool = True
    variable_delimiter: str = "{{"
    variable_end_delimiter: str = "}}"
    backup_enabled: bool = True

class PromptLoader:
    def __init__(self, config: PromptConfig = None):
        self.config = config or PromptConfig()
        self.template_cache: Dict[str, PromptTemplate] = {}
        self.variable_cache: Dict[str, List[str]] = {}
        self.template_registry: Dict[str, str] = {}  # name -> file_path mapping
        
        # Initialize template directory
        self.template_dir = Path(self.config.template_dir)
        
        # Load initial templates
        self._scan_templates()
        
        # Statistics
        self.stats = {
            "templates_loaded": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "template_updates": 0,
            "variables_extracted": 0
        }
    
    def _scan_templates(self):
        """
        Scan template directory and register all prompt files
        """
        try:
            if not self.template_dir.exists():
                logger.warning(f"Template directory not found: {self.template_dir}")
                return
            
            # Scan for prompt.txt files in role directories
            for role_dir in self.template_dir.iterdir():
                if role_dir.is_dir():
                    prompt_file = role_dir / "prompt.txt"
                    if prompt_file.exists():
                        role_name = role_dir.name
                        self.template_registry[role_name] = str(prompt_file)
                        logger.info(f"Registered template for role: {role_name}")
            
            self.stats["templates_loaded"] = len(self.template_registry)
            
        except Exception as e:
            logger.error(f"Failed to scan templates: {e}")
    
    async def load_prompt(self, role: str, variables: Dict[str, Any] = None) -> Optional[str]:
        """
        Load and render prompt template for a role
        """
        try:
            # Check cache first
            if self.config.cache_enabled:
                cached = self._get_cached_prompt(role)
                if cached:
                    self.stats["cache_hits"] += 1
                    return self._render_template(cached, variables or {})
            
            # Load from file
            template = await self._load_template_from_file(role)
            if not template:
                self.stats["cache_misses"] += 1
                return None
            
            # Cache the template
            if self.config.cache_enabled:
                self._cache_template(template)
            
            self.stats["cache_misses"] += 1
            return self._render_template(template, variables or {})
            
        except Exception as e:
            logger.error(f"Failed to load prompt for role {role}: {e}")
            return None
    
    async def _load_template_from_file(self, role: str) -> Optional[PromptTemplate]:
        """
        Load template from file
        """
        try:
            file_path = self.template_registry.get(role)
            if not file_path or not os.path.exists(file_path):
                logger.error(f"Template file not found for role: {role}")
                return None
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                logger.warning(f"Empty template file for role: {role}")
                return None
            
            # Extract variables
            variables = self._extract_variables(content)
            
            # Get file metadata
            stat = os.stat(file_path)
            
            # Create template object
            template = PromptTemplate(
                name=role,
                content=content,
                variables=variables,
                metadata={
                    "role": role,
                    "file_size": stat.st_size,
                    "encoding": "utf-8"
                },
                file_path=file_path,
                last_modified=stat.st_mtime
            )
            
            self.stats["variables_extracted"] += len(variables)
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to load template from file for role {role}: {e}")
            return None
    
    def _extract_variables(self, content: str) -> List[str]:
        """
        Extract variables from template content
        """
        try:
            # Extract variables between delimiters
            start_delim = self.config.variable_delimiter
            end_delim = self.config.variable_end_delimiter
            
            variables = []
            start = 0
            
            while True:
                start_idx = content.find(start_delim, start)
                if start_idx == -1:
                    break
                
                end_idx = content.find(end_delim, start_idx + len(start_delim))
                if end_idx == -1:
                    break
                
                variable = content[start_idx + len(start_delim):end_idx].strip()
                if variable and variable not in variables:
                    variables.append(variable)
                
                start = end_idx + len(end_delim)
            
            return variables
            
        except Exception as e:
            logger.error(f"Failed to extract variables: {e}")
            return []
    
    def _render_template(self, template: PromptTemplate, variables: Dict[str, Any]) -> str:
        """
        Render template with variables
        """
        try:
            content = template.content
            
            # Replace variables
            for var_name in template.variables:
                var_value = variables.get(var_name, f"{{{{{var_name}}}}}")  # Keep placeholder if not provided
                content = content.replace(f"{{{{{var_name}}}}}", str(var_value))
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            return template.content
    
    def _get_cached_prompt(self, role: str) -> Optional[PromptTemplate]:
        """
        Get cached prompt if valid
        """
        if role not in self.template_cache:
            return None
        
        cached = self.template_cache[role]
        
        # Check if cache is expired
        if time.time() - cached.last_modified > self.config.cache_ttl:
            del self.template_cache[role]
            return None
        
        # Check if file has been modified (auto-reload)
        if self.config.auto_reload:
            try:
                current_mtime = os.path.getmtime(cached.file_path)
                if current_mtime > cached.last_modified:
                    del self.template_cache[role]
                    return None
            except OSError:
                pass
        
        return cached
    
    def _cache_template(self, template: PromptTemplate):
        """
        Cache template
        """
        self.template_cache[template.name] = template
        
        # Limit cache size
        if len(self.template_cache) > 100:
            # Remove oldest entries
            oldest_templates = sorted(
                self.template_cache.items(),
                key=lambda x: x[1].last_modified
            )[:20]
            
            for name, _ in oldest_templates:
                del self.template_cache[name]
    
    async def update_template(self, role: str, content: str, backup: bool = None) -> bool:
        """
        Update template content
        """
        try:
            file_path = self.template_registry.get(role)
            if not file_path:
                logger.error(f"No template file registered for role: {role}")
                return False
            
            # Create backup if enabled
            if (backup if backup is not None else self.config.backup_enabled):
                backup_path = f"{file_path}.backup.{int(time.time())}"
                try:
                    if os.path.exists(file_path):
                        os.rename(file_path, backup_path)
                        logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
            
            # Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update cache
            if role in self.template_cache:
                del self.template_cache[role]
            
            self.stats["template_updates"] += 1
            logger.info(f"Updated template for role: {role}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update template for role {role}: {e}")
            return False
    
    async def create_template(self, role: str, content: str, file_path: str = None) -> bool:
        """
        Create new template
        """
        try:
            if file_path is None:
                role_dir = self.template_dir / role
                role_dir.mkdir(exist_ok=True)
                file_path = str(role_dir / "prompt.txt")
            
            # Write content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Register template
            self.template_registry[role] = file_path
            
            # Update cache
            template = await self._load_template_from_file(role)
            if template and self.config.cache_enabled:
                self._cache_template(template)
            
            self.stats["templates_loaded"] += 1
            logger.info(f"Created new template for role: {role}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create template for role {role}: {e}")
            return False
    
    def list_templates(self) -> List[str]:
        """
        List all available templates
        """
        return list(self.template_registry.keys())
    
    def get_template_info(self, role: str) -> Optional[Dict[str, Any]]:
        """
        Get template information
        """
        template = self._get_cached_prompt(role)
        if not template:
            return None
        
        return {
            "name": template.name,
            "variables": template.variables,
            "file_path": template.file_path,
            "last_modified": template.last_modified,
            "content_length": len(template.content),
            "metadata": template.metadata
        }
    
    def validate_template(self, content: str) -> Dict[str, Any]:
        """
        Validate template content
        """
        try:
            issues = []
            variables = self._extract_variables(content)
            
            # Check for unclosed variables
            open_count = content.count(self.config.variable_delimiter)
            close_count = content.count(self.config.variable_end_delimiter)
            
            if open_count != close_count:
                issues.append(f"Mismatched variable delimiters: {open_count} open, {close_count} close")
            
            # Check for empty variables
            for var in variables:
                if not var.strip():
                    issues.append("Empty variable found")
            
            # Check content length
            if len(content) > 50000:  # 50KB limit
                issues.append("Template content too large (>50KB)")
            
            # Check for required variables (common ones)
            required_vars = ["role", "task", "context"]
            missing_required = [var for var in required_vars if var not in variables]
            if missing_required:
                issues.append(f"Missing recommended variables: {missing_required}")
            
            return {
                "valid": len(issues) == 0,
                "variables": variables,
                "issues": issues,
                "content_length": len(content)
            }
            
        except Exception as e:
            return {
                "valid": False,
                "variables": [],
                "issues": [f"Validation error: {str(e)}"],
                "content_length": len(content) if content else 0
            }
    
    def clear_cache(self):
        """
        Clear template cache
        """
        self.template_cache.clear()
        logger.info("Template cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get loader statistics
        """
        return {
            **self.stats,
            "cache_size": len(self.template_cache),
            "registered_templates": len(self.template_registry),
            "cache_hit_rate": self.stats["cache_hits"] / max(1, self.stats["cache_hits"] + self.stats["cache_misses"])
        }
    
    def export_templates(self, export_path: str) -> bool:
        """
        Export all templates to a JSON file
        """
        try:
            export_data = {}
            
            for role in self.template_registry:
                template = self._get_cached_prompt(role)
                if template:
                    export_data[role] = {
                        "content": template.content,
                        "variables": template.variables,
                        "metadata": template.metadata
                    }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(export_data)} templates to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export templates: {e}")
            return False
    
    async def import_templates(self, import_path: str) -> bool:
        """
        Import templates from a JSON file
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            imported_count = 0
            for role, data in import_data.items():
                if await self.create_template(role, data["content"]):
                    imported_count += 1
            
            logger.info(f"Imported {imported_count} templates from {import_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import templates: {e}")
            return False
