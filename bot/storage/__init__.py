"""Storage modules for TLDRBot."""
from storage.memory import MemoryStorage
from storage.analytics import log_event, create_tables

__all__ = ['MemoryStorage', 'log_event', 'create_tables']

