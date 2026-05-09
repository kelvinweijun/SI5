# System Intelligence 5 (Discord Bot version)

A sophisticated, production-ready agentic AI system deployable on Render.com that operates as a Discord bot with advanced reasoning, memory, code execution, and OSINT capabilities.

## Architecture Overview

```
Discord Bot Interface
    ├── Slash Commands (/ask, /reason, /memory, /upload, /osint)
    ├── Natural Language Processing (mentions & DMs)
    ├── File Processing (ZIP repository analysis)
    └── Context Awareness (server, channel, user)

Multi-Layer Memory Architecture
    ├── Layer 1: Working Memory (current context)
    ├── Layer 2: Episodic Memory (conversation history)
    ├── Layer 3: Semantic Memory (learned concepts)
    ├── Layer 4: Procedural Memory (skills & strategies)
    ├── Graph Database (entity relationships)
    └── Vector Store (semantic search)

Advanced Reasoning Engine
    ├── Sequential (Chain-of-Thought)
    ├── Parallel (Tree-of-Thoughts)
    ├── Reflective (Self-Critique)
    └── Analogical (Pattern Matching)

OSINT Module (Admin-only, explicit activation)
    ├── User Intelligence
    ├── Server Intelligence
    ├── Message Pattern Analysis
    └── Social Graph Construction

LLM Client with Key Rotation
    ├── Primary: Cerebras API
    ├── Fallback: OpenAI, Anthropic
    └── Automatic failover on rate limits
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- Cerebras API Key ([Cerebras Cloud](https://cloud.cerebras.ai/))
- Render.com account (for deployment)

### 2. Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd agentic-ai-discord-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Create API keys file
mkdir -p config
echo "your-cerebras-api-key-1" > config/cerebras_api_keys.txt
echo "your-cerebras-api-key-2" >> config/cerebras_api_keys.txt

# Run the bot
python -m src.main
```

### 3. Render.com Deployment

#### Option A: Using render.yaml (Blueprint)

1. Push code to GitHub
2. In Render Dashboard: **New +** → **Blueprint**
3. Connect your repository
4. Render will automatically provision:
   - Web service (Discord bot)
   - Redis instance (caching)
   - Worker service (background processing)

#### Option B: Manual Setup

1. **Create Web Service**
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m src.main`
   - Environment Variables: Add all from `.env`

2. **Create Redis Instance**
   - Name: `agent-redis`
   - Plan: Starter (free)

3. **Create Worker Service**
   - Same repo, different start command: `python -m src.sleep_compute`

4. **Add Disk**
   - Name: `agent-data`
   - Mount Path: `/data`
   - Size: 10 GB

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application → Bot
3. Enable Privileged Intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
   - PRESENCE INTENT
4. Generate OAuth2 URL with scopes:
   - `bot`
   - `applications.commands`
5. Permissions needed:
   - Send Messages
   - Read Message History
   - Attach Files
   - Create Public Threads
   - Embed Links
   - Use Slash Commands
6. Invite bot to your server

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |
| `CEREBRAS_API_KEYS_FILE` | Path to API keys file | Yes |
| `SUPABASE_URL` | Supabase project URL | No |
| `SUPABASE_KEY` | Supabase service key | No |
| `REDIS_URL` | Redis connection string | No |
| `OSINT_ENABLED` | Enable OSINT features | No (default: false) |
| `AGENT_NAME` | Bot name | No (default: Sentinel) |

### API Keys File Format

Create `config/cerebras_api_keys.txt`:
```
# One key per line
ck-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ck-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
ck-zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
```

The system automatically rotates keys on rate limit errors.

## Features

### Memory-First Design
- **4-Layer Memory**: Working, Episodic, Semantic, Procedural
- **Graph Relationships**: Entity connections and disambiguation
- **Vector Search**: Semantic similarity retrieval
- **Sleep-Time Compute**: Background relationship building
- **Decay & Scoring**: Dynamic relevance weighting

### Advanced Reasoning
- **Tree-of-Thoughts**: Multi-path exploration for complex problems
- **Chain-of-Thought**: Step-by-step linear reasoning
- **Reflective**: Self-critique and refinement loops
- **Analogical**: Cross-domain pattern matching

### OSINT Capabilities (Admin-only)
- User metadata analysis
- Server structure mapping
- Message pattern recognition
- Social graph construction
- Structured intelligence reports (Markdown/JSON)

### File Processing
- ZIP repository upload and analysis
- Code structure extraction
- Language detection
- Line counting and metrics

## Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/ask <question>` | General Q&A with memory | Everyone |
| `/reason <problem> <mode>` | Advanced reasoning | Everyone |
| `/memory <query>` | Search memories | Everyone |
| `/upload <file>` | Upload ZIP for analysis | Everyone |
| `/osint <target> <scope>` | Intelligence gathering | Admin only |
| `/help` | Show help | Everyone |

## Security Considerations

1. **OSINT Module**: Disabled by default. Only enable for trusted environments.
2. **Code Sandbox**: Restricted Python execution with limited builtins.
3. **File Validation**: Only text/code files accepted. ZIP contents validated.
4. **Rate Limiting**: Built-in protection for API calls.
5. **Role-Based Access**: Admin commands require specific Discord roles.

## Monitoring

The bot exposes Prometheus metrics on `/metrics` (if configured):
- Request counts and latency
- Memory store sizes
- API key usage and rotation events
- Error rates by component

## Architecture Principles

1. **Reasoning IS Memory**: Memory is an active reasoning substrate, not passive storage
2. **Sleep-Time Compute**: Background processing builds relationships proactively
3. **Human On the Loop**: Agents operate autonomously; humans supervise at a higher level
4. **Self-Repair**: System accumulates context and adapts over time
5. **Skill Building**: Agents create procedural memories from repeated patterns

## License

MIT License - See LICENSE file for details.

## Support

For issues or questions:
- Open a GitHub issue
- Check the [Render.com docs](https://render.com/docs) for deployment help
- Review [Discord.py docs](https://discordpy.readthedocs.io/) for bot customization
