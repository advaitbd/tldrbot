#!/usr/bin/env python3
"""
Utility script to view data in the SQLite database.
This provides a simple way to query and explore the analytics data stored locally.
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from tabulate import tabulate

# Ensure we're in the correct directory
script_dir = Path(__file__).resolve().parent
os.chdir(script_dir)

# Ensure data directory exists
data_dir = script_dir / "data"
database_path = data_dir / "database.sqlite"

# Set required environment variables for configuration
os.environ.setdefault("BOT_TOKEN", "dummy_token_for_setup")
os.environ.setdefault("OPENAI_API_KEY", "dummy_key_for_setup")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir}/database.sqlite")

# Import after environment setup
from utils.analytics_storage import SessionLocal, UserEvent
from sqlalchemy import func

def check_database():
    """Check if the database file exists"""
    if not database_path.exists():
        print(f"Database file not found at: {database_path}")
        print("Please run setup_sqlite.py first to initialize the database.")
        sys.exit(1)

def view_recent_events(limit=20):
    """View the most recent events in the database"""
    check_database()
    
    with SessionLocal() as session:
        events = session.query(UserEvent).order_by(UserEvent.timestamp.desc()).limit(limit).all()
        
        if not events:
            print("No events found in the database.")
            return
        
        table_data = []
        for event in events:
            table_data.append([
                event.id,
                event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                f"{event.user_id} ({event.username or 'Unknown'})",
                event.chat_id,
                event.event_type,
                (event.extra[:30] + '...') if event.extra and len(event.extra) > 30 else (event.extra or '')
            ])
        
        headers = ["ID", "Timestamp", "User", "Chat ID", "Event Type", "Data"]
        print(tabulate(table_data, headers=headers, tablefmt="pretty"))
        print(f"\nShowing {len(events)} most recent events")

def view_event_stats(days=7):
    """View event statistics for the past days"""
    check_database()
    
    with SessionLocal() as session:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Event counts by type
        event_counts = session.query(
            UserEvent.event_type,
            func.count(UserEvent.id).label('count')
        ).filter(UserEvent.timestamp >= cutoff_date).group_by(UserEvent.event_type).all()
        
        # User counts
        user_count = session.query(func.count(func.distinct(UserEvent.user_id))).filter(
            UserEvent.timestamp >= cutoff_date
        ).scalar()
        
        # Chat counts
        chat_count = session.query(func.count(func.distinct(UserEvent.chat_id))).filter(
            UserEvent.timestamp >= cutoff_date
        ).scalar()
        
        # Format and display stats
        print(f"\n=== Event Statistics (Past {days} Days) ===")
        print(f"Total unique users: {user_count}")
        print(f"Total unique chats: {chat_count}")
        
        print("\nEvent Type Breakdown:")
        if event_counts:
            table_data = [(event_type, count) for event_type, count in event_counts]
            print(tabulate(table_data, headers=["Event Type", "Count"], tablefmt="pretty"))
        else:
            print("No events recorded in this period.")

def main():
    parser = argparse.ArgumentParser(description="View SQLite database analytics data")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Recent events command
    recent_parser = subparsers.add_parser("recent", help="View recent events")
    recent_parser.add_argument("-l", "--limit", type=int, default=20, 
                              help="Limit number of events to show (default: 20)")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="View event statistics")
    stats_parser.add_argument("-d", "--days", type=int, default=7, 
                             help="Number of days to include in stats (default: 7)")
    
    args = parser.parse_args()
    
    if args.command == "recent":
        view_recent_events(args.limit)
    elif args.command == "stats":
        view_event_stats(args.days)
    else:
        # Default behavior: show recent events
        view_recent_events()
        print("\nFor more options, use --help")

if __name__ == "__main__":
    main()