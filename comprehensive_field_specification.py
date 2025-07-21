#!/usr/bin/env python3
"""
Comprehensive Field Specification for NFL Player Data Collection
Defines all 74+ fields that should be collected for each player
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class PlayerFieldSpecification:
    """
    Complete specification of all fields to collect for NFL players
    Organized by category with position-specific variations
    """
    
    # Basic Information (Required for all players)
    BASIC_FIELDS = [
        'name',
        'jersey_number', 
        'position',
        'status',
        'height',
        'weight',
        'age',
        'team',
        'current_team'
    ]
    
    # Biographical Information
    BIOGRAPHICAL_FIELDS = [
        'birth_date',
        'birth_place', 
        'college',
        'high_school',
        'experience',
        'rookie_of_year',
        'hall_of_fame'
    ]
    
    # Draft Information
    DRAFT_FIELDS = [
        'draft_year',
        'draft_round',
        'draft_pick',
        'draft_team'
    ]
    
    # Social Media Profiles
    SOCIAL_MEDIA_FIELDS = [
        'twitter_handle',
        'instagram_handle', 
        'tiktok_handle',
        'youtube_handle',
        'twitter_url',
        'instagram_url',
        'tiktok_url',
        'youtube_url',
        'twitter_followers',
        'instagram_followers',
        'tiktok_followers',
        'youtube_subscribers',
        'twitter_following',
        'instagram_following',
        'tiktok_following',
        'twitter_verified',
        'instagram_verified'
    ]
    
    # Contract & Financial Information
    CONTRACT_FIELDS = [
        'contract_value',
        'contract_years',
        'current_salary',
        'cap_hit',
        'guaranteed_money',
        'signing_bonus',
        'dead_money'
    ]
    
    # Awards & Recognition
    AWARDS_FIELDS = [
        'championships',
        'mvp_awards',
        'all_pros',
        'pro_bowls',
        'awards'
    ]
    
    # Career Statistics (All Positions)
    CAREER_STATS_BASIC = [
        'career_games',
        'career_starts'
    ]
    
    # Position-Specific Career Statistics
    QB_CAREER_STATS = [
        'career_pass_attempts',
        'career_pass_completions',
        'career_pass_yards',
        'career_pass_tds',
        'career_pass_ints',
        'career_pass_rating',
        'career_rush_yards',
        'career_rush_tds'
    ]
    
    RB_CAREER_STATS = [
        'career_rush_yards',
        'career_rush_tds',
        'career_receptions',
        'career_rec_yards',
        'career_rec_tds'
    ]
    
    WR_TE_CAREER_STATS = [
        'career_receptions',
        'career_rec_yards',
        'career_rec_tds',
        'career_rush_yards',
        'career_rush_tds'
    ]
    
    DEFENSE_CAREER_STATS = [
        'career_tackles',
        'career_sacks',
        'career_interceptions'
    ]
    
    # 2023 Season Statistics (Position-Specific)
    QB_2023_STATS = [
        'passing_yards_2023',
        'passing_tds_2023',
        'rushing_yards_2023',
        'rushing_tds_2023'
    ]
    
    RB_2023_STATS = [
        'rushing_yards_2023',
        'rushing_tds_2023',
        'receiving_yards_2023',
        'receiving_tds_2023'
    ]
    
    WR_TE_2023_STATS = [
        'receiving_yards_2023', 
        'receiving_tds_2023',
        'rushing_yards_2023',
        'rushing_tds_2023'
    ]
    
    DEFENSE_2023_STATS = [
        'tackles_2023',
        'sacks_2023',
        'interceptions_2023'
    ]
    
    # URLs & References
    URL_FIELDS = [
        'wikipedia_url',
        'nfl_com_url',
        'espn_url',
        'pff_url',
        'spotrac_url',
        'google_news_url'
    ]
    
    # News & Media
    NEWS_FIELDS = [
        'news_headline_count',
        'recent_headlines',
        'news_bio_snippets'
    ]
    
    # Meta Information
    META_FIELDS = [
        'data_sources',
        'data_quality_score',
        'comprehensive_enhanced',
        'last_updated',
        'scraped_at',
        'data_source'
    ]
    
    # Gravity Score Components
    GRAVITY_FIELDS = [
        'brand_power',
        'proof',
        'proximity', 
        'velocity',
        'risk',
        'total_gravity'
    ]

class ComprehensiveFieldCollector:
    """
    Ensures all relevant fields are collected for each player
    """
    
    def __init__(self):
        self.spec = PlayerFieldSpecification()
    
    def get_required_fields_for_position(self, position: str) -> List[str]:
        """
        Get all required fields for a specific position
        """
        # Start with universal fields
        required_fields = (
            self.spec.BASIC_FIELDS + 
            self.spec.BIOGRAPHICAL_FIELDS + 
            self.spec.DRAFT_FIELDS +
            self.spec.SOCIAL_MEDIA_FIELDS +
            self.spec.CONTRACT_FIELDS +
            self.spec.AWARDS_FIELDS +
            self.spec.CAREER_STATS_BASIC +
            self.spec.URL_FIELDS +
            self.spec.NEWS_FIELDS +
            self.spec.META_FIELDS +
            self.spec.GRAVITY_FIELDS
        )
        
        # Add position-specific stats
        if position in ['QB']:
            required_fields.extend(self.spec.QB_CAREER_STATS)
            required_fields.extend(self.spec.QB_2023_STATS)
        elif position in ['RB', 'FB']:
            required_fields.extend(self.spec.RB_CAREER_STATS)
            required_fields.extend(self.spec.RB_2023_STATS)
        elif position in ['WR', 'TE']:
            required_fields.extend(self.spec.WR_TE_CAREER_STATS)
            required_fields.extend(self.spec.WR_TE_2023_STATS)
        elif position in ['CB', 'S', 'LB', 'DE', 'DT', 'OLB', 'ILB', 'SS', 'FS']:
            required_fields.extend(self.spec.DEFENSE_CAREER_STATS)
            required_fields.extend(self.spec.DEFENSE_2023_STATS)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(required_fields))
    
    def validate_player_data_completeness(self, player_data: Dict[str, Any], position: str) -> Dict[str, Any]:
        """
        Validate that player data contains all required fields for their position
        Returns analysis of missing fields and data quality
        """
        required_fields = self.get_required_fields_for_position(position)
        
        missing_fields = []
        populated_fields = []
        empty_fields = []
        
        for field in required_fields:
            value = player_data.get(field)
            if value is None:
                missing_fields.append(field)
            elif value == "" or value == "N/A" or value == "Unknown":
                empty_fields.append(field)
            else:
                populated_fields.append(field)
        
        total_required = len(required_fields)
        total_populated = len(populated_fields)
        completion_rate = (total_populated / total_required) * 100 if total_required > 0 else 0
        
        return {
            'total_required_fields': total_required,
            'populated_fields': total_populated,
            'missing_fields': len(missing_fields),
            'empty_fields': len(empty_fields), 
            'completion_rate': round(completion_rate, 1),
            'missing_field_list': missing_fields[:10],  # Show first 10 missing
            'data_quality_score': min(5.0, completion_rate / 20),  # Scale to 0-5
            'is_comprehensive': completion_rate >= 70.0  # 70%+ completion = comprehensive
        }
    
    def get_all_possible_fields(self) -> List[str]:
        """
        Get complete list of all possible fields across all positions
        """
        all_fields = (
            self.spec.BASIC_FIELDS + 
            self.spec.BIOGRAPHICAL_FIELDS + 
            self.spec.DRAFT_FIELDS +
            self.spec.SOCIAL_MEDIA_FIELDS +
            self.spec.CONTRACT_FIELDS +
            self.spec.AWARDS_FIELDS +
            self.spec.CAREER_STATS_BASIC +
            self.spec.QB_CAREER_STATS +
            self.spec.RB_CAREER_STATS +
            self.spec.WR_TE_CAREER_STATS +
            self.spec.DEFENSE_CAREER_STATS +
            self.spec.QB_2023_STATS +
            self.spec.RB_2023_STATS +
            self.spec.WR_TE_2023_STATS +
            self.spec.DEFENSE_2023_STATS +
            self.spec.URL_FIELDS +
            self.spec.NEWS_FIELDS +
            self.spec.META_FIELDS +
            self.spec.GRAVITY_FIELDS
        )
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(all_fields))
    
    def create_empty_player_template(self, position: str = "QB") -> Dict[str, Any]:
        """
        Create an empty player template with all required fields
        """
        required_fields = self.get_required_fields_for_position(position)
        template = {}
        
        for field in required_fields:
            if field in ['age', 'weight', 'experience', 'jersey_number']:
                template[field] = None  # Integer fields
            elif field in ['total_gravity', 'brand_power', 'proof', 'proximity', 'velocity', 'risk']:
                template[field] = 0.0  # Float fields
            elif field in ['championships', 'mvp_awards', 'all_pros', 'pro_bowls']:
                template[field] = 0  # Integer count fields
            else:
                template[field] = ""  # String fields
        
        return template

# Usage example and testing
def test_field_specification():
    """Test the field specification system"""
    collector = ComprehensiveFieldCollector()
    
    # Test different positions
    positions = ['QB', 'RB', 'WR', 'TE', 'CB', 'LB', 'DE']
    
    for position in positions:
        fields = collector.get_required_fields_for_position(position)
        print(f"\n{position}: {len(fields)} required fields")
        
        # Create template
        template = collector.create_empty_player_template(position)
        validation = collector.validate_player_data_completeness(template, position)
        print(f"Template validation: {validation['completion_rate']}% complete")
    
    all_fields = collector.get_all_possible_fields()
    print(f"\nTotal unique fields across all positions: {len(all_fields)}")
    
    return collector

if __name__ == "__main__":
    test_field_specification()