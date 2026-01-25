"""
Data Constraints for Synthetic Player Generation
================================================
Sport-specific rules and validations for synthetic data
"""

SPORT_CONSTRAINTS = {
    'nfl': {
        'age_range': (20, 35),
        'height_range': (66, 82),  # 5'6" to 6'10" in inches
        'weight_range': (160, 350),  # lbs
        'positions': ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'CB', 'S', 'K', 'P'],
        'stat_correlations': {
            'qb': {
                'career_touchdowns': {'min': 0, 'max': 600, 'correlates_with': 'career_yards'},
                'career_yards': {'min': 0, 'max': 80000, 'correlates_with': 'career_touchdowns'},
                'career_interceptions': {'min': 0, 'max': 300}
            },
            'rb': {
                'career_touchdowns': {'min': 0, 'max': 150},
                'career_yards': {'min': 0, 'max': 20000}
            },
            'wr': {
                'career_receptions': {'min': 0, 'max': 1500},
                'career_yards': {'min': 0, 'max': 25000}
            }
        }
    },
    'nba': {
        'age_range': (19, 35),
        'height_range': (70, 88),  # 5'10" to 7'4" in inches
        'weight_range': (160, 300),  # lbs
        'positions': ['PG', 'SG', 'SF', 'PF', 'C'],
        'stat_correlations': {
            'guard': {
                'career_points': {'min': 0, 'max': 40000},
                'career_assists': {'min': 0, 'max': 12000}
            },
            'forward': {
                'career_points': {'min': 0, 'max': 35000},
                'career_rebounds': {'min': 0, 'max': 15000}
            },
            'center': {
                'career_points': {'min': 0, 'max': 30000},
                'career_rebounds': {'min': 0, 'max': 20000}
            }
        }
    },
    'cfb': {
        'age_range': (18, 23),
        'height_range': (66, 82),
        'weight_range': (160, 350),
        'positions': ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'CB', 'S', 'K'],
        'stat_correlations': {
            'qb': {
                'career_touchdowns': {'min': 0, 'max': 150},
                'career_yards': {'min': 0, 'max': 20000}
            },
            'rb': {
                'career_touchdowns': {'min': 0, 'max': 80},
                'career_yards': {'min': 0, 'max': 6000}
            }
        }
    }
}


def validate_synthetic_player(player_data: dict, sport: str) -> bool:
    """Validate a synthetic player meets sport constraints"""
    constraints = SPORT_CONSTRAINTS.get(sport, {})
    
    # Age check
    if 'age' in player_data:
        age = player_data['age']
        age_range = constraints.get('age_range', (18, 40))
        if not (age_range[0] <= age <= age_range[1]):
            return False
    
    # Height check
    if 'height' in player_data:
        height = player_data['height']
        height_range = constraints.get('height_range', (60, 90))
        if not (height_range[0] <= height <= height_range[1]):
            return False
    
    # Weight check
    if 'weight' in player_data:
        weight = player_data['weight']
        weight_range = constraints.get('weight_range', (150, 400))
        if not (weight_range[0] <= weight <= weight_range[1]):
            return False
    
    return True

