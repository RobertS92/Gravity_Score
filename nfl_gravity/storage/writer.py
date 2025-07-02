"""Data storage and export functionality."""

import os
import json
import logging
import gzip
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..core.config import Config
from ..core.exceptions import StorageError
from ..core.utils import sanitize_filename, create_output_directory


class DataWriter:
    """Handles data storage in various formats with schema validation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.storage")
        
        # Ensure output directory exists
        os.makedirs(self.config.data_dir, exist_ok=True)
    
    def write_data(self, players: List[Dict[str, Any]], teams: List[Dict[str, Any]], 
                   output_dir: str) -> Dict[str, List[str]]:
        """
        Write player and team data to various formats.
        
        Args:
            players: List of player dictionaries
            teams: List of team dictionaries
            output_dir: Directory to write files to
            
        Returns:
            Dictionary mapping format names to lists of created file paths
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            output_files = {}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Write player data
            if players:
                player_files = self._write_player_data(players, output_dir, timestamp)
                output_files['players'] = player_files
            
            # Write team data
            if teams:
                team_files = self._write_team_data(teams, output_dir, timestamp)
                output_files['teams'] = team_files
            
            # Write schema information
            schema_file = self._write_schema(players, teams, output_dir, timestamp)
            output_files['schema'] = [schema_file]
            
            # Write metadata
            metadata_file = self._write_metadata(players, teams, output_dir, timestamp)
            output_files['metadata'] = [metadata_file]
            
            self.logger.info(f"Successfully wrote data to {output_dir}")
            return output_files
            
        except Exception as e:
            self.logger.error(f"Error writing data: {e}")
            raise StorageError(f"Failed to write data: {e}")
    
    def _write_player_data(self, players: List[Dict[str, Any]], 
                          output_dir: str, timestamp: str) -> List[str]:
        """Write player data in configured formats."""
        files_created = []
        
        try:
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(players)
            
            # Clean the DataFrame
            df = self._clean_dataframe(df)
            
            # Write in requested formats
            if 'parquet' in self.config.output_formats:
                parquet_file = os.path.join(output_dir, f"players_{timestamp}.parquet")
                self._write_parquet(df, parquet_file)
                files_created.append(parquet_file)
            
            if 'csv' in self.config.output_formats:
                csv_file = os.path.join(output_dir, f"players_{timestamp}.csv.gz")
                self._write_compressed_csv(df, csv_file)
                files_created.append(csv_file)
            
            # Also write uncompressed CSV for easy inspection
            csv_plain_file = os.path.join(output_dir, f"players_{timestamp}.csv")
            df.to_csv(csv_plain_file, index=False, encoding='utf-8')
            files_created.append(csv_plain_file)
            
            self.logger.info(f"Wrote {len(players)} player records to {len(files_created)} files")
            return files_created
            
        except Exception as e:
            self.logger.error(f"Error writing player data: {e}")
            raise StorageError(f"Failed to write player data: {e}")
    
    def _write_team_data(self, teams: List[Dict[str, Any]], 
                        output_dir: str, timestamp: str) -> List[str]:
        """Write team data in configured formats."""
        files_created = []
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(teams)
            
            # Clean the DataFrame
            df = self._clean_dataframe(df)
            
            # Write in requested formats
            if 'parquet' in self.config.output_formats:
                parquet_file = os.path.join(output_dir, f"teams_{timestamp}.parquet")
                self._write_parquet(df, parquet_file)
                files_created.append(parquet_file)
            
            if 'csv' in self.config.output_formats:
                csv_file = os.path.join(output_dir, f"teams_{timestamp}.csv.gz")
                self._write_compressed_csv(df, csv_file)
                files_created.append(csv_file)
            
            # Also write uncompressed CSV
            csv_plain_file = os.path.join(output_dir, f"teams_{timestamp}.csv")
            df.to_csv(csv_plain_file, index=False, encoding='utf-8')
            files_created.append(csv_plain_file)
            
            self.logger.info(f"Wrote {len(teams)} team records to {len(files_created)} files")
            return files_created
            
        except Exception as e:
            self.logger.error(f"Error writing team data: {e}")
            raise StorageError(f"Failed to write team data: {e}")
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare DataFrame for storage."""
        # Convert datetime objects to strings for better compatibility
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if column contains datetime objects
                sample_value = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if isinstance(sample_value, datetime):
                    df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Handle list columns (convert to JSON strings)
        for col in df.columns:
            if df[col].dtype == 'object':
                sample_value = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if isinstance(sample_value, list):
                    df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, list) else x)
        
        # Replace NaN values with None for better JSON compatibility
        df = df.where(pd.notnull(df), None)
        
        return df
    
    def _write_parquet(self, df: pd.DataFrame, filepath: str):
        """Write DataFrame to Parquet format."""
        try:
            # Convert pandas DataFrame to PyArrow Table for better type control
            table = pa.Table.from_pandas(df)
            
            # Write with compression
            pq.write_table(table, filepath, compression='snappy')
            
            self.logger.debug(f"Wrote Parquet file: {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error writing Parquet file {filepath}: {e}")
            raise
    
    def _write_compressed_csv(self, df: pd.DataFrame, filepath: str):
        """Write DataFrame to compressed CSV format."""
        try:
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                df.to_csv(f, index=False)
            
            self.logger.debug(f"Wrote compressed CSV file: {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error writing compressed CSV file {filepath}: {e}")
            raise
    
    def _write_schema(self, players: List[Dict[str, Any]], teams: List[Dict[str, Any]], 
                     output_dir: str, timestamp: str) -> str:
        """Write schema information for the data."""
        try:
            schema_info = {
                'timestamp': timestamp,
                'generated_at': datetime.now().isoformat(),
                'player_schema': self._extract_schema(players) if players else {},
                'team_schema': self._extract_schema(teams) if teams else {},
                'record_counts': {
                    'players': len(players),
                    'teams': len(teams)
                }
            }
            
            schema_file = os.path.join(output_dir, f"schema_{timestamp}.json")
            
            with open(schema_file, 'w', encoding='utf-8') as f:
                json.dump(schema_info, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Wrote schema file: {schema_file}")
            return schema_file
            
        except Exception as e:
            self.logger.error(f"Error writing schema file: {e}")
            raise
    
    def _extract_schema(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract schema information from data."""
        if not data:
            return {}
        
        schema = {}
        
        # Get all possible fields from all records
        all_fields = set()
        for record in data:
            all_fields.update(record.keys())
        
        # Analyze each field
        for field in all_fields:
            field_info = {
                'type': 'unknown',
                'nullable': False,
                'examples': [],
                'count': 0
            }
            
            values = []
            null_count = 0
            
            for record in data:
                if field in record:
                    value = record[field]
                    if value is None:
                        null_count += 1
                    else:
                        values.append(value)
                        field_info['count'] += 1
                        
                        # Add to examples (limit to 3)
                        if len(field_info['examples']) < 3:
                            field_info['examples'].append(value)
            
            # Determine type from values
            if values:
                first_value = values[0]
                if isinstance(first_value, bool):
                    field_info['type'] = 'boolean'
                elif isinstance(first_value, int):
                    field_info['type'] = 'integer'
                elif isinstance(first_value, float):
                    field_info['type'] = 'float'
                elif isinstance(first_value, str):
                    field_info['type'] = 'string'
                elif isinstance(first_value, list):
                    field_info['type'] = 'array'
                elif isinstance(first_value, dict):
                    field_info['type'] = 'object'
                else:
                    field_info['type'] = str(type(first_value).__name__)
            
            field_info['nullable'] = null_count > 0
            field_info['null_count'] = null_count
            field_info['total_records'] = len(data)
            
            schema[field] = field_info
        
        return schema
    
    def _write_metadata(self, players: List[Dict[str, Any]], teams: List[Dict[str, Any]], 
                       output_dir: str, timestamp: str) -> str:
        """Write metadata about the extraction run."""
        try:
            metadata = {
                'extraction_timestamp': timestamp,
                'generated_at': datetime.now().isoformat(),
                'nfl_gravity_version': '1.0.0',
                'record_counts': {
                    'players': len(players),
                    'teams': len(teams),
                    'total_records': len(players) + len(teams)
                },
                'data_sources': self._collect_data_sources(players, teams),
                'team_coverage': self._analyze_team_coverage(players),
                'position_distribution': self._analyze_position_distribution(players),
                'extraction_summary': {
                    'teams_with_players': len(set(p.get('team') for p in players if p.get('team'))),
                    'players_with_social_media': len([p for p in players if p.get('twitter_handle') or p.get('instagram_handle')]),
                    'players_with_wikipedia': len([p for p in players if p.get('wikipedia_url')]),
                    'avg_fields_per_player': sum(len(p.keys()) for p in players) / len(players) if players else 0
                }
            }
            
            metadata_file = os.path.join(output_dir, f"metadata_{timestamp}.json")
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.debug(f"Wrote metadata file: {metadata_file}")
            return metadata_file
            
        except Exception as e:
            self.logger.error(f"Error writing metadata file: {e}")
            raise
    
    def _collect_data_sources(self, players: List[Dict[str, Any]], 
                             teams: List[Dict[str, Any]]) -> Dict[str, int]:
        """Collect information about data sources used."""
        sources = {}
        
        all_records = players + teams
        
        for record in all_records:
            source = record.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        return sources
    
    def _analyze_team_coverage(self, players: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze how many players were found for each team."""
        team_counts = {}
        
        for player in players:
            team = player.get('team', 'unknown')
            team_counts[team] = team_counts.get(team, 0) + 1
        
        return team_counts
    
    def _analyze_position_distribution(self, players: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze distribution of player positions."""
        position_counts = {}
        
        for player in players:
            position = player.get('position', 'unknown')
            position_counts[position] = position_counts.get(position, 0) + 1
        
        return position_counts
    
    def read_latest_data(self, data_type: str = 'players') -> Optional[pd.DataFrame]:
        """
        Read the most recent data file.
        
        Args:
            data_type: Type of data to read ('players' or 'teams')
            
        Returns:
            DataFrame with the data or None if not found
        """
        try:
            # Find the most recent directory
            data_dirs = [d for d in os.listdir(self.config.data_dir) 
                        if os.path.isdir(os.path.join(self.config.data_dir, d))]
            
            if not data_dirs:
                return None
            
            latest_dir = max(data_dirs)
            latest_path = os.path.join(self.config.data_dir, latest_dir)
            
            # Find the most recent file of the requested type
            files = [f for f in os.listdir(latest_path) 
                    if f.startswith(data_type) and f.endswith('.parquet')]
            
            if not files:
                # Try CSV if no parquet
                files = [f for f in os.listdir(latest_path) 
                        if f.startswith(data_type) and f.endswith('.csv')]
            
            if not files:
                return None
            
            latest_file = max(files)
            file_path = os.path.join(latest_path, latest_file)
            
            # Read the file
            if latest_file.endswith('.parquet'):
                return pd.read_parquet(file_path)
            elif latest_file.endswith('.csv'):
                return pd.read_csv(file_path)
            
        except Exception as e:
            self.logger.error(f"Error reading latest {data_type} data: {e}")
            return None
    
    def get_data_info(self) -> Dict[str, Any]:
        """Get information about stored data."""
        try:
            info = {
                'data_directory': self.config.data_dir,
                'available_dates': [],
                'latest_extraction': None,
                'total_files': 0
            }
            
            if not os.path.exists(self.config.data_dir):
                return info
            
            # Get all data directories (dates)
            data_dirs = []
            for item in os.listdir(self.config.data_dir):
                item_path = os.path.join(self.config.data_dir, item)
                if os.path.isdir(item_path):
                    data_dirs.append(item)
            
            info['available_dates'] = sorted(data_dirs)
            
            if data_dirs:
                latest_dir = max(data_dirs)
                info['latest_extraction'] = latest_dir
                
                # Count files in latest directory
                latest_path = os.path.join(self.config.data_dir, latest_dir)
                files = os.listdir(latest_path)
                info['total_files'] = len(files)
                info['latest_files'] = files
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting data info: {e}")
            return {'error': str(e)}
