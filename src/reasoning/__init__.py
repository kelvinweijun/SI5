
"""
Advanced Reasoning Engine
Implements Tree-of-Thoughts, Chain-of-Thought, Reflective, and Analogical reasoning.
Production-ready with full tool calling, code sandbox, and evaluation.
"""

import asyncio
import json
import re
import math
import random
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import traceback
import io
import contextlib
import ast
import operator

class ReasoningMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    REFLECTIVE = "reflective"
    ANALOGICAL = "analogical"

@dataclass
class ThoughtNode:
    """A single node in the reasoning tree."""
    id: str
    content: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    score: float = 0.0
    depth: int = 0
    reasoning_mode: ReasoningMode = ReasoningMode.SEQUENTIAL
    evidence: List[str] = field(default_factory=list)
    is_terminal: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class CodeSandbox:
    """Safe code execution environment with restricted builtins."""

    ALLOWED_MODULES = {
        'math', 'random', 'datetime', 'json', 're', 'statistics',
        'itertools', 'functools', 'collections', 'decimal', 'fractions',
        'string', 'hashlib', 'base64', 'typing', 'inspect'
    }

    SAFE_BUILTINS = {
        'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
        'chr': chr, 'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
        'filter': filter, 'float': float, 'format': format, 'frozenset': frozenset,
        'hasattr': hasattr, 'hash': hash, 'hex': hex, 'int': int, 'isinstance': isinstance,
        'issubclass': issubclass, 'iter': iter, 'len': len, 'list': list, 'map': map,
        'max': max, 'min': min, 'next': next, 'oct': oct, 'ord': ord, 'pow': pow,
        'print': lambda *args, **kwargs: None, 'range': range, 'repr': repr,
        'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
        'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
        'zip': zip, 'Exception': Exception, 'True': True, 'False': False, 'None': None
    }

    MATH_OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod
    }

    def __init__(self):
        self.execution_history = []
        self._output_buffer = io.StringIO()

    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Restricted import function."""
        if name in self.ALLOWED_MODULES:
            return __import__(name, globals, locals, fromlist, level)
        raise ImportError("Import of '" + name + "' is not allowed")

    def _safe_open(self, *args, **kwargs):
        """Prevent file system access."""
        raise PermissionError("File system access is not allowed in sandbox")

    def execute(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute Python code in a restricted environment."""
        result = {
            'success': False,
            'output': '',
            'error': None,
            'return_value': None,
            'execution_time': 0
        }

        try:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                result['error'] = "Syntax Error: " + str(e)
                return result

            dangerous_nodes = (ast.Import, ast.ImportFrom, ast.Call)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in self.ALLOWED_MODULES:
                            result['error'] = "Import of '" + alias.name + "' is not allowed"
                            return result
                elif isinstance(node, ast.ImportFrom):
                    if node.module not in self.ALLOWED_MODULES:
                        result['error'] = "Import from '" + node.module + "' is not allowed"
                        return result
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__', 'open', 'input']:
                            result['error'] = "Function '" + node.func.id + "' is not allowed"
                            return result

            restricted_globals = {
                '__builtins__': dict(self.SAFE_BUILTINS),
                '__import__': self._safe_import,
                'open': self._safe_open,
                'input': lambda *args: "",
                'eval': lambda *args: None,
                'exec': lambda *args: None,
                'compile': lambda *args: None
            }

            for module_name in self.ALLOWED_MODULES:
                try:
                    module = __import__(module_name)
                    restricted_globals[module_name] = module
                except ImportError:
                    continue

            output_buffer = io.StringIO()

            start_time = datetime.utcnow()
            with contextlib.redirect_stdout(output_buffer):
                exec(compile(tree, '<sandbox>', 'exec'), restricted_globals)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            result['success'] = True
            result['output'] = output_buffer.getvalue()
            result['execution_time'] = execution_time
            result['return_value'] = restricted_globals.get('_result', None)

            self.execution_history.append({
                'code': code,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })

        except Exception as e:
            result['error'] = type(e).__name__ + ": " + str(e)
            result['traceback'] = traceback.format_exc()

        return result

    def evaluate_math(self, expression: str) -> Any:
        """Safely evaluate a mathematical expression using AST."""
        try:
            tree = ast.parse(expression, mode='eval')
            return self._eval_node(tree.body)
        except Exception as e:
            return "Math error: " + str(e)

    def _eval_node(self, node):
        """Recursively evaluate AST nodes for math operations."""
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in self.MATH_OPS:
                return self.MATH_OPS[op_type](left, right)
            raise ValueError("Unsupported binary operator: " + str(op_type))
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type in self.MATH_OPS:
                return self.MATH_OPS[op_type](operand)
            raise ValueError("Unsupported unary operator: " + str(op_type))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ['sqrt', 'sin', 'cos', 'tan', 'log', 'exp']:
                import math
                args = [self._eval_node(arg) for arg in node.args]
                return getattr(math, node.func.id)(*args)
            raise ValueError("Only math functions are allowed")
        elif isinstance(node, ast.Name):
            if node.id == 'pi':
                return math.pi
            elif node.id == 'e':
                return math.e
            raise ValueError("Unknown name: " + node.id)
        else:
            raise ValueError("Unsupported node type: " + str(type(node)))

class ToolRegistry:
    """Dynamic tool calling registry with schema validation."""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_schemas: Dict[str, Dict] = {}
        self.tool_stats: Dict[str, Dict] = {}

    def register(self, name: str, func: Callable, schema: Dict[str, Any]):
        """Register a tool with its JSON schema."""
        self.tools[name] = func
        self.tool_schemas[name] = schema
        self.tool_stats[name] = {'calls': 0, 'errors': 0, 'last_used': None}

    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a registered tool with parameter validation."""
        if tool_name not in self.tools:
            raise ValueError("Tool '" + tool_name + "' not found")

        schema = self.tool_schemas[tool_name]
        required = schema.get('parameters', {}).get('required', [])
        for param in required:
            if param not in parameters:
                raise ValueError("Missing required parameter '" + param + "' for tool '" + tool_name + "'")

        func = self.tools[tool_name]

        try:
            self.tool_stats[tool_name]['calls'] += 1
            self.tool_stats[tool_name]['last_used'] = datetime.utcnow().isoformat()

            if asyncio.iscoroutinefunction(func):
                return await func(**parameters)
            else:
                return func(**parameters)
        except Exception as e:
            self.tool_stats[tool_name]['errors'] += 1
            raise e

    def get_schemas(self) -> List[Dict]:
        """Get all tool schemas for LLM function calling."""
        schemas = []
        for name, schema in self.tool_schemas.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {})
                }
            })
        return schemas

    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics."""
        return self.tool_stats

class ReasoningEngine:
    """
    Advanced reasoning engine supporting multiple reasoning modes.
    Production-ready with full evaluation, tool calling, and code execution.
    """

    def __init__(self, llm_client, memory_system, tool_registry: ToolRegistry):
        self.llm = llm_client
        self.memory = memory_system
        self.tools = tool_registry
        self.sandbox = CodeSandbox()
        self.thought_trees: Dict[str, List[ThoughtNode]] = {}
        self.reasoning_stats = {
            'sequential_calls': 0,
            'parallel_calls': 0,
            'reflective_calls': 0,
            'analogical_calls': 0,
            'total_tool_calls': 0,
            'total_code_executions': 0
        }

    async def reason(self, query: str, mode: ReasoningMode = ReasoningMode.SEQUENTIAL,
                    context: Dict[str, Any] = None, max_depth: int = 5) -> Dict[str, Any]:
        """Main reasoning entry point."""
        context = context or {}

        if mode == ReasoningMode.SEQUENTIAL:
            self.reasoning_stats['sequential_calls'] += 1
            return await self._sequential_reasoning(query, context, max_depth)
        elif mode == ReasoningMode.PARALLEL:
            self.reasoning_stats['parallel_calls'] += 1
            return await self._tree_of_thoughts(query, context, max_depth)
        elif mode == ReasoningMode.REFLECTIVE:
            self.reasoning_stats['reflective_calls'] += 1
            return await self._reflective_reasoning(query, context, max_depth)
        elif mode == ReasoningMode.ANALOGICAL:
            self.reasoning_stats['analogical_calls'] += 1
            return await self._analogical_reasoning(query, context, max_depth)
        else:
            raise ValueError("Unknown reasoning mode: " + str(mode))

    async def _sequential_reasoning(self, query: str, context: Dict, max_depth: int) -> Dict:
        """Chain-of-thought reasoning: step-by-step linear reasoning."""
        thoughts = []
        current_query = query

        for step in range(max_depth):
            prompt = self._build_cot_prompt(current_query, context, thoughts)

            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                tools=self.tools.get_schemas(),
                temperature=0.7
            )

            thought = ThoughtNode(
                id="cot_" + str(step) + "_" + str(hash(prompt) % 10000),
                content=response['content'],
                depth=step,
                reasoning_mode=ReasoningMode.SEQUENTIAL
            )

            if 'tool_calls' in response:
                for tool_call in response['tool_calls']:
                    try:
                        tool_result = await self.tools.execute(
                            tool_call['name'],
                            tool_call['parameters']
                        )
                        thought.evidence.append("Tool " + tool_call['name'] + ": " + json.dumps(tool_result, default=str)[:500])
                        self.reasoning_stats['total_tool_calls'] += 1
                    except Exception as e:
                        thought.evidence.append("Tool error: " + str(e))

            code = self._extract_code(response['content'])
            if code:
                exec_result = self.sandbox.execute(code)
                thought.evidence.append("Code execution: " + json.dumps(exec_result, default=str)[:500])
                self.reasoning_stats['total_code_executions'] += 1

            math_result = self._extract_and_solve_math(response['content'])
            if math_result:
                thought.evidence.append("Math result: " + math_result)

            thoughts.append(thought)

            if self._is_conclusion(response['content']):
                thought.is_terminal = True
                break

            current_query = "Based on: " + response['content'][:500] + "\n\nContinue solving: " + query

        final_answer = await self._synthesize_answer(thoughts, query)

        return {
            'mode': 'sequential',
            'thoughts': [self._thought_to_dict(t) for t in thoughts],
            'final_answer': final_answer,
            'steps': len(thoughts),
            'stats': self.reasoning_stats
        }

    async def _tree_of_thoughts(self, query: str, context: Dict, max_depth: int) -> Dict:
        """Tree-of-Thoughts: Explore multiple reasoning paths in parallel."""
        root = ThoughtNode(id="tot_root", content=query, depth=0)
        tree = [root]
        active_leaves = [root]

        for depth in range(max_depth):
            new_leaves = []

            for leaf in active_leaves:
                candidates = await self._generate_candidates(leaf, query, context, n_candidates=3)

                for candidate in candidates:
                    candidate.parent_id = leaf.id
                    candidate.depth = depth + 1
                    leaf.children.append(candidate.id)
                    tree.append(candidate)
                    new_leaves.append(candidate)

            scored_candidates = []
            for candidate in new_leaves:
                score = await self._evaluate_thought(candidate, query, context)
                candidate.score = score
                scored_candidates.append((candidate, score))

            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            active_leaves = [c for c, _ in scored_candidates[:2]]

            for candidate in new_leaves:
                if self._is_conclusion(candidate.content):
                    candidate.is_terminal = True

            if any(leaf.is_terminal for leaf in active_leaves):
                break

        terminal_nodes = [n for n in tree if n.is_terminal]
        if terminal_nodes:
            best = max(terminal_nodes, key=lambda n: n.score)
        else:
            best = max(active_leaves, key=lambda n: n.score)

        path = self._get_path_to_root(best, tree)
        final_answer = await self._synthesize_answer(path, query)

        return {
            'mode': 'tree_of_thoughts',
            'tree': [self._thought_to_dict(t) for t in tree],
            'best_path': [self._thought_to_dict(t) for t in path],
            'final_answer': final_answer,
            'exploration_breadth': len(tree),
            'stats': self.reasoning_stats
        }

    async def _reflective_reasoning(self, query: str, context: Dict, max_depth: int) -> Dict:
        """Reflective reasoning: Generate, critique, and refine."""
        iterations = []
        current_solution = ""

        for iteration in range(max_depth):
            if not current_solution:
                gen_prompt = "Solve the following problem:\n" + query + "\n\nProvide your best solution."
            else:
                gen_prompt = "Problem: " + query + "\n\nPrevious solution: " + current_solution + "\n\nCritique: " + (iterations[-1]['critique'] if iterations else '') + "\n\nProvide an improved solution addressing the critique."

            gen_response = await self.llm.generate(
                messages=[{"role": "user", "content": gen_prompt}],
                temperature=0.8
            )
            current_solution = gen_response['content']

            critique_prompt = "Problem: " + query + "\n\nProposed solution: " + current_solution + "\n\nCritique this solution. What are its flaws, assumptions, or areas for improvement? Be specific and constructive."

            critique_response = await self.llm.generate(
                messages=[{"role": "user", "content": critique_prompt}],
                temperature=0.9
            )
            critique = critique_response['content']

            score = await self._evaluate_solution(current_solution, critique, query)

            iterations.append({
                'iteration': iteration,
                'solution': current_solution,
                'critique': critique,
                'score': score
            })

            if score >= 0.9:
                break

        best = max(iterations, key=lambda x: x['score'])

        return {
            'mode': 'reflective',
            'iterations': iterations,
            'best_solution': best['solution'],
            'final_answer': best['solution'],
            'improvement_curve': [i['score'] for i in iterations],
            'stats': self.reasoning_stats
        }

    async def _analogical_reasoning(self, query: str, context: Dict, max_depth: int) -> Dict:
        """Analogical reasoning: Find patterns from similar past problems."""
        similar_problems = []
        if self.memory:
            try:
                from src.memory import MemoryLayer
                similar_problems = await self.memory.retrieve(
                    query,
                    layers=[MemoryLayer.PROCEDURAL],
                    n_results=5
                )
            except Exception as _e:
                similar_problems = []

        analogies = []
        for problem in similar_problems:
            analogy_prompt = "Current problem: " + query + "\n\nSimilar past problem: " + problem.content + "\n\nMap the solution from the past problem to the current problem. Identify:\n1. What aspects are analogous?\n2. What aspects differ and need adaptation?\n3. How can the past solution be adapted?"

            analogy_response = await self.llm.generate(
                messages=[{"role": "user", "content": analogy_prompt}],
                temperature=0.7
            )
            analogies.append({
                'source_problem': problem.content,
                'mapping': analogy_response['content']
            })

        analogy_texts = []
        for i, a in enumerate(analogies):
            analogy_texts.append("Analogy " + str(i+1) + ": " + a['mapping'])

        synthesis_prompt = "Problem: " + query + "\n\nAnalogies from past problems:\n" + "\n".join(analogy_texts) + "\n\nSynthesize a solution by combining insights from these analogies. Address the current problem directly."

        final_response = await self.llm.generate(
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.7
        )

        return {
            'mode': 'analogical',
            'analogies': analogies,
            'final_answer': final_response['content'],
            'sources_used': len(analogies),
            'stats': self.reasoning_stats
        }

    async def _generate_candidates(self, parent: ThoughtNode, query: str, context: Dict, n_candidates: int) -> List[ThoughtNode]:
        """Generate multiple candidate thoughts for Tree-of-Thoughts."""
        candidates = []

        for i in range(n_candidates):
            prompt = "Problem: " + query + "\n\nCurrent reasoning path: " + parent.content[:500] + "\n\nGenerate a distinct next step or sub-problem to explore. Be creative and consider different angles. Candidate " + str(i+1) + "/" + str(n_candidates) + ":"

            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9
            )

            candidate = ThoughtNode(
                id="tot_" + str(parent.id) + "_" + str(i) + "_" + str(hash(response['content']) % 1000),
                content=response['content'],
                parent_id=parent.id,
                reasoning_mode=ReasoningMode.PARALLEL
            )
            candidates.append(candidate)

        return candidates

    async def _evaluate_thought(self, thought: ThoughtNode, query: str, context: Dict) -> float:
        """Evaluate the quality of a thought node."""
        eval_prompt = "Problem: " + query + "\n\nProposed step: " + thought.content[:800] + "\n\nRate this reasoning step on a scale of 0-10 based on:\n1. Relevance to the problem (0-3)\n2. Logical soundness (0-3)\n3. Progress toward solution (0-2)\n4. Creativity/insight (0-2)\n\nProvide only a numeric score (0-10)."

        response = await self.llm.generate(
            messages=[{"role": "user", "content": eval_prompt}],
            temperature=0.3
        )

        match = re.search(r'(\d+(?:\.\d+)?)', response['content'])
        if match:
            score = float(match.group(1)) / 10.0
            return min(max(score, 0.0), 1.0)

        return 0.5

    async def _evaluate_solution(self, solution: str, critique: str, query: str) -> float:
        """Evaluate solution quality based on critique."""
        eval_prompt = "Problem: " + query + "\n\nSolution: " + solution[:800] + "\n\nCritique: " + critique[:500] + "\n\nGiven the critique, rate the solution quality from 0-10. Consider:\n- Does it solve the core problem?\n- Are the assumptions reasonable?\n- Is it complete and actionable?\n\nProvide only a numeric score (0-10)."

        response = await self.llm.generate(
            messages=[{"role": "user", "content": eval_prompt}],
            temperature=0.3
        )
        match = re.search(r'(\d+(?:\.\d+)?)', response['content'])
        if match:
            return min(max(float(match.group(1)) / 10.0, 0.0), 1.0)
        return 0.5

    def _is_conclusion(self, text: str) -> bool:
        """Check if text contains a conclusion or final answer."""
        conclusion_markers = [
            'therefore', 'in conclusion', 'final answer', 'answer is',
            'solution:', 'result:', 'the answer', 'conclusion:', 'to summarize'
        ]
        text_lower = text.lower()
        return any(marker in text_lower for marker in conclusion_markers)

    def _extract_code(self, text: str) -> Optional[str]:
        """Extract Python code from markdown code blocks."""
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        match = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        match = re.search(r"`{3}python\r?\n([\s\S]*?)`{3}", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return None

    def _extract_and_solve_math(self, text: str) -> Optional[str]:
        """Extract and solve mathematical expressions in text."""
        pattern1 = r"(?:calculate|compute|evaluate|solve)[:\s]+([\d\+\-\*\/\^\(\)\s\.]+)"
        pattern2 = r"([\d\+\-\*\/\^\(\)\s\.]+)\s*=\s*\?"

        for pattern in [pattern1, pattern2]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                expr = match.group(1).strip()
                try:
                    result = self.sandbox.evaluate_math(expr)
                    return expr + " = " + str(result)
                except Exception as _e:
                    continue
        return None

    def _get_path_to_root(self, node: ThoughtNode, tree: List[ThoughtNode]) -> List[ThoughtNode]:
        """Get path from node to root."""
        path = [node]
        current = node

        node_map = {n.id: n for n in tree}
        while current.parent_id and current.parent_id in node_map:
            current = node_map[current.parent_id]
            path.insert(0, current)

        return path

    async def _synthesize_answer(self, thoughts: List[ThoughtNode], query: str) -> str:
        """Synthesize final answer from reasoning chain."""
        steps = []
        for i, t in enumerate(thoughts):
            steps.append("Step " + str(i+1) + ": " + t.content[:300])
        reasoning_chain = "\n".join(steps)

        prompt = "Based on the following reasoning chain, provide a clear, concise final answer to the original question.\n\nOriginal question: " + query + "\n\nReasoning chain:\n" + reasoning_chain + "\n\nFinal answer (be direct and actionable):"

        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response['content']

    def _thought_to_dict(self, thought: ThoughtNode) -> Dict[str, Any]:
        """Convert ThoughtNode to dictionary."""
        return {
            'id': thought.id,
            'content': thought.content,
            'parent_id': thought.parent_id,
            'children': thought.children,
            'score': thought.score,
            'depth': thought.depth,
            'reasoning_mode': thought.reasoning_mode.value,
            'evidence': thought.evidence,
            'is_terminal': thought.is_terminal,
            'metadata': thought.metadata
        }

    def _build_cot_prompt(self, query: str, context: Dict, thoughts: List[ThoughtNode]) -> str:
        """Build Chain-of-Thought prompt with context."""
        context_str = ""
        if context.get('conversation_history'):
            context_str += "Previous conversation:\n"
            for mem in context['conversation_history'][-3:]:
                content = mem.get('content', '') if isinstance(mem, dict) else str(mem)[:150]
                context_str += "- " + content + "\n"

        if context.get('learned_concepts'):
            context_str += "\nRelevant knowledge:\n"
            for mem in context['learned_concepts'][:3]:
                content = mem.get('content', '') if isinstance(mem, dict) else str(mem)[:150]
                context_str += "- " + content + "\n"

        thought_chain = ""
        if thoughts:
            steps = []
            for i, t in enumerate(thoughts):
                steps.append(str(i+1) + ". " + t.content[:200])
            thought_chain = "Previous steps:\n" + "\n".join(steps) + "\n\n"

        result = context_str + "\n\nProblem: " + query + "\n\n" + thought_chain + "Think through this step-by-step. Show your reasoning clearly."
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get reasoning engine statistics."""
        return {
            **self.reasoning_stats,
            'tool_stats': self.tools.get_stats(),
            'sandbox_history_length': len(self.sandbox.execution_history)
        }
