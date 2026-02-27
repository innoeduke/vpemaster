"""
Backward-compatible wrapper — all logic now lives in services/blockchain_service.py.
"""
from .services.blockchain_service import record_level as record_level_completion_on_chain  # noqa: F401
from .services.blockchain_service import verify_level as verify_level_on_chain  # noqa: F401
