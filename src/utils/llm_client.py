
"""
LLM Client with API Key Rotation
Handles Cerebras API with automatic failover between multiple keys.
Updated with accurate rate limits from Cerebras official documentation.
"""

import os
import asyncio
import random
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

class CerebrasClient:
    """
    Cerebras API client with intelligent key rotation.

    Rate Limits (Free Tier):
    - gpt-oss-120b: 30 RPM, 64K TPM, 900 RPH, 14.4K RPD
    - llama3.1-8b: 30 RPM, 60K TPM

    Rate Limits (Pay-as-you-go):
    - gpt-oss-120b: 1K RPM, 1M TPM

    Features:
    - Automatic key rotation on rate limits (429 errors)
    - Exponential backoff with jitter
    - Request tracking and rate limit monitoring via response headers
    - Support for multiple models
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_keys = self._load_api_keys()
        self.current_key_index = 0
        self.key_usage = {key: {'requests': 0, 'last_used': None, 'errors': 0, 'rate_limit_hits': 0} for key in self.api_keys}

        self.max_retries = config.get('cerebras_max_retries', 5)
        self.retry_delay = config.get('cerebras_retry_delay', 2.0)

        # Updated rate limits from official Cerebras docs
        # Free tier defaults - adjust if you have pay-as-you-go
        self.rate_limit_rpm = config.get('cerebras_rate_limit_rpm', 30)
        self.rate_limit_tpm = config.get('cerebras_rate_limit_tpm', 64000)

        self.default_model = config.get('cerebras_default_model', 'gpt-oss-120b')

        self._request_timestamps = []
        self._token_usage = []
        self._lock = asyncio.Lock()

        # Initialize Cerebras client
        self._init_client()

    def _load_api_keys(self) -> List[str]:
        """Load API keys from file."""
        key_file = self.config.get('cerebras_api_keys_file', './config/cerebras_api_keys.txt')
        keys = []

        try:
            with open(key_file, 'r') as f:
                for line in f:
                    key = line.strip()
                    if key and not key.startswith('#'):
                        keys.append(key)
        except FileNotFoundError:
            # Fallback to environment variable
            env_key = os.environ.get('CEREBRAS_API_KEY')
            if env_key:
                keys.append(env_key)

        if not keys:
            raise ValueError("No Cerebras API keys found. Please set CEREBRAS_API_KEY or provide a keys file.")

        return keys

    def _init_client(self):
        """Initialize the Cerebras SDK client."""
        try:
            from cerebras.cloud.sdk import Cerebras
            self._client_class = Cerebras
        except ImportError:
            raise ImportError("cerebras-cloud-sdk not installed. Run: pip install cerebras-cloud-sdk")

    def _get_client(self):
        """Get client with current API key."""
        key = self.api_keys[self.current_key_index]
        return self._client_class(api_key=key)

    def _rotate_key(self):
        """Rotate to next available API key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"Rotated to API key index {self.current_key_index}")

    async def _check_rate_limit(self):
        """Check if we are approaching rate limits."""
        async with self._lock:
            now = datetime.utcnow()

            # Clean old timestamps (older than 1 minute)
            self._request_timestamps = [
                ts for ts in self._request_timestamps 
                if (now - ts).total_seconds() < 60
            ]

            # Check RPM
            if len(self._request_timestamps) >= self.rate_limit_rpm:
                oldest = min(self._request_timestamps)
                wait_time = 60 - (now - oldest).total_seconds()
                if wait_time > 0:
                    print(f"Rate limit approaching. Waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)

    def _parse_rate_limit_headers(self, response) -> Dict[str, Any]:
        """Parse Cerebras rate limit headers from response."""
        headers = {}
        if hasattr(response, 'headers'):
            h = response.headers
            headers = {
                'limit_requests_day': h.get('x-ratelimit-limit-requests-day'),
                'limit_tokens_minute': h.get('x-ratelimit-limit-tokens-minute'),
                'remaining_requests_day': h.get('x-ratelimit-remaining-requests-day'),
                'remaining_tokens_minute': h.get('x-ratelimit-remaining-tokens-minute'),
                'reset_requests_day': h.get('x-ratelimit-reset-requests-day'),
                'reset_tokens_minute': h.get('x-ratelimit-reset-tokens-minute'),
            }
        return headers

    async def generate(self, messages: List[Dict[str, str]] = None, 
                      prompt: str = None,
                      temperature: float = 0.7,
                      max_tokens: int = 4096,
                      tools: List[Dict] = None,
                      model: str = None) -> Dict[str, Any]:
        """
        Generate completion with automatic retry and key rotation.

        Args:
            messages: List of message dicts for chat completion
            prompt: Single prompt string (alternative to messages)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            tools: Tool schemas for function calling
            model: Model to use (defaults to config)

        Returns:
            Dict with 'content', 'tool_calls', 'usage', 'rate_limit_info', etc.
        """
        model = model or self.default_model

        # Convert prompt to messages if needed
        if prompt and not messages:
            messages = [{"role": "user", "content": prompt}]

        last_error = None

        for attempt in range(self.max_retries):
            try:
                await self._check_rate_limit()

                client = self._get_client()

                # Build request parameters
                params = {
                    "messages": messages,
                    "model": model,
                    "temperature": temperature,
                    "max_completion_tokens": max_tokens,
                }

                if tools:
                    params["tools"] = tools
                    params["tool_choice"] = "auto"

                # Make request
                response = client.chat.completions.create(**params)

                # Parse rate limit headers
                rate_limit_info = self._parse_rate_limit_headers(response)

                # Track usage
                async with self._lock:
                    self._request_timestamps.append(datetime.utcnow())
                    key = self.api_keys[self.current_key_index]
                    self.key_usage[key]['requests'] += 1
                    self.key_usage[key]['last_used'] = datetime.utcnow()

                # Parse response
                result = {
                    'content': response.choices[0].message.content or '',
                    'model': model,
                    'finish_reason': response.choices[0].finish_reason,
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                        'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                        'total_tokens': response.usage.total_tokens if response.usage else 0
                    },
                    'rate_limit_info': rate_limit_info
                }

                # Check for tool calls
                if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                    result['tool_calls'] = []
                    for tc in response.choices[0].message.tool_calls:
                        result['tool_calls'].append({
                            'id': tc.id,
                            'name': tc.function.name,
                            'parameters': json.loads(tc.function.arguments)
                        })

                return result

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors (429)
                if any(indicator in error_str for indicator in ['rate limit', '429', 'too many requests', 'quota', 'tokens per minute']):
                    print(f"Rate limit hit on key {self.current_key_index}. Rotating...")
                    self.key_usage[self.api_keys[self.current_key_index]]['rate_limit_hits'] += 1
                    self._rotate_key()

                    # Exponential backoff with jitter
                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    continue

                # Check for authentication errors
                elif any(indicator in error_str for indicator in ['auth', 'key', 'unauthorized', '401']):
                    print(f"Auth error on key {self.current_key_index}. Rotating...")
                    self.key_usage[self.api_keys[self.current_key_index]]['errors'] += 1
                    self._rotate_key()
                    continue

                # Other errors - retry with backoff
                else:
                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Error: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        raise Exception(f"Failed after {self.max_retries} attempts. Last error: {last_error}")

    def get_key_status(self) -> Dict[str, Any]:
        """Get status of all API keys."""
        return {
            'total_keys': len(self.api_keys),
            'current_key': self.current_key_index,
            'key_usage': {
                f"key_{i}": {
                    'requests': info['requests'],
                    'last_used': info['last_used'].isoformat() if info['last_used'] else None,
                    'errors': info['errors'],
                    'rate_limit_hits': info['rate_limit_hits']
                }
                for i, (key, info) in enumerate(self.key_usage.items())
            }
        }

class LLMManager:
    """
    Manages multiple LLM providers with fallback.
    Primary: Cerebras API
    Fallback: OpenAI, Anthropic (if configured)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.primary = CerebrasClient(config)
        self.fallbacks = []

        # Initialize fallback providers if keys available
        if os.environ.get('OPENAI_API_KEY'):
            try:
                import openai
                self.fallbacks.append(('openai', openai.AsyncOpenAI()))
            except ImportError:
                print('Warning: OpenAI fallback not available')

        if os.environ.get('ANTHROPIC_API_KEY'):
            try:
                import anthropic
                self.fallbacks.append(('anthropic', anthropic.AsyncAnthropic()))
            except ImportError:
                print('Warning: Anthropic fallback not available')

    async def generate(self, **kwargs) -> Dict[str, Any]:
        """Generate with primary, fallback if needed."""
        try:
            return await self.primary.generate(**kwargs)
        except Exception as e:
            print(f"Primary LLM failed: {e}. Trying fallbacks...")

            for provider_name, client in self.fallbacks:
                try:
                    if provider_name == 'openai':
                        response = await client.chat.completions.create(
                            model="gpt-4",
                            messages=kwargs.get('messages', []),
                            temperature=kwargs.get('temperature', 0.7),
                            max_tokens=kwargs.get('max_tokens', 4096)
                        )
                        return {
                            'content': response.choices[0].message.content,
                            'model': 'gpt-4',
                            'usage': {
                                'prompt_tokens': response.usage.prompt_tokens,
                                'completion_tokens': response.usage.completion_tokens,
                                'total_tokens': response.usage.total_tokens
                            }
                        }

                    elif provider_name == 'anthropic':
                        response = await client.messages.create(
                            model="claude-3-opus-20240229",
                            messages=kwargs.get('messages', []),
                            max_tokens=kwargs.get('max_tokens', 4096)
                        )
                        return {
                            'content': response.content[0].text,
                            'model': 'claude-3-opus',
                            'usage': {
                                'prompt_tokens': response.usage.input_tokens,
                                'completion_tokens': response.usage.output_tokens,
                                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                            }
                        }

                except Exception as fallback_error:
                    print(f"Fallback {provider_name} failed: {fallback_error}")
                    continue

            raise Exception("All LLM providers failed")
