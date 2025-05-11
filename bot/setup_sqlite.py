#!/usr/bin/env python3
"""
Script to initialize SQLite database for local development.
This creates the necessary tables and verifies the connection.
"""
import os
import sys
from pathlib import Path

# Ensure we're in the correct directory
script_dir = Path(__file__).resolve().parent
os.chdir(script_dir)

# Ensure data directory exists
data_dir = script_dir / "data"
data_dir.mkdir(exist_ok=True)

# Set required environment variables for configuration
os.environ.setdefault("BOT_TOKEN", "dummy_token_for_setup")
os.environ.setdefault("OPENAI_API_KEY", "dummy_key_for_setup")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir}/database.sqlite")

# Import after environment setup
from utils.analytics_storage import create_tables, engine, SessionLocal, UserEvent

def init_database():
    """Initialize the SQLite database with necessary tables"""
    print(f"Initializing SQLite database at: {os.environ['DATABASE_URL']}")
    
    try:
        # Create tables
        create_tables()
        print("Tables created successfully!")
        
        # Test connection by adding and querying a test event
        with SessionLocal() as session:
            # Add test event
            test_event = UserEvent(
                user_id=0,
                chat_id=0,
                event_type="db_initialization_test",
                username="test_user",
                extra="This is a test event to verify database setup"
            )
            session.add(test_event)
            session.commit()
            
            # Query to verify it was added
            event = session.query(UserEvent).filter_by(event_type="db_initialization_test").first()
            assert event is not None, "Failed to retrieve test event"
            
            print(f"Test event created with ID: {event.id}")
            print("Database connection verified successfully!")
            
            # Clean up test event
            session.delete(event)
            session.commit()
            print("Test event cleaned up")
        
        print("\nSQLite database initialized and ready for use!")
        print("You can now start the bot with the local SQLite database")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()