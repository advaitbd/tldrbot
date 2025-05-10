# Local Development Setup: SQLite and Redis

This guide will help you set up a local development environment for the TeleBot project, eliminating the need to connect to PostgreSQL and external Redis servers.

## Overview

In production, TeleBot uses PostgreSQL to store analytics data and Redis for queue management. For local development, we can use:

### SQLite Database
- No need to install and run a PostgreSQL server
- Self-contained in a single file
- Easy setup and maintenance
- No external dependencies

### Redis Options
- Use a local Redis server installation
- Use Redis Cloud free tier
- Configure mock Redis (for advanced users)

## Setup Instructions

### 1. Update your `.env` file

Add the following lines to your `.env` file in the `TeleBot/bot/` directory:

```
export DATABASE_URL=sqlite:///data/database.sqlite
export REDIS_URL=redis://localhost:6379/0
```

The first line configures SQLAlchemy to use a SQLite database stored in the `data` directory.
The second line configures the Redis connection for queue management.

### 2. Initialize the Database

Run the setup script to initialize the SQLite database:

```bash
cd TeleBot/bot
python setup_sqlite.py
```

This script will:
- Create the `data` directory if it doesn't exist
- Initialize the SQLite database with the required tables
- Verify the database connection works properly

### 3. Verify the Setup

You should see output confirming that the database has been initialized successfully. The SQLite database file will be created at `TeleBot/bot/data/database.sqlite`.

## Viewing Database Data

Use the included utility script to view and analyze data in the SQLite database:

```bash
# View recent events (default: 20)
python view_sqlite_data.py recent

# View recent events with custom limit
python view_sqlite_data.py recent --limit 50

# View statistics for the past 7 days (default)
python view_sqlite_data.py stats

# View statistics for a custom period
python view_sqlite_data.py stats --days 30
```

## Redis Setup Options

### Option 1: Install Redis Locally

1. **Install Redis**:
   - macOS: `brew install redis`
   - Ubuntu: `sudo apt install redis-server`
   - Windows: Use Redis with WSL or download from https://github.com/microsoftarchive/redis/releases

2. **Start Redis Server**:
   - macOS/Linux: `redis-server`
   - Windows: Run the Redis Server executable

### Option 2: Use Redis Cloud

1. Sign up for a free Redis Cloud account at https://redis.com/try-free/
2. Create a database and get your connection string
3. Update your `.env` file with the Redis Cloud URL:
   ```
   export REDIS_URL=redis://username:password@host:port
   ```

## Switching Between Development and Production

### Database

To switch back to PostgreSQL, update the `DATABASE_URL` in your `.env` file:

```
export DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

### Redis

To switch to a production Redis instance, update the `REDIS_URL` in your `.env` file:

```
export REDIS_URL=redis://username:password@host:port/db
```

## Important Notes

- The SQLite database is intended for **local development only**
- The database file is excluded from git via `.gitignore`
- All analytics data is stored locally and won't be synced with production
- SQLite has some limitations compared to PostgreSQL, but they shouldn't impact development
- Redis is required for the bot to function properly (for queue management)
- If you don't have Redis installed, you'll need to install it or use Redis Cloud

## Troubleshooting

### Database Not Found

If you see an error about the database not being found, run the `setup_sqlite.py` script again to initialize it.

### SQLAlchemy Errors

If you encounter SQLAlchemy errors, ensure you're using a compatible version (2.0 or later).

### Data Directory Permission Issues

Ensure the `TeleBot/bot/data` directory has write permissions for your user.

### Redis Connection Issues

If you see a Redis connection error:

1. Verify that Redis is running: `redis-cli ping` (should return `PONG`)
2. Check your Redis URL format: `redis://hostname:port/db` 
3. If using Redis Cloud, verify your credentials and network connectivity
4. Try a different Redis database number (e.g., `redis://localhost:6379/1`)

## Technical Implementation

### SQLite
- Database file location: `TeleBot/bot/data/database.sqlite`
- Uses SQLAlchemy ORM with the same models as PostgreSQL
- Schema compatibility is maintained between SQLite and PostgreSQL
- Environment variable configuration remains the same, only the connection URL changes

### Redis
- Used for queue management and task processing
- Same interface is used for local and production Redis
- The bot uses Redis to manage asynchronous LLM job processing
- No persistent data is stored in Redis (only transient message queues)