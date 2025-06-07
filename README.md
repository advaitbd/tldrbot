# TeleBot

A production-ready Telegram bot with freemium functionality, AI-powered conversation management, and integrated payment processing. Built with Python, Redis, PostgreSQL, and Stripe integration for scalable deployment.

## 🌟 Key Features

### 🎯 **Freemium Business Model**
- **Free Tier**: 5 daily, 100 monthly summaries, 3 groups max
- **Premium Tier**: Unlimited access with Stripe integration
- **Real-time Quota Tracking**: Redis-based usage monitoring
- **Graceful Degradation**: Premium users bypass quotas during outages

### 🤖 **AI-Powered Conversation Management**
- **Smart Summaries**: `/summarize` command with configurable message count
- **Multi-Model Support**: OpenAI, Groq, DeepSeek with strategy pattern
- **Context-Aware Responses**: Reply chains and conversation threading
- **Quality Controls**: Content filtering and rate limiting

### 💳 **Production Payment System**
- **Stripe Integration**: Secure payment processing with webhooks
- **Subscription Management**: Automatic renewals, cancellations, grace periods
- **Real-time Status Sync**: Instant premium activation/deactivation
- **Payment Links**: Dynamic checkout with Telegram ID tracking

### 📊 **Enterprise-Grade Infrastructure**
- **Redis Caching**: High-performance quota management and session storage
- **PostgreSQL Database**: Reliable user data and analytics storage
- **Health Monitoring**: Comprehensive health checks and error tracking
- **Webhook Security**: Stripe signature verification and replay protection

## 🏗️ Technical Architecture

### 🧩 Core Components

#### **1. Freemium Management Layer**
- **UsageService**: Centralized quota checking and counter management
- **QuotaManager**: Redis-based usage tracking with automatic resets
- **Premium Logic**: Bypass mechanisms and fail-safe blocking
- **Analytics**: User behavior tracking and conversion metrics

#### **2. Payment Processing**
- **StripeService**: Webhook handling, subscription management
- **WebhookHandlers**: Secure event processing with signature verification
- **User Management**: Premium status synchronization
- **Error Recovery**: Retry logic and graceful failure handling

#### **3. AI Services**
- **Strategy Pattern**: Pluggable AI model architecture
- **Model Management**: OpenAI, Groq, DeepSeek providers
- **Response Processing**: Context-aware summarization
- **Performance Monitoring**: Response time and quality tracking

#### **4. Data Layer**
- **PostgreSQL**: User profiles, subscription data, analytics
- **Redis**: Session storage, quota counters, rate limiting
- **Memory Storage**: Chat history buffering (400 messages)
- **Health Checks**: Database and cache connectivity monitoring

#### **5. Bot Framework**
- **Command Handlers**: Core bot functionality with quota enforcement
- **Message Handlers**: Reply processing and conversation management
- **Webhook Integration**: Stripe event processing
- **Error Handling**: Comprehensive logging and recovery mechanisms

## 🚀 Quick Start

### 📋 Prerequisites
- **Python 3.10+** (recommended: 3.11 for best performance)
- **Redis** (6.0+) for quota management and caching
- **PostgreSQL** (12+) for user data and analytics
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **API Keys** for AI services (at least one required)
- **Stripe Account** (optional, for payment processing)

### ⚡ Development Setup

#### 1. **Clone and Setup Environment**
```bash
# Clone the repository
git clone https://github.com/your-org/telebot.git
cd telebot

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. **Database Setup**
```bash
# Start PostgreSQL (example with Docker)
docker run --name telebot-postgres \
  -e POSTGRES_DB=telebot \
  -e POSTGRES_USER=telebot \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 -d postgres:14

# Start Redis (example with Docker)
docker run --name telebot-redis \
  -p 6379:6379 -d redis:7-alpine
```

#### 3. **Environment Configuration**
Create `.env` file in the project root:

```bash
# === REQUIRED SETTINGS ===
# Telegram Bot Token from @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Database connections
DATABASE_URL=postgresql://telebot:your_password@localhost:5432/telebot
REDIS_URL=redis://localhost:6379/0

# AI Service (at least one required)
OPENAI_API_KEY=sk-...your_openai_key
# OR
GROQ_API_KEY=gsk_...your_groq_key
# OR  
DEEPSEEK_API_KEY=sk-...your_deepseek_key

# === OPTIONAL SETTINGS ===
# AI Model Configuration
OPENAI_MODEL=gpt-4o-mini          # Default: gpt-4o-mini
GROQ_MODEL=llama3-8b-8192         # Default: llama3-8b-8192  
DEEPSEEK_MODEL=deepseek-chat      # Default: deepseek-chat

# Payment Processing (for production)
STRIPE_API_KEY=sk_live_...        # Your Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...   # Webhook endpoint secret
STRIPE_PAYMENT_LINK=https://buy.stripe.com/...  # Payment link

# Production Deployment
WEBHOOK_URL=https://your-domain.com/webhook/telegram
PORT=8000

# Content Filtering
CENSOR=spam,abuse,inappropriate   # Comma-separated blocked words

# Environment
ENVIRONMENT=development           # development|staging|production
```

#### 4. **Database Migration**
```bash
# Navigate to bot directory
cd bot

# Initialize database (creates tables)
python -c "
from utils.analytics_storage import init_db
init_db()
print('✅ Database initialized successfully')
"
```

#### 5. **Run Development Server**
```bash
# From the bot/ directory
python main.py

# You should see:
# ✅ Bot started successfully
# ✅ Database connection healthy
# ✅ Redis connection healthy  
# 🤖 Bot is running...
```

## 🧪 Testing

### **Run Test Suite**
```bash
# Run all tests with coverage
cd bot
python -m pytest tests/ -v --tb=short

# Run specific test categories
python -m pytest tests/test_quota_logic.py -v          # Quota management tests
python -m pytest tests/test_webhook_handlers.py -v     # Payment processing tests  
python -m pytest tests/test_integration.py -v          # End-to-end integration tests

# Run with coverage report
python -m pytest tests/ --cov=. --cov-report=html
```

### **Test Categories**
- **🎯 Quota Logic**: Freemium enforcement, Redis operations, premium bypass
- **💳 Webhook Handlers**: Stripe integration, payment processing, security
- **🔗 Integration**: End-to-end workflows, database operations, error recovery

### **Mock Services for Testing**
All external dependencies are properly mocked:
- ✅ Stripe API calls
- ✅ Redis operations  
- ✅ Database transactions
- ✅ AI service responses
- ✅ Telegram API calls

## 📱 Usage Guide

### **Core Commands**
```bash
/help          # Show available commands and usage statistics
/summarize     # AI-powered chat summary (respects quotas)
/usage         # Check your quota usage and subscription status  
/upgrade       # Get premium subscription link
/cancel        # Cancel any ongoing operation
```

### **Freemium System**
- **Free Users**: 5 daily summaries, 100 monthly, max 3 groups
- **Premium Users**: Unlimited access to all features  
- **Quota Enforcement**: Automatic blocking when limits exceeded
- **Grace Period**: Premium users maintain access during payment issues

### **AI Models**
The bot supports multiple AI providers with automatic fallback:
- **OpenAI**: GPT-4o-mini (default) - Balanced performance and cost
- **Groq**: Llama 3-8B - Fast inference, good quality
- **DeepSeek**: DeepSeek-Chat - Cost-effective alternative

## 🔧 Development Guide

### **Project Structure**
```
telebot/
├── bot/                              # Main application code
│   ├── config/                       # Configuration management
│   │   ├── settings.py              # Environment variables and settings
│   │   └── __init__.py
│   ├── data/                         # Data storage
│   │   └── bot.db                   # SQLite database (development)
│   ├── handlers/                     # Request handlers
│   │   ├── conversations/           # Multi-step conversation flows  
│   │   ├── command_handlers.py      # Bot command processors
│   │   ├── message_handlers.py      # Message and reply handlers
│   │   └── webhook_handlers.py      # Stripe webhook processors
│   ├── services/                     # Business logic layer
│   │   ├── ai/                      # AI model strategies
│   │   │   ├── openai_service.py    # OpenAI integration
│   │   │   ├── groq_service.py      # Groq integration
│   │   │   └── deepseek_service.py  # DeepSeek integration
│   │   ├── usage_service.py         # Quota management service
│   │   └── stripe_service.py        # Payment processing
│   ├── tests/                        # Test suites
│   │   ├── test_quota_logic.py      # Freemium functionality tests
│   │   ├── test_webhook_handlers.py # Payment processing tests
│   │   └── test_integration.py      # End-to-end tests
│   ├── utils/                        # Utility modules
│   │   ├── quota_manager.py         # Redis-based quota tracking
│   │   ├── user_management.py       # User CRUD operations
│   │   ├── analytics_storage.py     # Database operations
│   │   └── memory_storage.py        # Chat history management
│   ├── main.py                       # Application entry point
│   └── pytest.ini                   # Test configuration
├── pm/                               # Project management
│   ├── architecture.md              # System architecture docs
│   └── implementation_tasks.md      # Development roadmap
├── requirements.txt                  # Python dependencies
├── SQLite_Setup.md                  # Database setup guide
└── README.md                        # This file
```

### **🚀 Adding New Features**

#### **1. New Bot Commands**
```python
# In bot/handlers/command_handlers.py

async def new_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new command with quota checking."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Check quota first
    if not await self.usage_service.within_quota(user.id, chat_id):
        await self._block_and_dm(user.id, update)
        return
    
    # Your command logic here
    
    # Increment usage counters
    await self.usage_service.increment_counters(user.id, chat_id)

# Register in main.py
application.add_handler(CommandHandler("newcmd", command_handlers.new_command))
```

#### **2. New AI Model Provider**
```python
# Create bot/services/ai/newprovider_service.py

from services.ai.base_ai_service import BaseAIService

class NewProviderService(BaseAIService):
    def __init__(self):
        self.api_key = settings.NEW_PROVIDER_API_KEY
        self.model = settings.NEW_PROVIDER_MODEL
    
    def get_response(self, prompt: str) -> str:
        # Implement your provider's API call
        pass

# Register in bot/services/ai/__init__.py
```

#### **3. Custom Webhook Handlers**
```python
# In bot/handlers/webhook_handlers.py

async def handle_custom_webhook(self, event_data: Dict) -> bool:
    """Handle custom webhook events."""
    try:
        # Process your webhook data
        return True
    except Exception as e:
        logger.error(f"Error handling custom webhook: {e}")
        return False
```

### **🔍 Debugging and Monitoring**

#### **Health Checks**
```bash
# Check system health
curl http://localhost:8000/health

# Check individual components
python -c "
from services.usage_service import UsageService
from services.stripe_service import StripeService

usage = UsageService()
stripe = StripeService()

print('Usage Service:', await usage.health_check())
print('Stripe Service:', stripe.get_payment_link() is not None)
"
```

#### **Logs and Metrics**
- **Application Logs**: Standard Python logging to console/file
- **Usage Analytics**: Stored in PostgreSQL `analytics` table
- **Error Tracking**: Comprehensive exception logging with context
- **Performance Metrics**: Response times, quota check duration

### **🌐 Production Deployment**

#### **Environment Setup**
```bash
# Production environment variables
ENVIRONMENT=production
WEBHOOK_URL=https://yourdomain.com
BOT_TOKEN=your_production_bot_token

# Database (managed service recommended)
DATABASE_URL=postgresql://user:pass@prod-db:5432/telebot

# Redis (managed service recommended)  
REDIS_URL=redis://prod-redis:6379/0

# Stripe (live keys)
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

#### **Docker Deployment**
```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot/ ./bot/
EXPOSE 8000

CMD ["python", "bot/main.py"]
```

#### **Health Monitoring**
The bot includes comprehensive health checks:
- ✅ Database connectivity
- ✅ Redis connectivity  
- ✅ Stripe API accessibility
- ✅ AI service availability
- ✅ Webhook endpoint status

### **🛡️ Security Considerations**

- **Environment Variables**: Never commit secrets to version control
- **Webhook Security**: Stripe signature verification implemented
- **Rate Limiting**: Redis-based quota enforcement prevents abuse
- **Input Validation**: All user inputs are sanitized and validated
- **Database Security**: Parameterized queries prevent SQL injection
- **Error Handling**: Sensitive information never exposed in error messages

## 🤝 Contributing

### **Development Workflow**
1. **Fork the repository** and create a feature branch
2. **Set up development environment** following the quick start guide
3. **Run tests** to ensure everything works: `python -m pytest tests/ -v`
4. **Implement your feature** with appropriate quota checking
5. **Add tests** for new functionality
6. **Update documentation** as needed
7. **Submit a pull request** with clear description

### **Code Standards**
- **Type Hints**: All functions should have proper type annotations
- **Async/Await**: Use async patterns for I/O operations
- **Error Handling**: Comprehensive try/catch with logging
- **Testing**: Unit tests required for all new features
- **Documentation**: Docstrings for all public functions

### **Pull Request Checklist**
- [ ] All tests pass (`python -m pytest tests/ -v`)
- [ ] New functionality includes appropriate tests
- [ ] Quota checking implemented for user-facing features
- [ ] Error handling and logging added
- [ ] Documentation updated
- [ ] No hardcoded secrets or credentials

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Support

### **Getting Help**
- 📖 **Documentation**: Check this README and `/pm/architecture.md`
- 🐛 **Bug Reports**: Create an issue with reproduction steps
- 💡 **Feature Requests**: Open an issue with detailed description
- 🔧 **Development Help**: Check existing issues and discussions

### **Troubleshooting**

#### **Common Issues**

**Bot not starting:**
```bash
# Check environment variables
python -c "from config.settings import *; print('✅ Config loaded')"

# Verify database connection
python -c "from utils.analytics_storage import SessionLocal; print('✅ DB connected')"

# Test Redis connection
python -c "import redis; r=redis.from_url('redis://localhost:6379'); r.ping(); print('✅ Redis connected')"
```

**Tests failing:**
```bash
# Clean test environment
cd bot
python -m pytest tests/ -v --tb=long

# Check for missing environment variables
python -c "import os; print([k for k in os.environ if 'TEST' in k])"
```

**Quota system not working:**
```bash
# Verify Redis quota keys
redis-cli KEYS "usage:*"
redis-cli KEYS "groups:*"

# Check quota manager
python -c "from utils.quota_manager import QuotaManager; qm=QuotaManager(); print('✅ Quota manager ready')"
```

### **Performance Optimization**
- **Redis Connection Pooling**: Configured automatically
- **Database Connection Management**: SQLAlchemy session handling
- **Async Operations**: Non-blocking I/O for scalability
- **Caching Strategy**: Redis for session data, memory for chat history
- **Error Recovery**: Graceful degradation and retry logic

---

## 🚀 Quick Commands Reference

```bash
# Development
python main.py                              # Start bot
python -m pytest tests/ -v                  # Run tests
python -c "from utils.analytics_storage import init_db; init_db()"  # Setup DB

# Production
docker build -t telebot .                   # Build container
docker run -p 8000:8000 telebot            # Run container
curl http://localhost:8000/health           # Health check

# Debugging  
redis-cli MONITOR                           # Watch Redis operations
tail -f bot.log                             # Monitor application logs
python -c "from services.usage_service import UsageService; import asyncio; print(asyncio.run(UsageService().health_check()))"  # Test services
```

**🎉 Ready to build something amazing? Start with the [Quick Start](#-quick-start) guide!**
