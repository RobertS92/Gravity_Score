"""Data validation and cleaning utilities using Pydantic."""

import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, validator, ValidationError as PydanticValidationError

from .exceptions import ValidationError

logger = logging.getLogger("nfl_gravity")


class PlayerData(BaseModel):
    """Pydantic model for NFL player data validation."""
    
    # Basic Info
    name: str = Field(..., min_length=1, max_length=100)
    team: str = Field(..., min_length=2, max_length=50)
    position: str = Field(..., min_length=1, max_length=10)
    jersey_number: Optional[int] = Field(None, ge=0, le=99)
    
    # Physical Stats
    height: Optional[str] = Field(None, pattern=r'^\d+[\'\-"]\d+["]?$|^\d+\.\d+$|^\d+$')
    weight: Optional[int] = Field(None, ge=100, le=500)
    age: Optional[int] = Field(None, ge=18, le=50)
    birth_date: Optional[date] = None
    
    # Career Info
    college: Optional[str] = Field(None, max_length=100)
    draft_year: Optional[int] = Field(None, ge=1936, le=datetime.now().year + 1)
    draft_round: Optional[int] = Field(None, ge=1, le=7)
    draft_pick: Optional[int] = Field(None, ge=1, le=300)
    years_pro: Optional[int] = Field(None, ge=0, le=30)
    
    # Performance Stats (season)
    games_played: Optional[int] = Field(None, ge=0, le=20)
    games_started: Optional[int] = Field(None, ge=0, le=20)
    
    # Social Media
    twitter_handle: Optional[str] = Field(None, max_length=50)
    instagram_handle: Optional[str] = Field(None, max_length=50)
    twitter_followers: Optional[int] = Field(None, ge=0)
    instagram_followers: Optional[int] = Field(None, ge=0)
    
    # Wikipedia Data
    wikipedia_url: Optional[str] = None
    career_highlights: Optional[List[str]] = None
    awards: Optional[List[str]] = None
    
    # Metadata
    data_source: Optional[str] = None
    scraped_at: Optional[datetime] = None
    
    @validator('name')
    def validate_name(cls, v):
        """Validate player name format."""
        if not v or len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        # Remove extra whitespace
        return ' '.join(v.strip().split())
    
    @validator('team')
    def validate_team(cls, v):
        """Validate team name."""
        valid_teams = [
            '49ers', 'bears', 'bengals', 'bills', 'broncos', 'browns', 'buccaneers',
            'cardinals', 'chargers', 'chiefs', 'colts', 'commanders', 'cowboys',
            'dolphins', 'eagles', 'falcons', 'giants', 'jaguars', 'jets', 'lions',
            'packers', 'panthers', 'patriots', 'raiders', 'rams', 'ravens',
            'saints', 'seahawks', 'steelers', 'texans', 'titans', 'vikings'
        ]
        if v.lower() not in valid_teams:
            logger.warning(f"Unknown team: {v}")
        return v.lower()
    
    @validator('position')
    def validate_position(cls, v):
        """Validate position abbreviation."""
        valid_positions = [
            'QB', 'RB', 'FB', 'WR', 'TE', 'LT', 'LG', 'C', 'RG', 'RT', 'G', 'T', 'OL',
            'DE', 'DT', 'NT', 'OLB', 'ILB', 'MLB', 'CB', 'S', 'FS', 'SS', 'SAF', 'DB',
            'K', 'P', 'LS', 'KR', 'PR', 'ST'
        ]
        if v.upper() not in valid_positions:
            logger.warning(f"Unknown position: {v}")
        return v.upper()
    
    @validator('twitter_handle', 'instagram_handle')
    def validate_social_handle(cls, v):
        """Validate social media handle format."""
        if v:
            # Remove @ symbol if present
            v = v.lstrip('@')
            # Check format
            if not re.match(r'^[a-zA-Z0-9_]+$', v):
                raise ValueError('Invalid social media handle format')
        return v
    
    @validator('wikipedia_url')
    def validate_wikipedia_url(cls, v):
        """Validate Wikipedia URL format."""
        if v and not v.startswith('https://en.wikipedia.org/wiki/'):
            raise ValueError('Invalid Wikipedia URL format')
        return v


class TeamData(BaseModel):
    """Pydantic model for NFL team data validation."""
    
    name: str = Field(..., min_length=1, max_length=50)
    city: str = Field(..., min_length=1, max_length=50)
    division: str = Field(..., min_length=1, max_length=20)
    conference: str = Field(..., pattern=r'^(AFC|NFC)$')
    founded: Optional[int] = Field(None, ge=1920, le=datetime.now().year)
    stadium: Optional[str] = Field(None, max_length=100)
    head_coach: Optional[str] = Field(None, max_length=100)
    
    # Team Stats
    wins: Optional[int] = Field(None, ge=0, le=17)
    losses: Optional[int] = Field(None, ge=0, le=17)
    ties: Optional[int] = Field(None, ge=0, le=17)
    
    # Social Media
    twitter_handle: Optional[str] = Field(None, max_length=50)
    instagram_handle: Optional[str] = Field(None, max_length=50)
    official_website: Optional[str] = None
    
    # Metadata
    data_source: Optional[str] = None
    scraped_at: Optional[datetime] = None
    
    @validator('division')
    def validate_division(cls, v):
        """Validate NFL division."""
        valid_divisions = [
            'AFC North', 'AFC South', 'AFC East', 'AFC West',
            'NFC North', 'NFC South', 'NFC East', 'NFC West'
        ]
        if v not in valid_divisions:
            logger.warning(f"Unknown division: {v}")
        return v


class PlayerDataValidator:
    """Validator class for player data with cleaning and validation."""
    
    def __init__(self):
        self.logger = logging.getLogger("nfl_gravity.validators")
        self.discarded_fields = []
    
    def validate_and_clean(self, raw_data: Dict[str, Any]) -> Optional[PlayerData]:
        """
        Validate and clean raw player data.
        
        Args:
            raw_data: Raw player data dictionary
            
        Returns:
            Validated PlayerData instance or None if validation fails
        """
        try:
            # Clean and prepare data
            cleaned_data = self._clean_raw_data(raw_data)
            
            # Validate using Pydantic model
            player_data = PlayerData(**cleaned_data)
            
            self.logger.info(f"Successfully validated player: {player_data.name}")
            return player_data
            
        except PydanticValidationError as e:
            self.logger.error(f"Validation failed for player data: {e}")
            self._log_discarded_fields(raw_data, e.errors())
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during validation: {e}")
            return None
    
    def _clean_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean raw data before validation."""
        cleaned = {}
        
        for key, value in raw_data.items():
            if value is None or value == '':
                continue
                
            # Convert string values
            if isinstance(value, str):
                value = value.strip()
                if value.lower() in ['n/a', 'unknown', 'null', 'none', '--']:
                    continue
            
            # Handle specific field conversions
            if key in ['weight', 'age', 'jersey_number', 'draft_year', 'draft_round', 'draft_pick']:
                try:
                    cleaned[key] = int(value)
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not convert {key}={value} to int")
                    continue
            elif key in ['twitter_followers', 'instagram_followers']:
                try:
                    # Handle formatted numbers like "1.2K"
                    if isinstance(value, str):
                        value = self._convert_social_metric(value)
                    cleaned[key] = int(value)
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not convert {key}={value} to int")
                    continue
            elif key == 'birth_date' and isinstance(value, str):
                try:
                    cleaned[key] = datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    self.logger.warning(f"Could not parse birth_date: {value}")
                    continue
            else:
                cleaned[key] = value
        
        return cleaned
    
    def _convert_social_metric(self, value: str) -> int:
        """Convert social media metric string to number."""
        value = value.replace(',', '').strip()
        if 'K' in value:
            return int(float(value.replace('K', '')) * 1000)
        elif 'M' in value:
            return int(float(value.replace('M', '')) * 1000000)
        else:
            return int(float(value))
    
    def _log_discarded_fields(self, raw_data: Dict[str, Any], errors: List[Dict]) -> None:
        """Log discarded fields with reasons."""
        for error in errors:
            field = '.'.join(str(loc) for loc in error['loc'])
            reason = error['msg']
            value = raw_data.get(field, 'N/A')
            
            self.discarded_fields.append({
                'field': field,
                'value': value,
                'reason': reason
            })
            
            self.logger.warning(f"Discarded field {field}={value}: {reason}")


class TeamDataValidator:
    """Validator class for team data with cleaning and validation."""
    
    def __init__(self):
        self.logger = logging.getLogger("nfl_gravity.validators")
        self.discarded_fields = []
    
    def validate_and_clean(self, raw_data: Dict[str, Any]) -> Optional[TeamData]:
        """
        Validate and clean raw team data.
        
        Args:
            raw_data: Raw team data dictionary
            
        Returns:
            Validated TeamData instance or None if validation fails
        """
        try:
            # Clean and prepare data
            cleaned_data = self._clean_raw_data(raw_data)
            
            # Validate using Pydantic model
            team_data = TeamData(**cleaned_data)
            
            self.logger.info(f"Successfully validated team: {team_data.name}")
            return team_data
            
        except PydanticValidationError as e:
            self.logger.error(f"Validation failed for team data: {e}")
            self._log_discarded_fields(raw_data, e.errors())
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during validation: {e}")
            return None
    
    def _clean_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean raw data before validation."""
        cleaned = {}
        
        for key, value in raw_data.items():
            if value is None or value == '':
                continue
                
            # Convert string values
            if isinstance(value, str):
                value = value.strip()
                if value.lower() in ['n/a', 'unknown', 'null', 'none', '--']:
                    continue
            
            # Handle specific field conversions
            if key in ['founded', 'wins', 'losses', 'ties']:
                try:
                    cleaned[key] = int(value)
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not convert {key}={value} to int")
                    continue
            else:
                cleaned[key] = value
        
        return cleaned
    
    def _log_discarded_fields(self, raw_data: Dict[str, Any], errors: List[Dict]) -> None:
        """Log discarded fields with reasons."""
        for error in errors:
            field = '.'.join(str(loc) for loc in error['loc'])
            reason = error['msg']
            value = raw_data.get(field, 'N/A')
            
            self.discarded_fields.append({
                'field': field,
                'value': value,
                'reason': reason
            })
            
            self.logger.warning(f"Discarded field {field}={value}: {reason}")
