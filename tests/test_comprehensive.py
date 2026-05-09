"""
Comprehensive Test Suite for Agentic AI Discord Bot
Tests all major components to ensure production readiness.
"""

import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime

# Test Memory System
@pytest.mark.asyncio
async def test_memory_store_and_retrieve():
    from src.memory import MultiLayerMemory, MemoryLayer, MemoryPriority

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'graph_db_path': os.path.join(tmpdir, 'graph_db.json'),
            'chromadb_path': os.path.join(tmpdir, 'chromadb'),
            'collection_name': 'test_memories',
            'memory_decay_rate': 0.01,
            'memory_score_threshold': 0.3,
            'max_memories_per_layer': 1000,
            'sleep_interval': 300
        }

        memory = MultiLayerMemory(config)
        await memory.initialize()

        # Store a memory
        memory_id = await memory.store(
            content="Test memory about Python debugging with user123",
            layer=MemoryLayer.EPISODIC,
            priority=MemoryPriority.MEDIUM,
            entities=["user:123", "python", "debugging"],
            metadata={'user_id': '123', 'task_type': 'debugging'}
        )

        assert memory_id is not None
        assert len(memory_id) == 16

        # Retrieve it
        results = await memory.retrieve("Python debugging", n_results=5)
        assert len(results) > 0
        assert any("Python debugging" in r.content for r in results)

        # Test context building
        context = await memory.get_context('123', 'server1', 'channel1', 'help with python')
        assert 'conversation_history' in context
        assert 'user_id' in context

        # Test stats
        stats = memory.get_stats()
        assert stats['episodic_memories'] >= 1

        await memory.shutdown()

@pytest.mark.asyncio
async def test_memory_graph_relationships():
    from src.memory import MemoryGraph

    with tempfile.TemporaryDirectory() as tmpdir:
        graph = MemoryGraph(os.path.join(tmpdir, 'test_graph.json'))

        graph.add_entity("user:123", "user", {"name": "Alice"})
        graph.add_entity("user:456", "user", {"name": "Bob"})
        graph.add_relationship("user:123", "user:456", "friends", weight=2.0)

        related = graph.get_related("user:123", depth=1)
        assert len(related) == 1
        assert related[0][0] == "user:456"

        path = graph.find_path("user:123", "user:456")
        assert path is not None
        assert len(path) == 2

        graph.save()
        assert os.path.exists(os.path.join(tmpdir, 'test_graph.json'))

# Test Reasoning Engine
@pytest.mark.asyncio
async def test_sequential_reasoning():
    from src.reasoning import ReasoningEngine, ToolRegistry, ReasoningMode

    class MockLLM:
        async def generate(self, **kwargs):
            content = kwargs.get('messages', [{}])[0].get('content', '')
            if 'Solve' in content:
                return {'content': 'Step 1: Analyze the problem. The answer is 4.', 'usage': {}}
            return {'content': 'Reasoning step completed.', 'usage': {}}

    tools = ToolRegistry()
    tools.register("calculate", lambda expression: 4, {
        "description": "Calculate", "parameters": {"type": "object", "properties": {}}
    })

    engine = ReasoningEngine(MockLLM(), None, tools)

    result = await engine.reason(
        query="What is 2+2?",
        mode=ReasoningMode.SEQUENTIAL,
        max_depth=2
    )

    assert 'final_answer' in result
    assert result['mode'] == 'sequential'
    assert 'steps' in result

@pytest.mark.asyncio
async def test_tree_of_thoughts():
    from src.reasoning import ReasoningEngine, ToolRegistry, ReasoningMode

    class MockLLM:
        async def generate(self, **kwargs):
            return {'content': 'Candidate solution approach.', 'usage': {}}

    tools = ToolRegistry()
    engine = ReasoningEngine(MockLLM(), None, tools)

    result = await engine.reason(
        query="Optimize the database query",
        mode=ReasoningMode.PARALLEL,
        max_depth=2
    )

    assert 'final_answer' in result
    assert result['mode'] == 'tree_of_thoughts'
    assert 'exploration_breadth' in result

def test_code_sandbox():
    from src.reasoning import CodeSandbox

    sandbox = CodeSandbox()

    # Test safe execution
    result = sandbox.execute("x = 2 + 2\nprint(x)")
    assert result['success'] is True
    assert '4' in result['output']

    # Test dangerous code blocking
    result = sandbox.execute("import os\nos.system('ls')")
    assert result['success'] is False
    assert 'Blocked' in result['error'] or 'not allowed' in result['error']

    # Test math evaluation
    result = sandbox.evaluate_math("2 + 3 * 4")
    assert result == 14

# Test OSINT Module
def test_osint_report_generation():
    from src.osint import IntelligenceReport, OSINTScope, RiskLevel

    report = IntelligenceReport(
        target_id="123456",
        target_type="discord_user",
        scope=OSINTScope.USER,
        timestamp=datetime.utcnow()
    )

    report.findings = [
        {
            'category': 'Account Metadata',
            'source': 'Discord API',
            'confidence': 'High',
            'details': 'Account created: 2020-01-01',
            'timestamp': datetime.utcnow().isoformat()
        }
    ]
    report.confidence_score = 0.8
    report.risk_assessment = RiskLevel.LOW

    md = report.to_markdown()
    assert '# Intelligence Report' in md
    assert 'Account Metadata' in md

    json_str = report.to_json()
    data = json.loads(json_str)
    assert data['target_id'] == '123456'

# Test Security Module
def test_input_validator():
    from src.utils.security import InputValidator, SecurityPolicy

    validator = InputValidator()

    # Test message sanitization
    clean = validator.sanitize_message("Hello world")
    assert clean == "Hello world"

    # Test long message truncation
    long_msg = "x" * 5000
    truncated = validator.sanitize_message(long_msg)
    assert len(truncated) < 5000
    assert 'truncated' in truncated

    # Test code validation
    ok, error = validator.validate_code("x = 1 + 1")
    assert ok is True

    ok, error = validator.validate_code("import os")
    assert ok is False

    # Test file validation
    ok, error = validator.validate_file("test.py", 1000)
    assert ok is True

    ok, error = validator.validate_file("test.exe", 1000)
    assert ok is False

def test_rate_limiter():
    from src.utils.security import RateLimiter

    limiter = RateLimiter(max_requests=3, window_seconds=60)

    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is False  # Rate limited

    assert limiter.get_remaining("user1") == 0
    assert limiter.get_remaining("user2") == 3

# Test Personality Engine
def test_personality_engine():
    from src.personality import PersonalityEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        personality = PersonalityEngine(
            config_path=os.path.join(tmpdir, 'personality.json'),
            dialogue_path=os.path.join(tmpdir, 'dialogue.txt')
        )

        assert personality.personality['name'] == 'Sentinel'

        prompt = personality.build_prompt(
            "How do I debug Python?",
            memory_context="User likes Python",
            user_info={'name': 'Alice', 'id': '123'}
        )

        assert 'Sentinel' in prompt
        assert 'How do I debug Python?' in prompt
        assert 'Alice' in prompt

# Test Health Module
def test_metrics_collector():
    from src.utils.health import MetricsCollector

    metrics = MetricsCollector()

    asyncio.run(metrics.record_request(0.5, True))
    asyncio.run(metrics.record_memory_access(True))
    asyncio.run(metrics.record_llm_request(True))

    stats = metrics.get_metrics()
    assert stats['requests_total'] == 1
    assert stats['memory_hit_rate'] == 1.0
    assert stats['llm_requests'] == 1

    prometheus = metrics.get_prometheus_format()
    assert 'agent_requests_total' in prometheus

# Integration Test
@pytest.mark.asyncio
async def test_full_pipeline():
    """Test the full agent pipeline from message to response."""
    from src.memory import MultiLayerMemory, MemoryLayer, MemoryPriority
    from src.reasoning import ReasoningEngine, ToolRegistry

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'graph_db_path': os.path.join(tmpdir, 'graph_db.json'),
            'chromadb_path': os.path.join(tmpdir, 'chromadb'),
            'collection_name': 'test',
            'memory_decay_rate': 0.01,
            'memory_score_threshold': 0.3
        }

        memory = MultiLayerMemory(config)
        await memory.initialize()

        # Store some context
        await memory.store(
            content="User Alice likes Python programming",
            layer=MemoryLayer.SEMANTIC,
            priority=MemoryPriority.MEDIUM,
            entities=["user:123", "Alice", "python"],
            metadata={'user_id': '123'}
        )

        # Retrieve context
        context = await memory.get_context('123', 'server1', 'channel1', 'help with python code')
        assert 'learned_concepts' in context

        await memory.shutdown()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
