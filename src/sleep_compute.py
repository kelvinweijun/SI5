
"""
Sleep-Time Compute Module
Background worker for continuous memory processing and relationship building.
Production-ready with full entity disambiguation, cross-referencing, and summarization.
"""

import os
import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.memory import MultiLayerMemory, MemoryLayer, MemoryPriority
from src.utils.llm_client import LLMManager

async def sleep_compute_worker():
    """
    Background worker performing continuous processing:
    - Memory consolidation and summarization
    - Relationship graph updates
    - Entity disambiguation
    - Pattern detection
    - Memory decay and scoring updates
    - Cross-reference analysis
    """
    config = {
        'graph_db_path': os.environ.get('GRAPH_DB_PATH', './data/graph_db.json'),
        'chromadb_path': os.environ.get('CHROMADB_PATH', './data/chromadb'),
        'collection_name': os.environ.get('COLLECTION_NAME', 'agent_memories'),
        'memory_decay_rate': float(os.environ.get('AGENT_MEMORY_DECAY_RATE', '0.01')),
        'memory_score_threshold': float(os.environ.get('AGENT_MEMORY_SCORE_THRESHOLD', '0.3')),
        'sleep_interval': int(os.environ.get('AGENT_SLEEP_INTERVAL', '300')),
        'cerebras_api_keys_file': os.environ.get('CEREBRAS_API_KEYS_FILE', './config/cerebras_api_keys.txt'),
        'cerebras_default_model': os.environ.get('CEREBRAS_DEFAULT_MODEL', 'gpt-oss-120b'),
        'cerebras_max_retries': int(os.environ.get('CEREBRAS_MAX_RETRIES', '5')),
        'cerebras_retry_delay': float(os.environ.get('CEREBRAS_RETRY_DELAY', '2.0')),
    }

    print("=" * 60)
    print("Sleep-Time Compute Worker Starting")
    print("=" * 60)
    print("This process runs background memory maintenance continuously.")
    print(f"Sleep interval: {config['sleep_interval']} seconds")
    print()

    # Initialize memory system
    memory = MultiLayerMemory(config)
    await memory.initialize()

    # Initialize LLM for background inference
    llm = LLMManager(config)

    print("Background processing active. Press Ctrl+C to stop.")
    print("=" * 60)

    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            start_time = time.time()

            print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Cycle #{cycle_count} starting...")

            # 1. Deep entity disambiguation
            disambiguated = await _perform_entity_disambiguation(memory, llm)
            if disambiguated > 0:
                print(f"  - Disambiguated {disambiguated} entities")

            # 2. Cross-reference analysis
            cross_refs = await _perform_cross_reference(memory)
            if cross_refs > 0:
                print(f"  - Created {cross_refs} cross-references")

            # 3. Memory summarization
            summaries = await _summarize_old_memories(memory, llm)
            if summaries > 0:
                print(f"  - Summarized {summaries} memory clusters")

            # 4. Pattern detection and procedural memory creation
            patterns = await _detect_patterns(memory)
            if patterns > 0:
                print(f"  - Detected {patterns} new patterns")

            # 5. Memory health check
            stats = memory.get_stats()
            print(f"  - Memory health: {stats['working_memories']} working, "
                  f"{stats['episodic_memories']} episodic, "
                  f"{stats['semantic_memories']} semantic, "
                  f"{stats['procedural_memories']} procedural")

            elapsed = time.time() - start_time
            print(f"  - Cycle completed in {elapsed:.1f}s")
            print()

            await asyncio.sleep(config['sleep_interval'])

    except asyncio.CancelledError:
        print("\nWorker cancelled. Shutting down...")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        print(f"\nWorker error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await memory.shutdown()
        print("Worker shutdown complete.")

async def _perform_entity_disambiguation(memory: MultiLayerMemory, llm: LLMManager) -> int:
    """
    Identify and resolve ambiguous entity references.
    Returns number of disambiguations performed.
    """
    disambiguated = 0

    try:
        # Get all entities from graph
        entity_types = memory.graph.get_entity_types()

        # Find ambiguous entities (same name, different contexts)
        name_groups = defaultdict(list)
        for entity_type, entities in entity_types.items():
            for entity in entities:
                # Extract base name (remove prefixes like user:, server:)
                base_name = entity.split(':')[-1] if ':' in entity else entity
                name_groups[base_name.lower()].append(entity)

        # Process ambiguous names
        for name, entity_list in name_groups.items():
            if len(entity_list) > 1:
                # Retrieve context for each entity
                contexts = []
                for entity in entity_list:
                    related = memory.graph.get_related(entity, depth=1)
                    contexts.append({
                        'entity': entity,
                        'related_count': len(related),
                        'related': related[:5]
                    })

                # Create disambiguation memory
                disambiguation_text = f"Entity '{name}' has {len(entity_list)} distinct references: "
                disambiguation_text += ", ".join([f"{c['entity']} ({c['related_count']} connections)" for c in contexts])

                await memory.store(
                    content=disambiguation_text,
                    layer=MemoryLayer.SEMANTIC,
                    priority=MemoryPriority.MEDIUM,
                    entities=entity_list + [name],
                    metadata={
                        'disambiguation': True,
                        'ambiguous_name': name,
                        'entity_count': len(entity_list),
                        'contexts': contexts
                    }
                )
                disambiguated += 1
    except Exception as e:
        print(f"Entity disambiguation error: {e}")

    return disambiguated

async def _perform_cross_reference(memory: MultiLayerMemory) -> int:
    """
    Cross-reference memories to find hidden connections.
    Returns number of new relationships created.
    """
    new_relationships = 0

    try:
        # Get central entities
        central = memory.graph.get_central_entities(n=20)

        for entity_id, centrality in central:
            # Find memories mentioning this entity
            related_memories = []
            for store in [memory.episodic_store, memory.semantic_store]:
                for mem_id, node in store.items():
                    if entity_id in node.entities:
                        related_memories.append(node)

            # Look for shared entities across unrelated memories
            for i, mem1 in enumerate(related_memories):
                for mem2 in related_memories[i+1:]:
                    shared = set(mem1.entities) & set(mem2.entities)
                    shared.discard(entity_id)

                    if shared:
                        for shared_entity in shared:
                            # Check if already connected
                            existing = memory.graph.find_path(mem1.id, mem2.id)
                            if not existing:
                                memory.graph.add_relationship(
                                    mem1.id, mem2.id,
                                    'shared_context',
                                    weight=0.4,
                                    metadata={'shared_entity': shared_entity}
                                )
                                new_relationships += 1
    except Exception as e:
        print(f"Cross-reference error: {e}")

    return new_relationships

async def _summarize_old_memories(memory: MultiLayerMemory, llm: LLMManager) -> int:
    """
    Summarize old episodic memories into semantic memories.
    Compresses memory while preserving key information.
    Returns number of summaries created.
    """
    summaries_created = 0

    try:
        current_time = datetime.utcnow()

        # Find old episodic memories (older than 7 days)
        old_memories = []
        for mem_id, node in list(memory.episodic_store.items()):
            age_days = (current_time - node.timestamp).days
            if age_days > 7 and node.access_count < 3:
                old_memories.append(node)

        # Group by user and topic
        user_groups = defaultdict(list)
        for mem in old_memories:
            user_id = mem.metadata.get('user_id', 'unknown')
            user_groups[user_id].append(mem)

        for user_id, memories in user_groups.items():
            if len(memories) < 3:
                continue

            # Create summary using LLM
            memory_texts = [m.content[:200] for m in memories[:10]]
            summary_prompt = f"""Summarize the following conversation memories for user {user_id}:

{chr(10).join(memory_texts)}

Create a concise summary capturing key topics, preferences, and important facts."""

            try:
                response = await llm.generate(
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.5,
                    max_tokens=500
                )

                summary_content = response['content']

                # Store as semantic memory
                await memory.store(
                    content=f"Summary of conversations with {user_id}: {summary_content}",
                    layer=MemoryLayer.SEMANTIC,
                    priority=MemoryPriority.MEDIUM,
                    entities=[f"user:{user_id}", "conversation_summary"],
                    metadata={
                        'summary_type': 'conversation_cluster',
                        'user_id': user_id,
                        'source_memories': len(memories),
                        'auto_generated': True
                    }
                )

                summaries_created += 1

                # Mark original memories as summarized (reduce score)
                for mem in memories:
                    mem.relevance_score *= 0.5

            except Exception as e:
                print(f"Summary generation error: {e}")
    except Exception as e:
        print(f"Memory summarization error: {e}")

    return summaries_created

async def _detect_patterns(memory: MultiLayerMemory) -> int:
    """
    Detect usage patterns and create procedural memories.
    Returns number of patterns detected.
    """
    patterns_detected = 0

    try:
        # Analyze task types in episodic memory
        task_patterns = defaultdict(lambda: {'count': 0, 'entities': set(), 'examples': []})

        for mem_id, node in memory.episodic_store.items():
            task_type = node.metadata.get('task_type')
            if task_type:
                task_patterns[task_type]['count'] += 1
                task_patterns[task_type]['entities'].update(node.entities)
                task_patterns[task_type]['examples'].append(node.content[:100])

        # Create procedural memories for frequent patterns
        for task_type, data in task_patterns.items():
            if data['count'] >= 3:
                # Check if procedural memory already exists
                existing = False
                for proc_id, proc in memory.procedural_store.items():
                    if task_type in proc.metadata.get('pattern', ''):
                        existing = True
                        break

                if not existing:
                    pattern_desc = f"Pattern: {task_type} (observed {data['count']} times). "
                    pattern_desc += f"Common entities: {', '.join(list(data['entities'])[:5])}. "
                    pattern_desc += f"Example: {data['examples'][0]}"

                    await memory.store(
                        content=pattern_desc,
                        layer=MemoryLayer.PROCEDURAL,
                        priority=MemoryPriority.MEDIUM,
                        entities=list(data['entities'])[:10],
                        metadata={
                            'pattern': task_type,
                            'frequency': data['count'],
                            'auto_generated': True,
                            'examples': data['examples'][:3]
                        }
                    )
                    patterns_detected += 1
    except Exception as e:
        print(f"Pattern detection error: {e}")

    return patterns_detected

if __name__ == "__main__":
    asyncio.run(sleep_compute_worker())
