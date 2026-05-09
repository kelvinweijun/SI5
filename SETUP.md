# Setup & Deployment Guide

## Table of Contents
1. [Local Development Setup](#local-development-setup)
2. [Discord Bot Configuration](#discord-bot-configuration)
3. [Cerebras API Setup](#cerebras-api-setup)
4. [Render.com Deployment](#rendercom-deployment)
5. [Environment Variables](#environment-variables)
6. [Troubleshooting](#troubleshooting)

## Local Development Setup

### Step 1: Clone and Setup
```bash
git clone <your-repo>
cd agentic-ai-discord-bot
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### Step 2: Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

### Step 3: API Keys
Create `config/cerebras_api_keys.txt`:
```bash
mkdir -p config
echo "your-api-key-1" > config/cerebras_api_keys.txt
echo "your-api-key-2" >> config/cerebras_api_keys.txt
```

### Step 4: Run
```bash
python -m src.main
```

## Discord Bot Configuration

### Creating a Bot Application
1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → Name it (e.g., "Sentinel")
3. Go to **Bot** tab on the left
4. Click **Add Bot**
5. Under **Privileged Gateway Intents**, enable:
   - ☑️ MESSAGE CONTENT INTENT
   - ☑️ SERVER MEMBERS INTENT
   - ☑️ PRESENCE INTENT
6. Click **Reset Token** and copy the token (save to `DISCORD_BOT_TOKEN`)

### OAuth2 URL Generator
1. Go to **OAuth2** → **URL Generator**
2. Select scopes:
   - ☑️ `bot`
   - ☑️ `applications.commands`
3. Select bot permissions:
   - ☑️ Send Messages
   - ☑️ Read Messages/View Channels
   - ☑️ Read Message History
   - ☑️ Attach Files
   - ☑️ Create Public Threads
   - ☑️ Embed Links
   - ☑️ Use Slash Commands
   - ☑️ Add Reactions
4. Copy the generated URL and open it in browser
5. Select your server and authorize

## Cerebras API Setup

### Getting API Keys
1. Sign up at [Cerebras Cloud](https://cloud.cerebras.ai/)
2. Navigate to **API Keys** section
3. Generate new keys (create multiple for rotation)
4. Save them to `config/cerebras_api_keys.txt` (one per line)

### Rate Limits
- Default: 30 requests/minute per key
- With 3 keys: effective 90 requests/minute
- The bot automatically rotates on rate limit errors

## Render.com Deployment

### Method 1: Blueprint (Recommended)

1. Push your code to GitHub
2. In Render Dashboard, click **New +** → **Blueprint**
3. Connect your GitHub repository
4. Render reads `render.yaml` and creates:
   - Web Service (Discord bot)
   - Redis instance
   - Background Worker
   - Persistent Disk

### Method 2: Manual Setup

#### Web Service (Bot)
1. **New +** → **Web Service**
2. Connect repository
3. Configure:
   - **Name**: `agentic-bot`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m src.main`
4. Add Environment Variables (see table below)
5. Click **Create Web Service**

#### Redis (Required)
1. **New +** → **Redis**
2. **Name**: `agent-redis`
3. **Plan**: Starter (free tier)
4. Click **Create Redis**

#### Background Worker
1. **New +** → **Background Worker**
2. Same repository
3. **Start Command**: `python -m src.sleep_compute`
4. Same environment variables as web service

#### Persistent Disk
1. In Web Service settings, go to **Disks**
2. **Add Disk**:
   - **Name**: `agent-data`
   - **Mount Path**: `/data`
   - **Size**: 10 GB

### Environment Variables on Render

Set these in your Web Service dashboard:

| Variable | Value Source |
|----------|--------------|
| `DISCORD_BOT_TOKEN` | From Discord Developer Portal |
| `CEREBRAS_API_KEYS_FILE` | `/etc/secrets/cerebras_api_keys.txt` |
| `SUPABASE_URL` | From Supabase dashboard |
| `SUPABASE_KEY` | From Supabase dashboard |
| `REDIS_URL` | Auto-populated from Redis service |
| `OSINT_ENABLED` | `false` (enable only if needed) |

### Secret Files
For `cerebras_api_keys.txt`:
1. Go to Web Service → **Environment** → **Secret Files**
2. **Add Secret File**:
   - **Name**: `cerebras_api_keys`
   - **Path**: `/etc/secrets/cerebras_api_keys.txt`
   - **Content**: Paste your API keys (one per line)

## Environment Variables Reference

### Required
- `DISCORD_BOT_TOKEN` - Discord bot authentication token
- `CEREBRAS_API_KEYS_FILE` - Path to file containing API keys

### Optional (but recommended)
- `SUPABASE_URL` / `SUPABASE_KEY` - External database (free tier available)
- `REDIS_URL` - Caching and rate limiting
- `AGENT_NAME` - Bot display name (default: Sentinel)

### Optional (features)
- `OSINT_ENABLED` - Enable OSINT module (`true`/`false`)
- `OSINT_MAX_DEPTH` - Investigation depth (default: 3)
- `ADMIN_USER_IDS` - Comma-separated Discord user IDs with admin access

### Optional (tuning)
- `AGENT_MEMORY_DECAY_RATE` - Memory decay speed (default: 0.01)
- `AGENT_MEMORY_SCORE_THRESHOLD` - Minimum relevance score (default: 0.3)
- `AGENT_SLEEP_INTERVAL` - Background processing interval in seconds (default: 300)
- `CEREBRAS_RATE_LIMIT_RPM` - Requests per minute limit (default: 30)
- `MAX_FILE_SIZE` - Max upload size in bytes (default: 25MB)

## Troubleshooting

### Bot doesn't respond to commands
1. Check `DISCORD_BOT_TOKEN` is correct
2. Verify bot has `applications.commands` scope
3. Ensure bot has required permissions in server
4. Check Render logs for errors

### Rate limit errors
1. Add more API keys to `cerebras_api_keys.txt`
2. Check `CEREBRAS_RATE_LIMIT_RPM` setting
3. Verify keys are valid and not expired

### Memory not persisting
1. Check disk is mounted at `/data`
2. Verify `GRAPH_DB_PATH` and `CHROMADB_PATH` point to `/data/`
3. Ensure disk has available space

### OSINT not working
1. Verify `OSINT_ENABLED=true`
2. Check user has Admin role
3. Review logs for permission errors

### Import errors
1. Ensure `PYTHONPATH` includes project root
2. Run `pip install -r requirements.txt` again
3. Check Python version (3.11+ required)
