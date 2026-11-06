"""Hosting edition metadata; accounts are owned exclusively by the core."""
import os

def current_edition():
    value = os.getenv('RIGHAVEN_EDITION', 'community').lower()
    if value not in ('community', 'cloud'):
        raise ValueError('RIGHAVEN_EDITION must be community or cloud')
    return value
