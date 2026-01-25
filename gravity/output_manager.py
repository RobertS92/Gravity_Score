"""
Output File Manager
===================
Manages automatic file naming with incrementing counters for Gravity Final Scores

Automatically saves files to:
- Gravity_Final_Scores/NFL/NFL_Final_001.csv
- Gravity_Final_Scores/NFL/NFL_Final_002.csv
- etc.
"""
import os
import re
from pathlib import Path
from typing import Optional


class OutputManager:
    """Manages output file paths with auto-incrementing counters"""
    
    def __init__(self, base_dir: str = "Gravity_Final_Scores"):
        self.base_dir = Path(base_dir)
        
        # Create base directory if it doesn't exist
        self.base_dir.mkdir(exist_ok=True)
        
        # Create sport-specific directories
        for sport in ['NFL', 'NBA', 'WNBA', 'CFB', 'NCAAB', 'WNCAAB']:
            (self.base_dir / sport).mkdir(exist_ok=True)
    
    def get_next_filename(self, sport: str, extension: str = 'csv', 
                         prefix: Optional[str] = None) -> str:
        """
        Get the next available filename with auto-incremented counter
        
        Args:
            sport: Sport name (NFL, NBA, etc.)
            extension: File extension (csv, json, xlsx)
            prefix: Optional prefix (defaults to "{sport}_Final")
            
        Returns:
            Full path to the next available file
            
        Example:
            >>> manager.get_next_filename('NFL', 'csv')
            'Gravity_Final_Scores/NFL/NFL_Final_001.csv'
        """
        sport_upper = sport.upper()
        sport_dir = self.base_dir / sport_upper
        
        # Create directory if it doesn't exist
        sport_dir.mkdir(exist_ok=True, parents=True)
        
        # Default prefix
        if prefix is None:
            prefix = f"{sport_upper}_Final"
        
        # Find existing files with this pattern
        pattern = rf"{re.escape(prefix)}_(\d+)\.{re.escape(extension)}"
        
        max_number = 0
        for file in sport_dir.glob(f"{prefix}_*.{extension}"):
            match = re.match(pattern, file.name)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)
        
        # Next number
        next_number = max_number + 1
        
        # Format with leading zeros (3 digits)
        filename = f"{prefix}_{next_number:03d}.{extension}"
        
        return str(sport_dir / filename)
    
    def get_latest_file(self, sport: str, extension: str = 'csv',
                       prefix: Optional[str] = None) -> Optional[str]:
        """
        Get the most recent file for a sport
        
        Args:
            sport: Sport name (NFL, NBA, etc.)
            extension: File extension
            prefix: Optional prefix (defaults to "{sport}_Final")
            
        Returns:
            Path to the latest file, or None if no files exist
        """
        sport_upper = sport.upper()
        sport_dir = self.base_dir / sport_upper
        
        if not sport_dir.exists():
            return None
        
        if prefix is None:
            prefix = f"{sport_upper}_Final"
        
        # Find all matching files
        pattern = rf"{re.escape(prefix)}_(\d+)\.{re.escape(extension)}"
        
        files = []
        for file in sport_dir.glob(f"{prefix}_*.{extension}"):
            match = re.match(pattern, file.name)
            if match:
                number = int(match.group(1))
                files.append((number, str(file)))
        
        if not files:
            return None
        
        # Return the file with the highest number
        files.sort(reverse=True)
        return files[0][1]
    
    def list_files(self, sport: str) -> list:
        """
        List all final score files for a sport
        
        Args:
            sport: Sport name (NFL, NBA, etc.)
            
        Returns:
            List of (number, filepath) tuples, sorted by number
        """
        sport_upper = sport.upper()
        sport_dir = self.base_dir / sport_upper
        
        if not sport_dir.exists():
            return []
        
        files = []
        pattern = rf"{sport_upper}_Final_(\d+)\.(csv|json|xlsx)"
        
        for file in sport_dir.glob(f"{sport_upper}_Final_*"):
            match = re.match(pattern, file.name)
            if match:
                number = int(match.group(1))
                files.append((number, str(file)))
        
        files.sort()
        return files
    
    def get_file_info(self, filepath: str) -> dict:
        """
        Get information about a file
        
        Returns:
            Dict with file stats (size, modified time, etc.)
        """
        path = Path(filepath)
        
        if not path.exists():
            return {}
        
        stat = path.stat()
        
        return {
            'path': str(path),
            'name': path.name,
            'size': stat.st_size,
            'size_mb': stat.st_size / (1024 * 1024),
            'modified': stat.st_mtime,
            'exists': True
        }


# Convenience function for quick use
def get_next_output_path(sport: str, extension: str = 'csv') -> str:
    """
    Quick function to get the next output path
    
    Example:
        >>> path = get_next_output_path('NFL', 'csv')
        >>> # Returns: 'Gravity_Final_Scores/NFL/NFL_Final_001.csv'
    """
    manager = OutputManager()
    return manager.get_next_filename(sport, extension)


def get_latest_output_path(sport: str, extension: str = 'csv') -> Optional[str]:
    """
    Quick function to get the latest output path
    
    Example:
        >>> path = get_latest_output_path('NFL')
        >>> # Returns: 'Gravity_Final_Scores/NFL/NFL_Final_005.csv'
    """
    manager = OutputManager()
    return manager.get_latest_file(sport, extension)

