"""
Simple database integration for NFL Gravity without external dependencies.
Uses SQL queries to interact with the existing PostgreSQL database.
"""

import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def execute_sql_query(query, params=None):
    """Execute SQL query using the existing database connection."""
    try:
        from app import db
        
        if params:
            result = db.session.execute(query, params)
        else:
            result = db.session.execute(query)
        
        db.session.commit()
        return result
    except Exception as e:
        logger.error(f"SQL query error: {e}")
        db.session.rollback()
        raise

def create_players_table():
    """Create players table if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS players (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        team VARCHAR(100),
        position VARCHAR(20),
        jersey_number VARCHAR(10),
        age INTEGER,
        height VARCHAR(20),
        weight INTEGER,
        college VARCHAR(200),
        experience VARCHAR(50),
        status VARCHAR(50) DEFAULT 'Active',
        data_source VARCHAR(100) DEFAULT 'NFL.com',
        twitter_handle VARCHAR(100),
        instagram_handle VARCHAR(100),
        twitter_followers INTEGER,
        instagram_followers INTEGER,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, team)
    );
    """
    
    try:
        execute_sql_query(create_table_sql)
        logger.info("Players table created/verified successfully")
    except Exception as e:
        logger.error(f"Error creating players table: {e}")
        raise

def save_players_to_db(players_data):
    """Save players data to the database."""
    try:
        # First ensure the table exists
        create_players_table()
        
        insert_sql = """
        INSERT INTO players (
            name, team, position, jersey_number, age, height, weight, 
            college, experience, status, data_source, scraped_at
        ) VALUES (
            %(name)s, %(team)s, %(position)s, %(jersey_number)s, %(age)s, 
            %(height)s, %(weight)s, %(college)s, %(experience)s, %(status)s, 
            %(data_source)s, %(scraped_at)s
        )
        ON CONFLICT (name, team) DO UPDATE SET
            position = EXCLUDED.position,
            jersey_number = EXCLUDED.jersey_number,
            age = EXCLUDED.age,
            height = EXCLUDED.height,
            weight = EXCLUDED.weight,
            college = EXCLUDED.college,
            experience = EXCLUDED.experience,
            status = EXCLUDED.status,
            data_source = EXCLUDED.data_source,
            scraped_at = EXCLUDED.scraped_at,
            updated_at = CURRENT_TIMESTAMP
        """
        
        for player in players_data:
            player_params = {
                'name': player.get('name'),
                'team': player.get('team'),
                'position': player.get('position'),
                'jersey_number': player.get('jersey_number'),
                'age': player.get('age'),
                'height': player.get('height'),
                'weight': player.get('weight'),
                'college': player.get('college'),
                'experience': player.get('experience'),
                'status': player.get('status', 'Active'),
                'data_source': player.get('data_source', 'NFL.com'),
                'scraped_at': datetime.now()
            }
            
            execute_sql_query(insert_sql, player_params)
        
        logger.info(f"Successfully saved {len(players_data)} players to database")
        
    except Exception as e:
        logger.error(f"Error saving players to database: {e}")
        raise

def get_all_players_from_db():
    """Get all players from the database."""
    try:
        # First ensure the table exists
        create_players_table()
        
        query = """
        SELECT 
            name, team, position, jersey_number, age, height, weight,
            college, experience, status, data_source, 
            twitter_handle, instagram_handle, twitter_followers, instagram_followers,
            scraped_at, updated_at
        FROM players
        ORDER BY team, position, name
        """
        
        result = execute_sql_query(query)
        players = result.fetchall()
        
        # Convert to list of dictionaries
        player_list = []
        for player in players:
            player_dict = {
                'name': player[0],
                'team': player[1],
                'position': player[2],
                'jersey_number': player[3],
                'age': player[4],
                'height': player[5],
                'weight': player[6],
                'college': player[7],
                'experience': player[8],
                'status': player[9],
                'data_source': player[10],
                'twitter_handle': player[11],
                'instagram_handle': player[12],
                'twitter_followers': player[13],
                'instagram_followers': player[14],
                'scraped_at': player[15].isoformat() if player[15] else None,
                'updated_at': player[16].isoformat() if player[16] else None
            }
            player_list.append(player_dict)
        
        logger.info(f"Retrieved {len(player_list)} players from database")
        return player_list
        
    except Exception as e:
        logger.error(f"Error retrieving players from database: {e}")
        return []

def get_players_by_team(team_name):
    """Get players for a specific team."""
    try:
        query = """
        SELECT * FROM players 
        WHERE team = %(team)s
        ORDER BY position, jersey_number
        """
        
        result = execute_sql_query(query, {'team': team_name})
        players = result.fetchall()
        
        # Convert to list of dictionaries (simplified)
        player_list = []
        for player in players:
            player_dict = {
                'name': player[1],
                'team': player[2],
                'position': player[3],
                'jersey_number': player[4],
                'age': player[5],
                'height': player[6],
                'weight': player[7],
                'college': player[8],
                'experience': player[9],
                'status': player[10],
                'scraped_at': player[16].isoformat() if player[16] else None,
                'updated_at': player[17].isoformat() if player[17] else None
            }
            player_list.append(player_dict)
        
        return player_list
        
    except Exception as e:
        logger.error(f"Error retrieving players for team {team_name}: {e}")
        return []

def get_database_stats():
    """Get statistics about the database."""
    try:
        # Total players
        total_query = "SELECT COUNT(*) FROM players"
        total_result = execute_sql_query(total_query)
        total_players = total_result.fetchone()[0]
        
        # Players by team
        team_query = """
        SELECT team, COUNT(*) as player_count 
        FROM players 
        GROUP BY team 
        ORDER BY player_count DESC
        """
        team_result = execute_sql_query(team_query)
        team_stats = team_result.fetchall()
        
        # Players by position
        position_query = """
        SELECT position, COUNT(*) as player_count 
        FROM players 
        GROUP BY position 
        ORDER BY player_count DESC
        """
        position_result = execute_sql_query(position_query)
        position_stats = position_result.fetchall()
        
        # Latest update time
        update_query = "SELECT MAX(updated_at) FROM players"
        update_result = execute_sql_query(update_query)
        last_updated = update_result.fetchone()[0]
        
        return {
            "total_players": total_players,
            "teams": len(team_stats),
            "positions": len(position_stats),
            "team_stats": team_stats,
            "position_stats": position_stats,
            "last_updated": last_updated.isoformat() if last_updated else None
        }
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {
            "total_players": 0,
            "teams": 0,
            "positions": 0,
            "team_stats": [],
            "position_stats": [],
            "last_updated": None
        }

def test_database_functions():
    """Test database functions."""
    try:
        print("Testing database functions...")
        
        # Test table creation
        create_players_table()
        print("✅ Table creation successful")
        
        # Test sample data insertion
        sample_players = [
            {
                'name': 'Test Player',
                'team': '49ers',
                'position': 'QB',
                'jersey_number': '1',
                'age': 25,
                'height': '6\'0"',
                'weight': 200,
                'college': 'Test University',
                'experience': 'Rookie',
                'status': 'Active',
                'data_source': 'Test'
            }
        ]
        
        save_players_to_db(sample_players)
        print("✅ Sample data insertion successful")
        
        # Test data retrieval
        players = get_all_players_from_db()
        print(f"✅ Data retrieval successful: {len(players)} players")
        
        # Test stats
        stats = get_database_stats()
        print(f"✅ Stats retrieval successful: {stats['total_players']} total players")
        
        print("✅ All database tests passed!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")

if __name__ == "__main__":
    test_database_functions()