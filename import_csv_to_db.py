#!/usr/bin/env python3
"""
Import CSV player data with gravity scores into PostgreSQL database.
Updates comprehensive_nfl_players table with gravity scores from CSV files.
"""

import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_gravity_scores():
    """Import gravity scores from CSV files into database."""
    
    # Connect to database
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found")
    
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        # 1. Import ECOS players with gravity scores
        ecos_file = 'data/ecos_players.csv'
        if os.path.exists(ecos_file):
            logger.info(f"Importing ECOS players from {ecos_file}...")
            df_ecos = pd.read_csv(ecos_file)
            
            updated_count = 0
            for _, row in df_ecos.iterrows():
                cursor.execute('''
                    UPDATE comprehensive_nfl_players 
                    SET brand_power = %s, 
                        proof = %s, 
                        proximity = %s, 
                        velocity = %s, 
                        risk = %s, 
                        total_gravity = %s,
                        twitter_followers = %s,
                        instagram_followers = %s,
                        tiktok_followers = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE LOWER(name) = LOWER(%s)
                    AND (team IN ('bills', 'dolphins', 'broncos') 
                         OR LOWER(current_team) LIKE LOWER(%s))
                ''', (
                    float(row['brand_power']) if pd.notna(row['brand_power']) else None,
                    float(row['proof']) if pd.notna(row['proof']) else None,
                    float(row['proximity']) if pd.notna(row['proximity']) else None,
                    float(row['velocity']) if pd.notna(row['velocity']) else None,
                    float(row['risk']) if pd.notna(row['risk']) else None,
                    float(row['total_gravity']) if pd.notna(row['total_gravity']) else None,
                    int(row['twitter_followers']) if pd.notna(row['twitter_followers']) else None,
                    int(row['instagram_followers']) if pd.notna(row['instagram_followers']) else None,
                    int(row['tiktok_followers']) if pd.notna(row['tiktok_followers']) else None,
                    row['name'],
                    f"%{row['current_team'].split()[-1]}%"  # Match team name
                ))
                
                if cursor.rowcount > 0:
                    updated_count += 1
            
            conn.commit()
            logger.info(f"✅ Updated {updated_count} ECOS players with gravity scores")
        
        # 2. Import NFL players with gravity scores (if available)
        nfl_file = 'data/ecos_methodology_all_players_20250722_024930.csv'
        if os.path.exists(nfl_file):
            logger.info(f"Importing NFL players from {nfl_file}...")
            df_nfl = pd.read_csv(nfl_file)
            
            # Check if gravity columns exist
            has_gravity = 'total_gravity' in df_nfl.columns
            
            if has_gravity:
                updated_count = 0
                for _, row in df_nfl.iterrows():
                    cursor.execute('''
                        UPDATE comprehensive_nfl_players 
                        SET brand_power = %s, 
                            proof = %s, 
                            proximity = %s, 
                            velocity = %s, 
                            risk = %s, 
                            total_gravity = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE LOWER(name) = LOWER(%s)
                    ''', (
                        float(row['brand_power']) if pd.notna(row.get('brand_power')) else None,
                        float(row['proof']) if pd.notna(row.get('proof')) else None,
                        float(row['proximity']) if pd.notna(row.get('proximity')) else None,
                        float(row['velocity']) if pd.notna(row.get('velocity')) else None,
                        float(row['risk']) if pd.notna(row.get('risk')) else None,
                        float(row['total_gravity']) if pd.notna(row.get('total_gravity')) else None,
                        row['name'] if 'name' in row else row.get('Player', '')
                    ))
                    
                    if cursor.rowcount > 0:
                        updated_count += 1
                
                conn.commit()
                logger.info(f"✅ Updated {updated_count} NFL players with gravity scores")
            else:
                logger.info("NFL CSV doesn't have gravity scores - skipping")
        
        # 3. Verify import
        cursor.execute('''
            SELECT COUNT(*) 
            FROM comprehensive_nfl_players 
            WHERE total_gravity IS NOT NULL
        ''')
        total_with_scores = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM comprehensive_nfl_players 
            WHERE total_gravity IS NOT NULL 
            AND team IN ('bills', 'dolphins', 'broncos')
        ''')
        ecos_with_scores = cursor.fetchone()[0]
        
        logger.info(f"📊 Database now has:")
        logger.info(f"   - {total_with_scores} total players with gravity scores")
        logger.info(f"   - {ecos_with_scores} ECOS players with gravity scores")
        
    except Exception as e:
        logger.error(f"Error importing data: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import_gravity_scores()
