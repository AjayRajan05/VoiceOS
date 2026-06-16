"""
Autonomous System Tests - End-to-end testing of autonomous agent capabilities
Tests the complete autonomous agent workflow with tool generation and execution
"""

import asyncio
import logging
import pytest
import tempfile
import shutil
from pathlib import Path
import json
import time

from agents.autonomous.state_manager import AutonomousStateManager, TaskStatus, ActionType
from agents.autonomous.tool_generator import AutonomousToolGenerator, GeneratedTool
from agents.autonomous.tool_executor import AutonomousToolExecutor
from agents.autonomous.agent_loop import AutonomousAgentLoop
from agents.core.planner import Planner, TaskType
from agents.core.safety import SafetyModule
from permissions.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)

class TestAutonomousSystem:
    """Test suite for autonomous agent system"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        temp_dir = tempfile.mkdtemp(prefix="voiceos_test_")
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def autonomous_components(self, temp_workspace):
        """Setup autonomous components for testing"""
        # Initialize components
        state_manager = AutonomousStateManager(temp_workspace)
        safety_module = SafetyModule()
        permission_engine = PermissionEngine(None)  # Mock event bus
        tool_generator = AutonomousToolGenerator(state_manager, safety_module, permission_engine)
        tool_executor = AutonomousToolExecutor(state_manager, safety_module, permission_engine)
        agent_loop = AutonomousAgentLoop(state_manager, tool_generator, tool_executor, safety_module, permission_engine)
        
        return {
            "state_manager": state_manager,
            "tool_generator": tool_generator,
            "tool_executor": tool_executor,
            "agent_loop": agent_loop,
            "safety_module": safety_module,
            "permission_engine": permission_engine
        }
    
    @pytest.mark.asyncio
    async def test_autonomous_task_classification(self):
        """Test planner autonomous task classification"""
        planner = Planner()
        
        # Test autonomous task patterns
        autonomous_requests = [
            "Build a Python script to scrape product prices",
            "Create a web scraper for news articles",
            "Develop a complete solution for data analysis",
            "Automate this workflow for daily reports",
            "Analyze and iterate on this dataset"
        ]
        
        for request in autonomous_requests:
            plan = planner.analyze_input(request)
            assert plan.type == TaskType.AUTONOMOUS, f"Request should be classified as autonomous: {request}"
            assert plan.confidence >= 0.8, f"Should have high confidence for autonomous task: {request}"
            assert plan.role == "autonomous", f"Should have autonomous role: {request}"
    
    @pytest.mark.asyncio
    async def test_state_manager_task_creation(self, autonomous_components):
        """Test state manager task creation and tracking"""
        state_manager = autonomous_components["state_manager"]
        
        # Create task
        task_id = state_manager.create_task(
            user_request="Build a web scraper",
            goal="Create a Python script to scrape web data"
        )
        
        assert task_id is not None, "Task ID should be generated"
        
        # Check task state
        task_state = state_manager.get_task_state(task_id)
        assert task_state is not None, "Task state should exist"
        assert task_state.status == TaskStatus.PENDING, "Task should be pending"
        assert task_state.user_request == "Build a web scraper", "User request should match"
        assert task_state.goal == "Create a Python script to scrape web data", "Goal should match"
        
        # Check workspace creation
        workspace_path = Path(task_state.workspace_path)
        assert workspace_path.exists(), "Workspace should be created"
        assert (workspace_path / "tools").exists(), "Tools directory should exist"
        assert (workspace_path / "outputs").exists(), "Outputs directory should exist"
        assert (workspace_path / "logs").exists(), "Logs directory should exist"
    
    @pytest.mark.asyncio
    async def test_tool_generation(self, autonomous_components):
        """Test autonomous tool generation"""
        tool_generator = autonomous_components["tool_generator"]
        state_manager = autonomous_components["state_manager"]
        
        # Create task
        task_id = state_manager.create_task(
            user_request="Create web scraper",
            goal="Build a tool to scrape web data"
        )
        
        # Generate tool
        tool = await tool_generator.generate_tool(
            task_id=task_id,
            tool_type="web_scraper",
            requirements={
                "name": "test_scraper",
                "description": "Test web scraper",
                "url": "https://example.com",
                "selector": "content"
            }
        )
        
        assert tool is not None, "Tool should be generated"
        assert tool.name == "test_scraper", "Tool name should match"
        assert tool.safety_level in ["low", "medium"], "Tool should have valid safety level"
        
        # Check tool file creation
        tool_file = Path(tool.workspace_path) / "tools" / f"{tool.name}.py"
        assert tool_file.exists(), "Tool file should be created"
        
        # Check tool code
        with open(tool_file, 'r') as f:
            code = f.read()
        assert "def execute_tool" in code, "Tool should have execute_tool function"
        assert "scrape_url" in code, "Tool should have scraping functionality"
    
    @pytest.mark.asyncio
    async def test_tool_execution(self, autonomous_components):
        """Test autonomous tool execution"""
        tool_executor = autonomous_components["tool_executor"]
        tool_generator = autonomous_components["tool_generator"]
        state_manager = autonomous_components["state_manager"]
        
        # Create task
        task_id = state_manager.create_task(
            user_request="Execute data analysis",
            goal="Run data analysis tool"
        )
        
        # Generate tool
        tool = await tool_generator.generate_tool(
            task_id=task_id,
            tool_type="data_analyzer",
            requirements={
                "name": "test_analyzer",
                "description": "Test data analyzer",
                "data": [{"value": 10}, {"value": 20}, {"value": 30}]
            }
        )
        
        # Execute tool
        result = await tool_executor.execute_tool(
            task_id=task_id,
            tool=tool,
            parameters={"data": [{"value": 10}, {"value": 20}, {"value": 30}]}
        )
        
        assert result["status"] in ["success", "error"], "Result should have valid status"
        if result["status"] == "success":
            assert "result" in result, "Successful execution should have result"
    
    @pytest.mark.asyncio
    async def test_autonomous_agent_loop(self, autonomous_components):
        """Test complete autonomous agent loop"""
        agent_loop = autonomous_components["agent_loop"]
        
        # Execute autonomous task
        result = await agent_loop.execute_autonomous_task(
            user_request="Build a simple data analyzer",
            goal="Create a tool to analyze numeric data"
        )
        
        assert result["status"] in ["completed", "failed"], "Task should have final status"
        assert "task_id" in result, "Result should include task ID"
        assert "execution_time" in result, "Result should include execution time"
        assert "iterations" in result, "Result should include iteration count"
        
        # Check workspace
        if result["status"] == "completed":
            workspace_path = Path(result["workspace_path"])
            assert workspace_path.exists(), "Workspace should exist"
    
    @pytest.mark.asyncio
    async def test_safety_validation(self, autonomous_components):
        """Test safety validation for autonomous operations"""
        tool_generator = autonomous_components["tool_generator"]
        state_manager = autonomous_components["state_manager"]
        
        # Create task
        task_id = state_manager.create_task(
            user_request="Test safety",
            goal="Test safety validation"
        )
        
        # Try to generate dangerous tool
        dangerous_code = '''
import os
def execute_tool(parameters):
    os.system("rm -rf /")  # Dangerous operation
    return {"status": "success"}
'''
        
        # Mock tool with dangerous code
        from agents.autonomous.tool_generator import GeneratedTool
        dangerous_tool = GeneratedTool(
            tool_id="dangerous",
            name="dangerous_tool",
            description="Dangerous tool",
            code=dangerous_code,
            parameters={},
            safety_level="high",
            dependencies=[],
            workspace_path=state_manager.get_task_state(task_id).workspace_path
        )
        
        # Validate safety
        safety_result = await tool_generator._validate_tool_safety(dangerous_code, task_id)
        
        assert not safety_result["safe"], "Dangerous code should not be safe"
        assert "dangerous pattern" in safety_result["reason"].lower(), "Should detect dangerous patterns"
    
    @pytest.mark.asyncio
    async def test_workspace_isolation(self, autonomous_components):
        """Test workspace isolation for autonomous tasks"""
        state_manager = autonomous_components["state_manager"]
        tool_generator = autonomous_components["tool_generator"]
        
        # Create two tasks
        task1_id = state_manager.create_task("Task 1", "Goal 1")
        task2_id = state_manager.create_task("Task 2", "Goal 2")
        
        # Generate tools for both tasks
        tool1 = await tool_generator.generate_tool(task1_id, "data_analyzer", {"name": "tool1"})
        tool2 = await tool_generator.generate_tool(task2_id, "data_analyzer", {"name": "tool2"})
        
        # Check workspace separation
        workspace1 = Path(tool1.workspace_path)
        workspace2 = Path(tool2.workspace_path)
        
        assert workspace1 != workspace2, "Workspaces should be different"
        assert workspace1.exists(), "Workspace 1 should exist"
        assert workspace2.exists(), "Workspace 2 should exist"
        
        # Check tool files are in correct workspaces
        tool1_file = workspace1 / "tools" / "tool1.py"
        tool2_file = workspace2 / "tools" / "tool2.py"
        
        assert (workspace1 / "tools" / "tool1.py").exists(), "Tool 1 should be in workspace 1"
        assert (workspace2 / "tools" / "tool2.py").exists(), "Tool 2 should be in workspace 2"
        assert not (workspace1 / "tools" / "tool2.py").exists(), "Tool 2 should not be in workspace 1"
        assert not (workspace2 / "tools" / "tool1.py").exists(), "Tool 1 should not be in workspace 2"
    
    @pytest.mark.asyncio
    async def test_logging_and_tracking(self, autonomous_components):
        """Test comprehensive logging and tracking"""
        state_manager = autonomous_components["state_manager"]
        agent_loop = autonomous_components["agent_loop"]
        
        # Execute task with logging
        result = await agent_loop.execute_autonomous_task(
            user_request="Test logging",
            goal="Generate comprehensive logs"
        )
        
        # Check task state
        task_id = result["task_id"]
        task_state = state_manager.get_task_state(task_id)
        
        assert len(task_state.actions) > 0, "Should have logged actions"
        assert len(task_state.intermediate_results) >= 0, "Should have intermediate results"
        
        # Check log files
        log_file = Path(task_state.workspace_path) / "logs" / "actions.log"
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_content = f.read()
            assert len(log_content) > 0, "Log file should not be empty"
    
    def test_statistics_and_metrics(self, autonomous_components):
        """Test statistics and metrics collection"""
        agent_loop = autonomous_components["agent_loop"]
        tool_executor = autonomous_components["tool_executor"]
        
        # Get initial statistics
        loop_stats = agent_loop.get_loop_statistics()
        executor_stats = tool_executor.get_execution_statistics()
        
        assert "total_tasks" in loop_stats, "Should have total tasks metric"
        assert "max_iterations" in loop_stats, "Should have max iterations metric"
        assert "total_executions" in executor_stats, "Should have total executions metric"
        assert "success_rate" in executor_stats, "Should have success rate metric"
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, autonomous_components):
        """Test error handling and recovery mechanisms"""
        agent_loop = autonomous_components["agent_loop"]
        
        # Execute task that might fail
        result = await agent_loop.execute_autonomous_task(
            user_request="Test error handling",
            goal="Intentionally fail to test error handling"
        )
        
        # Should handle errors gracefully
        assert result["status"] in ["completed", "failed"], "Should handle errors gracefully"
        if result["status"] == "failed":
            assert "error" in result, "Failed result should include error information"

# Integration Test
@pytest.mark.asyncio
async def test_end_to_end_autonomous_workflow():
    """End-to-end test of complete autonomous workflow"""
    # Setup components
    temp_dir = tempfile.mkdtemp(prefix="voiceos_e2e_")
    try:
        state_manager = AutonomousStateManager(temp_dir)
        safety_module = SafetyModule()
        permission_engine = PermissionEngine(None)
        tool_generator = AutonomousToolGenerator(state_manager, safety_module, permission_engine)
        tool_executor = AutonomousToolExecutor(state_manager, safety_module, permission_engine)
        agent_loop = AutonomousAgentLoop(state_manager, tool_generator, tool_executor, safety_module, permission_engine)
        
        # Execute complete workflow
        result = await agent_loop.execute_autonomous_task(
            user_request="Build a Python script to analyze sample data and generate insights",
            goal="Create data analysis tool with visualization"
        )
        
        # Verify results
        assert result["status"] in ["completed", "failed"], "Should complete or fail gracefully"
        assert "task_id" in result, "Should have task ID"
        assert result["execution_time"] > 0, "Should have execution time"
        
        if result["status"] == "completed":
            # Verify workspace and generated files
            workspace_path = Path(result["workspace_path"])
            assert workspace_path.exists(), "Workspace should exist"
            assert (workspace_path / "tools").exists(), "Tools directory should exist"
            
            # Check for generated tools
            tools_dir = workspace_path / "tools"
            tool_files = list(tools_dir.glob("*.py"))
            assert len(tool_files) > 0, "Should have generated at least one tool"
        
        logger.info(f"End-to-end test completed with status: {result['status']}")
        
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # Run tests
    logging.basicConfig(level=logging.INFO)
    
    # Simple test run
    asyncio.run(test_end_to_end_autonomous_workflow())
    print("✅ End-to-end autonomous system test completed successfully!")
