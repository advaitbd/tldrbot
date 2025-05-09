# Simple in-memory user API key storage for BYOK (Bring Your Own Key) LLM support.
# This can be replaced with persistent storage (e.g., Redis, DB) if needed.

from typing import Dict, Optional

# Structure: {user_id: {provider: api_key}}
_user_api_keys: Dict[int, Dict[str, str]] = {}

def set_user_api_key(user_id: int, provider: str, api_key: str) -> None:
    """Set or update the API key for a user and provider."""
    if user_id not in _user_api_keys:
        _user_api_keys[user_id] = {}
    _user_api_keys[user_id][provider.lower()] = api_key

def get_user_api_key(user_id: int, provider: str) -> Optional[str]:
    """Retrieve the API key for a user and provider, or None if not set."""
    return _user_api_keys.get(user_id, {}).get(provider.lower())

def clear_user_api_key(user_id: int, provider: str) -> None:
    """Remove a user's API key for a provider."""
    if user_id in _user_api_keys:
        _user_api_keys[user_id].pop(provider.lower(), None)
        if not _user_api_keys[user_id]:
            _user_api_keys.pop(user_id)

def get_all_user_keys(user_id: int) -> Dict[str, str]:
    """Get all provider keys for a user."""
    return dict(_user_api_keys.get(user_id, {}))
