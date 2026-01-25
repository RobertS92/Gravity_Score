#!/usr/bin/env python3
"""
ML Feature Engineering
======================

Advanced feature engineering for ML models:
- Interaction features
- Ratio features
- Time-series features
- Aggregations
- Categorical encodings
- Text features

Author: Gravity Score Team
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


# ============================================================================
# FEATURE ENGINEER
# ============================================================================

class MLFeatureEngineer:
    """
    Advanced feature engineering for ML models
    
    Creates sophisticated features from raw player data
    """
    
    def __init__(self):
        """Initialize feature engineer"""
        self.generated_features = []
        self.encoding_maps = {}
    
    def engineer_features(self, df: pd.DataFrame, include_all: bool = True) -> pd.DataFrame:
        """
        Generate all engineered features
        
        Args:
            df: Input DataFrame with player data
            include_all: If True, generate all features; if False, only essential ones
            
        Returns:
            DataFrame with additional engineered features
        """
        df = df.copy()
        self.generated_features = []
        
        logger.info("🔧 Engineering ML features...")
        
        # Core features (always include)
        df = self._create_interaction_features(df)
        df = self._create_ratio_features(df)
        df = self._create_aggregation_features(df)
        
        if include_all:
            # Advanced features
            df = self._create_time_series_features(df)
            df = self._create_categorical_encodings(df)
            df = self._create_text_features(df)
            df = self._create_position_features(df)
            df = self._create_career_stage_features(df)
        
        logger.info(f"✅ Created {len(self.generated_features)} new features")
        
        return df
    
    def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create interaction features between key variables
        
        Examples:
        - Position × Performance metrics
        - Age × Experience
        - Social followers × Performance
        """
        # Age × Experience
        if 'identity.age' in df.columns and 'identity.years_in_league' in df.columns:
            df['feat_age_experience_ratio'] = df['identity.age'] / (df['identity.years_in_league'] + 1)
            self.generated_features.append('feat_age_experience_ratio')
        
        # Performance × Social (marketability indicator)
        if 'proof.career_points' in df.columns and 'brand.instagram_followers' in df.columns:
            df['feat_points_per_follower'] = df['proof.career_points'] / (df['brand.instagram_followers'] + 1)
            self.generated_features.append('feat_points_per_follower')
        
        # Awards × Experience (achievement rate)
        if 'proof.awards_count' in df.columns and 'identity.years_in_league' in df.columns:
            df['feat_awards_per_year'] = df['proof.awards_count'] / (df['identity.years_in_league'] + 1)
            self.generated_features.append('feat_awards_per_year')
        
        # Pro Bowls × Years (consistency indicator)
        if 'proof.pro_bowls' in df.columns and 'identity.years_in_league' in df.columns:
            df['feat_pro_bowl_rate'] = df['proof.pro_bowls'] / (df['identity.years_in_league'] + 1)
            self.generated_features.append('feat_pro_bowl_rate')
        
        # All-Star × Years (NBA)
        if 'proof.all_star_selections' in df.columns and 'identity.years_in_league' in df.columns:
            df['feat_all_star_rate'] = df['proof.all_star_selections'] / (df['identity.years_in_league'] + 1)
            self.generated_features.append('feat_all_star_rate')
        
        # Physical × Performance (efficiency indicator for NFL)
        if all(c in df.columns for c in ['identity.weight', 'proof.career_yards']):
            df['feat_yards_per_pound'] = df['proof.career_yards'] / (df['identity.weight'] + 1)
            self.generated_features.append('feat_yards_per_pound')
        
        # Social media cross-platform ratio
        if all(c in df.columns for c in ['brand.instagram_followers', 'brand.twitter_followers']):
            df['feat_insta_twitter_ratio'] = (df['brand.instagram_followers'] + 1) / (df['brand.twitter_followers'] + 1)
            self.generated_features.append('feat_insta_twitter_ratio')
        
        return df
    
    def _create_ratio_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create ratio features for normalization
        
        Examples:
        - Points per game / team average
        - Social engagement rate
        - Performance efficiency metrics
        """
        # Points efficiency (points per game relative to career average)
        if all(c in df.columns for c in ['proof.current_season_points', 'proof.career_points', 'proof.games_played']):
            career_ppg = df['proof.career_points'] / (df['proof.games_played'] + 1)
            current_ppg = df['proof.current_season_points'] / 17  # Assuming 17 game season
            df['feat_ppg_vs_career'] = current_ppg / (career_ppg + 1)
            self.generated_features.append('feat_ppg_vs_career')
        
        # Yards efficiency
        if all(c in df.columns for c in ['proof.current_season_yards', 'proof.career_yards', 'proof.games_played']):
            career_ypg = df['proof.career_yards'] / (df['proof.games_played'] + 1)
            current_ypg = df['proof.current_season_yards'] / 17
            df['feat_ypg_vs_career'] = current_ypg / (career_ypg + 1)
            self.generated_features.append('feat_ypg_vs_career')
        
        # Social engagement rate (total followers / media mentions)
        if all(c in df.columns for c in ['brand.total_social_followers', 'brand.media_mentions']):
            df['feat_social_engagement_rate'] = df['brand.media_mentions'] / (df['brand.total_social_followers'] + 1) * 1000000
            self.generated_features.append('feat_social_engagement_rate')
        
        # Award density (awards per career game)
        if all(c in df.columns for c in ['proof.awards_count', 'proof.games_played']):
            df['feat_award_density'] = df['proof.awards_count'] / (df['proof.games_played'] + 1)
            self.generated_features.append('feat_award_density')
        
        # Injury rate (games missed per season)
        if all(c in df.columns for c in ['risk.games_missed_career', 'identity.years_in_league']):
            df['feat_injury_rate_per_season'] = df['risk.games_missed_career'] / (df['identity.years_in_league'] + 1)
            self.generated_features.append('feat_injury_rate_per_season')
        
        # Contract efficiency (contract value per award)
        if all(c in df.columns for c in ['identity.contract_value', 'proof.awards_count']):
            df['feat_contract_per_award'] = df['identity.contract_value'] / (df['proof.awards_count'] + 1)
            self.generated_features.append('feat_contract_per_award')
        
        # BMI (Body Mass Index)
        if all(c in df.columns for c in ['identity.height', 'identity.weight']):
            height_m = df['identity.height'] * 0.0254  # inches to meters
            df['feat_bmi'] = df['identity.weight'] * 0.453592 / (height_m ** 2 + 0.01)  # lbs to kg
            self.generated_features.append('feat_bmi')
        
        return df
    
    def _create_time_series_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create time-series features for trend analysis
        
        Examples:
        - Year-over-year growth rates
        - Momentum indicators
        - Career trajectory features
        """
        # YoY growth rate
        if 'velocity.year_over_year_change' in df.columns:
            yoy = df['velocity.year_over_year_change'].fillna(0)
            
            # Growth momentum (positive=growing, negative=declining)
            df['feat_growth_momentum'] = np.where(yoy > 0, 1, np.where(yoy < -5, -1, 0))
            self.generated_features.append('feat_growth_momentum')
            
            # Growth magnitude (absolute change)
            df['feat_growth_magnitude'] = np.abs(yoy)
            self.generated_features.append('feat_growth_magnitude')
        
        # Career trajectory (peak detection)
        if 'velocity.career_trajectory' in df.columns:
            trajectory_map = {
                'ascending': 2,
                'peak': 1,
                'declining': -1,
                'plateau': 0
            }
            df['feat_trajectory_numeric'] = df['velocity.career_trajectory'].map(trajectory_map).fillna(0)
            self.generated_features.append('feat_trajectory_numeric')
        
        # Recent form (last season vs career average)
        if all(c in df.columns for c in ['proof.current_season_points', 'proof.career_points', 'proof.games_played']):
            career_avg = df['proof.career_points'] / (df['proof.games_played'] + 1)
            current_form = df['proof.current_season_points'] / 17
            df['feat_recent_form_ratio'] = current_form / (career_avg + 1)
            self.generated_features.append('feat_recent_form_ratio')
        
        # Prime years indicator (age 25-29 for most sports)
        if 'identity.age' in df.columns:
            df['feat_in_prime'] = ((df['identity.age'] >= 25) & (df['identity.age'] <= 29)).astype(int)
            self.generated_features.append('feat_in_prime')
        
        return df
    
    def _create_aggregation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create aggregated statistical features
        
        Examples:
        - Career totals
        - Per-game averages
        - Recent performance averages
        """
        # Total social media presence
        social_cols = [c for c in df.columns if 'followers' in c or 'subscribers' in c]
        if social_cols:
            df['feat_total_social'] = df[social_cols].fillna(0).sum(axis=1)
            self.generated_features.append('feat_total_social')
        
        # Total career achievements
        achievement_cols = [
            'proof.pro_bowls', 'proof.all_pro_selections', 'proof.super_bowl_wins',
            'proof.all_star_selections', 'proof.championships', 'proof.mvp_awards'
        ]
        available_achievement_cols = [c for c in achievement_cols if c in df.columns]
        if available_achievement_cols:
            df['feat_total_achievements'] = df[available_achievement_cols].fillna(0).sum(axis=1)
            self.generated_features.append('feat_total_achievements')
        
        # Total career offensive production (NFL)
        offensive_cols = [
            'proof.career_points', 'proof.career_yards', 
            'proof.career_touchdowns', 'proof.career_receptions'
        ]
        available_offensive_cols = [c for c in offensive_cols if c in df.columns]
        if available_offensive_cols:
            df['feat_total_offensive_production'] = df[available_offensive_cols].fillna(0).sum(axis=1)
            self.generated_features.append('feat_total_offensive_production')
        
        # Total career defensive production (NFL)
        defensive_cols = [
            'proof.career_sacks', 'proof.career_interceptions', 
            'proof.career_tackles', 'proof.career_forced_fumbles'
        ]
        available_defensive_cols = [c for c in defensive_cols if c in df.columns]
        if available_defensive_cols:
            df['feat_total_defensive_production'] = df[available_defensive_cols].fillna(0).sum(axis=1)
            self.generated_features.append('feat_total_defensive_production')
        
        # Average per-game stats
        if 'proof.games_played' in df.columns and df['proof.games_played'].notna().sum() > 0:
            games = df['proof.games_played'].fillna(1)
            
            if 'proof.career_points' in df.columns:
                df['feat_points_per_game'] = df['proof.career_points'] / games
                self.generated_features.append('feat_points_per_game')
            
            if 'proof.career_yards' in df.columns:
                df['feat_yards_per_game'] = df['proof.career_yards'] / games
                self.generated_features.append('feat_yards_per_game')
            
            if 'proof.career_touchdowns' in df.columns:
                df['feat_touchdowns_per_game'] = df['proof.career_touchdowns'] / games
                self.generated_features.append('feat_touchdowns_per_game')
        
        return df
    
    def _create_categorical_encodings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create encoded versions of categorical variables
        
        Uses target encoding or frequency encoding
        """
        # Position encoding (grouped by offensive/defensive)
        if 'position' in df.columns or 'identity.position' in df.columns:
            pos_col = 'position' if 'position' in df.columns else 'identity.position'
            
            # Offensive/Defensive grouping for NFL
            offensive_positions = ['QB', 'RB', 'WR', 'TE', 'OL', 'OT', 'OG', 'C']
            defensive_positions = ['DL', 'DE', 'DT', 'LB', 'DB', 'S', 'CB']
            
            df['feat_is_offensive'] = df[pos_col].isin(offensive_positions).astype(int)
            df['feat_is_defensive'] = df[pos_col].isin(defensive_positions).astype(int)
            self.generated_features.extend(['feat_is_offensive', 'feat_is_defensive'])
            
            # Skill position indicator (QB, RB, WR, TE)
            skill_positions = ['QB', 'RB', 'WR', 'TE', 'PG', 'SG', 'SF']
            df['feat_is_skill_position'] = df[pos_col].isin(skill_positions).astype(int)
            self.generated_features.append('feat_is_skill_position')
        
        # Team encoding (frequency encoding)
        if 'team' in df.columns or 'identity.team' in df.columns:
            team_col = 'team' if 'team' in df.columns else 'identity.team'
            team_freq = df[team_col].value_counts(normalize=True)
            df['feat_team_frequency'] = df[team_col].map(team_freq).fillna(0)
            self.generated_features.append('feat_team_frequency')
        
        # Conference encoding
        if 'identity.conference' in df.columns:
            conf_freq = df['identity.conference'].value_counts(normalize=True)
            df['feat_conference_frequency'] = df['identity.conference'].map(conf_freq).fillna(0)
            self.generated_features.append('feat_conference_frequency')
        
        # Draft status encoding
        if 'identity.draft_year' in df.columns:
            df['feat_was_drafted'] = (df['identity.draft_year'] != 'Undrafted').astype(int)
            self.generated_features.append('feat_was_drafted')
        
        if 'identity.draft_round' in df.columns:
            # Early round pick indicator (rounds 1-3)
            draft_round_numeric = pd.to_numeric(df['identity.draft_round'], errors='coerce')
            df['feat_early_round_pick'] = (draft_round_numeric <= 3).fillna(False).astype(int)
            self.generated_features.append('feat_early_round_pick')
        
        return df
    
    def _create_text_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features from text fields
        
        Examples:
        - Award counts from text
        - Sentiment indicators
        - Keyword presence
        """
        # Extract award counts from text lists
        if 'proof.awards' in df.columns:
            # Count of awards
            df['feat_awards_text_count'] = df['proof.awards'].apply(
                lambda x: len(str(x).split(',')) if pd.notna(x) and str(x) != '' else 0
            )
            self.generated_features.append('feat_awards_text_count')
            
            # Check for prestigious awards
            prestigious_keywords = ['MVP', 'All-Pro', 'Pro Bowl', 'All-Star', 'Champion', 'Rookie of the Year']
            for keyword in prestigious_keywords:
                feat_name = f'feat_has_{keyword.lower().replace(" ", "_")}'
                df[feat_name] = df['proof.awards'].apply(
                    lambda x: 1 if pd.notna(x) and keyword.lower() in str(x).lower() else 0
                )
                self.generated_features.append(feat_name)
        
        # Extract injury severity from text
        if 'risk.injury_history' in df.columns:
            severe_injuries = ['ACL', 'Achilles', 'concussion', 'fracture', 'torn']
            df['feat_severe_injury_history'] = df['risk.injury_history'].apply(
                lambda x: any(injury.lower() in str(x).lower() for injury in severe_injuries) if pd.notna(x) else 0
            ).astype(int)
            self.generated_features.append('feat_severe_injury_history')
        
        # Controversy indicators
        if 'risk.controversies' in df.columns:
            df['feat_has_controversies'] = (df['risk.controversies'].notna() & (df['risk.controversies'] != '')).astype(int)
            self.generated_features.append('feat_has_controversies')
        
        return df
    
    def _create_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create position-specific features
        
        Different positions have different key metrics
        """
        if 'position' not in df.columns and 'identity.position' not in df.columns:
            return df
        
        pos_col = 'position' if 'position' in df.columns else 'identity.position'
        
        # QB-specific features
        qb_mask = df[pos_col] == 'QB'
        if qb_mask.any() and 'proof.career_completions' in df.columns:
            df.loc[qb_mask, 'feat_qb_completion_rate'] = (
                df.loc[qb_mask, 'proof.career_completions'] / 
                (df.loc[qb_mask, 'proof.career_attempts'].fillna(1) + 1)
            )
            self.generated_features.append('feat_qb_completion_rate')
        
        # RB-specific features
        rb_mask = df[pos_col] == 'RB'
        if rb_mask.any() and 'proof.career_yards' in df.columns:
            df.loc[rb_mask, 'feat_rb_yards_per_carry'] = (
                df.loc[rb_mask, 'proof.career_yards'] / 
                (df.loc[rb_mask, 'proof.career_rushing_attempts'].fillna(1) + 1)
            )
            self.generated_features.append('feat_rb_yards_per_carry')
        
        # WR-specific features
        wr_mask = df[pos_col] == 'WR'
        if wr_mask.any() and 'proof.career_receptions' in df.columns:
            df.loc[wr_mask, 'feat_wr_yards_per_reception'] = (
                df.loc[wr_mask, 'proof.career_yards'] / 
                (df.loc[wr_mask, 'proof.career_receptions'].fillna(1) + 1)
            )
            self.generated_features.append('feat_wr_yards_per_reception')
        
        # Defensive player features
        defensive_positions = ['DL', 'DE', 'DT', 'LB', 'DB', 'S', 'CB']
        def_mask = df[pos_col].isin(defensive_positions)
        if def_mask.any() and 'proof.career_tackles' in df.columns:
            df.loc[def_mask, 'feat_def_total_impact'] = (
                df.loc[def_mask, 'proof.career_tackles'].fillna(0) +
                df.loc[def_mask, 'proof.career_sacks'].fillna(0) * 2 +
                df.loc[def_mask, 'proof.career_interceptions'].fillna(0) * 3
            )
            self.generated_features.append('feat_def_total_impact')
        
        return df
    
    def _create_career_stage_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create features indicating career stage
        
        Rookie, developing, prime, veteran, declining
        """
        if 'identity.years_in_league' not in df.columns:
            return df
        
        years = df['identity.years_in_league'].fillna(0)
        
        # Career stage categories
        df['feat_is_rookie'] = (years <= 1).astype(int)
        df['feat_is_developing'] = ((years > 1) & (years <= 3)).astype(int)
        df['feat_is_established'] = ((years > 3) & (years <= 7)).astype(int)
        df['feat_is_veteran'] = (years > 7).astype(int)
        
        self.generated_features.extend([
            'feat_is_rookie', 'feat_is_developing', 
            'feat_is_established', 'feat_is_veteran'
        ])
        
        # Contract status (rookie contract vs veteran)
        if 'identity.contract_value' in df.columns:
            # High value indicator (top 25%)
            contract_75th = df['identity.contract_value'].quantile(0.75)
            df['feat_high_value_contract'] = (df['identity.contract_value'] >= contract_75th).astype(int)
            self.generated_features.append('feat_high_value_contract')
        
        return df
    
    def get_feature_names(self) -> List[str]:
        """Get list of all generated feature names"""
        return self.generated_features


# ============================================================================
# FEATURE SELECTOR
# ============================================================================

class FeatureSelector:
    """
    Intelligent feature selection
    
    Removes low-variance, highly correlated, and low-importance features
    """
    
    @staticmethod
    def select_features(
        df: pd.DataFrame, 
        target: str,
        variance_threshold: float = 0.01,
        correlation_threshold: float = 0.95,
        max_features: int = 100
    ) -> List[str]:
        """
        Select best features for modeling
        
        Args:
            df: DataFrame with features
            target: Target variable name
            variance_threshold: Remove features with variance below this
            correlation_threshold: Remove one of pair of features with correlation above this
            max_features: Maximum number of features to return
            
        Returns:
            List of selected feature names
        """
        logger.info("🔍 Selecting best features...")
        
        # Get numeric features (exclude target)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if target in numeric_cols:
            numeric_cols.remove(target)
        
        if not numeric_cols:
            return []
        
        selected = numeric_cols.copy()
        
        # Remove low variance features
        variances = df[selected].var()
        low_var = variances[variances < variance_threshold].index.tolist()
        selected = [f for f in selected if f not in low_var]
        logger.info(f"  Removed {len(low_var)} low-variance features")
        
        # Remove highly correlated features
        if len(selected) > 1:
            corr_matrix = df[selected].corr().abs()
            upper_triangle = corr_matrix.where(
                np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
            )
            to_drop = [col for col in upper_triangle.columns 
                      if any(upper_triangle[col] > correlation_threshold)]
            selected = [f for f in selected if f not in to_drop]
            logger.info(f"  Removed {len(to_drop)} highly correlated features")
        
        # If still too many features, select by correlation with target
        if len(selected) > max_features and target in df.columns:
            target_corr = df[selected + [target]].corr()[target].abs()
            target_corr = target_corr.drop(target).sort_values(ascending=False)
            selected = target_corr.head(max_features).index.tolist()
            logger.info(f"  Selected top {max_features} features by target correlation")
        
        logger.info(f"✅ Selected {len(selected)} features")
        
        return selected


if __name__ == '__main__':
    print("""
ML Feature Engineering
======================

Generate advanced ML features:
    from gravity.ml_feature_engineering import MLFeatureEngineer
    
    engineer = MLFeatureEngineer()
    df_with_features = engineer.engineer_features(df)
    
    # Get generated feature names
    feature_names = engineer.get_feature_names()

Select best features:
    from gravity.ml_feature_engineering import FeatureSelector
    
    selected = FeatureSelector.select_features(df, target='gravity_score')
    """)

