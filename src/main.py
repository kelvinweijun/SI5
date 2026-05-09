
"""
Main Entry Point
Initializes and runs the agentic AI Discord bot with health checks.
Production-ready with full error handling and graceful shutdown.
"""

import os
import sys
import asyncio
import signal
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.memory import MultiLayerMemory, MemoryLayer, MemoryPriority
from src.reasoning import ReasoningEngine, ToolRegistry
from src.osint import OSINTCollector
from src.discord import AgenticBot
from src.personality import PersonalityEngine
from src.utils.llm_client import LLMManager
from src.utils.health import HealthCheckServer, MetricsCollector
from src.utils.security import SecurityPolicy, InputValidator, RateLimiter

def load_config() -> dict:
    """Load configuration from environment variables with defaults."""
    return {
        'discord_bot_token': os.environ.get('DISCORD_BOT_TOKEN'),
        'command_prefix': os.environ.get('COMMAND_PREFIX', '!'),
        'admin_roles': os.environ.get('ADMIN_ROLES', 'Admin,Administrator').split(','),
        'allowed_servers': os.environ.get('ALLOWED_SERVERS', 'all').split(','),
        'cerebras_api_keys_file': os.environ.get('CEREBRAS_API_KEYS_FILE', 'cerebras_api_keys.txt'),
        'cerebras_default_model': os.environ.get('CEREBRAS_DEFAULT_MODEL', 'gpt-oss-120b'),
        'cerebras_max_retries': int(os.environ.get('CEREBRAS_MAX_RETRIES', '5')),
        'cerebras_retry_delay': float(os.environ.get('CEREBRAS_RETRY_DELAY', '2.0')),
        'cerebras_rate_limit_rpm': int(os.environ.get('CEREBRAS_RATE_LIMIT_RPM', '30')),
        'cerebras_rate_limit_tpm': int(os.environ.get('CEREBRAS_RATE_LIMIT_TPM', '64000')),
        'graph_db_path': os.environ.get('GRAPH_DB_PATH', './data/graph_db.json'),
        'chromadb_path': os.environ.get('CHROMADB_PATH', './data/chromadb'),
        'collection_name': os.environ.get('COLLECTION_NAME', 'agent_memories'),
        'memory_decay_rate': float(os.environ.get('AGENT_MEMORY_DECAY_RATE', '0.01')),
        'memory_score_threshold': float(os.environ.get('AGENT_MEMORY_SCORE_THRESHOLD', '0.3')),
        'max_memories_per_layer': int(os.environ.get('AGENT_MAX_MEMORIES_PER_LAYER', '10000')),
        'sleep_interval': int(os.environ.get('AGENT_SLEEP_INTERVAL', '300')),
        'osint_enabled': os.environ.get('OSINT_ENABLED', 'false').lower() == 'true',
        'osint_max_depth': int(os.environ.get('OSINT_MAX_DEPTH', '3')),
        'osint_rate_limit_delay': float(os.environ.get('OSINT_RATE_LIMIT_DELAY', '1.5')),
        'tineye_api_key': os.environ.get('TINEYE_API_KEY'),
        'google_api_key': os.environ.get('GOOGLE_API_KEY'),
        'personality_file': os.environ.get('AGENT_PERSONALITY_FILE', './config/personality.json'),
        'max_file_size': int(os.environ.get('MAX_FILE_SIZE', str(25 * 1024 * 1024))),
        'port': int(os.environ.get('PORT', '10000')),
        'host': os.environ.get('HOST', '0.0.0.0'),
    }

async def main():
    """Main async entry point with full initialization."""
    config = load_config()

    if not config['discord_bot_token']:
        print("ERROR: DISCORD_BOT_TOKEN not set!")
        sys.exit(1)

    print("=" * 60)
    print("Agentic AI Discord Bot - Starting up")
    print("=" * 60)

    # Initialize metrics
    metrics = MetricsCollector()

    # Initialize security
    security_policy = SecurityPolicy(max_file_size=config['max_file_size'])
    validator = InputValidator(security_policy)
    rate_limiter = RateLimiter()

    # Initialize components
    print("Initializing memory system...")
    memory = MultiLayerMemory(config)
    await memory.initialize()

    print("Initializing LLM manager...")
    llm = LLMManager(config)

    print("Initializing reasoning engine...")
    tools = ToolRegistry()
    _register_default_tools(tools, memory, llm)
    reasoning = ReasoningEngine(llm, memory, tools)

    print("Initializing OSINT collector...")
    osint = OSINTCollector(config)

    print("Initializing personality engine...")
    personality = PersonalityEngine(
        config_path=config['personality_file'],
        dialogue_path='./config/dialogue.txt'
    )

    print("Initializing Discord bot...")
    bot = AgenticBot(config, memory, reasoning, osint, llm)

    # Start health check server
    print(f"Starting health check server on port {config['port']}...")
    health_server = HealthCheckServer(port=config['port'], metrics=metrics)
    await health_server.start()

    # Handle shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\nShutdown signal received. Cleaning up...")
        shutdown_event.set()
        asyncio.create_task(bot.close())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot
    try:
        print("Connecting to Discord...")
        await bot.start(config['discord_bot_token'])
    except KeyboardInterrupt:
        print("Keyboard interrupt received.")
    except Exception as e:
        print(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.close()
        print("Bot shutdown complete.")

def _register_default_tools(tools: ToolRegistry, memory, llm):
    """Register default tools for the reasoning engine."""

    async def search_memory_func(query: str, user_id: str = None):
        entities = {user_id} if user_id else set()
        return await memory.retrieve(query, context_entities=entities, n_results=5)

    tools.register(
        name="search_memory",
        func=search_memory_func,
        schema={
            "description": "Search through the agent's memory for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "user_id": {"type": "string", "description": "Optional user ID to filter by"}
                },
                "required": ["query"]
            }
        }
    )

    def calculate_func(expression: str):
        try:
            # Safe evaluation using ast
            import ast
            import operator

            allowed_ops = {
                ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.Pow: operator.pow, ast.USub: operator.neg
            }

            tree = ast.parse(expression, mode='eval')

            def eval_node(node):
                if isinstance(node, ast.Num):
                    return node.n
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    return allowed_ops[type(node.op)](eval_node(node.left), eval_node(node.right))
                elif isinstance(node, ast.UnaryOp):
                    return allowed_ops[type(node.op)](eval_node(node.operand))
                else:
                    raise ValueError(f"Unsupported node: {type(node)}")

            return eval_node(tree.body)
        except Exception as e:
            return f"Error: {str(e)}"

    tools.register(
        name="calculate",
        func=calculate_func,
        schema={
            "description": "Perform mathematical calculations safely",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
                },
                "required": ["expression"]
            }
        }
    )

    def get_time_func():
        from datetime import datetime
        return datetime.utcnow().isoformat()

    tools.register(
        name="get_current_time",
        func=get_time_func,
        schema={
            "description": "Get current UTC time",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    )

if __name__ == "__main__":
    asyncio.run(main())
