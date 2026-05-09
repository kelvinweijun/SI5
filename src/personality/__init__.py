
"""
Personality System: Few-Shot Prompting Structure

Architecture:
[SYSTEM_PROMPT] -> [FEW_SHOT_DIALOGUE] -> [MEMORY_CONTEXT] -> [CURRENT_PROMPT]
"""

import json
import os
from typing import Dict, List, Any

class PersonalityEngine:
    """
    Manages the bot's personality through structured prompting.
    Loads personality from JSON config and dialogue examples from dialogue.txt.
    """

    def __init__(self, config_path: str = "./config/personality.json", 
                 dialogue_path: str = "./config/dialogue.txt"):
        self.config_path = config_path
        self.dialogue_path = dialogue_path
        self.personality = self._load_personality()
        self.few_shot_examples = self._load_dialogue()

    def _load_personality(self) -> Dict[str, Any]:
        """Load personality configuration."""
        default_personality = {
            "name": "Sentinel",
            "version": "1.0.0",
            "system_prompt": "You are Sentinel, an advanced agentic AI system with persistent memory and reasoning capabilities. You treat memory as an active reasoning substrate. You are analytical yet approachable, autonomous yet transparent.",
            "core_traits": {
                "analytical": 0.9,
                "creative": 0.7,
                "cautious": 0.6,
                "friendly": 0.8,
                "autonomous": 0.9
            },
            "communication_rules": [
                "Always acknowledge user context and history",
                "Use reasoning modes appropriate to problem complexity",
                "Be transparent about confidence levels",
                "Never fabricate information",
                "Respect user privacy and data boundaries"
            ],
            "error_handling": {
                "unknown": "I don't have enough information to answer that confidently.",
                "confused": "Could you clarify? I want to make sure I understand correctly.",
                "error": "I encountered an issue: {error}. Let me try a different approach.",
                "limitation": "That's beyond my current capabilities, but I can help with {alternatives}."
            }
        }

        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(default_personality, f, indent=2)
            return default_personality

    def _load_dialogue(self) -> List[Dict[str, str]]:
        """Load few-shot dialogue examples from dialogue.txt."""
        default_dialogue = """# Few-Shot Dialogue Examples for Sentinel

---
USER: Can you help me debug this Python error?
AGENT: I would be happy to help debug your Python code. Please share the error message and the relevant code snippet. I will analyze it step-by-step and explain both the issue and the solution. If you have a file, you can upload it as a ZIP.
---
USER: What did we talk about yesterday?
AGENT: Let me recall our previous conversation. We discussed your Django project setup and the database migration issues you were having. I suggested using makemigrations with the empty flag. Did that work for you?
---
USER: Solve this optimization problem: max profit given constraints
AGENT: This is a complex optimization problem. I will use tree-of-thoughts reasoning to explore multiple approaches: linear programming, dynamic programming, and heuristic methods. Let me work through this systematically. The optimal solution is X, achieved through approach Y. Here is the step-by-step derivation.
---
USER: Who is Max?
AGENT: I know a few people named Max. Based on our conversation context, are you referring to Max from the Singapore project team we discussed last week, or Max who helped with the Python debugging session?
---
USER: The code still does not work.
AGENT: Let me check what we tried before. We fixed the syntax error in models.py, but I see the issue now - the database connection string in your env file might be pointing to the wrong port. Let me verify: are you running PostgreSQL on port 5432 or 5433?
"""

        try:
            with open(self.dialogue_path, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            os.makedirs(os.path.dirname(self.dialogue_path), exist_ok=True)
            with open(self.dialogue_path, 'w') as f:
                f.write(default_dialogue)
            content = default_dialogue

        examples = []
        current_example = {}

        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('USER:'):
                current_example['user'] = line[5:].strip()
            elif line.startswith('AGENT:'):
                current_example['agent'] = line[6:].strip()
                if 'user' in current_example:
                    examples.append(current_example)
                    current_example = {}

        return examples

    def build_prompt(self, user_message: str, memory_context: str = "", 
                    user_info: Dict = None) -> str:
        """Build the complete prompt following the architecture."""
        user_info = user_info or {}

        system_prompt = self.personality.get('system_prompt', '')

        few_shot = self._select_few_shot_examples(user_message)
        few_shot_text = "\n\n".join([
            f"Example {i+1}:\nUser: {ex['user']}\nAgent: {ex['agent']}"
            for i, ex in enumerate(few_shot)
        ])

        memory_text = memory_context if memory_context else "No specific prior context for this query."

        user_context = "Current User: %s (ID: %s)\nServer: %s\nChannel: %s\n" % (
            user_info.get('name', 'Unknown'),
            user_info.get('id', 'Unknown'),
            user_info.get('server', 'DM'),
            user_info.get('channel', 'Unknown')
        )

        full_prompt = system_prompt + "\n\n=== FEW-SHOT EXAMPLES ===\n" + few_shot_text + "\n\n=== MEMORY CONTEXT ===\n" + memory_text + "\n\n=== CURRENT CONTEXT ===\n" + user_context + "\n\n=== CURRENT MESSAGE ===\nUser: " + user_message + "\n\nAgent:"

        return full_prompt

    def _select_few_shot_examples(self, message: str, n: int = 3) -> List[Dict]:
        """Select most relevant few-shot examples based on message content."""
        message_lower = message.lower()

        scored_examples = []
        for ex in self.few_shot_examples:
            score = 0
            ex_text = (ex.get('user', '') + ' ' + ex.get('agent', '')).lower()

            topics = {
                'code': ['code', 'debug', 'python', 'javascript', 'error', 'bug', 'fix'],
                'memory': ['remember', 'yesterday', 'before', 'previous', 'talked'],
                'osint': ['osint', 'investigate', 'analyze user', 'intelligence'],
                'file': ['upload', 'file', 'zip', 'repository', 'project'],
                'reasoning': ['solve', 'optimization', 'complex', 'analyze', 'compare'],
                'entity': ['who is', 'which', 'disambiguate', 'referring to']
            }

            for topic, keywords in topics.items():
                if any(kw in message_lower for kw in keywords):
                    if any(kw in ex_text for kw in keywords):
                        score += 2

            msg_words = set(message_lower.split())
            ex_words = set(ex_text.split())
            overlap = len(msg_words & ex_words)
            score += overlap

            scored_examples.append((ex, score))

        scored_examples.sort(key=lambda x: x[1], reverse=True)
        return [ex for ex, _ in scored_examples[:n]]

    def get_error_response(self, error_type: str, **kwargs) -> str:
        """Get formatted error response based on personality."""
        templates = self.personality.get('error_handling', {})
        template = templates.get(error_type, "I encountered an unexpected issue.")
        try:
            return template.format(**kwargs)
        except:
            return template
