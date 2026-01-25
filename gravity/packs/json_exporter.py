"""
JSON Exporter
Exports pack data as deterministic JSON with schema version
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class JSONExporter:
    """
    Exports pack data to JSON with full audit trail
    """
    
    SCHEMA_VERSION = "1.0"
    
    def export_to_json(
        self,
        pack_data: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        Export pack data to JSON file
        
        Args:
            pack_data: Complete pack data dict
            output_path: Output file path
        
        Returns:
            Path to created file
        """
        logger.info(f"Exporting pack to JSON: {output_path}")
        
        # Add schema metadata
        json_output = {
            'schema_version': self.SCHEMA_VERSION,
            'exported_at': datetime.utcnow().isoformat(),
            'data': pack_data
        }
        
        # Create output directory if needed
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON (deterministic sorting)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, sort_keys=True, default=str)
        
        logger.info(f"JSON exported successfully: {output_path}")
        
        return str(output_file.absolute())


def export_pack_json(pack_data: Dict[str, Any], output_path: str) -> str:
    """
    Export pack to JSON
    
    Args:
        pack_data: Pack data dict
        output_path: Output file path
    
    Returns:
        Path to created file
    """
    exporter = JSONExporter()
    return exporter.export_to_json(pack_data, output_path)
