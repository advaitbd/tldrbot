# SQLite Local Development Database

This directory contains the SQLite database file for local development. Using SQLite instead of PostgreSQL simplifies the local development setup and removes the need for a separate database server.

## Setup Instructions

1. Ensure your `.env` file includes the SQLite database URL:
   ```
   export DATABASE_URL=sqlite:///data/database.sqlite
   ```

2. Run the database initialization script:
   ```
   python setup_sqlite.py
   ```

3. The script will create the necessary tables and verify the database connection.

## Important Notes

- This SQLite database is intended for **local development only**
- For production deployments, continue using PostgreSQL
- The database file (`database.sqlite`) is excluded from git via `.gitignore`
- All analytics data is stored locally in this database

## Switching Between SQLite and PostgreSQL

To switch back to PostgreSQL, simply update the `DATABASE_URL` in your `.env` file to point to your PostgreSQL instance:

```
export DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## Database Schema

The database contains the following tables:

- `user_events`: Logs all user interactions with the bot for analytics purposes