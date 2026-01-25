"""Test registry mapping feature names to test implementations"""

from typing import Dict, List

# Map test function names to actual test scripts and arguments
TEST_REGISTRY: Dict[str, Dict[str, any]] = {
    'test_nfl_scraper': {
        'script': 'gravity/nfl_scraper.py',
        'args': ['player', 'Patrick Mahomes', 'Chiefs', 'QB'],
        'description': 'Test NFL player data scraping with Patrick Mahomes',
        'timeout': 180
    },
    'test_nba_scraper': {
        'script': 'gravity/nba_scraper.py',
        'args': ['player', 'LeBron James', 'Lakers', 'SF'],
        'description': 'Test NBA player data scraping with LeBron James',
        'timeout': 180
    },
    'test_cfb_scraper': {
        'script': 'gravity/cfb_scraper.py',
        'args': ['player', 'Caleb Williams', 'USC', 'QB'],
        'description': 'Test college football scraper',
        'timeout': 180
    },
    'test_data_pipeline': {
        'script': 'test_all_changes.py',
        'args': [],
        'description': 'Run comprehensive test suite for all recent changes',
        'timeout': 600
    },
    'test_social_collection': {
        'script': 'quick_social_collector.py',
        'args': [],
        'description': 'Test social media data collection',
        'timeout': 120
    },
    'test_contract_collection': {
        'script': 'test_contract_social_nfl.py',
        'args': [],
        'description': 'Test contract data collection for NFL',
        'timeout': 180
    },
    'test_risk_analysis': {
        'script': 'test_risk_collection.py',
        'args': [],
        'description': 'Test risk analysis and injury data collection',
        'timeout': 300
    },
    'test_ml_pipeline': {
        'script': 'train_models.py',
        'args': [],
        'description': 'Test machine learning pipeline',
        'timeout': 600
    },
    'test_nil_collector': {
        'script': 'test_nil_collector.py',
        'args': [],
        'description': 'Test NIL (Name, Image, Likeness) data collection',
        'timeout': 180
    },
    'test_recruiting_collector': {
        'script': 'test_recruiting_collector.py',
        'args': [],
        'description': 'Test recruiting data collection',
        'timeout': 180
    },
    'test_free_collectors': {
        'script': 'test_free_collectors.py',
        'args': [],
        'description': 'Test free API collectors (no Firecrawl costs)',
        'timeout': 180
    },
    'test_nfl_2_per_team': {
        'script': 'test_nfl_2_per_team.py',
        'args': [],
        'description': 'Test NFL scraper with 2 players per team',
        'timeout': 300
    },
    'test_nba_2_per_team': {
        'script': 'test_nba_2_per_team.py',
        'args': [],
        'description': 'Test NBA scraper with 2 players per team',
        'timeout': 300
    },
    'test_cfb_2_per_team': {
        'script': 'test_cfb_2_per_team.py',
        'args': [],
        'description': 'Test CFB scraper with 2 players per team',
        'timeout': 300
    },
}

# Keyword-based test inference mapping
KEYWORD_MAPPING: Dict[str, List[str]] = {
    'test_nfl_scraper': ['nfl', 'football', 'mahomes', 'chiefs'],
    'test_nba_scraper': ['nba', 'basketball', 'lebron', 'lakers'],
    'test_cfb_scraper': ['cfb', 'college football', 'ncaaf', 'ncaa'],
    'test_data_pipeline': ['pipeline', 'comprehensive', 'all changes'],
    'test_social_collection': ['social', 'social media', 'twitter', 'instagram'],
    'test_contract_collection': ['contract', 'contracts', 'spotrac'],
    'test_risk_analysis': ['risk', 'injury', 'injuries', 'controversy'],
    'test_ml_pipeline': ['ml', 'machine learning', 'model', 'training'],
    'test_nil_collector': ['nil', 'name image likeness'],
    'test_recruiting_collector': ['recruiting', 'recruit', '247sports'],
    'test_free_collectors': ['free', 'free api', 'pytrends'],
}


def infer_test_from_keywords(feature_name: str, description: str = "") -> str:
    """
    Infer test function name from feature name and description using keywords.
    
    Args:
        feature_name: Name of the feature
        description: Description of the feature
    
    Returns:
        Test function name from TEST_REGISTRY, or empty string if no match
    """
    combined_text = f"{feature_name} {description}".lower()
    
    # Score each test based on keyword matches
    scores = {}
    for test_name, keywords in KEYWORD_MAPPING.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        if score > 0:
            scores[test_name] = score
    
    # Return test with highest score
    if scores:
        return max(scores, key=scores.get)
    
    return ""


def get_test_info(test_name: str) -> Dict[str, any]:
    """
    Get test information from registry.
    
    Args:
        test_name: Name of the test function
    
    Returns:
        Test info dict, or None if not found
    """
    return TEST_REGISTRY.get(test_name)


def list_all_tests() -> List[str]:
    """Get list of all registered test names"""
    return list(TEST_REGISTRY.keys())

