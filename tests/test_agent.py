
import pytest
import asyncio

# Test memory system
@pytest.mark.asyncio
async def test_memory_store_and_retrieve():
    from src.memory import MultiLayerMemory, MemoryLayer, MemoryPriority

    config = {
        'graph_db_path': './test_data/graph_db.json',
        'chromadb_path': './test_data/chromadb',
        'memory_decay_rate': 0.01,
        'memory_score_threshold': 0.3
    }

    memory = MultiLayerMemory(config)
    await memory.initialize()

    # Store a memory
    memory_id = await memory.store(
        content="Test memory about Python debugging",
        layer=MemoryLayer.EPISODIC,
        priority=MemoryPriority.MEDIUM,
        entities=["user:123", "python", "debugging"],
        metadata={'user_id': '123'}
    )

    assert memory_id is not None

    # Retrieve it
    results = await memory.retrieve("Python debugging", n_results=5)
    assert len(results) > 0

    await memory.shutdown()

# Test reasoning engine
@pytest.mark.asyncio
async def test_sequential_reasoning():
    from src.reasoning import ReasoningEngine, ToolRegistry, ReasoningMode

    # Mock LLM client
    class MockLLM:
        async def generate(self, **kwargs):
            return {'content': 'Test reasoning step', 'usage': {}}

    tools = ToolRegistry()
    engine = ReasoningEngine(MockLLM(), None, tools)

    result = await engine.reason(
        query="What is 2+2?",
        mode=ReasoningMode.SEQUENTIAL,
        max_depth=2
    )

    assert 'final_answer' in result
    assert result['mode'] == 'sequential'
