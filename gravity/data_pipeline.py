#!/usr/bin/env python3
"""
Data Pipeline for Gravity Score
================================

Comprehensive pipeline to:
1. Flatten nested player data structures
2. Impute missing values intelligently
3. Extract features from raw data
4. Calculate Gravity Score

Author: Gravity Score Team
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import re
import json

logger = logging.getLogger(__name__)


# ============================================================================
# DATA FLATTENER
# ============================================================================

class DataFlattener:
    """Flatten nested player data structures for analysis"""
    
    def __init__(self, max_years: int = 3):
        """
        Args:
            max_years: Maximum number of historical years to keep (default: 3)
        """
        self.max_years = max_years
    
    def _convert_value(self, value: Any) -> Any:
        """
        Convert values to pandas-compatible types.
        Specifically converts booleans to integers to avoid pandas TypeError.
        
        Args:
            value: Any value
            
        Returns:
            Converted value (bool → int, else unchanged)
        """
        if isinstance(value, bool):
            return int(value)  # True → 1, False → 0
        return value
    
    def flatten_player_data(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten a single player's nested data structure
        
        Args:
            player_data: Raw nested player data dictionary
            
        Returns:
            Flattened dictionary with dot-notation keys
        """
        flat = {}
        
        # Flatten top-level fields
        for key in ['player_name', 'team', 'position', 'collection_timestamp', 'data_quality_score']:
            flat[key] = player_data.get(key, '')
        
        # Flatten nested sections
        for section in ['identity', 'brand', 'proof', 'proximity', 'velocity', 'risk']:
            section_data = player_data.get(section, {})
            if isinstance(section_data, dict):
                self._flatten_section(flat, section, section_data)
        
        return flat
    
    def _flatten_section(self, flat: Dict, prefix: str, data: Dict):
        """Recursively flatten a section"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}"
            
            # Handle nested dictionaries (like stats by year)
            if isinstance(value, dict) and key in ['career_stats_by_year', 'pro_bowls_by_year', 
                                                     'all_pro_selections_by_year', 'super_bowl_wins_by_year']:
                # Limit to recent years only
                self._flatten_year_dict(flat, full_key, value)
            
            # Handle lists (convert to JSON string or count)
            elif isinstance(value, list):
                if len(value) > 0 and isinstance(value[0], dict):
                    # For complex lists (like awards), just count
                    flat[f"{full_key}_count"] = len(value)
                    # Store first few items as sample
                    for i, item in enumerate(value[:3]):
                        if isinstance(item, dict):
                            for k, v in item.items():
                                flat[f"{full_key}_{i}_{k}"] = self._convert_value(v)
                        else:
                            flat[f"{full_key}_{i}"] = self._convert_value(item)
                else:
                    # Simple list - join as string
                    flat[full_key] = ', '.join(str(v) for v in value)
            
            # Handle nested dicts (like current_season_stats)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flat[f"{full_key}.{sub_key}"] = self._convert_value(sub_value)
            
            # Simple values
            else:
                flat[full_key] = self._convert_value(value)
    
    def _flatten_year_dict(self, flat: Dict, prefix: str, year_data: Dict):
        """Flatten year-by-year data, keeping only recent years"""
        current_year = datetime.now().year
        years = sorted([int(y) for y in year_data.keys() if str(y).isdigit()], reverse=True)
        
        # Keep only recent years
        recent_years = years[:self.max_years]
        
        for year in recent_years:
            year_stats = year_data.get(str(year), {})
            if isinstance(year_stats, dict):
                for stat_key, stat_value in year_stats.items():
                    flat[f"{prefix}.{year}.{stat_key}"] = self._convert_value(stat_value)
            else:
                flat[f"{prefix}.{year}"] = self._convert_value(year_stats)
    
    def flatten_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flatten a DataFrame of player data
        
        Args:
            df: DataFrame with nested player data
            
        Returns:
            Flattened DataFrame
        """
        flattened_rows = []
        
        for _, row in df.iterrows():
            flat_row = self.flatten_player_data(row.to_dict())
            flattened_rows.append(flat_row)
        
        return pd.DataFrame(flattened_rows)


# ============================================================================
# DATA IMPUTER
# ============================================================================

class DataImputer:
    """Intelligently impute missing values based on position and context"""
    
    POSITION_DEFAULTS = {
        # NFL Positions
        'QB': {'height': 74, 'weight': 220},  # 6'2", 220 lbs
        'RB': {'height': 70, 'weight': 215},  # 5'10", 215 lbs
        'WR': {'height': 72, 'weight': 200},  # 6'0", 200 lbs
        'TE': {'height': 77, 'weight': 250},  # 6'5", 250 lbs
        'OL': {'height': 77, 'weight': 310},  # 6'5", 310 lbs
        'DL': {'height': 76, 'weight': 290},  # 6'4", 290 lbs
        'LB': {'height': 73, 'weight': 240},  # 6'1", 240 lbs
        'DB': {'height': 71, 'weight': 195},  # 5'11", 195 lbs
        'S': {'height': 72, 'weight': 205},   # 6'0", 205 lbs
        'CB': {'height': 71, 'weight': 190},  # 5'11", 190 lbs
        'K': {'height': 71, 'weight': 200},   # 5'11", 200 lbs
        'P': {'height': 73, 'weight': 210},   # 6'1", 210 lbs
        
        # NBA Positions
        'PG': {'height': 74, 'weight': 190},  # 6'2", 190 lbs
        'SG': {'height': 77, 'weight': 205},  # 6'5", 205 lbs
        'SF': {'height': 79, 'weight': 220},  # 6'7", 220 lbs
        'PF': {'height': 81, 'weight': 230},  # 6'9", 230 lbs
        'C': {'height': 83, 'weight': 250},   # 6'11", 250 lbs
    }
    
    def impute_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute missing values in player DataFrame
        
        Args:
            df: DataFrame with potentially missing values
            
        Returns:
            DataFrame with imputed values
        """
        df = df.copy()
        
        # Impute physical measurements based on position
        df = self._impute_physical_stats(df)
        
        # Impute numeric fields with position-aware medians
        df = self._impute_numeric_fields(df)
        
        # Impute categorical fields
        df = self._impute_categorical_fields(df)
        
        # Calculate missing age from birth_date
        df = self._impute_age(df)
        
        # Estimate years_in_league from draft_year
        df = self._impute_years_in_league(df)
        
        logger.info(f"✅ Data imputation complete")
        return df
    
    def _impute_physical_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Impute height/weight based on position"""
        for position, defaults in self.POSITION_DEFAULTS.items():
            mask = (df['position'] == position) | (df.get('identity.position') == position)
            
            # Height
            height_col = 'identity.height' if 'identity.height' in df.columns else 'height'
            if height_col in df.columns:
                df.loc[mask & df[height_col].isna(), height_col] = defaults['height']
            
            # Weight
            weight_col = 'identity.weight' if 'identity.weight' in df.columns else 'weight'
            if weight_col in df.columns:
                df.loc[mask & df[weight_col].isna(), weight_col] = defaults['weight']
        
        return df
    
    def _impute_numeric_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Impute numeric fields with medians or 0"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if df[col].isna().sum() > 0:
                # Use median for most fields
                if 'followers' in col or 'subscribers' in col or 'views' in col:
                    median_val = df[col].median()
                    df[col].fillna(median_val, inplace=True)
                
                # Use 0 for counts and stats
                elif any(x in col for x in ['count', 'career_', 'current_season', 'games', 'points', 'yards']):
                    df[col].fillna(0, inplace=True)
                
                # Use position-based median for percentages
                elif 'pct' in col or 'percentage' in col or 'rate' in col:
                    if 'position' in df.columns:
                        df[col] = df.groupby('position')[col].transform(
                            lambda x: x.fillna(x.median()) if x.median() else x.fillna(0)
                        )
                    else:
                        df[col].fillna(df[col].median(), inplace=True)
        
        return df
    
    def _impute_categorical_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Impute categorical fields with 'Unknown' or most common"""
        categorical_cols = df.select_dtypes(include=['object']).columns
        
        for col in categorical_cols:
            if df[col].isna().sum() > 0:
                # For important fields, use most common value
                if any(x in col for x in ['team', 'position', 'conference', 'college']):
                    mode_val = df[col].mode()[0] if not df[col].mode().empty else 'Unknown'
                    df[col].fillna(mode_val, inplace=True)
                # For others, use 'Unknown' or empty string
                else:
                    df[col].fillna('Unknown', inplace=True)
        
        return df
    
    def _impute_age(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate age from birth_date if missing"""
        age_col = 'identity.age' if 'identity.age' in df.columns else 'age'
        birth_col = 'identity.birth_date' if 'identity.birth_date' in df.columns else 'birth_date'
        
        if age_col in df.columns and birth_col in df.columns:
            missing_age = df[age_col].isna()
            
            for idx in df[missing_age].index:
                birth_date = df.at[idx, birth_col]
                if pd.notna(birth_date):
                    try:
                        birth_str = str(birth_date).split('T')[0]
                        birth = datetime.strptime(birth_str, '%Y-%m-%d')
                        today = datetime.now()
                        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
                        df.at[idx, age_col] = age
                    except:
                        pass
        
        return df
    
    def _impute_years_in_league(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate years_in_league from draft_year"""
        years_col = 'identity.years_in_league' if 'identity.years_in_league' in df.columns else 'years_in_league'
        draft_col = 'identity.draft_year' if 'identity.draft_year' in df.columns else 'draft_year'
        
        if years_col in df.columns and draft_col in df.columns:
            current_year = datetime.now().year
            missing_years = df[years_col].isna()
            
            for idx in df[missing_years].index:
                draft_year = df.at[idx, draft_col]
                if pd.notna(draft_year) and str(draft_year).isdigit():
                    years = current_year - int(draft_year)
                    df.at[idx, years_col] = max(0, years)
        
        return df


# ============================================================================
# FEATURE EXTRACTOR
# ============================================================================

class FeatureExtractor:
    """Extract derived features from raw player data"""
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract all derived features
        
        Args:
            df: DataFrame with raw player data
            
        Returns:
            DataFrame with additional feature columns
        """
        df = df.copy()
        
        logger.info("🔧 Extracting features...")
        
        # Physical features
        df = self._extract_physical_features(df)
        
        # Performance features
        df = self._extract_performance_features(df)
        
        # Social media features
        df = self._extract_social_features(df)
        
        # Risk features
        df = self._extract_risk_features(df)
        
        # Velocity/momentum features
        df = self._extract_velocity_features(df)
        
        logger.info(f"✅ Feature extraction complete - {len(df.columns)} total columns")
        return df
    
    def _extract_physical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract physical measurement features"""
        # BMI calculation
        height_col = self._find_col(df, ['identity.height', 'height'])
        weight_col = self._find_col(df, ['identity.weight', 'weight'])
        
        if height_col and weight_col:
            # Convert height to meters, weight to kg
            def safe_height_to_meters(x):
                if pd.notna(x):
                    inches = self._parse_height_to_inches(x)
                    return inches * 0.0254 if inches is not None else None
                return None
            
            def safe_weight_to_kg(x):
                if pd.notna(x):
                    lbs = self._parse_weight_to_lbs(x)
                    return lbs * 0.453592 if lbs is not None else None
                return None
            
            height_m = df[height_col].apply(safe_height_to_meters)
            weight_kg = df[weight_col].apply(safe_weight_to_kg)
            
            df['feature.bmi'] = weight_kg / (height_m ** 2)
        
        # Age categories
        age_col = self._find_col(df, ['identity.age', 'age'])
        if age_col:
            df['feature.age_category'] = pd.cut(df[age_col], bins=[0, 22, 25, 28, 35, 100],
                                                 labels=['Rookie', 'Young', 'Prime', 'Veteran', 'Aging'])
        
        return df
    
    def _extract_performance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract performance metrics"""
        # Career efficiency (points per game, etc.)
        ppg_col = self._find_col(df, ['proof.career_ppg', 'career_ppg', 'proof.career_stats.career_ppg'])
        if ppg_col:
            df['feature.scoring_level'] = pd.cut(df[ppg_col], bins=[0, 5, 10, 15, 20, 100],
                                                   labels=['Low', 'Average', 'Good', 'High', 'Elite'])
        
        # Pro Bowl / All-Star rate
        pro_bowls_col = self._find_col(df, ['proof.pro_bowls', 'pro_bowls'])
        years_col = self._find_col(df, ['identity.years_in_league', 'years_in_league'])
        
        if pro_bowls_col and years_col:
            df['feature.pro_bowl_rate'] = df[pro_bowls_col] / df[years_col].replace(0, 1)
        
        # Award count (total accolades)
        awards_col = self._find_col(df, ['proof.awards_count', 'awards_count'])
        if awards_col:
            df['feature.total_awards'] = df[awards_col]
        
        return df
    
    def _extract_social_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract social media engagement features"""
        # Total social reach
        social_cols = [
            self._find_col(df, ['brand.instagram_followers', 'instagram_followers']),
            self._find_col(df, ['brand.twitter_followers', 'twitter_followers']),
            self._find_col(df, ['brand.tiktok_followers', 'tiktok_followers']),
            self._find_col(df, ['brand.youtube_subscribers', 'youtube_subscribers'])
        ]
        
        social_cols = [c for c in social_cols if c]
        if social_cols:
            # Convert to numeric, handling non-numeric values
            social_df = df[social_cols].apply(pd.to_numeric, errors='coerce')
            df['feature.total_social_reach'] = social_df.sum(axis=1).fillna(0)
        
        # Engagement rate (average across platforms)
        engagement_cols = [
            self._find_col(df, ['brand.instagram_engagement_rate', 'instagram_engagement_rate']),
            self._find_col(df, ['brand.twitter_engagement_rate', 'twitter_engagement_rate']),
            self._find_col(df, ['brand.tiktok_engagement_rate', 'tiktok_engagement_rate'])
        ]
        
        engagement_cols = [c for c in engagement_cols if c]
        if engagement_cols:
            # Convert to numeric, handling non-numeric values (like 'Unknown')
            engagement_df = df[engagement_cols].apply(pd.to_numeric, errors='coerce')
            df['feature.avg_engagement_rate'] = engagement_df.mean(axis=1).fillna(0)
        
        # Verified accounts count
        verified_cols = [
            self._find_col(df, ['brand.instagram_verified', 'instagram_verified']),
            self._find_col(df, ['brand.twitter_verified', 'twitter_verified'])
        ]
        
        verified_cols = [c for c in verified_cols if c]
        if verified_cols:
            # Convert verified columns to numeric (handle string boolean values)
            for col in verified_cols:
                df[col] = pd.to_numeric(df[col].replace({
                    'True': 1, 'true': 1, 'Yes': 1, 'yes': 1, True: 1,
                    'False': 0, 'false': 0, 'No': 0, 'no': 0, False: 0,
                    None: 0, '': 0, 'Unknown': 0
                }), errors='coerce').fillna(0).astype(int)
            
            df['feature.verified_accounts'] = df[verified_cols].sum(axis=1)
        
        return df
    
    def _extract_risk_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract risk-related features"""
        # Injury risk composite
        injury_score_col = self._find_col(df, ['risk.injury_risk_score', 'injury_risk_score'])
        games_missed_col = self._find_col(df, ['risk.games_missed_career', 'games_missed_career'])
        
        if injury_score_col and games_missed_col:
            df['feature.injury_risk_composite'] = (df[injury_score_col] * 0.6 + 
                                                     (df[games_missed_col] / 100) * 0.4)
        
        # Controversy risk
        controversy_score_col = self._find_col(df, ['risk.controversy_risk_score', 'controversy_risk_score'])
        if controversy_score_col:
            df['feature.reputation_risk'] = df[controversy_score_col]
        
        # Contract security
        contract_col = self._find_col(df, ['identity.current_contract_length', 'current_contract_length'])
        if contract_col:
            df['feature.contract_security'] = df[contract_col].apply(
                lambda x: 'Secure' if x >= 3 else 'At-Risk' if x >= 1 else 'Uncertain'
            )
        
        return df
    
    def _extract_velocity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract momentum/velocity features"""
        # Social momentum
        follower_growth_col = self._find_col(df, ['velocity.follower_growth_rate_30d', 'follower_growth_rate_30d'])
        if follower_growth_col:
            df['feature.social_momentum'] = df[follower_growth_col]
        
        # Performance trend
        perf_trend_col = self._find_col(df, ['velocity.performance_trend', 'performance_trend'])
        if perf_trend_col:
            df['feature.performance_momentum'] = perf_trend_col
        
        # Media buzz
        media_surge_col = self._find_col(df, ['velocity.media_buzz_surge', 'media_buzz_surge'])
        if media_surge_col:
            df['feature.media_momentum'] = df[media_surge_col]
        
        # Compute velocity from year-over-year stats
        logger.info("🔢 Computing velocity from year-over-year stats...")
        velocity_data = df.apply(self._compute_velocity_from_stats, axis=1)
        
        # Add computed velocity columns
        if not velocity_data.empty:
            df['feature.performance_level'] = velocity_data.apply(lambda x: x.get('performance_level', 'Unknown'))
            df['feature.performance_trend_computed'] = velocity_data.apply(lambda x: x.get('trend', 'stable'))
            df['feature.yoy_improvement_pct'] = velocity_data.apply(lambda x: x.get('yoy_change_pct', 0))
            df['feature.career_trajectory'] = velocity_data.apply(lambda x: x.get('trajectory', 'stable'))
            df['feature.peak_performance_year'] = velocity_data.apply(lambda x: x.get('peak_year', None))
        
        return df
    
    def _compute_velocity_from_stats(self, row: pd.Series) -> Dict:
        """
        Compute performance velocity from year-over-year stats
        
        Analyzes career_stats_by_year columns to determine:
        - Performance level (high/mid/low)
        - Trend (increasing/stable/declining)
        - YoY change percentage
        - Career trajectory
        
        Returns dict with velocity metrics
        """
        result = {
            'performance_level': 'Unknown',
            'trend': 'stable',
            'yoy_change_pct': 0,
            'trajectory': 'stable',
            'peak_year': None
        }
        
        # Get position to determine key stat
        position = row.get('position', row.get('identity.position', ''))
        
        # Determine key performance stat by position
        if position in ['QB']:
            key_stat = 'avgPoints'  # For NFL: passing yards
            stat_aliases = ['passingYards', 'yards', 'avgPoints', 'Points Per Game']
        elif position in ['RB', 'WR', 'TE']:
            key_stat = 'avgPoints'  # Total yards or points
            stat_aliases = ['totalYards', 'receivingYards', 'rushingYards', 'avgPoints', 'Points Per Game']
        elif position in ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F']:
            key_stat = 'avgPoints'  # Points per game for basketball
            stat_aliases = ['avgPoints', 'Points Per Game', 'ppg']
        else:
            key_stat = 'avgPoints'
            stat_aliases = ['avgPoints', 'Points Per Game', 'yards', 'totalYards']
        
        # Extract year-over-year data
        years_data = {}
        current_year = datetime.now().year
        
        # Look for career_stats_by_year columns
        for col in row.index:
            if 'career_stats_by_year' in col or 'proof.career_stats_by_year' in col:
                # Extract year from column name
                parts = col.split('.')
                year = None
                stat_name = None
                
                for i, part in enumerate(parts):
                    if part.isdigit() and 2000 <= int(part) <= 2030:
                        year = int(part)
                        if i + 1 < len(parts):
                            stat_name = parts[i + 1]
                        break
                
                if year and stat_name:
                    # Check if this is one of our key stats
                    if stat_name in stat_aliases or key_stat in stat_name:
                        value = row[col]
                        if pd.notna(value) and value != 0:
                            try:
                                # Parse value (might be string like "25.5")
                                numeric_value = float(str(value).replace(',', ''))
                                if year not in years_data:
                                    years_data[year] = {}
                                years_data[year][stat_name] = numeric_value
                            except:
                                pass
        
        # If we have at least 2 years of data, compute velocity
        if len(years_data) >= 2:
            sorted_years = sorted(years_data.keys())
            
            # Get values for each year (use first available stat)
            year_values = {}
            for year in sorted_years:
                for alias in stat_aliases:
                    if alias in years_data[year]:
                        year_values[year] = years_data[year][alias]
                        break
            
            if len(year_values) >= 2:
                values = list(year_values.values())
                years = list(year_values.keys())
                
                # Determine performance level (based on recent average)
                recent_avg = sum(values[-2:]) / len(values[-2:])
                
                if position in ['QB']:
                    if recent_avg >= 4000:
                        result['performance_level'] = 'Elite'
                    elif recent_avg >= 3500:
                        result['performance_level'] = 'High'
                    elif recent_avg >= 2500:
                        result['performance_level'] = 'Mid'
                    else:
                        result['performance_level'] = 'Low'
                elif position in ['RB']:
                    if recent_avg >= 1500:
                        result['performance_level'] = 'Elite'
                    elif recent_avg >= 1000:
                        result['performance_level'] = 'High'
                    elif recent_avg >= 500:
                        result['performance_level'] = 'Mid'
                    else:
                        result['performance_level'] = 'Low'
                elif position in ['WR', 'TE']:
                    if recent_avg >= 1200:
                        result['performance_level'] = 'Elite'
                    elif recent_avg >= 800:
                        result['performance_level'] = 'High'
                    elif recent_avg >= 400:
                        result['performance_level'] = 'Mid'
                    else:
                        result['performance_level'] = 'Low'
                elif position in ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F']:
                    # Basketball PPG thresholds
                    if recent_avg >= 25:
                        result['performance_level'] = 'Elite'
                    elif recent_avg >= 18:
                        result['performance_level'] = 'High'
                    elif recent_avg >= 10:
                        result['performance_level'] = 'Mid'
                    else:
                        result['performance_level'] = 'Low'
                else:
                    # Generic thresholds
                    max_val = max(values)
                    if recent_avg >= max_val * 0.9:
                        result['performance_level'] = 'High'
                    elif recent_avg >= max_val * 0.6:
                        result['performance_level'] = 'Mid'
                    else:
                        result['performance_level'] = 'Low'
                
                # Calculate YoY change (last 2 years)
                if len(values) >= 2:
                    yoy_change = ((values[-1] - values[-2]) / values[-2]) * 100
                    result['yoy_change_pct'] = round(yoy_change, 1)
                    
                    # Determine trend
                    if yoy_change >= 10:
                        result['trend'] = 'increasing'
                    elif yoy_change <= -10:
                        result['trend'] = 'declining'
                    else:
                        result['trend'] = 'stable'
                
                # Determine overall trajectory (looking at all years)
                if len(values) >= 3:
                    # Calculate linear trend
                    x = list(range(len(values)))
                    y = values
                    
                    # Simple linear regression
                    n = len(x)
                    x_mean = sum(x) / n
                    y_mean = sum(y) / n
                    
                    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
                    
                    if denominator != 0:
                        slope = numerator / denominator
                        
                        # Categorize trajectory
                        avg_value = sum(values) / len(values)
                        slope_pct = (slope / avg_value) * 100 if avg_value != 0 else 0
                        
                        if slope_pct >= 5:
                            result['trajectory'] = 'ascending'
                        elif slope_pct <= -5:
                            result['trajectory'] = 'descending'
                        elif slope_pct >= 2:
                            result['trajectory'] = 'improving'
                        elif slope_pct <= -2:
                            result['trajectory'] = 'declining'
                        else:
                            result['trajectory'] = 'stable'
                
                # Find peak performance year
                max_value = max(values)
                max_idx = values.index(max_value)
                result['peak_year'] = years[max_idx]
        
        return result
    
    def _find_col(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """
        Find first existing column from candidates.
        Handles both nested (brand.instagram_followers) and flattened (instagram_followers) names.
        """
        for col in candidates:
            # Try exact match first
            if col in df.columns:
                return col
            # Try without prefix (flattened version)
            simple = col.split('.')[-1]
            if simple in df.columns:
                return simple
            # Try with underscore instead of dot
            underscore = col.replace('.', '_')
            if underscore in df.columns:
                return underscore
        return None
    
    def _parse_height_to_inches(self, height: Any) -> float:
        """Parse height string to inches"""
        if pd.isna(height):
            return None
        
        height_str = str(height)
        
        # Try format: 6'2" or 6-2
        match = re.match(r'(\d+)[\'"-](\d+)', height_str)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            return feet * 12 + inches
        
        # Try format: 74 (inches)
        try:
            return float(height_str)
        except:
            return None
    
    def _parse_weight_to_lbs(self, weight: Any) -> float:
        """Parse weight string to lbs"""
        if pd.isna(weight):
            return None
        
        weight_str = str(weight).replace('lbs', '').replace('lb', '').strip()
        
        try:
            return float(weight_str)
        except:
            return None


# ============================================================================
# GRAVITY SCORE CALCULATOR
# ============================================================================

class GravityScoreCalculator:
    """
    Calculate comprehensive Gravity Score - COMMERCIAL VALUE OPTIMIZED
    
    Designed for: Endorsement valuation, investment decisions, NIL pricing, marketability
    Time horizons: Current season (now), 3-year trajectory, career potential
    
    Gravity Score = Weighted combination of:
    - Performance Score (20%) - Current season weighted heavily
    - Market Value Score (25%) - Contracts + endorsements
    - Social Influence Score (30%) - Brand reach + celebrity effect
    - Velocity/Momentum Score (15%) - Growth trajectory
    - Risk Score (10% - inverse) - Injuries + scandals with severity scaling
    """
    
    WEIGHTS = {
        'performance': 0.15,  # Reduced - less important for commercial value
        'market': 0.30,      # Increased - contracts + endorsements
        'social': 0.35,      # Increased - brand reach is everything
        'velocity': 0.10,    # Reduced slightly
        'risk': 0.10         # Keep same
    }
    
    # Position-based commercial value multipliers
    # Higher multiplier = more commercial value for that position
    POSITION_COMMERCIAL_MULTIPLIERS = {
        # High commercial value positions (face of franchise)
        'QB': 1.5,   # Quarterbacks are the face of the franchise
        'WR': 1.3,   # Wide receivers are highly visible
        'RB': 1.2,   # Running backs get attention
        'TE': 1.1,   # Tight ends (Gronk, Kelce effect)
        
        # Medium commercial value
        'CB': 1.0,   # Cornerbacks (some stars)
        'S': 1.0,    # Safeties
        'LB': 0.9,   # Linebackers
        'DE': 0.9,   # Defensive ends (some stars like Bosa)
        'DT': 0.8,   # Defensive tackles
        'EDGE': 0.9, # Edge rushers
        'OLB': 0.9,  # Outside linebackers
        'ILB': 0.8,  # Inside linebackers
        
        # Low commercial value (invisible positions)
        'C': 0.5,    # Centers - almost no commercial value
        'G': 0.5,    # Guards
        'T': 0.5,    # Tackles
        'OT': 0.5,   # Offensive tackles
        'OG': 0.5,   # Offensive guards
        'OL': 0.5,   # Offensive line (generic)
        'LS': 0.3,   # Long snappers
        'K': 0.4,    # Kickers
        'P': 0.3,    # Punters
        'FB': 0.6,   # Fullbacks
    }
    
    def calculate_gravity_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Gravity Score for all players
        
        Args:
            df: DataFrame with player data and features
            
        Returns:
            DataFrame with gravity score columns added
        """
        df = df.copy()
        
        logger.info("⚡ Calculating Gravity Scores...")
        
        # Calculate component scores
        df['gravity.performance_score'] = self._calculate_performance_score(df).fillna(0)
        df['gravity.market_score'] = self._calculate_market_score(df).fillna(0)
        df['gravity.social_score'] = self._calculate_social_score(df).fillna(0)
        df['gravity.velocity_score'] = self._calculate_velocity_score(df).fillna(0)
        df['gravity.risk_score'] = self._calculate_risk_score(df).fillna(0)
        
        # Ensure all component scores are numeric and non-negative
        for col in ['gravity.performance_score', 'gravity.market_score', 'gravity.social_score', 
                    'gravity.velocity_score', 'gravity.risk_score']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).clip(lower=0, upper=100)
        
        # Apply position-based commercial multipliers
        position_col = self._find_col(df, ['position', 'identity.position'])
        if position_col:
            df['position_commercial_multiplier'] = df[position_col].map(
                self.POSITION_COMMERCIAL_MULTIPLIERS
            ).fillna(1.0)
            
            # Apply multiplier to market and social (commercial value drivers)
            df['gravity.market_score'] = (df['gravity.market_score'] * df['position_commercial_multiplier']).clip(0, 100)
            df['gravity.social_score'] = (df['gravity.social_score'] * df['position_commercial_multiplier']).clip(0, 100)
            
            # Also apply smaller multiplier to performance (visibility matters)
            perf_multiplier = 0.7 + (0.3 * df['position_commercial_multiplier'])
            df['gravity.performance_score'] = (df['gravity.performance_score'] * perf_multiplier).clip(0, 100)
            
            logger.info(f"Applied position multipliers to {df[position_col].notna().sum()} players")
            logger.info(f"  QB multiplier: {self.POSITION_COMMERCIAL_MULTIPLIERS.get('QB', 1.0)}x")
            logger.info(f"  C/G/T multiplier: {self.POSITION_COMMERCIAL_MULTIPLIERS.get('C', 1.0)}x")
        else:
            logger.warning("Position column not found - skipping position multipliers")
            df['position_commercial_multiplier'] = 1.0
        
        # Calculate final weighted Gravity Score
        df['gravity_score'] = (
            df['gravity.performance_score'] * self.WEIGHTS['performance'] +
            df['gravity.market_score'] * self.WEIGHTS['market'] +
            df['gravity.social_score'] * self.WEIGHTS['social'] +
            df['gravity.velocity_score'] * self.WEIGHTS['velocity'] +
            (100 - df['gravity.risk_score']) * self.WEIGHTS['risk']  # Inverse risk
        )
        
        # Ensure total score is numeric
        df['gravity_score'] = pd.to_numeric(df['gravity_score'], errors='coerce').fillna(0)
        
        # Use absolute scale - DON'T normalize to max
        # Cap at 100 but don't force highest to 100
        df['gravity_score'] = df['gravity_score'].clip(0, 100)
        
        # Add percentile ranking
        df['gravity_percentile'] = df['gravity_score'].rank(pct=True) * 100
        
        # Add tier classification
        df['gravity_tier'] = pd.cut(df['gravity_score'], 
                                      bins=[0, 50, 65, 80, 90, 100],
                                      labels=['Developing', 'Solid', 'Impact', 'Elite', 'Superstar'])
        
        logger.info(f"✅ Gravity Scores calculated - Range: {df['gravity_score'].min():.1f} to {df['gravity_score'].max():.1f}")
        logger.info(f"   Average: {df['gravity_score'].mean():.1f}, Median: {df['gravity_score'].median():.1f}")
        return df
    
    def _calculate_performance_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate performance score (0-100)
        Multi-horizon approach:
        - Current season: 50% (immediate value)
        - Recent 3-year trend: 25% (consistency)
        - Career legacy: 25% (long-term brand value)
        """
        score = pd.Series(0.0, index=df.index)
        
        # === CURRENT SEASON PERFORMANCE (50 points) ===
        # Most important for immediate endorsement value
        # Look for current year stats
        current_yards = self._find_col(df, ['stats.current_season.yards', 'current_season_yards', 'stats.2024.yards'])
        current_tds = self._find_col(df, ['stats.current_season.touchdowns', 'current_season_touchdowns', 'stats.2024.touchdowns'])
        current_ppg = self._find_col(df, ['stats.current_season.ppg', 'current_season_ppg'])
        
        if current_yards:
            score += self._normalize(df[current_yards], 0, 2000) * 0.25
        elif current_ppg:
            score += self._normalize(df[current_ppg], 0, 30) * 0.25
        
        if current_tds:
            score += self._normalize(df[current_tds], 0, 20) * 0.15
        
        # Fallback to career if current not available (still give partial credit)
        if not current_yards and not current_ppg:
            career_ppg = self._find_col(df, ['proof.career_ppg', 'career_ppg'])
            if career_ppg:
                score += self._normalize(df[career_ppg], 0, 25) * 0.20  # Reduced weight
        
        # Pro Bowl THIS year or recent selection (recency matters)
        pro_bowls = self._find_col(df, ['proof.pro_bowls', 'pro_bowls'])
        if pro_bowls:
            # Recent Pro Bowls matter more
            score += self._normalize(df[pro_bowls].clip(0, 3), 0, 3) * 0.10
        
        # === RECENT 3-YEAR TREND (25 points) ===
        # Shows consistency and current form
        # Use feature extracted stats if available
        recent_performance = self._find_col(df, ['feature.recent_performance_avg', 'proof.career_ppg'])
        if recent_performance:
            score += self._normalize(df[recent_performance], 0, 25) * 0.25
        
        # === CAREER LEGACY (25 points) ===
        # Important for long-term brand deals (Nike, Gatorade lifetime contracts)
        all_pro = self._find_col(df, ['proof.all_pro_selections', 'all_pro_selections'])
        championships = self._find_col(df, ['proof.super_bowl_wins', 'proof.national_championships', 'super_bowl_wins'])
        
        if all_pro:
            score += self._normalize(df[all_pro], 0, 8) * 0.10
        if championships:
            score += self._normalize(df[championships], 0, 4) * 0.10
        if pro_bowls:
            # Career Pro Bowls for legacy (capped at 10)
            score += self._normalize(df[pro_bowls].clip(0, 10), 0, 10) * 0.05
        
        # Ensure minimum baseline (even worst players get some score)
        score = score.clip(lower=0.05)  # Minimum 5% baseline
        
        # Normalize to 0-100 range
        score_normalized = score * 100
        return score_normalized.clip(0, 100)
    
    def _calculate_market_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate market value score (0-100)
        Endorsements weighted heavily - that's where commercial value shines
        """
        score = pd.Series(0.0, index=df.index)
        
        # Contract value (35 points) - APY matters most
        contract_col = self._find_col(df, ['contract_value', 'identity.contract_value', 
                                           'brand.contract_value', 'proximity.contract_value'])
        if contract_col:
            contract_data = pd.to_numeric(df[contract_col], errors='coerce').fillna(0)
            if contract_data.max() > 0:  # Avoid division by zero
                # Use actual max or 500M, whichever is higher (handles mega-contracts like Mahomes $450M)
                contract_max = max(contract_data.max(), 500000000)
                score += self._normalize(contract_data, 0, contract_max) * 0.35
                logger.info(f"Market: Using contract column '{contract_col}' (found {contract_data.notna().sum()}/{len(df)} values, max=${contract_data.max():,.0f})")
            else:
                logger.warning(f"Market: Contract column '{contract_col}' found but all values are 0 or invalid")
        else:
            logger.warning("Market: No contract column found. Searched: contract_value, identity.contract_value, brand.contract_value, proximity.contract_value")
            # List available columns for debugging
            available_cols = [c for c in df.columns if 'contract' in c.lower() or 'salary' in c.lower() or 'value' in c.lower()]
            if available_cols:
                logger.info(f"Market: Available related columns: {available_cols[:10]}")
        
        # Endorsement value (40 points) - HIGHEST weight for commercial value
        # This is where athletes really make money
        endorsement_col = self._find_col(df, ['endorsement_value', 'proximity.endorsement_value', 'endorsements',
                                              'brand.endorsement_value', 'endorsement_annual_value'])
        if endorsement_col:
            endorsement_data = pd.to_numeric(df[endorsement_col], errors='coerce').fillna(0)
            if endorsement_data.max() > 0:
                score += self._normalize(endorsement_data, 0, 20000000) * 0.30  # Up to $20M
                logger.info(f"Market: Using endorsement column '{endorsement_col}' (found {endorsement_data.notna().sum()}/{len(df)} values, max=${endorsement_data.max():,.0f})")
            else:
                logger.warning(f"Market: Endorsement column '{endorsement_col}' found but all values are 0")
        else:
            logger.warning("Market: No endorsement column found. Searched: endorsement_value, proximity.endorsement_value, endorsements")
            # List available columns for debugging
            available_cols = [c for c in df.columns if 'endorsement' in c.lower() or 'sponsor' in c.lower()]
            if available_cols:
                logger.info(f"Market: Available related columns: {available_cols[:10]}")
        
        # Estimated endorsement potential from social reach (25 points) - INCREASED weight
        # If we don't have endorsement data, estimate from social followers
        social_followers = self._find_col(df, ['feature.total_social_reach', 'feat_total_social', 'total_social_followers', 
                                              'brand.total_social_followers', 'brand.instagram_followers', 'instagram_followers'])
        if social_followers:
            social_data = pd.to_numeric(df[social_followers], errors='coerce').fillna(0)
            if social_data.max() > 0:
                # Rule of thumb: 1M followers ≈ $100K endorsement potential per year
                # For stars: 10M+ followers can command $1M+ per year
                estimated_endorsement = social_data / 10  # 1M followers = $100K, 10M = $1M
                score += self._normalize(estimated_endorsement, 0, 15000000) * 0.25  # Increased from 0.10
                logger.info(f"Market: Estimated endorsement from social reach '{social_followers}' (max followers: {social_data.max():,.0f})")
        
        # NIL valuation for college (10 points) - reduced since this is NFL
        nil_col = self._find_col(df, ['nil_valuation', 'proof.nil_valuation', 'nil_deal_count'])
        if nil_col:
            nil_data = pd.to_numeric(df[nil_col], errors='coerce').fillna(0)
            if nil_data.max() > 0:
                score += self._normalize(nil_data, 0, 3000000) * 0.10  # Reduced from 0.25
                logger.info(f"Market: Using NIL column '{nil_col}'")
        
        # === FALLBACK: Estimate from position + performance if no data ===
        # This ensures we have baseline scores even when data is missing
        if score.sum() == 0 or score.max() < 0.1:
            position_col = self._find_col(df, ['position', 'identity.position'])
            perf_score_col = 'gravity.performance_score' if 'gravity.performance_score' in df.columns else None
            
            if position_col:
                # Position-based contract estimates (in millions APY)
                position_contracts = {
                    'QB': 30, 'WR': 15, 'RB': 8, 'TE': 10,
                    'DE': 12, 'CB': 10, 'LB': 8, 'S': 7, 'DT': 8,
                    'EDGE': 12, 'OLB': 8, 'ILB': 7,
                    'C': 5, 'G': 6, 'T': 8, 'OT': 8, 'OG': 6, 'OL': 6,
                    'FB': 3, 'K': 4, 'P': 3, 'LS': 2
                }
                base_contract = df[position_col].map(position_contracts).fillna(3) * 1000000
                
                # Scale by performance if available (0-100 -> 0.5x to 2x multiplier)
                if perf_score_col:
                    perf_scores = pd.to_numeric(df[perf_score_col], errors='coerce').fillna(50)
                    perf_multiplier = 0.5 + (perf_scores / 100) * 1.5
                else:
                    # Use pro bowls as proxy for performance
                    pro_bowls = self._find_col(df, ['proof.pro_bowls', 'pro_bowls'])
                    if pro_bowls:
                        pb_data = pd.to_numeric(df[pro_bowls], errors='coerce').fillna(0)
                        perf_multiplier = 0.5 + (pb_data.clip(0, 10) / 10) * 1.5
                    else:
                        perf_multiplier = 1.0
                
                estimated_contract = base_contract * perf_multiplier
                # Use more realistic max for normalization (top QBs get ~$50M APY)
                contract_max = 50000000  # $50M APY max (more realistic than $500M total)
                contract_contribution = self._normalize(estimated_contract, 0, contract_max) * 0.35
                score += contract_contribution
                
                # Also estimate endorsement from position
                position_endorsements = {
                    'QB': 5000000, 'WR': 2000000, 'RB': 1000000, 'TE': 1500000,
                    'DE': 500000, 'CB': 300000, 'LB': 200000, 'S': 150000,
                    'C': 50000, 'G': 50000, 'T': 50000, 'OT': 50000, 'OG': 50000
                }
                base_endorsement = df[position_col].map(position_endorsements).fillna(50000)
                if perf_score_col:
                    endorsement_multiplier = 0.3 + (perf_scores / 100) * 2.0
                else:
                    endorsement_multiplier = 1.0
                estimated_endorsement = base_endorsement * endorsement_multiplier
                # Use more realistic max for normalization (top stars get ~$20M/year)
                endorsement_max = 20000000  # $20M/year max
                score += self._normalize(estimated_endorsement, 0, endorsement_max) * 0.30
                
                logger.info(f"Market: Estimated contracts/endorsements from position/performance for {len(df)} players")
        
        # Ensure minimum baseline (even worst players get some score)
        score = score.clip(lower=0.05)  # Minimum 5% baseline
        
        # Scale up scores to fill 0-100 range better
        # If max score is low, scale it up proportionally
        score_max = score.max()
        if score_max > 0 and score_max < 0.5:
            # Scale up so top players reach 70-90 range
            scale_factor = 0.8 / score_max  # Target 80% for top players
            score = score * scale_factor
            score = score.clip(0, 1.0)  # Cap at 1.0 (100%)
        
        # Log summary
        non_zero_scores = (score > 0).sum()
        logger.info(f"Market Score Summary: {non_zero_scores}/{len(df)} players have non-zero market scores")
        logger.info(f"  Average market score: {score.mean():.2f}, Max: {score.max():.2f}")
        
        # Normalize to 0-100 range
        score_normalized = score * 100
        return score_normalized.clip(0, 100)
    
    def _calculate_social_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate social influence score (0-100)
        Social reach = Brand reach = Commercial power
        Includes celebrity connection multiplier (Taylor Swift effect)
        """
        score = pd.Series(0.0, index=df.index)
        
        # === DIRECT REACH (45 points) ===
        # Instagram (most valuable for brands - younger demographics)
        instagram_col = self._find_col(df, ['instagram_followers', 'brand.instagram_followers', 'instagram',
                                            'brand.instagram', 'social.instagram_followers'])
        if instagram_col:
            ig_data = pd.to_numeric(df[instagram_col], errors='coerce').fillna(0)
            if ig_data.max() > 0:  # Avoid division by zero
                score += self._normalize(ig_data, 0, 20000000) * 0.25
                logger.info(f"Social: Using Instagram column '{instagram_col}' (found {ig_data.notna().sum()}/{len(df)} values, max={ig_data.max():,.0f})")
            else:
                logger.warning(f"Social: Instagram column '{instagram_col}' found but all values are 0")
        else:
            logger.warning("Social: No Instagram column found. Searched: instagram_followers, brand.instagram_followers")
            # List available columns for debugging
            available_cols = [c for c in df.columns if 'instagram' in c.lower() or 'ig' in c.lower()]
            if available_cols:
                logger.info(f"Social: Available related columns: {available_cols[:10]}")
        
        # TikTok (trending platform, Gen Z)
        tiktok_col = self._find_col(df, ['tiktok_followers', 'brand.tiktok_followers', 'tiktok',
                                        'brand.tiktok', 'social.tiktok_followers'])
        if tiktok_col:
            tt_data = pd.to_numeric(df[tiktok_col], errors='coerce').fillna(0)
            if tt_data.max() > 0:
                score += self._normalize(tt_data, 0, 10000000) * 0.10
                logger.info(f"Social: Using TikTok column '{tiktok_col}' (found {tt_data.notna().sum()}/{len(df)} values)")
            else:
                logger.warning(f"Social: TikTok column '{tiktok_col}' found but all values are 0")
        
        # Twitter/X (news, engagement, older demos)
        twitter_col = self._find_col(df, ['twitter_followers', 'brand.twitter_followers', 'twitter',
                                          'brand.twitter', 'social.twitter_followers', 'x_followers'])
        if twitter_col:
            tw_data = pd.to_numeric(df[twitter_col], errors='coerce').fillna(0)
            if tw_data.max() > 0:
                score += self._normalize(tw_data, 0, 5000000) * 0.10  # Increased from 0.05
                logger.info(f"Social: Using Twitter column '{twitter_col}' (found {tw_data.notna().sum()}/{len(df)} values)")
            else:
                logger.warning(f"Social: Twitter column '{twitter_col}' found but all values are 0")
        
        # Total reach fallback (use if individual platforms not found)
        if not instagram_col and not twitter_col:
            total_reach = self._find_col(df, ['feature.total_social_reach', 'feat_total_social', 'total_social_followers', 
                                              'brand.total_social_followers', 'social.total_followers'])
            if total_reach:
                total_data = pd.to_numeric(df[total_reach], errors='coerce').fillna(0)
                if total_data.max() > 0:
                    score += self._normalize(total_data, 0, 25000000) * 0.45  # Increased weight
                    logger.info(f"Social: Using total reach fallback '{total_reach}' (max={total_data.max():,.0f})")
        
        # Engagement rate multiplier (5 points)
        engagement_col = self._find_col(df, ['instagram_engagement_rate', 'twitter_engagement_rate', 
                                             'feature.avg_engagement_rate', 'brand.engagement_rate'])
        if engagement_col:
            eng_data = pd.to_numeric(df[engagement_col], errors='coerce').fillna(0)
            if eng_data.max() > 0:
                score += self._normalize(eng_data, 0, 10) * 0.05
        
        # === MEDIA PRESENCE (30 points) ===
        # Media mentions (20 points)
        headlines_col = self._find_col(df, ['news_headline_count_30d', 'brand.news_headline_count_30d', 'news_mentions',
                                            'media_mentions', 'headline_count'])
        if headlines_col:
            headlines_data = pd.to_numeric(df[headlines_col], errors='coerce').fillna(0)
            if headlines_data.max() > 0:
                score += self._normalize(headlines_data, 0, 200) * 0.20
                logger.info(f"Social: Using headlines column '{headlines_col}' (found {headlines_data.notna().sum()}/{len(df)} values)")
        
        # Google trends score (10 points)
        trends_col = self._find_col(df, ['google_trends_score', 'brand.google_trends_score', 'media_buzz',
                                         'trends_score'])
        if trends_col:
            trends_data = pd.to_numeric(df[trends_col], errors='coerce').fillna(0)
            if trends_data.max() > 0:
                score += self._normalize(trends_data, 0, 100) * 0.10
        
        # === CELEBRITY CONNECTION MULTIPLIER (25 points) ===
        # This is where Travis Kelce's Taylor Swift relationship matters!
        celebrity_boost = self._calculate_celebrity_boost(df)
        score += celebrity_boost * 0.25
        
        # === FALLBACK: Estimate from position + performance if no data ===
        # This ensures we have baseline scores even when data is missing
        if score.sum() == 0 or score.max() < 0.1:
            position_col = self._find_col(df, ['position', 'identity.position'])
            perf_score_col = 'gravity.performance_score' if 'gravity.performance_score' in df.columns else None
            
            if position_col:
                # Position-based follower estimates (realistic ranges)
                position_followers = {
                    'QB': 2000000, 'WR': 500000, 'RB': 300000, 'TE': 400000,
                    'DE': 200000, 'CB': 150000, 'LB': 100000, 'S': 80000, 'DT': 60000,
                    'EDGE': 200000, 'OLB': 100000, 'ILB': 80000,
                    'C': 50000, 'G': 50000, 'T': 50000, 'OT': 50000, 'OG': 50000, 'OL': 50000,
                    'FB': 30000, 'K': 40000, 'P': 20000, 'LS': 10000
                }
                base_followers = df[position_col].map(position_followers).fillna(50000)
                
                # Scale by performance if available
                if perf_score_col:
                    perf_scores = pd.to_numeric(df[perf_score_col], errors='coerce').fillna(50)
                    perf_multiplier = 0.5 + (perf_scores / 100) * 2.0
                else:
                    # Use pro bowls as proxy
                    pro_bowls = self._find_col(df, ['proof.pro_bowls', 'pro_bowls'])
                    if pro_bowls:
                        pb_data = pd.to_numeric(df[pro_bowls], errors='coerce').fillna(0)
                        perf_multiplier = 0.5 + (pb_data.clip(0, 10) / 10) * 2.0
                    else:
                        perf_multiplier = 1.0
                
                estimated_followers = base_followers * perf_multiplier
                # Use Instagram normalization (most valuable platform)
                # Scale up estimates to be more realistic (multiply by 2-3x for stars)
                follower_contribution = self._normalize(estimated_followers, 0, 20000000) * 0.45
                score += follower_contribution
                
                # Estimate media mentions from position/performance
                if perf_score_col:
                    # High performers get more media attention
                    # Scale based on position too (QBs get more media)
                    position_media_multiplier = df[position_col].map({
                        'QB': 3.0, 'WR': 2.0, 'RB': 1.5, 'TE': 1.5,
                        'DE': 1.2, 'CB': 1.0, 'LB': 0.8, 'S': 0.8,
                        'C': 0.3, 'G': 0.3, 'T': 0.3
                    }).fillna(0.5)
                    media_estimate = (perf_scores / 100) * 50 * position_media_multiplier  # 0-150 mentions for stars
                else:
                    # Baseline by position
                    position_media_baseline = df[position_col].map({
                        'QB': 30, 'WR': 15, 'RB': 10, 'TE': 10,
                        'DE': 8, 'CB': 5, 'LB': 3, 'S': 3,
                        'C': 1, 'G': 1, 'T': 1
                    }).fillna(1)
                    media_estimate = position_media_baseline
                score += self._normalize(media_estimate, 0, 200) * 0.20
                
                logger.info(f"Social: Estimated followers/media from position/performance for {len(df)} players")
        
        # Ensure minimum baseline (even worst players get some score)
        score = score.clip(lower=0.05)  # Minimum 5% baseline
        
        # Scale up scores to fill 0-100 range better
        # If max score is low, scale it up proportionally
        score_max = score.max()
        if score_max > 0 and score_max < 0.5:
            # Scale up so top players reach 70-90 range
            scale_factor = 0.8 / score_max  # Target 80% for top players
            score = score * scale_factor
            score = score.clip(0, 1.0)  # Cap at 1.0 (100%)
        
        # Log summary
        non_zero_scores = (score > 0).sum()
        logger.info(f"Social Score Summary: {non_zero_scores}/{len(df)} players have non-zero social scores")
        logger.info(f"  Average social score: {score.mean():.2f}, Max: {score.max():.2f}")
        
        # Normalize to 0-100 range
        score_normalized = score * 100
        return score_normalized.clip(0, 100)
    
    def _calculate_celebrity_boost(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate celebrity connection boost (0-1)
        
        Factors:
        - Dating A-list celebrities (Taylor Swift level)
        - Viral social moments
        - Hollywood/entertainment crossover
        - Mainstream media presence beyond sports
        """
        boost = pd.Series(0.0, index=df.index)
        
        # Proxy indicators for celebrity status
        
        # Massive social following suggests crossover appeal
        instagram_col = self._find_col(df, ['instagram_followers', 'brand.instagram_followers'])
        if instagram_col:
            # 5M+ followers = significant celebrity crossover
            boost += self._normalize(df[instagram_col], 5000000, 20000000) * 0.4
        
        # High media mentions relative to performance = celebrity effect
        media_col = self._find_col(df, ['news_headline_count_30d', 'brand.news_headline_count_30d'])
        pro_bowls = self._find_col(df, ['pro_bowls', 'proof.pro_bowls'])
        
        if media_col and pro_bowls:
            # If media mentions are disproportionately high vs accolades = celebrity factor
            media_per_accolade = df[media_col] / (df[pro_bowls] + 1)  # +1 to avoid divide by zero
            boost += self._normalize(media_per_accolade, 0, 50) * 0.3
        elif media_col:
            # High media mentions alone
            boost += self._normalize(df[media_col], 50, 300) * 0.3
        
        # Google Trends score suggests mainstream recognition
        trends_col = self._find_col(df, ['google_trends_score', 'brand.google_trends_score'])
        if trends_col:
            boost += self._normalize(df[trends_col], 50, 100) * 0.3
        
        return boost.clip(0, 1)
    
    def _calculate_velocity_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate momentum/velocity score (0-100)
        Growth trajectory = Future commercial value
        """
        score = pd.Series(0.0, index=df.index)
        
        # === SOCIAL GROWTH (35 points) ===
        # Follower growth (20 points)
        growth_col = self._find_col(df, ['velocity.follower_growth_rate_30d', 'follower_growth_rate_30d'])
        if growth_col:
            score += self._normalize(df[growth_col], -10, 100) * 0.20  # Up to 100% growth
        
        # Media buzz surge (15 points)
        media_col = self._find_col(df, ['velocity.media_buzz_surge', 'media_buzz_surge', 'brand.news_headline_count_30d'])
        if media_col:
            score += self._normalize(df[media_col], 0, 150) * 0.15
        
        # === PERFORMANCE TREND (35 points) ===
        # Year-over-year performance change (20 points)
        perf_trend_col = self._find_col(df, ['velocity.performance_trend', 'performance_trend', 'feature.performance_level'])
        perf_numeric = None
        if perf_trend_col:
            # Convert string to numeric if needed
            if df[perf_trend_col].dtype == 'object':
                trend_map = {
                    'declining': 0.2, 'low': 0.3, 'stable': 0.5, 'mid': 0.6,
                    'improving': 0.8, 'high': 0.85, 'elite': 1.0
                }
                perf_numeric = df[perf_trend_col].map(trend_map).fillna(0.5)
            else:
                perf_numeric = self._normalize(df[perf_trend_col], 0, 100)
            score += perf_numeric * 0.20
        
        # Career phase (15 points) - Age-based trajectory
        age_col = self._find_col(df, ['identity.age', 'age'])
        years_col = self._find_col(df, ['identity.years_in_league', 'years_in_league'])
        
        if age_col:
            # Optimal commercial age: 24-29 (rising or peak)
            career_phase = df[age_col].apply(self._calculate_career_phase_score)
            score += career_phase * 0.15
        
        # === MARKET MOMENTUM (30 points) ===
        # Contract year/free agency (15 points)
        free_agency_col = self._find_col(df, ['risk.free_agency_year', 'free_agency_year'])
        current_year = datetime.now().year
        if free_agency_col:
            # Convert to numeric, handling non-numeric values
            free_agency_years = pd.to_numeric(df[free_agency_col], errors='coerce')
            years_to_fa = free_agency_years - current_year
            # Contract year (0-1 years) = high momentum
            fa_momentum = years_to_fa.apply(lambda x: 1.0 if pd.notna(x) and 0 <= x <= 1 else 0.5 if pd.notna(x) and x <= 2 else 0.3)
            score += fa_momentum * 0.15
        
        # Brand trajectory (15 points)
        # Combine social growth + performance trend
        if growth_col and perf_trend_col and perf_numeric is not None:
            combined_momentum = (self._normalize(df[growth_col], -10, 100) + perf_numeric) / 2
            score += combined_momentum * 0.15
        elif growth_col:
            # If only growth data available, use it
            score += self._normalize(df[growth_col], -10, 100) * 0.15
        elif perf_numeric is not None:
            # If only performance trend available, use it
            score += perf_numeric * 0.15
        
        # Ensure minimum baseline (even worst players get some score)
        score = score.clip(lower=0.05)  # Minimum 5% baseline
        
        # Normalize to 0-100 range
        score_normalized = score * 100
        return score_normalized.clip(0, 100)
    
    def _calculate_career_phase_score(self, age):
        """
        Calculate career phase score based on age (0-1)
        Commercial value peaks at different ages by position
        """
        if pd.isna(age):
            return 0.5
        
        # Optimal commercial age: 24-29
        if 24 <= age <= 29:
            return 1.0  # Peak commercial value
        elif 22 <= age < 24:
            return 0.8  # Rising star
        elif 30 <= age <= 32:
            return 0.7  # Still strong, slight decline
        elif age < 22:
            return 0.6  # Unproven
        elif 33 <= age <= 35:
            return 0.4  # Declining
        else:
            return 0.2  # Limited upside
    
    def _calculate_risk_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate risk score (0-100, higher = more risk)
        Severity-scaled: Minor incidents hurt less, major scandals devastate commercial value
        
        Risk breakdown:
        - Injury risk: 40% (reliability for endorsements)
        - Off-field incidents: 50% (brand safety - CRITICAL)
        - Age risk: 10% (declining performance)
        """
        risk = pd.Series(0.0, index=df.index)
        
        # === INJURY RISK (40 points) ===
        # Games missed career (15 points)
        games_missed_career = self._find_col(df, ['games_missed_career', 'risk.games_missed_career', 'career_games_missed'])
        if games_missed_career:
            risk += self._normalize(df[games_missed_career], 0, 80) * 0.15
        
        # Games missed last season (15 points)
        games_missed_recent = self._find_col(df, ['games_missed_last_season', 'risk.games_missed_last_season', 'recent_games_missed'])
        if games_missed_recent:
            risk += self._normalize(df[games_missed_recent], 0, 17) * 0.15
        
        # Current injury status (10 points) - BIG impact if out NOW
        injury_status = self._find_col(df, ['current_injury_status', 'risk.current_injury_status', 'injury_status'])
        if injury_status:
            # If status contains "Out", "Injured", "IR" = 10 points
            is_injured = df[injury_status].astype(str).str.contains('Out|Injured|IR|Questionable', case=False, na=False)
            risk += is_injured.astype(float) * 0.10
        
        # Fallback: Use injury_risk_score if individual components not available
        injury_score_col = self._find_col(df, ['injury_risk_score', 'risk.injury_risk_score'])
        if injury_score_col and not games_missed_career:
            risk += self._normalize(df[injury_score_col], 0, 100) * 0.40
        
        # === OFF-FIELD RISK (50 points) ===
        # This is CRITICAL for brand safety and commercial value
        
        # Controversy count with severity scaling (35 points)
        controversies = self._find_col(df, ['controversies', 'risk.controversies', 'controversy_count'])
        arrests = self._find_col(df, ['arrests', 'risk.arrests', 'arrest_count'])
        suspensions = self._find_col(df, ['suspensions', 'risk.suspensions', 'suspension_count'])
        fines = self._find_col(df, ['fines', 'risk.fines', 'fine_count'])
        
        incident_risk = pd.Series(0.0, index=df.index)
        
        if controversies:
            # Each controversy = base 10 points, but scales with severity
            # Domestic violence, assault = high severity
            # DUI, marijuana = medium severity
            # Multiple incidents = compounding penalty
            # #region agent log
            try:
                import json
                import os
                log_path = '/Users/robcseals/Gravity_Score/.cursor/debug.log'
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                raw_col = df[controversies]
                with open(log_path, 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"pre-fix","hypothesisId":"A","location":"data_pipeline.py:1416","message":"Before fillna - controversy column type and sample","data":{"column_name":controversies,"dtype":str(raw_col.dtype),"sample_values":str(raw_col.head(5).tolist()),"has_nan":bool(raw_col.isna().any())},"timestamp":int(datetime.now().timestamp()*1000)}) + '\n')
            except Exception as e:
                pass
            # #endregion
            # Convert to numeric first, handling non-numeric values (like 'Unknown')
            controversy_count = pd.to_numeric(df[controversies], errors='coerce').fillna(0)
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"pre-fix","hypothesisId":"A","location":"data_pipeline.py:1417","message":"After numeric conversion - controversy_count type and sample","data":{"dtype":str(controversy_count.dtype),"sample_values":str(controversy_count.head(5).tolist()),"is_numeric":bool(pd.api.types.is_numeric_dtype(controversy_count))},"timestamp":int(datetime.now().timestamp()*1000)}) + '\n')
            except Exception as e:
                pass
            # #endregion
            
            # Base risk from count
            incident_risk += self._normalize(controversy_count, 0, 5) * 0.20
            
            # Multiplier for repeat offenders
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"pre-fix","hypothesisId":"B","location":"data_pipeline.py:1422","message":"Before apply lambda - final check","data":{"dtype":str(controversy_count.dtype),"is_numeric":bool(pd.api.types.is_numeric_dtype(controversy_count)),"min_val":float(controversy_count.min()) if pd.api.types.is_numeric_dtype(controversy_count) else "N/A","max_val":float(controversy_count.max()) if pd.api.types.is_numeric_dtype(controversy_count) else "N/A"},"timestamp":int(datetime.now().timestamp()*1000)}) + '\n')
            except Exception as e:
                pass
            # #endregion
            repeat_multiplier = controversy_count.apply(lambda x: 1.0 if pd.notna(x) and x <= 1 else 1.3 if pd.notna(x) and x <= 2 else 1.5 if pd.notna(x) and x <= 3 else 2.0 if pd.notna(x) else 1.0)
            incident_risk = incident_risk * repeat_multiplier
        
        if arrests:
            # Arrests are MAJOR red flags for brands
            arrest_count = pd.to_numeric(df[arrests], errors='coerce').fillna(0)
            incident_risk += self._normalize(arrest_count, 0, 3) * 0.25
        
        if suspensions:
            # Suspensions = lost marketing time + scandal
            suspension_count = pd.to_numeric(df[suspensions], errors='coerce').fillna(0)
            incident_risk += self._normalize(suspension_count, 0, 3) * 0.15
        
        if fines:
            # Fines indicate rule-breaking behavior
            fine_count = pd.to_numeric(df[fines], errors='coerce').fillna(0)
            incident_risk += self._normalize(fine_count, 0, 5) * 0.10
        
        risk += incident_risk.clip(0, 0.50)  # Cap at 50 points
        
        # Fallback: Use controversy_risk_score if individual components not available
        controversy_score_col = self._find_col(df, ['controversy_risk_score', 'risk.controversy_risk_score'])
        if controversy_score_col and not controversies:
            risk += self._normalize(df[controversy_score_col], 0, 100) * 0.50
        
        # === AGE RISK (10 points) ===
        # Younger = unproven, Older = declining
        age_col = self._find_col(df, ['age', 'identity.age'])
        if age_col:
            # Optimal age for commercial value: 25-30
            age_risk = df[age_col].apply(lambda x: 
                0 if pd.isna(x) else
                abs(27 - x) * 3 if x < 27 else  # Young = moderate risk
                abs(27 - x) * 5 if x > 30 else  # Old = higher risk
                0  # 27 = optimal
            )
            risk += self._normalize(age_risk, 0, 50) * 0.10
        
        return (risk * 100).clip(0, 100)
    
    def _find_col(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """
        Find first existing column from candidates.
        Handles both nested (brand.instagram_followers) and flattened (instagram_followers) names.
        """
        for col in candidates:
            # Try exact match first
            if col in df.columns:
                return col
            # Try without prefix (flattened version)
            simple = col.split('.')[-1]
            if simple in df.columns:
                return simple
            # Try with underscore instead of dot
            underscore = col.replace('.', '_')
            if underscore in df.columns:
                return underscore
        return None
    
    def _normalize(self, series: pd.Series, min_val: float, max_val: float) -> pd.Series:
        """Normalize series to 0-1 range, handling edge cases"""
        # Ensure series is numeric
        series = pd.to_numeric(series, errors='coerce').fillna(0)
        
        if max_val == min_val:
            # All values are the same, return 0.5 (neutral)
            return pd.Series(0.5, index=series.index)
        
        denominator = max_val - min_val
        if denominator == 0:
            return pd.Series(0.5, index=series.index)
        
        # Normalize: (value - min) / (max - min)
        normalized = ((series - min_val) / denominator).clip(0, 1)
        
        # Fill any remaining NaN with 0
        return normalized.fillna(0)


# ============================================================================
# COMPLETE PIPELINE
# ============================================================================

class GravityPipeline:
    """Complete data processing pipeline"""
    
    def __init__(self, max_years: int = 3):
        self.flattener = DataFlattener(max_years=max_years)
        self.imputer = DataImputer()
        self.feature_extractor = FeatureExtractor()
        self.scorer = GravityScoreCalculator()
    
    def process(self, input_data: Any, output_format: str = 'dataframe') -> Any:
        """
        Run complete pipeline
        
        Args:
            input_data: Raw player data (JSON, dict, DataFrame, or CSV path)
            output_format: 'dataframe', 'csv', or 'json'
            
        Returns:
            Processed data in requested format
        """
        logger.info("🚀 Starting Gravity Pipeline...")
        
        # Step 1: Load data
        if isinstance(input_data, str):
            # File path
            if input_data.endswith('.csv'):
                df = pd.read_csv(input_data)
            elif input_data.endswith('.json'):
                df = pd.read_json(input_data)
            else:
                raise ValueError(f"Unsupported file format: {input_data}")
        elif isinstance(input_data, pd.DataFrame):
            df = input_data
        elif isinstance(input_data, list):
            # List of player dicts
            df = pd.DataFrame(input_data)
        else:
            raise ValueError(f"Unsupported input type: {type(input_data)}")
        
        logger.info(f"📊 Loaded {len(df)} players")
        
        # Step 2: Flatten nested data
        logger.info("🔄 Flattening nested data...")
        df = self.flattener.flatten_dataframe(df)
        
        # Step 3: Impute missing values
        logger.info("🔧 Imputing missing data...")
        df = self.imputer.impute_data(df)
        
        # Step 4: Extract features
        logger.info("⚙️  Extracting features...")
        df = self.feature_extractor.extract_features(df)
        
        # Step 5: Calculate Gravity Scores
        logger.info("⚡ Calculating Gravity Scores...")
        df = self.scorer.calculate_gravity_scores(df)
        
        logger.info(f"✅ Pipeline complete! {len(df)} players processed")
        logger.info(f"   Top Score: {df['gravity_score'].max():.1f}")
        logger.info(f"   Avg Score: {df['gravity_score'].mean():.1f}")
        logger.info(f"   Columns: {len(df.columns)}")
        
        # Return in requested format
        if output_format == 'dataframe':
            return df
        elif output_format == 'csv':
            return df.to_csv(index=False)
        elif output_format == 'json':
            return df.to_json(orient='records')
        else:
            return df

