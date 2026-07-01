"""
Core Planner Module - Task Classification and Planning
Analyzes user input and determines execution strategy
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

class TaskType(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    AUTONOMOUS = "autonomous"
    WORKFLOW = "workflow"
    DELEGATION = "delegation"

@dataclass
class TaskPlan:
    type: TaskType
    intent: str
    confidence: float
    steps: List[str]
    tools_required: List[str]
    role: Optional[str] = None
    context: Dict[str, Any] = None

class Planner:
    def __init__(self):
        self.simple_patterns = {
            r'open\s+(.+?)\s*$': 'open_application',
            r'launch\s+(.+?)\s*$': 'open_application',
            r'start\s+(.+?)\s*$': 'open_application',
            r'type\s+(.+?)\s*$': 'type_text',
            r'write\s+(.+?)\s*$': 'type_text',
            r'switch\s+(?:to\s+)?(?:window|tab)\s*(.+?)?$': 'switch_window',
            r'close\s+(.+?)\s*$': 'close_application',
            r'click\s+(.+?)\s*$': 'click_element',
            r'scroll\s+(up|down|left|right)': 'scroll',
            r'copy\s+(.+?)?$': 'copy_text',
            r'paste\s*(.+?)?$': 'paste_text',
            r'screenshot\s*(.+?)?$': 'take_screenshot',
            r'search\s+(?:for\s+)?(.+?)\s*$': 'web_search_simple',
            r'focus\s+(?:on\s+)?(.+?)\s*$': 'focus_application',
            r'open\s+(vscode|cursor|code)\s*$': 'open_application',
            r'edit\s+file\s+(.+?)\s*$': 'edit_file',
            r'create\s+file\s+(.+?)\s+with\s+(.+?)\s*$': 'create_file_with_content',
            r'create\s+file\s+(.+?)\s*$': 'create_file',
            r'run\s+(?:file|script|code)\s*(.+?)?$': 'run_code',
            r'install\s+plugin\s+(.+?)\s*$': 'install_plugin',
            r'search\s+plugins\s+(?:for\s+)?(.+?)\s*$': 'search_plugins',
        }
        
        self.workflow_patterns = {
            r'research\s+(.+?)\s+and\s+(?:write|build|create)\s+(.+?)\s*$': ('researcher', 'developer'),
            r'analyze\s+(.+?)\s+and\s+create\s+(?:a\s+)?report\s*$': ('analyst', 'researcher'),
            r'research\s+(.+?)\s+and\s+analyze\s+(.+?)\s*$': ('researcher', 'analyst'),
        }
        
        self.complex_patterns = {
            r'research\s+(.+?)\s*$': 'researcher',
            r'analyze\s+(.+?)\s*$': 'analyst',
            r'summarize\s+(.+?)\s*$': 'summarizer',
            r'write\s+(?:a\s+)?(?:code|script|program)\s*(?:for\s+)?(.+?)?$': 'developer',
            r'develop\s+(.+?)\s*$': 'developer',
            r'create\s+(?:a\s+)?(?:report|document|summary)\s*(?:for\s+)?(.+?)?$': 'researcher',
            r'compare\s+(.+?)\s*$': 'analyst',
            r'find\s+(?:information|data)\s+(?:about|on)\s+(.+?)\s*$': 'researcher',
            r'investigate\s+(.+?)\s*$': 'researcher',
        }
        
        self.autonomous_patterns = {
            r'build\s+(?:a\s+)?(?:project|solution|system)\s*(?:for\s+)?(.+?)?$': 'autonomous_build',
            r'automate\s+(?:this\s+)?workflow\s*(?:for\s+)?(.+?)?$': 'autonomous_automate',
            r'develop\s+(?:a\s+)?(?:full\s+)?(?:solution|system)\s*(?:for\s+)?(.+?)?$': 'autonomous_develop',
            r'develop\s+(?:a\s+)?(?:complete|full)\s+(?:solution|system)\s*(?:for\s+)?(.+?)?$': 'autonomous_develop',
            r'create\s+(?:a\s+)?(?:complete|full)\s+(?:application|program|system)\s*(?:for\s+)?(.+?)?$': 'autonomous_create',
            r'implement\s+(?:a\s+)?(?:complete|full)\s+(?:solution|system)\s*(?:for\s+)?(.+?)?$': 'autonomous_implement',
            r'analyze\s+and\s+iterate\s+(?:on\s+)?(.+?)?$': 'autonomous_analyze_iterate',
            r'build\s+(?:a\s+)?python\s+script\s+to\s+(.+?)\s*$': 'autonomous_python_script',
            r'create\s+(?:a\s+)?(?:web\s+)?scraper\s+(?:for\s+)?(.+?)?$': 'autonomous_scraper',
            r'create\s+(?:a\s+)?(?:web\s+)?scraper\s+to\s+(.+?)\s*$': 'autonomous_scraper',
            r'design\s+(?:and\s+)?implement\s+(?:a\s+)?(.+?)\s*system\s*$': 'autonomous_design_implement',
        }
        
        self.simple_tools = {
            'open_application': ['os_open_app'],
            'type_text': ['os_type_text'],
            'switch_window': ['os_switch_window'],
            'close_application': ['os_close_app'],
            'click_element': ['os_click'],
            'scroll': ['os_scroll'],
            'copy_text': ['os_copy'],
            'paste_text': ['os_paste'],
            'take_screenshot': ['os_screenshot'],
            'web_search_simple': ['web_search'],
            'focus_application': ['system_focus_app'],
            'edit_file': ['ide_workflow'],
            'create_file': ['ide_workflow'],
            'create_file_with_content': ['ide_workflow'],
            'run_code': ['ide_workflow'],
            'install_plugin': ['marketplace'],
            'search_plugins': ['marketplace'],
        }
    
    def analyze_input(self, user_input: str) -> TaskPlan:
        """
        Analyze user input and generate execution plan
        """
        raw = user_input.strip()
        normalized = raw.lower()

        try:
            from agents.workflow.meta_planner import (
                analyze_compound,
                analyze_delegation,
                analyze_parallel,
            )
            parallel = analyze_parallel(raw)
            if parallel:
                return parallel
            delegation = analyze_delegation(raw)
            if delegation:
                return delegation
            autonomous_result = self._check_autonomous_patterns(normalized)
            if autonomous_result:
                logger.info(f"Autonomous task detected: {autonomous_result.intent}")
                return autonomous_result
            meta = analyze_compound(raw)
            if meta:
                return meta
        except ImportError:
            pass

        # Check for autonomous tasks (again for inputs not handled by meta planner)
        autonomous_result = self._check_autonomous_patterns(normalized)
        if autonomous_result:
            logger.info(f"Autonomous task detected: {autonomous_result.intent}")
            return autonomous_result

        # Compound multi-agent workflows (regex)
        workflow_result = self._check_workflow_patterns(normalized)
        if workflow_result:
            return workflow_result

        # Check for autonomous tasks before compound workflow heuristics
        # (primary autonomous routing happens earlier, before meta_planner)
        
        # Check for simple tasks next (for low latency)
        simple_result = self._check_simple_patterns(normalized)
        if simple_result:
            logger.info(f"Simple task detected: {simple_result.intent}")
            return simple_result
        
        # Check for complex tasks
        complex_result = self._check_complex_patterns(normalized)
        if complex_result:
            logger.info(f"Complex task detected: {complex_result.intent}, role: {complex_result.role}")
            return complex_result
        
        # Default to complex researcher for unmatched natural language
        return TaskPlan(
            type=TaskType.COMPLEX,
            intent="general_query",
            confidence=0.5,
            steps=["research_and_respond"],
            tools_required=[],
            role="researcher",
            context={"original_input": raw},
        )
    
    def _check_workflow_patterns(self, user_input: str) -> Optional[TaskPlan]:
        import uuid
        for pattern, roles in self.workflow_patterns.items():
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                groups = match.groups()
                nodes = []
                for i, role in enumerate(roles):
                    goal = groups[i] if i < len(groups) else user_input
                    nodes.append({
                        "node_id": f"node_{i}",
                        "role": role,
                        "goal": goal,
                        "depends_on": [f"node_{i-1}"] if i > 0 else [],
                    })
                return TaskPlan(
                    type=TaskType.WORKFLOW,
                    intent="multi_agent_workflow",
                    confidence=0.85,
                    steps=[f"run_{role}" for role in roles],
                    tools_required=[],
                    role="workflow",
                    context={
                        "workflow_id": str(uuid.uuid4())[:8],
                        "workflow_nodes": nodes,
                        "parameters": groups,
                    },
                )
        return None
    
    def _check_simple_patterns(self, user_input: str) -> Optional[TaskPlan]:
        """Check if input matches simple task patterns"""
        for pattern, intent in self.simple_patterns.items():
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                tools = self.simple_tools.get(intent, [])
                steps = [intent]
                
                # Add extracted parameters to context
                context = {}
                if match.groups():
                    context['parameters'] = match.groups()
                
                return TaskPlan(
                    type=TaskType.SIMPLE,
                    intent=intent,
                    confidence=0.9,
                    steps=steps,
                    tools_required=tools,
                    context=context
                )
        return None
    
    def _check_complex_patterns(self, user_input: str) -> Optional[TaskPlan]:
        """Check if input matches complex task patterns"""
        for pattern, role in self.complex_patterns.items():
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                # Generate steps based on role
                steps = self._generate_complex_steps(role, match.groups())
                tools = self._get_complex_tools(role)
                
                context = {}
                if match.groups():
                    context['parameters'] = match.groups()
                
                return TaskPlan(
                    type=TaskType.COMPLEX,
                    intent=role,
                    confidence=0.8,
                    steps=steps,
                    tools_required=tools,
                    role=role,
                    context=context
                )
        return None
    
    def _check_autonomous_patterns(self, user_input: str) -> Optional[TaskPlan]:
        """Check if input matches autonomous task patterns"""
        for pattern, intent in self.autonomous_patterns.items():
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                steps = self._generate_autonomous_steps(intent, match.groups())
                tools = self._get_autonomous_tools(intent)
                
                # Add extracted parameters to context
                context = {}
                if match.groups():
                    context['parameters'] = match.groups()
                
                return TaskPlan(
                    type=TaskType.AUTONOMOUS,
                    intent=intent,
                    confidence=0.9,
                    steps=steps,
                    tools_required=tools,
                    role="autonomous",
                    context=context
                )
        return None
    
    def _generate_autonomous_steps(self, intent: str, parameters: tuple) -> List[str]:
        """Generate execution steps for autonomous tasks"""
        autonomous_steps = {
            'autonomous_build': [
                'analyze_requirements',
                'generate_tools',
                'implement_solution',
                'test_and_refine'
            ],
            'autonomous_automate': [
                'analyze_workflow',
                'identify_automation_points',
                'create_automation_tools',
                'implement_automation'
            ],
            'autonomous_develop': [
                'understand_scope',
                'design_architecture',
                'implement_components',
                'integrate_and_test'
            ],
            'autonomous_create': [
                'define_requirements',
                'design_system',
                'implement_features',
                'test_and_deploy'
            ],
            'autonomous_implement': [
                'analyze_specifications',
                'design_implementation',
                'code_development',
                'testing_and_validation'
            ],
            'autonomous_analyze_iterate': [
                'initial_analysis',
                'implement_solution',
                'analyze_results',
                'iterate_and_improve'
            ],
            'autonomous_python_script': [
                'define_script_requirements',
                'generate_python_code',
                'test_script',
                'refine_and_finalize'
            ],
            'autonomous_scraper': [
                'analyze_scraping_needs',
                'create_scraper_tool',
                'test_scraping',
                'process_and_analyze'
            ],
            'autonomous_design_implement': [
                'design_system_architecture',
                'implement_components',
                'integrate_system',
                'test_and_validate'
            ]
        }
        
        return autonomous_steps.get(intent, ['execute_autonomous_task'])
    
    def _get_autonomous_tools(self, intent: str) -> List[str]:
        """Get required tools for autonomous tasks"""
        autonomous_tools = {
            'autonomous_build': ['tool_generator', 'tool_executor', 'data_analyzer'],
            'autonomous_automate': ['tool_generator', 'tool_executor', 'automation_tools'],
            'autonomous_develop': ['tool_generator', 'tool_executor', 'code_analyzer'],
            'autonomous_create': ['tool_generator', 'tool_executor', 'system_builder'],
            'autonomous_implement': ['tool_generator', 'tool_executor', 'implementation_tools'],
            'autonomous_analyze_iterate': ['tool_generator', 'tool_executor', 'iteration_analyzer'],
            'autonomous_python_script': ['tool_generator', 'tool_executor', 'python_tools'],
            'autonomous_scraper': ['tool_generator', 'tool_executor', 'web_scraper'],
            'autonomous_design_implement': ['tool_generator', 'tool_executor', 'design_tools']
        }
        
        return autonomous_tools.get(intent, ['autonomous_core'])
    
    def _generate_complex_steps(self, role: str, parameters: tuple) -> List[str]:
        """Generate execution steps for complex tasks"""
        base_steps = {
            'researcher': [
                'search_web_sources',
                'extract_relevant_info',
                'synthesize_findings',
                'generate_summary'
            ],
            'analyst': [
                'gather_data',
                'perform_analysis',
                'compare_options',
                'provide_recommendations'
            ],
            'developer': [
                'understand_requirements',
                'design_solution',
                'write_code',
                'test_implementation'
            ],
            'summarizer': [
                'collect_content',
                'extract_key_points',
                'create_summary',
                'format_output'
            ]
        }
        
        return base_steps.get(role, ['execute_complex_task'])
    
    def _get_complex_tools(self, role: str) -> List[str]:
        """Get required tools for complex tasks"""
        role_tools = {
            'researcher': ['web_search', 'content_extractor', 'summarizer'],
            'analyst': ['web_search', 'data_processor', 'comparison_engine'],
            'developer': ['code_editor', 'file_manager', 'test_runner'],
            'summarizer': ['content_extractor', 'text_processor', 'formatter']
        }
        
        return role_tools.get(role, ['generic_complex_tools'])
    
    def estimate_execution_time(self, plan: TaskPlan) -> float:
        """Estimate execution time in seconds"""
        if plan.type == TaskType.SIMPLE:
            return 0.5  # Simple tasks are fast
        else:
            # Complex tasks take longer based on steps
            return len(plan.steps) * 2.0
    
    def validate_plan(self, plan: TaskPlan) -> bool:
        """Validate plan completeness"""
        if not plan.intent or not plan.steps:
            return False
        
        if plan.type == TaskType.COMPLEX and not plan.role:
            return False
        
        if plan.type == TaskType.WORKFLOW and not plan.context.get("workflow_nodes"):
            return False

        if plan.type == TaskType.DELEGATION and not plan.context.get("delegation_goal"):
            return False
        
        if plan.confidence < 0.3:
            return False
        
        return True
