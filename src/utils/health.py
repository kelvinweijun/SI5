
"""
Health Check & Monitoring Module
Provides Prometheus metrics and health endpoints for Render.com
"""

import time
import asyncio
from typing import Dict, Any
from datetime import datetime
from collections import deque

class MetricsCollector:
    """Collects and exposes runtime metrics."""

    def __init__(self):
        self.request_count = 0
        self.request_latency = deque(maxlen=1000)
        self.error_count = 0
        self.memory_hits = 0
        self.memory_misses = 0
        self.llm_requests = 0
        self.llm_errors = 0
        self.start_time = time.time()
        self.active_conversations = 0
        self._lock = asyncio.Lock()

    async def record_request(self, latency: float, success: bool = True):
        async with self._lock:
            self.request_count += 1
            self.request_latency.append(latency)
            if not success:
                self.error_count += 1

    async def record_memory_access(self, hit: bool):
        async with self._lock:
            if hit:
                self.memory_hits += 1
            else:
                self.memory_misses += 1

    async def record_llm_request(self, success: bool):
        async with self._lock:
            self.llm_requests += 1
            if not success:
                self.llm_errors += 1

    def get_metrics(self) -> Dict[str, Any]:
        avg_latency = sum(self.request_latency) / len(self.request_latency) if self.request_latency else 0
        total_memory = self.memory_hits + self.memory_misses
        memory_hit_rate = self.memory_hits / total_memory if total_memory > 0 else 0

        return {
            'uptime_seconds': time.time() - self.start_time,
            'requests_total': self.request_count,
            'requests_per_minute': self.request_count / ((time.time() - self.start_time) / 60),
            'avg_latency_ms': avg_latency * 1000,
            'error_rate': self.error_count / self.request_count if self.request_count > 0 else 0,
            'memory_hit_rate': memory_hit_rate,
            'llm_requests': self.llm_requests,
            'llm_error_rate': self.llm_errors / self.llm_requests if self.llm_requests > 0 else 0,
            'active_conversations': self.active_conversations,
            'timestamp': datetime.utcnow().isoformat()
        }

    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format."""
        m = self.get_metrics()
        return f"""# HELP agent_uptime_seconds Total uptime in seconds
# TYPE agent_uptime_seconds counter
agent_uptime_seconds {m['uptime_seconds']}

# HELP agent_requests_total Total requests processed
# TYPE agent_requests_total counter
agent_requests_total {m['requests_total']}

# HELP agent_request_latency_ms Average request latency
# TYPE agent_request_latency_ms gauge
agent_request_latency_ms {m['avg_latency_ms']}

# HELP agent_error_rate Error rate
# TYPE agent_error_rate gauge
agent_error_rate {m['error_rate']}

# HELP agent_memory_hit_rate Memory cache hit rate
# TYPE agent_memory_hit_rate gauge
agent_memory_hit_rate {m['memory_hit_rate']}

# HELP agent_llm_requests_total Total LLM requests
# TYPE agent_llm_requests_total counter
agent_llm_requests_total {m['llm_requests']}

# HELP agent_active_conversations Current active conversations
# TYPE agent_active_conversations gauge
agent_active_conversations {m['active_conversations']}
"""

class HealthCheckServer:
    """Simple HTTP server for health checks (Render.com requirement)."""

    def __init__(self, port: int = 10000, metrics: MetricsCollector = None):
        self.port = port
        self.metrics = metrics or MetricsCollector()
        self.app = None

    async def start(self):
        """Start the health check HTTP server."""
        from aiohttp import web

        self.app = web.Application()
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/metrics', self.metrics_handler)
        self.app.router.add_get('/status', self.status_handler)

        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()

        print(f"Health check server running on port {self.port}")

    async def health_handler(self, request):
        """Basic health check endpoint."""
        return web.Response(
            text=json.dumps({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}),
            content_type='application/json',
            status=200
        )

    async def metrics_handler(self, request):
        """Prometheus metrics endpoint."""
        return web.Response(
            text=self.metrics.get_prometheus_format(),
            content_type='text/plain',
            status=200
        )

    async def status_handler(self, request):
        """Detailed status endpoint."""
        status = {
            'status': 'healthy',
            'metrics': self.metrics.get_metrics(),
            'version': '1.0.0',
            'components': {
                'memory': 'active',
                'reasoning': 'active',
                'llm': 'active',
                'discord': 'active'
            }
        }
        return web.Response(
            text=json.dumps(status, indent=2, default=str),
            content_type='application/json',
            status=200
        )

import json
