"""
User management utilities for freemium functionality.
Handles premium status, user creation, and Stripe customer management.
"""
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .analytics_storage import SessionLocal, User

logger = logging.getLogger(__name__)

def get_or_create_user(telegram_id: int) -> User:
    """
    Get existing user or create new user if doesn't exist.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        User object
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    with SessionLocal() as session:
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user:
                user = User(telegram_id=telegram_id)
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.info(f"Created new user: {telegram_id}")
            
            return user
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error in get_or_create_user for {telegram_id}: {e}")
            raise

def update_premium_status(
    telegram_id: int, 
    premium: bool, 
    expires_at: Optional[datetime] = None,
    stripe_customer_id: Optional[str] = None
) -> bool:
    """
    Update user's premium status.
    
    Args:
        telegram_id: Telegram user ID
        premium: Premium status
        expires_at: When premium expires (None for permanent or free users)
        stripe_customer_id: Stripe customer ID (optional)
        
    Returns:
        True if successful, False otherwise
    """
    with SessionLocal() as session:
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user:
                user = User(telegram_id=telegram_id)
                session.add(user)
            
            user.premium = premium
            user.premium_expires_at = expires_at
            
            if stripe_customer_id:
                user.stripe_customer_id = stripe_customer_id
            
            session.commit()
            logger.info(f"Updated premium status for {telegram_id}: premium={premium}, expires_at={expires_at}")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error in update_premium_status for {telegram_id}: {e}")
            return False

def is_premium(telegram_id: int) -> bool:
    """
    Check if user has active premium status.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        True if user is premium and subscription hasn't expired
    """
    with SessionLocal() as session:
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user or not user.premium:
                return False
            
            # Check if premium has expired
            if user.premium_expires_at and user.premium_expires_at <= datetime.utcnow():
                # Auto-downgrade expired premium user
                user.premium = False
                user.premium_expires_at = None
                session.commit()
                logger.info(f"Auto-downgraded expired premium user: {telegram_id}")
                return False
            
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in is_premium for {telegram_id}: {e}")
            # Fail-safe: if database error, assume not premium
            return False

def check_premium_expiry(telegram_id: int) -> Optional[datetime]:
    """
    Get premium expiry date for user.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        Expiry datetime or None if not premium or no expiry
    """
    with SessionLocal() as session:
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if user and user.premium:
                return user.premium_expires_at
            
            return None
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in check_premium_expiry for {telegram_id}: {e}")
            return None

def get_premium_users() -> list:
    """
    Get list of all premium users for monitoring.
    
    Returns:
        List of User objects with premium status
    """
    with SessionLocal() as session:
        try:
            users = session.query(User).filter_by(premium=True).all()
            return users
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_premium_users: {e}")
            return [] 