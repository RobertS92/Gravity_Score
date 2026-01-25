"""
NIL Connectors Package
"""

from gravity.nil.connectors.base import BaseNILConnector, ConnectorError, RateLimitError, DataNotFoundError
from gravity.nil.connectors.on3_connector import On3Connector
from gravity.nil.connectors.opendorse_connector import OpendorseConnector
from gravity.nil.connectors.inflcr_connector import INFLCRConnector
from gravity.nil.connectors.teamworks_connector import TeamworksConnector
from gravity.nil.connectors.sports247_connector import Sports247Connector
from gravity.nil.connectors.rivals_connector import RivalsConnector

__all__ = [
    'BaseNILConnector',
    'ConnectorError',
    'RateLimitError',
    'DataNotFoundError',
    'On3Connector',
    'OpendorseConnector',
    'INFLCRConnector',
    'TeamworksConnector',
    'Sports247Connector',
    'RivalsConnector'
]
