"""
Database Versioning System for NFL Player Data
Tracks historical changes and always shows latest data in main view
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

logger = logging.getLogger(__name__)

Base = declarative_base()

class PlayerData(Base):
    """Current player data - always shows latest version"""
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    team = Column(String(50), nullable=False)
    position = Column(String(10))
    age = Column(Integer)
    jersey_number = Column(Integer)
    height = Column(String(10))
    weight = Column(String(10))
    experience = Column(Integer)
    
    # Social Media
    twitter_handle = Column(String(255))
    twitter_followers = Column(Integer)
    twitter_following = Column(Integer)
    twitter_verified = Column(Boolean)
    twitter_url = Column(String(500))
    
    instagram_handle = Column(String(255))
    instagram_followers = Column(Integer)
    instagram_following = Column(Integer)
    instagram_verified = Column(Boolean)
    instagram_url = Column(String(500))
    
    tiktok_handle = Column(String(255))
    tiktok_followers = Column(Integer)
    tiktok_following = Column(Integer)
    tiktok_url = Column(String(500))
    
    youtube_handle = Column(String(255))
    youtube_subscribers = Column(Integer)
    youtube_verified = Column(Boolean)
    youtube_url = Column(String(500))
    
    # Biographical
    birth_date = Column(String(50))
    birth_place = Column(String(255))
    college = Column(String(255))
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_pick = Column(Integer)
    draft_team = Column(String(50))
    hometown = Column(String(255))
    high_school = Column(String(255))
    wikipedia_url = Column(String(500))
    wikipedia_summary = Column(Text)
    
    # Career Stats
    career_games = Column(Integer)
    career_starts = Column(Integer)
    career_touchdowns = Column(Integer)
    career_yards = Column(Integer)
    career_receptions = Column(Integer)
    career_interceptions = Column(Integer)
    career_sacks = Column(Float)
    career_tackles = Column(Integer)
    pro_bowls = Column(String(255))
    all_pro = Column(String(255))
    rookie_year = Column(Integer)
    
    # Contract & Financial
    current_salary = Column(String(50))
    contract_value = Column(String(50))
    contract_years = Column(Integer)
    guaranteed_money = Column(String(50))
    signing_bonus = Column(String(50))
    career_earnings = Column(String(50))
    cap_hit = Column(String(50))
    dead_money = Column(String(50))
    spotrac_url = Column(String(500))
    
    # Awards & Achievements
    awards = Column(Text)
    honors = Column(Text)
    records = Column(Text)
    career_highlights = Column(Text)
    championships = Column(Text)
    hall_of_fame = Column(Boolean)
    
    # Metadata
    data_sources = Column(Text)
    data_quality_score = Column(Float)
    collection_timestamp = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, default=1)

class PlayerDataHistory(Base):
    """Historical versions of player data"""
    __tablename__ = 'player_history'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, nullable=False)  # References PlayerData.id
    name = Column(String(255), nullable=False)
    team = Column(String(50), nullable=False)
    
    # Store all previous data as JSON
    previous_data = Column(JSON)
    
    # Change tracking
    changed_fields = Column(Text)  # JSON list of changed field names
    change_type = Column(String(50))  # 'update', 'new', 'social_media_update', etc.
    
    # Timestamps
    version_date = Column(DateTime, default=datetime.utcnow)
    previous_version = Column(Integer)
    new_version = Column(Integer)

class DatabaseVersioning:
    """Manages database versioning and historical tracking"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/nfl_gravity')
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(self.engine)
        logger.info("Database versioning system initialized")
    
    def get_or_create_player(self, name: str, team: str) -> PlayerData:
        """Get existing player or create new one"""
        session = self.SessionLocal()
        try:
            # Look for existing player
            player = session.query(PlayerData).filter_by(name=name, team=team).first()
            
            if not player:
                # Create new player
                player = PlayerData(name=name, team=team, version=1)
                session.add(player)
                session.commit()
                logger.info(f"Created new player record: {name} ({team})")
            
            return player
        finally:
            session.close()
    
    def update_player_data(self, player_data: Dict) -> Dict:
        """Update player data with versioning"""
        session = self.SessionLocal()
        try:
            name = player_data['name']
            team = player_data['team']
            
            # Get or create player
            player = session.query(PlayerData).filter_by(name=name, team=team).first()
            
            if not player:
                # New player
                player = self._create_new_player(session, player_data)
                result = {
                    'action': 'created',
                    'player_id': player.id,
                    'version': 1,
                    'changes': list(player_data.keys())
                }
            else:
                # Update existing player
                result = self._update_existing_player(session, player, player_data)
            
            session.commit()
            return result
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating player data: {e}")
            raise
        finally:
            session.close()
    
    def _create_new_player(self, session, player_data: Dict) -> PlayerData:
        """Create new player record"""
        player = PlayerData(
            name=player_data['name'],
            team=player_data['team'],
            version=1
        )
        
        # Set all fields
        self._set_player_fields(player, player_data)
        
        session.add(player)
        session.flush()  # Get the ID
        
        return player
    
    def _update_existing_player(self, session, player: PlayerData, new_data: Dict) -> Dict:
        """Update existing player with versioning"""
        # Store current data before update
        current_data = self._player_to_dict(player)
        
        # Find changed fields
        changed_fields = []
        for field, new_value in new_data.items():
            if hasattr(player, field):
                current_value = getattr(player, field)
                if current_value != new_value and new_value is not None:
                    changed_fields.append(field)
        
        if not changed_fields:
            return {
                'action': 'no_changes',
                'player_id': player.id,
                'version': player.version
            }
        
        # Create history record
        history = PlayerDataHistory(
            player_id=player.id,
            name=player.name,
            team=player.team,
            previous_data=current_data,
            changed_fields=json.dumps(changed_fields),
            change_type='update',
            previous_version=player.version,
            new_version=player.version + 1
        )
        
        session.add(history)
        
        # Update player with new data
        self._set_player_fields(player, new_data)
        player.version += 1
        player.last_updated = datetime.utcnow()
        
        return {
            'action': 'updated',
            'player_id': player.id,
            'version': player.version,
            'changes': changed_fields,
            'previous_version': player.version - 1
        }
    
    def _set_player_fields(self, player: PlayerData, data: Dict):
        """Set player fields from data dict"""
        for field, value in data.items():
            if hasattr(player, field) and value is not None:
                setattr(player, field, value)
    
    def _player_to_dict(self, player: PlayerData) -> Dict:
        """Convert player object to dictionary"""
        result = {}
        for column in player.__table__.columns:
            result[column.name] = getattr(player, column.name)
        return result
    
    def get_player_history(self, player_id: int) -> List[Dict]:
        """Get historical versions of a player"""
        session = self.SessionLocal()
        try:
            history = session.query(PlayerDataHistory).filter_by(player_id=player_id).order_by(PlayerDataHistory.version_date.desc()).all()
            
            return [{
                'version_date': h.version_date.isoformat(),
                'previous_version': h.previous_version,
                'new_version': h.new_version,
                'changed_fields': json.loads(h.changed_fields) if h.changed_fields else [],
                'change_type': h.change_type,
                'previous_data': h.previous_data
            } for h in history]
            
        finally:
            session.close()
    
    def get_all_players(self) -> List[Dict]:
        """Get all current players (latest versions only)"""
        session = self.SessionLocal()
        try:
            players = session.query(PlayerData).all()
            return [self._player_to_dict(player) for player in players]
        finally:
            session.close()
    
    def get_player_by_name(self, name: str, team: str) -> Optional[Dict]:
        """Get current player data by name and team"""
        session = self.SessionLocal()
        try:
            player = session.query(PlayerData).filter_by(name=name, team=team).first()
            return self._player_to_dict(player) if player else None
        finally:
            session.close()

def calculate_age_from_birth_date(birth_date: str) -> Optional[int]:
    """Calculate age from birth date string"""
    if not birth_date:
        return None
    
    try:
        # Try different date formats
        formats = ['%Y-%m-%d', '%B %d, %Y', '%m/%d/%Y', '%d/%m/%Y']
        
        for fmt in formats:
            try:
                birth_dt = datetime.strptime(birth_date, fmt)
                today = datetime.now()
                age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                return age
            except ValueError:
                continue
                
        # If no format works, try extracting year
        import re
        year_match = re.search(r'(\d{4})', birth_date)
        if year_match:
            birth_year = int(year_match.group(1))
            current_year = datetime.now().year
            return current_year - birth_year
            
    except Exception as e:
        logger.debug(f"Error calculating age from '{birth_date}': {e}")
    
    return None