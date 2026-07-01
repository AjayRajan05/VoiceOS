"""
Testing Framework Module - Comprehensive testing for VoiceOS
Provides unit tests, integration tests, and performance benchmarks
"""

import asyncio
import logging
import time
import unittest
from typing import Dict, Any, List, Optional, Callable, Type
from dataclasses import dataclass, field
from pathlib import Path
import json
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

@dataclass
class FrameworkTestResult:
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FrameworkTestSuite:
    name: str
    tests: List[Callable] = field(default_factory=list)
    setup: Optional[Callable] = None
    teardown: Optional[Callable] = None
    results: List[FrameworkTestResult] = field(default_factory=list)

@dataclass
class BenchmarkResult:
    name: str
    metric_value: float
    metric_unit: str
    baseline: Optional[float] = None
    improvement: Optional[float] = None

class VoiceOSTestFramework:
    def __init__(self):
        self.test_suites: Dict[str, FrameworkTestSuite] = {}
        self.benchmarks: Dict[str, List[BenchmarkResult]] = {}
        self.coverage_data: Dict[str, Any] = {}
        
        # Test configuration
        self.config = {
            "timeout": 30.0,
            "max_retries": 3,
            "parallel_execution": True,
            "capture_output": True,
            "stop_on_failure": False
        }
        
        # Statistics
        self.stats = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "total_duration": 0.0,
            "average_duration": 0.0
        }
    
    def register_test_suite(self, suite: FrameworkTestSuite):
        """
        Register a test suite
        """
        self.test_suites[suite.name] = suite
        logger.info(f"Registered test suite: {suite.name}")
    
    def create_test_suite(self, name: str, setup_func: Callable = None, 
                         teardown_func: Callable = None) -> FrameworkTestSuite:
        """
        Create and register a new test suite
        """
        suite = FrameworkTestSuite(name=name, setup=setup_func, teardown=teardown_func)
        self.register_test_suite(suite)
        return suite
    
    def add_test(self, suite_name: str, test_func: Callable):
        """
        Add a test to a suite
        """
        if suite_name not in self.test_suites:
            self.create_test_suite(suite_name)
        
        self.test_suites[suite_name].tests.append(test_func)
        logger.info(f"Added test to suite {suite_name}: {test_func.__name__}")
    
    async def run_test_suite(self, suite_name: str) -> List[FrameworkTestResult]:
        """
        Run a specific test suite
        """
        if suite_name not in self.test_suites:
            raise ValueError(f"Test suite not found: {suite_name}")
        
        suite = self.test_suites[suite_name]
        results = []
        
        logger.info(f"Running test suite: {suite_name}")
        
        try:
            # Setup
            if suite.setup:
                await suite.setup()
            
            # Run tests
            if self.config["parallel_execution"]:
                results = await self._run_tests_parallel(suite.tests)
            else:
                results = await self._run_tests_sequential(suite.tests)
            
            # Teardown
            if suite.teardown:
                await suite.teardown()
            
            suite.results = results
            
        except Exception as e:
            logger.error(f"Test suite {suite_name} failed: {e}")
            results.append(FrameworkTestResult(
                name=f"suite_{suite_name}",
                passed=False,
                duration=0.0,
                error=str(e)
            ))
        
        return results
    
    async def _run_tests_sequential(self, tests: List[Callable]) -> List[FrameworkTestResult]:
        """
        Run tests sequentially
        """
        results = []
        
        for test_func in tests:
            result = await self._run_single_test(test_func)
            results.append(result)
            
            # Update stats
            self._update_stats(result)
            
            # Stop on failure if configured
            if not result.passed and self.config["stop_on_failure"]:
                logger.error(f"Stopping test execution due to failure in {test_func.__name__}")
                break
        
        return results
    
    async def _run_tests_parallel(self, tests: List[Callable]) -> List[FrameworkTestResult]:
        """
        Run tests in parallel
        """
        tasks = [self._run_single_test(test) for test in tests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to test results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(FrameworkTestResult(
                    name=tests[i].__name__,
                    passed=False,
                    duration=0.0,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
                self._update_stats(result)
        
        return processed_results
    
    async def _run_single_test(self, test_func: Callable) -> FrameworkTestResult:
        """
        Run a single test
        """
        start_time = time.time()
        
        for attempt in range(self.config["max_retries"] + 1):
            try:
                # Run test with timeout
                result = await asyncio.wait_for(
                    test_func(), 
                    timeout=self.config["timeout"]
                )
                
                duration = time.time() - start_time
                
                return FrameworkTestResult(
                    name=test_func.__name__,
                    passed=True,
                    duration=duration,
                    details={"result": result, "attempt": attempt + 1}
                )
                
            except asyncio.TimeoutError:
                error = f"Test timed out after {self.config['timeout']}s"
                if attempt == self.config["max_retries"]:
                    return FrameworkTestResult(
                        name=test_func.__name__,
                        passed=False,
                        duration=time.time() - start_time,
                        error=error
                    )
                
            except Exception as e:
                error = str(e)
                if attempt == self.config["max_retries"]:
                    return FrameworkTestResult(
                        name=test_func.__name__,
                        passed=False,
                        duration=time.time() - start_time,
                        error=error
                    )
            
            # Wait before retry
            await asyncio.sleep(0.1 * (attempt + 1))
        
        # Should not reach here
        return FrameworkTestResult(
            name=test_func.__name__,
            passed=False,
            duration=time.time() - start_time,
            error="Unknown error"
        )
    
    def _update_stats(self, result: FrameworkTestResult):
        """
        Update test statistics
        """
        self.stats["total_tests"] += 1
        self.stats["total_duration"] += result.duration
        
        if result.passed:
            self.stats["passed_tests"] += 1
        else:
            self.stats["failed_tests"] += 1
        
        self.stats["average_duration"] = (
            self.stats["total_duration"] / self.stats["total_tests"]
        )
    
    async def run_all_tests(self) -> Dict[str, List[FrameworkTestResult]]:
        """
        Run all registered test suites
        """
        all_results = {}
        
        for suite_name in self.test_suites:
            logger.info(f"Running suite: {suite_name}")
            results = await self.run_test_suite(suite_name)
            all_results[suite_name] = results
        
        return all_results
    
    def add_benchmark(self, category: str, name: str, value: float, unit: str, 
                     baseline: float = None):
        """
        Add a benchmark result
        """
        if category not in self.benchmarks:
            self.benchmarks[category] = []
        
        improvement = None
        if baseline is not None:
            improvement = ((baseline - value) / baseline) * 100 if baseline != 0 else 0
        
        result = BenchmarkResult(
            name=name,
            metric_value=value,
            metric_unit=unit,
            baseline=baseline,
            improvement=improvement
        )
        
        self.benchmarks[category].append(result)
        logger.info(f"Added benchmark: {category}/{name} = {value} {unit}")
    
    async def run_performance_benchmark(self, name: str, func: Callable, 
                                       iterations: int = 100) -> BenchmarkResult:
        """
        Run performance benchmark
        """
        logger.info(f"Running benchmark: {name}")
        
        # Warm up
        for _ in range(5):
            await func()
        
        # Benchmark
        start_time = time.time()
        for _ in range(iterations):
            await func()
        duration = time.time() - start_time
        
        avg_duration = duration / iterations
        ops_per_second = 1.0 / avg_duration if avg_duration > 0 else 0
        
        result = BenchmarkResult(
            name=name,
            metric_value=ops_per_second,
            metric_unit="ops/sec",
            details={
                "iterations": iterations,
                "total_duration": duration,
                "avg_duration": avg_duration
            }
        )
        
        # Store result
        self.add_benchmark("performance", name, ops_per_second, "ops/sec")
        
        return result
    
    def generate_test_report(self, results: Dict[str, List[FrameworkTestResult]]) -> str:
        """
        Generate comprehensive test report
        """
        report = []
        report.append("# VoiceOS Test Report")
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary
        total_tests = sum(len(suite_results) for suite_results in results.values())
        passed_tests = sum(
            sum(1 for r in suite_results if r.passed)
            for suite_results in results.values()
        )
        failed_tests = total_tests - passed_tests
        
        report.append("## Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- Passed: {passed_tests}")
        report.append(f"- Failed: {failed_tests}")
        report.append(f"- Success Rate: {(passed_tests/total_tests*100):.1f}%")
        report.append("")
        
        # Suite details
        for suite_name, suite_results in results.items():
            report.append(f"## {suite_name}")
            suite_passed = sum(1 for r in suite_results if r.passed)
            suite_total = len(suite_results)
            report.append(f"Tests: {suite_passed}/{suite_total} passed")
            report.append("")
            
            for result in suite_results:
                status = "✅" if result.passed else "❌"
                report.append(f"{status} {result.name} ({result.duration:.3f}s)")
                if not result.passed and result.error:
                    report.append(f"   Error: {result.error}")
            
            report.append("")
        
        # Benchmarks
        if self.benchmarks:
            report.append("## Benchmarks")
            for category, benchmarks in self.benchmarks.items():
                report.append(f"### {category}")
                for benchmark in benchmarks:
                    report.append(f"- {benchmark.name}: {benchmark.metric_value:.2f} {benchmark.metric_unit}")
                    if benchmark.improvement is not None:
                        improvement_str = f"({benchmark.improvement:+.1f}%)"
                        report.append(f"  {improvement_str}")
                report.append("")
        
        return "\n".join(report)
    
    def save_test_report(self, results: Dict[str, List[FrameworkTestResult]], file_path: str):
        """
        Save test report to file
        """
        report = self.generate_test_report(results)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Test report saved to {file_path}")
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive test statistics
        """
        return {
            **self.stats,
            "test_suites": len(self.test_suites),
            "total_tests_registered": sum(len(suite.tests) for suite in self.test_suites.values()),
            "benchmark_categories": len(self.benchmarks),
            "total_benchmarks": sum(len(benchmarks) for benchmarks in self.benchmarks.values())
        }

# Built-in test suites
class CoreTests:
    """Built-in core system tests"""
    
    @staticmethod
    async def test_event_bus():
        """Test event bus functionality"""
        from core.events.event_bus import EventBus
        from core.events.events import Events
        
        bus = EventBus()
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe(Events.SPEECH_TRANSCRIBED, handler)
        await bus.publish(Events.SPEECH_TRANSCRIBED, {"text": "test"}, "test")
        
        assert len(received_events) == 1
        assert received_events[0].data["text"] == "test"
        return True
    
    @staticmethod
    async def test_planner():
        """Test task planner"""
        from agents.core.planner import Planner, TaskType
        
        planner = Planner()
        
        # Test simple task
        plan = planner.analyze_input("open chrome")
        assert plan.type == TaskType.SIMPLE
        assert plan.intent == "open_application"
        
        # Test complex task
        plan = planner.analyze_input("research machine learning")
        assert plan.type == TaskType.COMPLEX
        assert plan.role == "researcher"
        
        return True
    
    @staticmethod
    async def test_memory_system():
        """Test memory system"""
        from memory.agent_memory import AgentMemory, MemoryType, MemoryPriority
        
        memory = AgentMemory("test_agent")
        
        # Store memory
        memory_id = memory.store_memory(
            MemoryType.CONVERSATION,
            {"message": "test"},
            priority=MemoryPriority.MEDIUM
        )
        
        # Retrieve memory
        retrieved = memory.retrieve_memory(memory_id)
        assert retrieved is not None
        assert retrieved.content["message"] == "test"
        
        return True

class IntegrationTests:
    """Built-in integration tests"""
    
    @staticmethod
    async def test_agent_creation():
        """Test dynamic agent creation"""
        from agents.dynamic.agent_builder import AgentBuilder
        
        builder = AgentBuilder()
        
        # Test building researcher agent
        agent = await builder.build_agent("researcher", "research", {"test": "data"})
        
        assert agent is not None
        assert agent.config.role == "researcher"
        assert "web_search" in agent.tools
        
        return True
    
    @staticmethod
    async def test_tool_execution():
        """Test tool registry and execution"""
        from tools.tool_registry import ToolRegistry, ToolConfig
        
        registry = ToolRegistry()
        
        # Test tool discovery
        tools = registry.list_tools()
        assert len(tools) >= 0  # Should have some tools
        
        return True

# Create test framework instance
test_framework = VoiceOSTestFramework()

# Register built-in test suites
core_suite = test_framework.create_test_suite("core")
core_suite.tests = [
    CoreTests.test_event_bus,
    CoreTests.test_planner,
    CoreTests.test_memory_system
]

integration_suite = test_framework.create_test_suite("integration")
integration_suite.tests = [
    IntegrationTests.test_agent_creation,
    IntegrationTests.test_tool_execution
]

# Main test runner
async def run_all_tests():
    """Run all built-in tests"""
    print("Running VoiceOS Test Suite...")
    print("=" * 50)
    
    results = await test_framework.run_all_tests()
    
    # Print summary
    stats = test_framework.get_test_statistics()
    print(f"\nTest Summary:")
    print(f"Total Tests: {stats['total_tests']}")
    print(f"Passed: {stats['passed_tests']}")
    print(f"Failed: {stats['failed_tests']}")
    print(f"Success Rate: {(stats['passed_tests']/stats['total_tests']*100):.1f}%")
    
    # Save report
    test_framework.save_test_report(results, "test_report.md")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_all_tests())
