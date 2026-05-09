
"""
Agentic AI Memory Architecture
Multi-layer memory system with graph relationships, vector search, and decay mechanisms.
Production-ready with complete implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from enum import Enum
import hashlib
import json
import asyncio
import numpy as np
from collections import defaultdict
import networkx as nx
import chromadb
from sentence_transformers import SentenceTransformer
import pickle
import os

class MemoryLayer(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

class MemoryPriority(Enum):
    CRITICAL = 1.0
    HIGH = 0.8
    MEDIUM = 0.5
    LOW = 0.3
    EPHEMERAL = 0.1

@dataclass
class MemoryNode:
    """A single memory unit with metadata for scoring and retrieval."""
    id: str
    content: str
    layer: MemoryLayer
    priority: MemoryPriority
    timestamp: datetime
    last_accessed: datetime
    access_count: int = 0
    relevance_score: float = 1.0
    decay_rate: float = 0.01
    entities: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    source: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_score(self, current_time: datetime, context_entities: Set[str]) -> float:
        """Compute dynamic relevance score based on recency, frequency, and context."""
        age_hours = (current_time - self.timestamp).total_seconds() / 3600
        recency = np.exp(-self.decay_rate * age_hours)
        frequency = 1 + np.log1p(self.access_count)
        priority_weight = self.priority.value

        if context_entities and self.entities:
            overlap = len(set(self.entities) & context_entities) / max(len(self.entities), 1)
            context_boost = 1 + overlap
        else:
            context_boost = 1.0

        score = recency * frequency * priority_weight * context_boost * self.relevance_score
        return float(score)

    def touch(self):
        """Update access metadata."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'layer': self.layer.value,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'relevance_score': self.relevance_score,
            'decay_rate': self.decay_rate,
            'entities': self.entities,
            'relationships': self.relationships,
            'source': self.source,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryNode':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            content=data['content'],
            layer=MemoryLayer(data['layer']),
            priority=MemoryPriority(data['priority']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            access_count=data.get('access_count', 0),
            relevance_score=data.get('relevance_score', 1.0),
            decay_rate=data.get('decay_rate', 0.01),
            entities=data.get('entities', []),
            relationships=data.get('relationships', {}),
            source=data.get('source'),
            embedding=data.get('embedding'),
            metadata=data.get('metadata', {})
        )

class MemoryGraph:
    """Graph database for entity relationships using NetworkX with persistence."""

    def __init__(self, persist_path: Optional[str] = None):
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        self._load()

    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any]):
        """Add or update an entity node."""
        if entity_id not in self.graph:
            self.graph.add_node(
                entity_id,
                type=entity_type,
                **properties,
                created=datetime.utcnow().isoformat(),
                updated=datetime.utcnow().isoformat()
            )
        else:
            existing = dict(self.graph.nodes[entity_id])
            existing.update(properties)
            existing['updated'] = datetime.utcnow().isoformat()
            nx.set_node_attributes(self.graph, {entity_id: existing})

    def add_relationship(self, from_id: str, to_id: str, relation_type: str, 
                        weight: float = 1.0, metadata: Dict = None):
        """Add a weighted relationship between entities."""
        if not self.graph.has_edge(from_id, to_id):
            self.graph.add_edge(
                from_id, to_id,
                type=relation_type,
                weight=weight,
                metadata=metadata or {},
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            current_weight = self.graph[from_id][to_id]["weight"]
            self.graph[from_id][to_id]["weight"] = min(current_weight + weight, 10.0)
            self.graph[from_id][to_id]["updated"] = datetime.utcnow().isoformat()

    def get_related(self, entity_id: str, depth: int = 1, min_weight: float = 0.0) -> List[Tuple[str, str, float]]:
        """Get related entities up to a certain depth."""
        if entity_id not in self.graph:
            return []

        related = []
        visited = {entity_id}
        queue = [(entity_id, 0)]

        while queue:
            current, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    edge_data = self.graph[current][neighbor]
                    if edge_data.get("weight", 0) >= min_weight:
                        related.append((neighbor, edge_data.get("type", "unknown"), edge_data.get("weight", 0)))
                        visited.add(neighbor)
                        queue.append((neighbor, current_depth + 1))

        return related

    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find connection path between two entities."""
        try:
            return nx.shortest_path(self.graph, source, target, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_communities(self) -> List[List[str]]:
        """Detect entity communities."""
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(self.graph.to_undirected())
            communities = defaultdict(list)
            for node, comm_id in partition.items():
                communities[comm_id].append(node)
            return list(communities.values())
        except ImportError:
            return [list(c) for c in nx.weakly_connected_components(self.graph)]

    def get_entity_types(self) -> Dict[str, List[str]]:
        """Group entities by type."""
        types = defaultdict(list)
        for node, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "unknown")
            types[entity_type].append(node)
        return dict(types)

    def get_central_entities(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get most central entities by betweenness centrality."""
        if len(self.graph) == 0:
            return []
        try:
            centrality = nx.betweenness_centrality(self.graph)
            return sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:n]
        except:
            return []

    def _load(self):
        """Load graph from disk."""
        if self.persist_path and os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "r") as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Warning: Could not load graph: {e}")

    def save(self):
        """Save graph to disk."""
        if self.persist_path:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            data = nx.node_link_data(self.graph)
            with open(self.persist_path, "w") as f:
                json.dump(data, f, default=str, indent=2)

class VectorMemoryStore:
    """Vector database wrapper for semantic memory retrieval using ChromaDB."""

    def __init__(self, collection_name: str = "memories", persist_path: str = "./data/chromadb"):
        os.makedirs(persist_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, text: str) -> List[float]:
        """Encode text to vector embedding."""
        return self.encoder.encode(text, convert_to_numpy=True).tolist()

    def add(self, memory_id: str, content: str, metadata: Dict[str, Any]):
        """Add memory to vector store."""
        try:
            embedding = self.encode(content)
            self.collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata]
            )
        except Exception as e:
            print(f"Vector store add error: {e}")

    def search(self, query: str, n_results: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """Search vector store by semantic similarity."""
        try:
            embedding = self.encode(query)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=filter_dict
            )

            memories = []
            for i in range(len(results["ids"][0])):
                memories.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                })
            return memories
        except Exception as e:
            print(f"Vector store search error: {e}")
            return []

    def update(self, memory_id: str, content: str, metadata: Dict[str, Any]):
        """Update existing memory."""
        try:
            self.delete(memory_id)
            self.add(memory_id, content, metadata)
        except Exception as e:
            print(f"Vector store update error: {e}")

    def delete(self, memory_id: str):
        """Delete memory from vector store."""
        try:
            self.collection.delete(ids=[memory_id])
        except Exception as e:
            print(f"Vector store delete error: {e}")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            count = self.collection.count()
            return {"total_memories": count}
        except Exception as e:
            return {"total_memories": 0, "error": str(e)}

class MultiLayerMemory:
    """
    Central memory orchestrator implementing the 4-layer architecture.
    Production-ready with full persistence and background processing.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.working_memory: Dict[str, MemoryNode] = {}
        self.episodic_store: Dict[str, MemoryNode] = {}
        self.semantic_store: Dict[str, MemoryNode] = {}
        self.procedural_store: Dict[str, MemoryNode] = {}

        self.graph = MemoryGraph(config.get("graph_db_path", "./data/graph_db.json"))

        persist_path = config.get("chromadb_path", "./data/chromadb")
        os.makedirs(persist_path, exist_ok=True)
        self.vector_store = VectorMemoryStore(
            collection_name=config.get("collection_name", "agent_memories"),
            persist_path=persist_path
        )

        self.decay_rate = config.get("memory_decay_rate", 0.01)
        self.score_threshold = config.get("memory_score_threshold", 0.3)
        self.max_memories_per_layer = config.get("max_memories_per_layer", 10000)

        self._lock = asyncio.Lock()
        self._background_task = None
        self._running = False

        # Load persisted memory stores
        self._load_stores()

    def _load_stores(self):
        """Load memory stores from disk."""
        stores = {
            "working": (self.working_memory, MemoryLayer.WORKING),
            "episodic": (self.episodic_store, MemoryLayer.EPISODIC),
            "semantic": (self.semantic_store, MemoryLayer.SEMANTIC),
            "procedural": (self.procedural_store, MemoryLayer.PROCEDURAL)
        }

        for name, (store, layer) in stores.items():
            path = self.config.get(f"{name}_store_path", f"./data/{name}_store.pkl")
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        data = pickle.load(f)
                        for mem_id, mem_dict in data.items():
                            store[mem_id] = MemoryNode.from_dict(mem_dict)
                    print(f"Loaded {len(store)} {name} memories")
                except Exception as e:
                    print(f"Warning: Could not load {name} store: {e}")

    def _save_stores(self):
        """Save memory stores to disk."""
        stores = {
            "working": self.working_memory,
            "episodic": self.episodic_store,
            "semantic": self.semantic_store,
            "procedural": self.procedural_store
        }

        for name, store in stores.items():
            path = self.config.get(f"{name}_store_path", f"./data/{name}_store.pkl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                data = {mem_id: mem.to_dict() for mem_id, mem in store.items()}
                with open(path, 'wb') as f:
                    pickle.dump(data, f)
            except Exception as e:
                print(f"Warning: Could not save {name} store: {e}")

    async def initialize(self):
        """Start background memory maintenance."""
        self._running = True
        self._background_task = asyncio.create_task(self._sleep_compute())
        print("Memory system initialized with background processing")

    async def store(self, content: str, layer: MemoryLayer, 
                   priority: MemoryPriority = MemoryPriority.MEDIUM,
                   entities: List[str] = None, relationships: Dict[str, str] = None,
                   source: str = None, metadata: Dict = None) -> str:
        """Store a memory across all appropriate layers."""
        async with self._lock:
            memory_id = hashlib.sha256(
                f"{content}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16]

            node = MemoryNode(
                id=memory_id,
                content=content,
                layer=layer,
                priority=priority,
                timestamp=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                entities=entities or [],
                relationships=relationships or {},
                source=source,
                metadata=metadata or {}
            )

            # Store in appropriate layer
            if layer == MemoryLayer.WORKING:
                self.working_memory[memory_id] = node
            elif layer == MemoryLayer.EPISODIC:
                self.episodic_store[memory_id] = node
            elif layer == MemoryLayer.SEMANTIC:
                self.semantic_store[memory_id] = node
            elif layer == MemoryLayer.PROCEDURAL:
                self.procedural_store[memory_id] = node

            # Index in vector store for semantic retrieval
            self.vector_store.add(memory_id, content, {
                "layer": layer.value,
                "priority": priority.value,
                "timestamp": node.timestamp.isoformat(),
                "entities": json.dumps(entities or []),
                "source": source
            })

            # Build graph relationships
            for entity in (entities or []):
                self.graph.add_entity(
                    entity, "generic",
                    {"first_seen": datetime.utcnow().isoformat()}
                )
                self.graph.add_relationship(memory_id, entity, "mentions", weight=priority.value)

                for other_entity in (entities or []):
                    if other_entity != entity:
                        self.graph.add_relationship(entity, other_entity, "co_occurs", weight=0.5)

            for rel_type, target in (relationships or {}).items():
                self.graph.add_relationship(memory_id, target, rel_type, weight=priority.value)

            # Enforce max memories per layer
            await self._enforce_capacity(layer)

            return memory_id

    async def _enforce_capacity(self, layer: MemoryLayer):
        """Enforce maximum memory capacity per layer by removing lowest scored."""
        stores = {
            MemoryLayer.WORKING: self.working_memory,
            MemoryLayer.EPISODIC: self.episodic_store,
            MemoryLayer.SEMANTIC: self.semantic_store,
            MemoryLayer.PROCEDURAL: self.procedural_store
        }

        store = stores[layer]
        if len(store) > self.max_memories_per_layer:
            current_time = datetime.utcnow()
            scored = [(mem_id, node.compute_score(current_time, set())) 
                     for mem_id, node in store.items()]
            scored.sort(key=lambda x: x[1])

            to_remove = len(store) - self.max_memories_per_layer
            for mem_id, _ in scored[:to_remove]:
                del store[mem_id]
                self.vector_store.delete(mem_id)

    async def retrieve(self, query: str, context_entities: Set[str] = None,
                      layers: List[MemoryLayer] = None, n_results: int = 10) -> List[MemoryNode]:
        """Retrieve memories using hybrid search (vector + graph + score-based)."""
        async with self._lock:
            layers = layers or [MemoryLayer.WORKING, MemoryLayer.EPISODIC, MemoryLayer.SEMANTIC]
            context_entities = context_entities or set()
            current_time = datetime.utcnow()

            # Vector search for semantic similarity
            vector_results = self.vector_store.search(query, n_results=n_results * 2)
            vector_ids = {r["id"] for r in vector_results}

            # Graph-based expansion
            graph_expanded = set()
            for entity in context_entities:
                related = self.graph.get_related(entity, depth=2, min_weight=0.3)
                for related_entity, rel_type, weight in related:
                    graph_expanded.add(related_entity)

            # Collect candidates
            candidates = []
            all_stores = {
                MemoryLayer.WORKING: self.working_memory,
                MemoryLayer.EPISODIC: self.episodic_store,
                MemoryLayer.SEMANTIC: self.semantic_store,
                MemoryLayer.PROCEDURAL: self.procedural_store
            }

            for layer in layers:
                for memory_id, node in all_stores[layer].items():
                    if memory_id in vector_ids or any(e in graph_expanded for e in node.entities):
                        score = node.compute_score(current_time, context_entities)
                        if score >= self.score_threshold:
                            candidates.append((node, score))

            # Sort by score
            candidates.sort(key=lambda x: x[1], reverse=True)

            # Touch accessed memories
            for node, _ in candidates[:n_results]:
                node.touch()

            return [node for node, _ in candidates[:n_results]]

    async def get_context(self, user_id: str, server_id: str, 
                         channel_id: str, current_message: str) -> Dict[str, Any]:
        """Build rich context for a conversation turn."""
        words = set(current_message.lower().split())

        working = await self.retrieve(
            current_message, context_entities=words,
            layers=[MemoryLayer.WORKING], n_results=5
        )
        episodic = await self.retrieve(
            current_message, context_entities=words,
            layers=[MemoryLayer.EPISODIC], n_results=10
        )
        semantic = await self.retrieve(
            current_message, context_entities=words,
            layers=[MemoryLayer.SEMANTIC], n_results=5
        )

        user_memories = [m for m in episodic if m.metadata.get("user_id") == user_id]
        server_memories = [m for m in semantic if m.metadata.get("server_id") == server_id]

        user_entity = f"user:{user_id}"
        related_entities = self.graph.get_related(user_entity, depth=2)

        return {
            "working_memory": [m.to_dict() for m in working],
            "conversation_history": [m.to_dict() for m in user_memories],
            "learned_concepts": [m.to_dict() for m in semantic],
            "server_context": [m.to_dict() for m in server_memories],
            "related_entities": related_entities,
            "user_id": user_id,
            "server_id": server_id,
            "channel_id": channel_id
        }

    async def _sleep_compute(self):
        """Background processing for memory maintenance."""
        while self._running:
            try:
                await asyncio.sleep(self.config.get("sleep_interval", 300))
                await self._background_maintenance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Sleep compute error: {e}")
                await asyncio.sleep(60)

    async def _background_maintenance(self):
        """Perform background memory maintenance."""
        async with self._lock:
            current_time = datetime.utcnow()

            # 1. Decay old memories
            for store in [self.working_memory, self.episodic_store, self.semantic_store]:
                expired = []
                for memory_id, node in list(store.items()):
                    score = node.compute_score(current_time, set())
                    if score < self.score_threshold * 0.5:
                        expired.append(memory_id)

                for memory_id in expired:
                    del store[memory_id]
                    self.vector_store.delete(memory_id)

            # 2. Consolidate working memory to episodic
            consolidated = []
            for memory_id, node in list(self.working_memory.items()):
                if (current_time - node.timestamp).total_seconds() > 3600:
                    node.layer = MemoryLayer.EPISODIC
                    self.episodic_store[memory_id] = node
                    consolidated.append(memory_id)

            for memory_id in consolidated:
                del self.working_memory[memory_id]

            # 3. Build inferred relationships
            for memory_id, node in self.episodic_store.items():
                if len(node.entities) > 1:
                    for i, e1 in enumerate(node.entities):
                        for e2 in node.entities[i+1:]:
                            existing = self.graph.get_related(e1, depth=1)
                            if not any(r[0] == e2 for r in existing):
                                self.graph.add_relationship(e1, e2, "inferred_cooccurrence", weight=0.3)

            # 4. Detect patterns for procedural memory
            task_patterns = defaultdict(int)
            for node in self.episodic_store.values():
                if node.metadata.get("task_type"):
                    pattern_key = f"{node.metadata['task_type']}:{','.join(sorted(node.entities))}"
                    task_patterns[pattern_key] += 1

            for pattern, count in task_patterns.items():
                if count >= 3:
                    await self.store(
                        content=f"Pattern: {pattern} (observed {count} times)",
                        layer=MemoryLayer.PROCEDURAL,
                        priority=MemoryPriority.MEDIUM,
                        metadata={"pattern": pattern, "frequency": count, "auto_generated": True}
                    )

            # 5. Persist state
            self.graph.save()
            self._save_stores()

    async def get_entity_disambiguation(self, entity_name: str, context: str) -> Optional[str]:
        """Resolve ambiguous entity references."""
        candidates = []
        for node in list(self.episodic_store.values()) + list(self.semantic_store.values()):
            if entity_name.lower() in [e.lower() for e in node.entities]:
                score = node.compute_score(datetime.utcnow(), set(context.lower().split()))
                candidates.append((node, score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        if candidates:
            best_match = candidates[0][0]
            return f"{entity_name} (context: {best_match.content[:100]}...)"

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return {
            "working_memories": len(self.working_memory),
            "episodic_memories": len(self.episodic_store),
            "semantic_memories": len(self.semantic_store),
            "procedural_memories": len(self.procedural_store),
            "graph_entities": len(self.graph.graph.nodes()),
            "graph_relationships": len(self.graph.graph.edges()),
            "vector_stats": self.vector_store.get_collection_stats()
        }

    async def shutdown(self):
        """Graceful shutdown with state persistence."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        self.graph.save()
        self._save_stores()
        print("Memory system shutdown complete")
