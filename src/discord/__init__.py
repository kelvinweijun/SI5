
"""
Discord Bot Interface
Advanced Discord bot with slash commands, file processing, and context awareness.
Production-ready with full permission checking and error handling.
"""

import os
import json
import asyncio
import zipfile
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

class AgenticBot(commands.Bot):
    """
    Main Discord bot implementing the agentic AI system.
    Production-ready with full multi-server support, role-based access,
    file processing, and comprehensive error handling.
    """

    def __init__(self, config: Dict[str, Any], memory_system, reasoning_engine, osint_collector, llm_client):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        intents.guilds = True

        super().__init__(
            command_prefix=config.get('command_prefix', '!'),
            intents=intents,
            help_command=None
        )

        self.config = config
        self.memory = memory_system
        self.reasoning = reasoning_engine
        self.osint = osint_collector
        self.llm = llm_client

        self.admin_roles = config.get('admin_roles', ['Admin', 'Administrator'])
        self.allowed_servers = config.get('allowed_servers', ['all'])

        self.max_file_size = config.get('max_file_size', 25 * 1024 * 1024)
        self.allowed_extensions = [
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs',
            '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.sql',
            '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.toml',
            '.md', '.txt', '.rst', '.csv', '.log', '.ini', '.cfg',
            '.sh', '.bash', '.zsh', '.ps1', '.dockerfile', '.gitignore'
        ]

        self._conversation_locks = {}
        self._startup_time = datetime.utcnow()

    async def setup_hook(self):
        """Initialize bot systems."""
        await self.memory.initialize()
        await self.osint.initialize()

        self.memory_maintenance.start()
        self.status_rotation.start()

        # Sync slash commands globally and for each guild
        await self.tree.sync()
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=guild)
            except Exception as e:
                print(f"Could not sync commands for {guild.name}: {e}")

    @tasks.loop(minutes=5)
    async def memory_maintenance(self):
        """Periodic memory maintenance task."""
        try:
            stats = self.memory.get_stats()
            print(f"Memory stats: {json.dumps(stats, indent=2)}")
        except Exception as e:
            print(f"Memory maintenance error: {e}")

    @tasks.loop(minutes=10)
    async def status_rotation(self):
        """Rotate bot status to show capabilities."""
        import random
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name="for /ask commands"),
            discord.Activity(type=discord.ActivityType.listening, name="your questions"),
            discord.Activity(type=discord.ActivityType.playing, name="with reasoning trees"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.guilds)} servers"),
        ]
        await self.change_presence(activity=random.choice(statuses))

    async def on_ready(self):
        """Called when bot is ready."""
        print(f"\n{'='*60}")
        print(f"Bot logged in as {self.user} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} servers")
        print(f"Slash commands: {len(await self.tree.fetch_commands())}")
        print(f"{'='*60}\n")

        for guild in self.guilds:
            print(f"  - {guild.name} (ID: {guild.id}, Members: {guild.member_count})")

    async def on_guild_join(self, guild: discord.Guild):
        """Handle joining a new server."""
        if self.allowed_servers != ['all'] and str(guild.id) not in self.allowed_servers:
            print(f"Leaving unauthorized server: {guild.name} ({guild.id})")
            await guild.leave()
            return

        await self.memory.store(
            content=f"Joined server: {guild.name} (ID: {guild.id}, Members: {guild.member_count})",
            layer=MemoryLayer.EPISODIC,
            priority=MemoryPriority.MEDIUM,
            entities=[f"server:{guild.id}", guild.name],
            metadata={'server_id': str(guild.id), 'event': 'guild_join', 'member_count': guild.member_count}
        )

        system_channel = guild.system_channel
        if system_channel and system_channel.permissions_for(guild.me).send_messages:
            embed = discord.Embed(
                title=f"{self.config.get('AGENT_NAME', 'Sentinel')} - Agentic AI",
                description=(
                    "I am an advanced AI agent with persistent memory and reasoning capabilities.\n\n"
                    "**Features:**\n"
                    "• Multi-layer memory across conversations\n"
                    "• Advanced reasoning (Chain-of-Thought, Tree-of-Thoughts)\n"
                    "• Code analysis and execution\n"
                    "• File/repository processing\n\n"
                    "Use `/help` for commands or mention me to chat!"
                ),
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Agentic AI System v1.0")
            await system_channel.send(embed=embed)

        # Sync commands for new guild
        try:
            await self.tree.sync(guild=guild)
        except Exception as e:
            print(f"Could not sync commands for new guild {guild.name}: {e}")

    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author.bot:
            return

        is_mentioned = self.user.mentioned_in(message)
        is_dm = isinstance(message.channel, discord.DMChannel)

        if not is_mentioned and not is_dm and not message.content.startswith(self.command_prefix):
            await self._passive_observe(message)
            return

        await self.process_commands(message)

        if is_mentioned and not message.content.startswith(self.command_prefix):
            content = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
            if content:
                async with message.channel.typing():
                    await self._handle_conversation(message, content)

    async def _passive_observe(self, message: discord.Message):
        """Passively observe messages to build context."""
        try:
            await self.memory.store(
                content=f"[{message.channel.name}] {message.author.display_name}: {message.content[:200]}",
                layer=MemoryLayer.WORKING,
                priority=MemoryPriority.LOW,
                entities=[f"user:{message.author.id}", f"channel:{message.channel.id}"],
                metadata={
                    'user_id': str(message.author.id),
                    'channel_id': str(message.channel.id),
                    'server_id': str(message.guild.id) if message.guild else None,
                    'passive': True
                }
            )
        except Exception as e:
            print(f"Passive observation error: {e}")

    async def _handle_conversation(self, message: discord.Message, content: str):
        """Handle a conversational turn with full context."""
        user_id = str(message.author.id)

        # Prevent concurrent processing for same user
        if user_id in self._conversation_locks:
            await message.reply("I'm still processing your previous message. Please wait a moment.")
            return

        self._conversation_locks[user_id] = True

        try:
            context = await self.memory.get_context(
                user_id=user_id,
                server_id=str(message.guild.id) if message.guild else 'dm',
                channel_id=str(message.channel.id),
                current_message=content
            )

            system_prompt = await self._build_system_prompt(message.author, context)
            reasoning_mode = self._select_reasoning_mode(content)

            if reasoning_mode:
                result = await self.reasoning.reason(
                    query=content,
                    mode=reasoning_mode,
                    context=context
                )
                response_text = result['final_answer']
            else:
                response = await self.llm.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    temperature=0.7
                )
                response_text = response['content']

            # Store interaction
            await self.memory.store(
                content=f"User: {content[:300]}\nAgent: {response_text[:500]}",
                layer=MemoryLayer.EPISODIC,
                priority=MemoryPriority.MEDIUM,
                entities=[f"user:{message.author.id}", f"channel:{message.channel.id}"],
                relationships={'responded_to': f"user:{message.author.id}"},
                metadata={
                    'user_id': user_id,
                    'channel_id': str(message.channel.id),
                    'server_id': str(message.guild.id) if message.guild else 'dm',
                    'interaction_type': 'conversation'
                }
            )

            # Send response with chunking
            await self._send_chunked(message, response_text)

        except Exception as e:
            print(f"Conversation error: {e}")
            await message.reply(f"I encountered an error: {str(e)[:500]}")
        finally:
            del self._conversation_locks[user_id]

    async def _send_chunked(self, target, text: str, max_length: int = 1900):
        """Send long messages in chunks."""
        if len(text) <= max_length:
            if isinstance(target, discord.Message):
                await target.reply(text)
            else:
                await target.send(text)
            return

        # Split by paragraphs first, then by length
        chunks = []
        current = ""

        for paragraph in text.split('\n\n'):
            if len(current) + len(paragraph) + 2 > max_length:
                if current:
                    chunks.append(current)
                current = paragraph
            else:
                current += ("\n\n" if current else "") + paragraph

        if current:
            chunks.append(current)

        # If still too long, force split
        final_chunks = []
        for chunk in chunks:
            while len(chunk) > max_length:
                split_point = chunk.rfind(' ', 0, max_length)
                if split_point == -1:
                    split_point = max_length
                final_chunks.append(chunk[:split_point])
                chunk = chunk[split_point:].strip()
            if chunk:
                final_chunks.append(chunk)

        for i, chunk in enumerate(final_chunks):
            prefix = f"(Part {i+1}/{len(final_chunks)})\n" if len(final_chunks) > 1 else ""
            if isinstance(target, discord.Message):
                await target.reply(prefix + chunk)
            else:
                await target.send(prefix + chunk)

    async def _build_system_prompt(self, user: discord.User, context: Dict) -> str:
        """Build system prompt with personality and memory context."""
        personality = self._load_personality()

        memory_context = ""
        if context.get('conversation_history'):
            memory_context += "Previous conversations with this user:\n"
            for mem in context['conversation_history'][-5:]:
                content = mem.get('content', '') if isinstance(mem, dict) else str(mem)
                memory_context += f"- {content[:150]}\n"

        if context.get('server_context'):
            memory_context += "\nServer context:\n"
            for mem in context['server_context'][:3]:
                content = mem.get('content', '') if isinstance(mem, dict) else str(mem)
                memory_context += f"- {content[:150]}\n"

        if context.get('related_entities'):
            memory_context += "\nRelated entities:\n"
            for entity, rel_type, weight in context['related_entities'][:5]:
                memory_context += f"- {entity} ({rel_type}, weight: {weight:.2f})\n"

        return f"""{personality.get('system_prompt', 'You are an advanced AI assistant.')}

You are currently talking to: {user.display_name} (ID: {user.id})

{memory_context}

Respond naturally and helpfully. Use your memory to maintain continuity across conversations.
If you need to execute code or use tools, indicate this clearly.
"""

    def _load_personality(self) -> Dict[str, str]:
        """Load personality configuration."""
        personality_file = self.config.get('personality_file', './config/personality.json')
        try:
            with open(personality_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'system_prompt': 'You are an advanced AI assistant with memory and reasoning capabilities.',
                'name': 'Agent',
                'communication_style': 'professional but friendly'
            }

    def _select_reasoning_mode(self, content: str) -> Optional[Any]:
        """Select appropriate reasoning mode based on query complexity."""
        from src.reasoning import ReasoningMode

        content_lower = content.lower()

        complex_indicators = ['solve', 'analyze', 'compare', 'evaluate', 'optimize', 'design', 'prove']
        if any(ind in content_lower for ind in complex_indicators):
            if any(word in content_lower for word in ['multiple', 'different', 'options', 'alternatives', 'best']):
                return ReasoningMode.PARALLEL
            return ReasoningMode.SEQUENTIAL

        if any(word in content_lower for word in ['review', 'check', 'critique', 'improve', 'better']):
            return ReasoningMode.REFLECTIVE

        if any(word in content_lower for word in ['similar', 'like', 'pattern', 'analogy', 'compare to']):
            return ReasoningMode.ANALOGICAL

        return None

    async def _check_permissions(self, user: discord.Member, required_role: str = None) -> bool:
        """Check if user has required permissions."""
        if user.guild_permissions.administrator:
            return True

        if required_role:
            return any(role.name == required_role for role in user.roles)

        # Check admin role names
        return any(role.name in self.admin_roles for role in user.roles)

    # Slash Commands

    @app_commands.command(name="ask", description="Ask the AI agent a question")
    @app_commands.describe(question="Your question or request")
    async def ask_command(self, interaction: discord.Interaction, question: str):
        """Main Q&A command."""
        await interaction.response.defer(thinking=True)

        try:
            context = await self.memory.get_context(
                user_id=str(interaction.user.id),
                server_id=str(interaction.guild_id) if interaction.guild_id else 'dm',
                channel_id=str(interaction.channel_id),
                current_message=question
            )

            system_prompt = await self._build_system_prompt(interaction.user, context)

            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7
            )

            await self.memory.store(
                content=f"User asked: {question[:300]}\nAgent: {response['content'][:500]}",
                layer=MemoryLayer.EPISODIC,
                priority=MemoryPriority.MEDIUM,
                entities=[f"user:{interaction.user.id}"],
                metadata={
                    'user_id': str(interaction.user.id),
                    'channel_id': str(interaction.channel_id),
                    'interaction_type': 'slash_command'
                }
            )

            content = response['content']
            if len(content) > 2000:
                thread = await interaction.channel.create_thread(
                    name=f"Q: {question[:50]}...",
                    message=await interaction.original_response()
                )
                await self._send_chunked(thread, content)
            else:
                await interaction.followup.send(content)

        except Exception as e:
            print(f"Ask command error: {e}")
            await interaction.followup.send(f"Error: {str(e)[:500]}")

    @app_commands.command(name="reason", description="Use advanced reasoning for complex problems")
    @app_commands.describe(
        problem="The problem to solve",
        mode="Reasoning mode"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Sequential (Chain-of-Thought)", value="sequential"),
        app_commands.Choice(name="Parallel (Tree-of-Thoughts)", value="parallel"),
        app_commands.Choice(name="Reflective (Self-Critique)", value="reflective"),
        app_commands.Choice(name="Analogical (Pattern Matching)", value="analogical")
    ])
    async def reason_command(self, interaction: discord.Interaction, problem: str, mode: app_commands.Choice[str]):
        """Advanced reasoning command."""
        await interaction.response.defer(thinking=True)

        try:
            from src.reasoning import ReasoningMode

            mode_map = {
                'sequential': ReasoningMode.SEQUENTIAL,
                'parallel': ReasoningMode.PARALLEL,
                'reflective': ReasoningMode.REFLECTIVE,
                'analogical': ReasoningMode.ANALOGICAL
            }

            reasoning_mode = mode_map.get(mode.value, ReasoningMode.SEQUENTIAL)

            result = await self.reasoning.reason(
                query=problem,
                mode=reasoning_mode,
                max_depth=5
            )

            embed = discord.Embed(
                title=f"Reasoning: {mode.name}",
                description=f"**Problem:** {problem[:200]}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Final Answer",
                value=result['final_answer'][:1000],
                inline=False
            )

            if 'steps' in result:
                embed.add_field(name="Steps", value=str(result['steps']), inline=True)
            if 'exploration_breadth' in result:
                embed.add_field(name="Paths Explored", value=str(result['exploration_breadth']), inline=True)
            if 'improvement_curve' in result:
                embed.add_field(name="Iterations", value=str(len(result['improvement_curve'])), inline=True)

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Reason command error: {e}")
            await interaction.followup.send(f"Reasoning error: {str(e)[:500]}")

    @app_commands.command(name="osint", description="[ADMIN] Open Source Intelligence gathering")
    @app_commands.describe(
        target="Target user or server",
        scope="Intelligence scope"
    )
    @app_commands.choices(scope=[
        app_commands.Choice(name="User Profile", value="user"),
        app_commands.Choice(name="Server Analysis", value="server"),
        app_commands.Choice(name="Message Patterns", value="message")
    ])
    async def osint_command(self, interaction: discord.Interaction, target: str, scope: app_commands.Choice[str]):
        """OSINT command - admin only."""
        if not await self._check_permissions(interaction.user):
            await interaction.response.send_message("You need Admin role to use OSINT features.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            report = None

            if scope.value == 'user':
                user = None
                try:
                    user_id = int(target.replace('<@', '').replace('>', '').replace('!', ''))
                    user = await self.fetch_user(user_id)
                except:
                    if interaction.guild:
                        for member in interaction.guild.members:
                            if target.lower() in member.name.lower() or target.lower() in member.display_name.lower():
                                user = member
                                break

                if not user:
                    await interaction.followup.send("User not found.")
                    return

                report = await self.osint.collect_user_intelligence(str(user.id), user)

            elif scope.value == 'server' and interaction.guild:
                report = await self.osint.collect_server_intelligence(interaction.guild)

            elif scope.value == 'message':
                messages = []
                async for msg in interaction.channel.history(limit=100):
                    if str(msg.author.id) == target or target.lower() in msg.author.name.lower():
                        messages.append(msg)

                report = await self.osint.analyze_message_patterns(messages, target)

            else:
                await interaction.followup.send("Invalid scope or missing permissions.")
                return

            # Send report
            report_md = report.to_markdown()

            if len(report_md) > 2000:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, dir='/tmp') as f:
                    f.write(report_md)
                    temp_path = f.name

                await interaction.followup.send(
                    f"OSINT Report for {target}",
                    file=discord.File(temp_path, filename=f"osint_report_{target.replace(' ', '_')}.md")
                )
                os.unlink(temp_path)
            else:
                await interaction.followup.send(report_md)

        except Exception as e:
            print(f"OSINT error: {e}")
            await interaction.followup.send(f"OSINT error: {str(e)[:500]}")

    @app_commands.command(name="memory", description="Query the agent's memory")
    @app_commands.describe(query="What to recall or search for")
    async def memory_command(self, interaction: discord.Interaction, query: str):
        """Memory query command."""
        await interaction.response.defer(thinking=True)

        try:
            results = await self.memory.retrieve(
                query,
                context_entities={f"user:{interaction.user.id}"},
                n_results=5
            )

            if not results:
                await interaction.followup.send("No relevant memories found.")
                return

            embed = discord.Embed(
                title="Memory Recall",
                description=f"Query: {query}",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )

            for i, mem in enumerate(results, 1):
                value = mem.content[:200] + "..." if len(mem.content) > 200 else mem.content
                score = mem.compute_score(datetime.utcnow(), set())
                embed.add_field(
                    name=f"Memory {i} (Score: {score:.2f})",
                    value=value,
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Memory error: {e}")
            await interaction.followup.send(f"Memory error: {str(e)[:500]}")

    @app_commands.command(name="upload", description="Upload a ZIP file for analysis")
    async def upload_command(self, interaction: discord.Interaction, file: discord.Attachment):
        """Process uploaded ZIP files containing repositories."""
        await interaction.response.defer(thinking=True)

        try:
            if not file.filename.endswith('.zip'):
                await interaction.followup.send(
                    "I only accept ZIP files containing code repositories. Please compress your files and try again.",
                    ephemeral=True
                )
                return

            if file.size > self.max_file_size:
                await interaction.followup.send(
                    f"File too large ({file.size / 1024 / 1024:.1f}MB). Max: {self.max_file_size / 1024 / 1024:.1f}MB",
                    ephemeral=True
                )
                return

            temp_dir = tempfile.mkdtemp(dir='/tmp')
            zip_path = os.path.join(temp_dir, file.filename)

            await file.save(zip_path)

            analysis = await self._analyze_repository(zip_path, temp_dir)

            await self.memory.store(
                content=f"Analyzed repository: {file.filename}\n{analysis['summary']}",
                layer=MemoryLayer.SEMANTIC,
                priority=MemoryPriority.HIGH,
                entities=[f"user:{interaction.user.id}", file.filename],
                metadata={
                    'user_id': str(interaction.user.id),
                    'file_name': file.filename,
                    'file_size': file.size,
                    'analysis': analysis
                }
            )

            embed = discord.Embed(
                title=f"Repository Analysis: {file.filename}",
                description=analysis['summary'],
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="Files", value=str(analysis['file_count']), inline=True)
            embed.add_field(name="Languages", value=", ".join(analysis['languages'].keys())[:50] or "N/A", inline=True)
            embed.add_field(name="Total Lines", value=str(analysis['total_lines']), inline=True)

            if analysis.get('structure'):
                structure = "\n".join(analysis['structure'][:15])
                if len(structure) > 1000:
                    structure = structure[:1000] + "..."
                embed.add_field(name="Structure", value=f"```\n{structure}\n```", inline=False)

            if analysis.get('top_files'):
                top_files = "\n".join([f"{f['path']} ({f['lines']} lines)" for f in analysis['top_files'][:5]])
                embed.add_field(name="Largest Files", value=top_files, inline=False)

            await interaction.followup.send(embed=embed)

            shutil.rmtree(temp_dir)

        except Exception as e:
            print(f"Upload error: {e}")
            await interaction.followup.send(f"Upload error: {str(e)[:500]}")

    async def _analyze_repository(self, zip_path: str, extract_dir: str) -> Dict[str, Any]:
        """Analyze a ZIP repository with detailed metrics."""
        extract_path = os.path.join(extract_dir, 'extracted')
        os.makedirs(extract_path, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for item in zip_ref.namelist():
                if item.startswith('..') or item.startswith('/'):
                    raise ValueError("Invalid file path in ZIP")

            zip_ref.extractall(extract_path)

        file_count = 0
        total_lines = 0
        languages = {}
        structure = []
        top_files = []

        for root, dirs, files in os.walk(extract_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]

            level = root.replace(extract_path, '').count(os.sep)
            indent = '  ' * level
            rel_root = os.path.relpath(root, extract_path)
            if rel_root != '.':
                structure.append(f"{indent}{os.path.basename(root)}/")

            for file in files:
                if file.startswith('.'):
                    continue

                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)

                if ext in self.allowed_extensions:
                    file_count += 1
                    languages[ext] = languages.get(ext, 0) + 1

                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            total_lines += lines
                            top_files.append({'path': os.path.relpath(file_path, extract_path), 'lines': lines})
                    except Exception as _e:
                        continue

                subindent = '  ' * (level + 1)
                structure.append(f"{subindent}{file}")

        top_files.sort(key=lambda x: x['lines'], reverse=True)

        return {
            'summary': f"Analyzed {file_count} code files across {len(languages)} languages ({total_lines:,} total lines).",
            'file_count': file_count,
            'total_lines': total_lines,
            'languages': languages,
            'structure': structure,
            'top_files': top_files
        }

    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats_command(self, interaction: discord.Interaction):
        """Show bot statistics."""
        try:
            memory_stats = self.memory.get_stats()
            reasoning_stats = self.reasoning.get_stats()
            osint_stats = self.osint.get_stats()

            embed = discord.Embed(
                title="Bot Statistics",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="Memory",
                value=f"Working: {memory_stats['working_memories']}\n"
                      f"Episodic: {memory_stats['episodic_memories']}\n"
                      f"Semantic: {memory_stats['semantic_memories']}\n"
                      f"Graph: {memory_stats['graph_entities']} entities, {memory_stats['graph_relationships']} relations",
                inline=True
            )

            embed.add_field(
                name="Reasoning",
                value=f"Sequential: {reasoning_stats['sequential_calls']}\n"
                      f"Parallel: {reasoning_stats['parallel_calls']}\n"
                      f"Reflective: {reasoning_stats['reflective_calls']}\n"
                      f"Analogical: {reasoning_stats['analogical_calls']}",
                inline=True
            )

            embed.add_field(
                name="System",
                value=f"Servers: {len(self.guilds)}\n"
                      f"Uptime: {(datetime.utcnow() - self._startup_time).total_seconds() / 3600:.1f}h\n"
                      f"OSINT: {'Enabled' if osint_stats['enabled'] else 'Disabled'}",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)[:500]}")

    @app_commands.command(name="help", description="Show available commands and capabilities")
    async def help_command(self, interaction: discord.Interaction):
        """Help command."""
        embed = discord.Embed(
            title=f"{self.config.get('AGENT_NAME', 'Sentinel')} - Help",
            description="An advanced AI agent with memory, reasoning, and analysis capabilities.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        commands_info = [
            ("/ask <question>", "Ask me anything. I remember our conversations."),
            ("/reason <problem> <mode>", "Advanced reasoning: sequential, parallel, reflective, analogical."),
            ("/memory <query>", "Search through my memories of our conversations."),
            ("/upload <file>", "Upload a ZIP file containing code for analysis."),
            ("/stats", "View bot statistics and performance metrics."),
            ("/osint <target> <scope>", "[Admin only] Intelligence gathering."),
        ]

        for cmd, desc in commands_info:
            embed.add_field(name=cmd, value=desc, inline=False)

        embed.add_field(
            name="Natural Language",
            value="Mention me (@Bot) or DM me to chat naturally.",
            inline=False
        )

        embed.set_footer(text="Agentic AI System v1.0 | Memory-First Architecture")
        await interaction.response.send_message(embed=embed)

    async def close(self):
        """Graceful shutdown."""
        self.memory_maintenance.cancel()
        self.status_rotation.cancel()
        try:
            await self.memory.shutdown()
            await self.osint.shutdown()
        except Exception as e:
            print(f"Shutdown error: {e}")
        await super().close()
