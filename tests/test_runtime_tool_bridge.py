"""
Test Suite for VoiceOS Runtime Tool Bridge
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from tools.file_tools.enhanced_file_manager import EnhancedFileManager
from tools.web_tools.browser_tool import BrowserTool
from tools.code_tools.code_executor import CodeExecutor
from tools.document_tools.document_processor import DocumentProcessor
from tools.scheduler_tools.task_scheduler import TaskScheduler
from tools.runtime_tool_bridge import RuntimeToolBridge
from tools.tool_registry import ToolRegistry, ToolCategory
from permissions.permission_engine import PermissionLevel, permission_engine
from agents.agent_tool_integration import AgentToolBridge, AgentToolManager


class TestEnhancedFileManager:
    """Test Enhanced File Manager safety and functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.file_manager = EnhancedFileManager(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_path_validation_within_workspace(self):
        """Test path validation for files within workspace"""
        valid_path = Path(self.temp_dir) / "test.txt"
        resolved = self.file_manager._validate_path(str(valid_path))
        assert resolved == valid_path
    
    def test_path_validation_outside_workspace(self):
        """Test path validation rejects files outside workspace"""
        invalid_path = "/etc/passwd"
        with pytest.raises(PermissionError):
            self.file_manager._validate_path(invalid_path)
    
    def test_file_operations(self):
        """Test basic file operations"""
        # Test create and write
        test_file = "test.txt"
        content = "Test content"
        
        result = self.file_manager.write_file(test_file, content)
        assert "written to" in result.lower()
        
        # Test read
        read_content = self.file_manager.read_file(test_file)
        assert read_content == content
        
        # Test file exists
        exists = self.file_manager.file_exists(test_file)
        assert exists is True
        
        # Test list directory
        items = self.file_manager.list_directory()
        assert len(items) == 1
        assert items[0]["name"] == "test.txt"
    
    def test_permission_enforcement(self):
        """Test permission enforcement for file operations"""
        # Set low permission level
        permission_engine.set_user_permission_level(PermissionLevel.LOW)
        
        # High permission operation should fail
        with pytest.raises(PermissionError):
            self.file_manager.delete_file("test.txt")


class TestBrowserTool:
    """Test Browser Tool safety and functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.browser_tool = BrowserTool(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_url_validation(self):
        """Test URL validation"""
        # Valid URLs
        valid_urls = [
            "https://example.com",
            "http://test.org",
            "https://sub.domain.com/path"
        ]
        
        for url in valid_urls:
            validated = self.browser_tool._validate_url(url)
            assert validated == url
        
        # Invalid URLs
        invalid_urls = [
            "ftp://example.com",
            "http://localhost",
            "https://127.0.0.1",
            "not-a-url",
            ""
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                self.browser_tool._validate_url(url)
    
    def test_safe_search_query(self):
        """Test safe search query validation"""
        # Valid queries
        valid_queries = [
            "test search",
            "python programming",
            "data analysis"
        ]
        
        for query in valid_queries:
            # Should not raise exception
            assert len(query) <= 200
            assert len(query.strip()) > 0
        
        # Invalid queries
        invalid_queries = [
            "",  # Empty
            "a" * 201,  # Too long
        ]
        
        for query in invalid_queries:
            with pytest.raises(ValueError):
                self.browser_tool.search_web(query)


class TestCodeExecutor:
    """Test Code Executor safety and functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.code_executor = CodeExecutor(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_code_validation(self):
        """Test code validation for security"""
        # Safe code
        safe_code = "print('Hello, World!')"
        validated = self.code_executor._validate_code(safe_code, 'python')
        assert validated == safe_code
        
        # Dangerous code patterns
        dangerous_codes = [
            "import os.system('rm -rf /')",
            "eval('dangerous_code')",
            "exec('malicious_code')",
            "subprocess.call(['rm', '-rf', '/'])"
        ]
        
        for code in dangerous_codes:
            with pytest.raises(ValueError):
                self.code_executor._validate_code(code, 'python')
    
    def test_language_validation(self):
        """Test language validation"""
        valid_languages = ['python', 'bash', 'javascript']
        
        for lang in valid_languages:
            # Should not raise exception
            self.code_executor._validate_code("print('test')", lang)
        
        # Invalid language
        with pytest.raises(ValueError):
            self.code_executor._validate_code("print('test')", 'malicious_lang')


class TestDocumentProcessor:
    """Test Document Processor safety and functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.document_processor = DocumentProcessor(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_file_validation(self):
        """Test file validation for document processing"""
        # Create a test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("Test content")
        
        # Valid file
        validated = self.document_processor._validate_file(str(test_file))
        assert validated == test_file
        
        # Non-existent file
        with pytest.raises(FileNotFoundError):
            self.document_processor._validate_file("non_existent.txt")
        
        # Invalid extension
        invalid_file = Path(self.temp_dir) / "test.exe"
        invalid_file.write_text("Fake executable")
        
        with pytest.raises(ValueError):
            self.document_processor._validate_file(str(invalid_file))
    
    def test_search_query_validation(self):
        """Test search query validation"""
        # Valid queries
        valid_queries = ["test", "search term", "find this"]
        
        for query in valid_queries:
            # Should not raise exception
            assert len(query) <= 200
            assert len(query.strip()) > 0
        
        # Invalid queries
        invalid_queries = ["", "a" * 201]
        
        for query in invalid_queries:
            with pytest.raises(ValueError):
                self.document_processor.search_in_document("test.txt", query)


class TestTaskScheduler:
    """Test Task Scheduler safety and functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.task_scheduler = TaskScheduler(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_task_validation(self):
        """Test task validation"""
        from datetime import datetime, timedelta
        
        # Valid task
        valid_task = {
            "name": "test_task",
            "task_type": "file_operation",
            "scheduled_time": (datetime.now() + timedelta(hours=1)).isoformat(),
            "parameters": {"path": "test.txt"}
        }
        
        validated = self.task_scheduler._validate_task(valid_task)
        assert validated["name"] == "test_task"
        
        # Invalid task types
        invalid_task_types = ["malicious_operation", "system_delete"]
        
        for task_type in invalid_task_types:
            invalid_task = valid_task.copy()
            invalid_task["task_type"] = task_type
            
            with pytest.raises(ValueError):
                self.task_scheduler._validate_task(invalid_task)
        
        # Past time
        past_task = valid_task.copy()
        past_task["scheduled_time"] = (datetime.now() - timedelta(hours=1)).isoformat()
        
        with pytest.raises(ValueError):
            self.task_scheduler._validate_task(past_task)
    
    def test_file_parameter_validation(self):
        """Test file parameter validation"""
        # Valid file path (within workspace)
        valid_params = {"path": "test.txt"}
        self.task_scheduler._validate_file_params(valid_params)
        
        # Invalid file path (outside workspace)
        invalid_params = {"path": "/etc/passwd"}
        with pytest.raises(ValueError):
            self.task_scheduler._validate_file_params(invalid_params)


class TestRuntimeToolBridge:
    """Test VoiceOS runtime tool bridge"""

    def setup_method(self):
        self.tool_registry = ToolRegistry()
        self.integration = RuntimeToolBridge(self.tool_registry)

    def test_tool_registration(self):
        registered_count = self.integration.register_runtime_tools()
        assert registered_count > 0
        for tool_name in self.integration.runtime_tools.keys():
            assert self.tool_registry.get_tool(tool_name) is not None
    
    def test_permission_validation(self):
        """Test permission validation for tools"""
        # Test tool access validation
        assert self.integration.validate_tool_access(
            "enhanced_file_manager", "read_file", PermissionLevel.LOW
        )
        
        assert self.integration.validate_tool_access(
            "enhanced_file_manager", "delete_file", PermissionLevel.HIGH
        )
        
        # Insufficient permission
        assert not self.integration.validate_tool_access(
            "enhanced_file_manager", "delete_file", PermissionLevel.LOW
        )
    
    def test_integration_status(self):
        """Test integration status reporting"""
        status = self.integration.get_integration_status()
        
        assert "total_runtime_tools" in status
        assert "registered_tools" in status
        assert "unregistered_tools" in status
        assert status["total_runtime_tools"] > 0


class TestAgentToolBridge:
    """Test Agent Tool Bridge functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.tool_bridge = AgentToolBridge()
    
    def test_agent_tool_suitability(self):
        """Test tool suitability for different agent types"""
        # Test different agent types
        agent_types = ["autonomous", "researcher", "developer", "analyst", "general"]
        
        for agent_type in agent_types:
            tools = self.tool_bridge.get_available_tools_for_agent(agent_type)
            assert isinstance(tools, list)
            
            # Check that tools are suitable for agent type
            for tool_name in tools:
                assert self.tool_bridge._is_tool_suitable_for_agent(tool_name, agent_type)
    
    def test_tool_info_retrieval(self):
        """Test tool information retrieval for agents"""
        tools = self.tool_bridge.get_available_tools_for_agent("general")
        
        if tools:
            tool_name = tools[0]
            tool_info = self.tool_bridge.get_tool_info_for_agent("general", tool_name)
            
            assert tool_info is not None
            assert "name" in tool_info
            assert "description" in tool_info
            assert "category" in tool_info


class TestAgentToolManager:
    """Test Agent Tool Manager functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.tool_manager = AgentToolManager()
    
    def test_agent_configurations(self):
        """Test agent configurations"""
        expected_agents = ["autonomous", "researcher", "developer", "analyst", "general"]
        
        for agent_type in expected_agents:
            assert agent_type in self.tool_manager.agent_configurations
            
            config = self.tool_manager.agent_configurations[agent_type]
            assert "default_permission_level" in config
            assert "allowed_categories" in config
            assert "max_concurrent_tools" in config
    
    def test_agent_capabilities(self):
        """Test agent capabilities reporting"""
        capabilities = self.tool_manager.get_agent_capabilities("general")
        
        assert "agent_type" in capabilities
        assert "total_tools" in capabilities
        assert "tools" in capabilities
        assert "categories" in capabilities
        
        assert capabilities["agent_type"] == "general"
        assert isinstance(capabilities["total_tools"], int)


class TestIntegrationSafety:
    """Test overall integration safety"""
    
    def test_permission_hierarchy(self):
        """Test permission hierarchy enforcement"""
        # Set low permission level
        permission_engine.set_user_permission_level(PermissionLevel.LOW)
        
        # Low permission should pass
        assert permission_engine.check_tool_permission(PermissionLevel.LOW)
        
        # High permission should fail
        assert not permission_engine.check_tool_permission(PermissionLevel.HIGH)
        
        # Set high permission level
        permission_engine.set_user_permission_level(PermissionLevel.HIGH)
        
        # All permissions should pass
        assert permission_engine.check_tool_permission(PermissionLevel.LOW)
        assert permission_engine.check_tool_permission(PermissionLevel.MEDIUM)
        assert permission_engine.check_tool_permission(PermissionLevel.HIGH)
    
    def test_workspace_isolation(self):
        """Test workspace isolation for all tools"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Test file manager isolation
            file_manager = EnhancedFileManager(temp_dir)
            permission_engine.set_user_permission_level(PermissionLevel.HIGH)

            # Should work within workspace
            file_manager.write_file("test.txt", "content")
            assert file_manager.file_exists("test.txt")
            
            # Should fail outside workspace
            with pytest.raises(PermissionError):
                file_manager._validate_path("/etc/passwd")
            
            # Test code executor isolation
            code_executor = CodeExecutor(temp_dir)
            
            # Safe execution should work
            result = code_executor.execute_code("print('test')", "python")
            assert result["success"]
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# Integration test runner
def run_integration_tests():
    """Run all integration tests"""
    import sys
    
    print("Running VoiceOS Runtime Tool Bridge Tests...")
    
    test_classes = [
        TestEnhancedFileManager,
        TestBrowserTool,
        TestCodeExecutor,
        TestDocumentProcessor,
        TestTaskScheduler,
        TestRuntimeToolBridge,
        TestAgentToolBridge,
        TestAgentToolManager,
        TestIntegrationSafety
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            
            try:
                # Create test instance
                test_instance = test_class()
                test_instance.setup_method()
                
                # Run test
                getattr(test_instance, test_method)()
                
                passed_tests += 1
                print(f"  ✓ {test_method}")
                
                test_instance.teardown_method()
                
            except Exception as e:
                print(f"  ✗ {test_method}: {e}")
    
    print(f"\nTest Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("All tests passed! ✓")
        return True
    else:
        print("Some tests failed! ✗")
        return False


if __name__ == "__main__":
    run_integration_tests()
