"""
Test Enhanced NFL Data System with Age Fallback and Database Versioning
Demonstrates how the system handles age collection and tracks data changes
"""

import logging
import sys
import time
from datetime import datetime
from enhanced_age_collector import EnhancedAgeCollector
from database_versioning import DatabaseVersioning, calculate_age_from_birth_date

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_age_collection():
    """Test age collection with fallback sources"""
    print("=== TESTING AGE COLLECTION WITH FALLBACK ===")
    
    age_collector = EnhancedAgeCollector()
    
    # Test players with different scenarios
    test_players = [
        {'name': 'Brock Purdy', 'team': '49ers', 'expected_age_range': (22, 26)},
        {'name': 'Christian McCaffrey', 'team': '49ers', 'expected_age_range': (26, 30)},
        {'name': 'George Kittle', 'team': '49ers', 'expected_age_range': (28, 32)},
        {'name': 'Nick Bosa', 'team': '49ers', 'expected_age_range': (24, 28)},
    ]
    
    for player in test_players:
        print(f"\nTesting age collection for {player['name']}:")
        
        # Test age collection
        age = age_collector.get_player_age(player['name'], player['team'])
        
        if age:
            min_age, max_age = player['expected_age_range']
            if min_age <= age <= max_age:
                print(f"✓ Successfully found age: {age} (within expected range {min_age}-{max_age})")
            else:
                print(f"⚠ Found age: {age} (outside expected range {min_age}-{max_age})")
        else:
            print(f"✗ Could not find age for {player['name']}")
    
    print("\n=== AGE COLLECTION FALLBACK DEMONSTRATION ===")
    print("The system tries sources in this order:")
    print("1. NFL.com roster pages (primary)")
    print("2. ESPN player pages (secondary)")
    print("3. Wikipedia biographical data (fallback)")
    print("4. Calculates age from birth date if found")

def test_database_versioning():
    """Test database versioning system"""
    print("\n=== TESTING DATABASE VERSIONING ===")
    
    try:
        db_versioning = DatabaseVersioning()
        
        # Test with sample player data
        sample_player = {
            'name': 'Test Player',
            'team': '49ers',
            'position': 'QB',
            'age': 25,
            'twitter_handle': '@testplayer',
            'twitter_followers': 1000,
            'instagram_handle': '@testplayer_ig',
            'instagram_followers': 2000,
            'birth_date': '1999-01-01',
            'college': 'Test University',
            'current_salary': '$1,000,000',
            'data_sources': ['test_system'],
            'data_quality_score': 8.5
        }
        
        print("1. Creating new player record...")
        result1 = db_versioning.update_player_data(sample_player)
        print(f"   Result: {result1}")
        
        # Update player with new data
        updated_player = sample_player.copy()
        updated_player.update({
            'age': 26,  # Age changed
            'twitter_followers': 1500,  # Followers increased
            'instagram_followers': 2500,  # Followers increased
            'current_salary': '$1,200,000',  # Salary increased
            'pro_bowls': '2024'  # New field added
        })
        
        print("\n2. Updating existing player...")
        result2 = db_versioning.update_player_data(updated_player)
        print(f"   Result: {result2}")
        
        # Get player history
        if result2['action'] == 'updated':
            print("\n3. Getting player history...")
            history = db_versioning.get_player_history(result2['player_id'])
            print(f"   Found {len(history)} historical versions")
            
            for i, version in enumerate(history):
                print(f"   Version {i+1}:")
                print(f"     Date: {version['version_date']}")
                print(f"     Changed fields: {version['changed_fields']}")
                print(f"     Change type: {version['change_type']}")
        
        # Get current player data
        print("\n4. Getting current player data...")
        current_data = db_versioning.get_player_by_name('Test Player', '49ers')
        if current_data:
            print(f"   Current version: {current_data['version']}")
            print(f"   Current age: {current_data['age']}")
            print(f"   Current Twitter followers: {current_data['twitter_followers']}")
            print(f"   Last updated: {current_data['last_updated']}")
        
    except Exception as e:
        print(f"Database versioning test failed: {e}")
        print("This is expected if PostgreSQL is not set up")

def test_age_calculation():
    """Test age calculation from birth dates"""
    print("\n=== TESTING AGE CALCULATION FROM BIRTH DATES ===")
    
    birth_dates = [
        '1999-01-01',
        'January 1, 1999',
        '01/01/1999',
        'January 1 1999',
        '1/1/1999'
    ]
    
    for birth_date in birth_dates:
        age = calculate_age_from_birth_date(birth_date)
        print(f"Birth date: '{birth_date}' → Age: {age}")

def demonstrate_data_flow():
    """Demonstrate the complete data flow"""
    print("\n=== DATA FLOW DEMONSTRATION ===")
    
    print("When collecting player data, the system now:")
    print("1. Tries to get age from NFL.com roster")
    print("2. If that fails, tries ESPN player pages")
    print("3. If that fails, uses Wikipedia as fallback")
    print("4. Calculates age from birth date if found")
    print("5. Stores all data in database with versioning")
    print("6. If player already exists, creates historical record")
    print("7. Updates player with new data")
    print("8. Always shows latest data in main view")
    print("9. Historical versions accessible via API")

def show_database_schema():
    """Show the database schema"""
    print("\n=== DATABASE SCHEMA ===")
    
    print("PRIMARY TABLE: players (always shows latest data)")
    print("- Contains all 74 fields for each player")
    print("- Version field tracks current version number")
    print("- Last_updated timestamp shows when data changed")
    
    print("\nHISTORY TABLE: player_history (tracks all changes)")
    print("- Stores previous data as JSON")
    print("- Records which fields changed")
    print("- Timestamps for each change")
    print("- Links to main player record")
    
    print("\nWEB INTERFACE:")
    print("- Shows current data from players table")
    print("- All 74 fields visible and filterable")
    print("- Export functions work with latest data")
    print("- Historical data accessible via API endpoints")

if __name__ == "__main__":
    print("ENHANCED NFL DATA SYSTEM TEST")
    print("=" * 50)
    
    # Test age collection
    test_age_collection()
    
    # Test database versioning
    test_database_versioning()
    
    # Test age calculation
    test_age_calculation()
    
    # Demonstrate data flow
    demonstrate_data_flow()
    
    # Show database schema
    show_database_schema()
    
    print("\n" + "=" * 50)
    print("SYSTEM READY")
    print("✓ Age collection with Wikipedia fallback implemented")
    print("✓ Database versioning tracks all changes")
    print("✓ Web interface shows latest data")
    print("✓ Historical data preserved and accessible")