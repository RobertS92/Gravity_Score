"""
NIL Data Pipeline Package
"""

from gravity.nil.connector_orchestrator import ConnectorOrchestrator, run_nil_collection
from gravity.nil.connectors import (
    On3Connector,
    OpendorseConnector,
    INFLCRConnector,
    TeamworksConnector,
    Sports247Connector,
    RivalsConnector
)

__all__ = [
    'ConnectorOrchestrator',
    'run_nil_collection',
    'On3Connector',
    'OpendorseConnector',
    'INFLCRConnector',
    'TeamworksConnector',
    'Sports247Connector',
    'RivalsConnector'
]
