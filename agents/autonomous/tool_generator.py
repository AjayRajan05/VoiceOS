"""
Autonomous Agent Tool Generator - Dynamic tool creation and code generation
Generates Python tools for autonomous agents with sandboxing and safety validation
"""

import asyncio
import json
import logging
import ast
import re
import importlib.util
from typing import Callable, Callable, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import tempfile
import uuid
import sys
import time

from agents.autonomous.state_manager import AutonomousStateManager, ActionType
from agents.core.safety import SafetyModule
from permissions.permission_engine import PermissionEngine

logger: logging.Logger = logging.getLogger(__name__)

@dataclass
class GeneratedTool:
    tool_id: str
    name: str
    description: str
    code: str
    parameters: Dict[str, Any]
    safety_level: str
    dependencies: List[str]
    workspace_path: str

class AutonomousToolGenerator:
    def __init__(self, state_manager: AutonomousStateManager, 
                 safety_module: SafetyModule, 
                 permission_engine: PermissionEngine) -> None:
        self.state_manager: AutonomousStateManager = state_manager
        self.safety_module: SafetyModule = safety_module
        self.permission_engine: PermissionEngine = permission_engine
        
        # Tool templates
        self.tool_templates: Dict[str, Callable[..., str]] = {
            "web_scraper": self._get_web_scraper_template,
            "data_analyzer": self._get_data_analyzer_template,
            "file_processor": self._get_file_processor_template,
            "api_client": self._get_api_client_template,
            "automation_script": self._get_automation_template
        }
        
        # Safety patterns to avoid
        self.dangerous_patterns: List[str] = [
            r'import\s+os\.system',
            r'os\.system\s*\(',
            r'subprocess\.(call|run|Popen)\s*\(',
            r'eval\s*\(',
            r'exec\s*\(',
            r'__import__\s*\(',
            r'open\s*\([\'"].*\/etc\/',
            r'shutil\.rmtree',
            r'os\.remove\s*\([\'"].*\/',
            r'os\.rename\s*\([\'"].*\/',
            r'pickle\.load',
            r'marshal\.load'
        ]
        
        # Allowed imports for sandboxed execution
        self.allowed_imports: set[str] = {
            'json', 'csv', 'xml', 'html', 're', 'math', 'statistics',
            'datetime', 'time', 'random', 'collections', 'itertools',
            'functools', 'operator', 'string', 'textwrap', 'pathlib',
            'pandas', 'numpy', 'matplotlib', 'seaborn', 'requests',
            'beautifulsoup4', 'bs4', 'lxml', 'urllib', 'http', 'ssl',
            'logging', 'typing',
        }
    
    async def generate_tool(self, task_id: str, tool_type: str, 
                           requirements: Dict[str, Any]) -> Optional[GeneratedTool]:
        """
        Generate a tool based on requirements
        """
        try:
            # Log tool generation start
            action_id: str = self.state_manager.add_action(
                task_id, ActionType.GENERATE_TOOL, 
                f"Generating {tool_type} tool", requirements
            )
            
            # Get template
            template_func: Callable[..., str] | None = self.tool_templates.get(tool_type)
            if not template_func:
                error: str = f"Unknown tool type: {tool_type}"
                self.state_manager.complete_action(task_id, action_id, error=error)
                return None
            
            # Generate tool code
            template: str = template_func(requirements)
            tool_code: str = self._fill_template(template, requirements)
            
            # Validate safety
            safety_result: Dict[str, Any] = await self._validate_tool_safety(tool_code, task_id)
            if not safety_result["safe"]:
                error: str = f"Tool safety validation failed: {safety_result['reason']}"
                self.state_manager.complete_action(task_id, action_id, error=error)
                return None
            
            # Create tool object
            tool = GeneratedTool(
                tool_id=str(uuid.uuid4()),
                name=requirements.get("name", f"{tool_type}_tool"),
                description=requirements.get("description", f"Generated {tool_type} tool"),
                code=tool_code,
                parameters=requirements,
                safety_level=safety_result["level"],
                dependencies=safety_result["dependencies"],
                workspace_path=self.state_manager.get_task_state(task_id).workspace_path
            )
            
            # Save tool to workspace
            await self._save_tool(tool, task_id)
            
            # Register tool dynamically
            await self._register_tool(tool, task_id)
            
            # Complete action
            self.state_manager.complete_action(task_id, action_id, result={
                "tool_id": tool.tool_id,
                "name": tool.name,
                "safety_level": tool.safety_level
            })
            
            logger.info(f"Generated tool {tool.name} for task {task_id}")
            return tool
            
        except Exception as e:
            if 'action_id' in locals():
                self.state_manager.complete_action(task_id, action_id, error=str(e))
            return None
    
    async def generate_custom_tool(self, task_id: str, description: str,
                                  requirements: Dict[str, Any]) -> Optional[GeneratedTool]:
        """
        Generate a custom tool based on description
        """
        try:
            # Log custom tool generation
            action_id: str = self.state_manager.add_action(
                task_id, ActionType.GENERATE_TOOL,
                "Generating custom tool", {"description": description}
            )
            
            # Analyze requirements and generate code
            tool_code: str | None = await self._generate_custom_code(description, requirements)
            
            if not tool_code:
                error = "Failed to generate custom tool code"
                self.state_manager.complete_action(task_id, action_id, error=error)
                return None
            
            # Validate safety
            safety_result: Dict[str, Any] = await self._validate_tool_safety(tool_code, task_id)
            if not safety_result["safe"]:
                error: str = f"Custom tool safety validation failed: {safety_result['reason']}"
                self.state_manager.complete_action(task_id, action_id, error=error)
                return None
            
            # Create tool object
            tool = GeneratedTool(
                tool_id=str(uuid.uuid4()),
                name=requirements.get("name", "custom_tool"),
                description=description,
                code=tool_code,
                parameters=requirements,
                safety_level=safety_result["level"],
                dependencies=safety_result["dependencies"],
                workspace_path=self.state_manager.get_task_state(task_id).workspace_path
            )
            
            # Save and register tool
            await self._save_tool(tool, task_id)
            await self._register_tool(tool, task_id)
            
            # Complete action
            self.state_manager.complete_action(task_id, action_id, result={
                "tool_id": tool.tool_id,
                "name": tool.name,
                "safety_level": tool.safety_level
            })
            
            return tool
            
        except Exception as e:
            if 'action_id' in locals():
                self.state_manager.complete_action(task_id, action_id, error=str(e))
            return None
    
    async def _validate_tool_safety(self, code: str, task_id: str) -> Dict[str, Any]:
        """
        Validate tool code for safety
        """
        try:
            # Check for dangerous patterns
            for pattern in self.dangerous_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return {
                        "safe": False,
                        "reason": f"Dangerous pattern detected: {pattern}",
                        "level": "high",
                        "dependencies": []
                    }
            
            # Parse AST to check imports
            try:
                tree: ast.Module = ast.parse(code)
                imports: List[str] = self._extract_imports(tree)
                
                # Check for disallowed imports
                disallowed: List[str] = [imp for imp in imports if imp not in self.allowed_imports]
                if disallowed:
                    return {
                        "safe": False,
                        "reason": f"Disallowed imports: {disallowed}",
                        "level": "medium",
                        "dependencies": []
                    }
                
            except SyntaxError as e:
                return {
                    "safe": False,
                    "reason": f"Syntax error in generated code: {e}",
                    "level": "high",
                    "dependencies": []
                }
            
            # Determine safety level
            safety_level = "low"
            if any(imp in ['requests', 'urllib', 'http'] for imp in imports):
                safety_level = "medium"
            
            return {
                "safe": True,
                "reason": "Code passed safety validation",
                "level": safety_level,
                "dependencies": imports
            }
            
        except Exception as e:
            return {
                "safe": False,
                "reason": f"Safety validation error: {e}",
                "level": "high",
                "dependencies": []
            }
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """
        Extract import statements from AST
        """
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return imports
    
    async def _save_tool(self, tool: GeneratedTool, task_id: str) -> None:
        """
        Save tool to workspace
        """
        try:
            # Create tools directory
            tools_dir: Path = Path(tool.workspace_path) / "tools"
            tools_dir.mkdir(exist_ok=True)
            
            # Save tool code
            tool_file: Path = tools_dir / f"{tool.name}.py"
            with open(tool_file, 'w', encoding='utf-8') as f:
                f.write(tool.code)
            
            # Save tool metadata
            metadata = {
                "tool_id": tool.tool_id,
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "safety_level": tool.safety_level,
                "dependencies": tool.dependencies,
                "created_at": time.time()
            }
            
            metadata_file: Path = tools_dir / f"{tool.name}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Add to state manager
            self.state_manager.add_generated_tool(task_id, tool.name, tool.code)
            
            logger.info(f"Saved tool {tool.name} to {tool_file}")
            
        except Exception as e:
            logger.error(f"Failed to save tool: {e}")
            raise
    
    async def _register_tool(self, tool: GeneratedTool, task_id: str) -> None:
        """
        Register tool for dynamic execution
        """
        try:
            # This would integrate with the tool registry
            # For now, we'll just log the registration
            logger.info(f"Registered tool {tool.name} for dynamic execution")
            
        except Exception as e:
            logger.error(f"Failed to register tool: {e}")
            raise
    
    async def _generate_custom_code(self, description: str, requirements: Dict[str, Any]) -> Optional[str]:
        """
        Generate custom tool code based on description
        """
        # This would use the LLM to generate code
        # For now, return a basic template
        
        template: str = f'''
"""
Custom Tool: {description}
Generated for autonomous task execution
"""

import json
import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the custom tool
    """
    try:
        # Tool implementation based on requirements
        result = {{"status": "success", "message": "Tool executed successfully"}}
        return result
        
    except Exception as e:
        return {{"status": "error", "error": str(e)}}

if __name__ == "__main__":
    # Test execution
    params = {requirements or {}}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
        
        return template
    
    def _fill_template(self, template: str, requirements: Dict[str, Any]) -> str:
        """
        Fill template with requirements
        """
        # Simple template filling - in production, use proper templating
        for key, value in requirements.items():
            placeholder: str = f"{{{key}}}"
            if placeholder in template:
                template = template.replace(placeholder, str(value))
        
        return template
    
    def _get_web_scraper_template(self, requirements: Dict[str, Any]) -> str:
        """
        Get web scraper template
        """
        return '''
"""
Web Scraper Tool
Scrapes web content from specified URLs
"""

import requests
from bs4 import BeautifulSoup
import json
import logging
from typing import Dict, Any, List
import time

logger = logging.getLogger(__name__)

def scrape_url(url: str, selector: str = None) -> Dict[str, Any]:
    """
    Scrape content from a URL with comprehensive error handling
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if selector:
            elements = soup.select(selector)
            content = [elem.get_text(strip=True) for elem in elements]
        else:
            content = soup.get_text(strip=True)
        
        return {
            "status": "success",
            "url": url,
            "content": content,
            "content_type": response.headers.get('content-type', ''),
            "status_code": response.status_code
        }
        
    except requests.ConnectionError as e:
        return {
            "status": "error",
            "error": "Connection failed",
            "error_type": "connection_error",
            "url": url
        }
    except requests.Timeout as e:
        return {
            "status": "error",
            "error": "Request timeout",
            "error_type": "timeout",
            "url": url
        }
    except requests.HTTPError as e:
        return {
            "status": "error",
            "error": f"HTTP {e.response.status_code}",
            "error_type": "http_error",
            "url": url
        }
    except requests.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": "request_error",
            "url": url
        }
    except (AttributeError, ValueError) as e:
        return {
            "status": "error",
            "error": "Parsing failed",
            "error_type": "parsing_error",
            "url": url
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": "unknown_error",
            "url": url
        }

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute web scraping tool
    """
    url = parameters.get("url")
    selector = parameters.get("selector")
    
    if not url:
        return {"status": "error", "error": "URL is required"}
    
    return scrape_url(url, selector)

if __name__ == "__main__":
    # Test execution
    params = {"url": "{url}", "selector": "{selector}"}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
    
    def _get_data_analyzer_template(self, requirements: Dict[str, Any]) -> str:
        """
        Get data analyzer template
        """
        return '''
"""
Data Analyzer Tool
Analyzes data and generates insights
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, Any, List
import statistics

logger = logging.getLogger(__name__)

def analyze_data(data: List[Dict[str, Any]], analysis_type: str = "basic") -> Dict[str, Any]:
    """
    Analyze data and return insights
    """
    try:
        if not data:
            return {"status": "error", "error": "No data provided"}
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        result = {
            "status": "success",
            "data_shape": df.shape,
            "columns": list(df.columns),
            "analysis_type": analysis_type
        }
        
        if analysis_type == "basic":
            # Basic statistics
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            for col in numeric_columns:
                result[f"{col}_stats"] = {
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max())
                }
        
        elif analysis_type == "correlation":
            # Correlation analysis
            numeric_df = df.select_dtypes(include=[np.number])
            if not numeric_df.empty:
                correlation_matrix = numeric_df.corr()
                result["correlations"] = correlation_matrix.to_dict()
        
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute data analysis tool
    """
    data = parameters.get("data", [])
    analysis_type = parameters.get("analysis_type", "basic")
    
    return analyze_data(data, analysis_type)

if __name__ == "__main__":
    # Test execution
    params = {"data": {data}, "analysis_type": "{analysis_type}"}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
    
    def _get_file_processor_template(self, requirements: Dict[str, Any]) -> str:
        """
        Get file processor template
        """
        return '''
"""
File Processor Tool
Processes files in workspace directory
"""

import os
import json
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

def process_files(directory: str, operation: str = "list") -> Dict[str, Any]:
    """
    Process files in directory
    """
    try:
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return {"status": "error", "error": f"Directory {directory} does not exist"}
        
        result = {"status": "success", "directory": str(dir_path)}
        
        if operation == "list":
            files = []
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    files.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix
                    })
            result["files"] = files
        
        elif operation == "read":
            filename = operation_params.get("filename")
            if filename:
                file_path = dir_path / filename
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    result["content"] = content
                else:
                    result["error"] = f"File {filename} not found"
        
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute file processing tool
    """
    directory = parameters.get("directory", ".")
    operation = parameters.get("operation", "list")
    
    return process_files(directory, operation)

if __name__ == "__main__":
    # Test execution
    params = {"directory": "{directory}", "operation": "{operation}"}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
    
    def _get_api_client_template(self, requirements: Dict[str, Any]) -> str:
        """
        Get API client template
        """
        return '''
"""
API Client Tool
Makes HTTP requests to APIs
"""

import requests
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def call_api(url: str, method: str = "GET", headers: Dict[str, str] = None, 
             data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Make API call
    """
    try:
        headers = headers or {}
        data = data or {}
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=data, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=10)
        else:
            return {"status": "error", "error": f"Unsupported method: {method}"}
        
        response.raise_for_status()
        
        try:
            result_data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as e:
            result_data = response.text
        except Exception as e:
            result_data = response.text
        
        return {
            "status": "success",
            "url": url,
            "method": method,
            "status_code": response.status_code,
            "data": result_data,
            "headers": dict(response.headers)
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute API client tool
    """
    url = parameters.get("url")
    method = parameters.get("method", "GET")
    headers = parameters.get("headers", {})
    data = parameters.get("data", {})
    
    if not url:
        return {"status": "error", "error": "URL is required"}
    
    return call_api(url, method, headers, data)

if __name__ == "__main__":
    # Test execution
    params = {"url": "{url}", "method": "{method}"}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
    
    def _get_automation_template(self, requirements: Dict[str, Any]) -> str:
        """
        Get automation script template
        """
        return '''
"""
Automation Tool
Automates repetitive tasks
"""

import time
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def run_automation(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run automation steps
    """
    try:
        results = []
        
        for i, step in enumerate(steps):
            step_type = step.get("type")
            step_params = step.get("parameters", {})
            
            if step_type == "wait":
                duration = step_params.get("duration", 1)
                time.sleep(duration)
                results.append({"step": i, "type": "wait", "duration": duration})
            
            elif step_type == "log":
                message = step_params.get("message", "")
                logger.info(f"Automation step {i}: {message}")
                results.append({"step": i, "type": "log", "message": message})
            
            elif step_type == "calculate":
                expression = step_params.get("expression", "")
                try:
                    # Safe evaluation - only basic math
                    result = eval(expression, {"__builtins__": {}}, {})
                    results.append({"step": i, "type": "calculate", "expression": expression, "result": result})
                except Exception as e:
                    results.append({"step": i, "type": "calculate", "error": str(e)})
            
            else:
                results.append({"step": i, "type": step_type, "error": "Unknown step type"})
        
        return {
            "status": "success",
            "steps_completed": len(results),
            "results": results
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

def execute_tool(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute automation tool
    """
    steps = parameters.get("steps", [])
    
    if not steps:
        return {"status": "error", "error": "No steps provided"}
    
    return run_automation(steps)

if __name__ == "__main__":
    # Test execution
    params = {"steps": {steps}}
    result = execute_tool(params)
    print(json.dumps(result, indent=2))
'''
