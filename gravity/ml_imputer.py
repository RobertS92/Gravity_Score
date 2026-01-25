#!/usr/bin/env python3
"""
ML-Based Imputation Layer
==========================

Intelligent imputation using XGBoost to predict missing values.
Falls back to rule-based imputation if ML confidence is low.

Author: Gravity Score Team
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import pickle
import os
from pathlib import Path

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None

logger = logging.getLogger(__name__)


# ============================================================================
# ML IMPUTATION ENGINE
# ============================================================================

class MLImputer:
    """
    Machine learning-based imputation for missing player data.
    
    Uses XGBoost to learn complex relationships between features
    and predict missing values with confidence scores.
    """
    
    def __init__(self, models_dir: str = "models/imputation", confidence_threshold: float = 0.7):
        """
        Initialize ML Imputer
        
        Args:
            models_dir: Directory to save/load trained models
            confidence_threshold: Minimum confidence to use ML prediction (vs rule-based)
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.confidence_threshold = confidence_threshold
        self.trained_models = {}
        self.feature_columns = {}
        
        # Position-based defaults (fallback)
        self.position_defaults = {
            # NFL
            'QB': {'height': 74, 'weight': 220, 'age': 26},
            'RB': {'height': 70, 'weight': 215, 'age': 25},
            'WR': {'height': 72, 'weight': 200, 'age': 26},
            'TE': {'height': 77, 'weight': 250, 'age': 27},
            'OL': {'height': 77, 'weight': 310, 'age': 27},
            'DL': {'height': 76, 'weight': 290, 'age': 27},
            'LB': {'height': 73, 'weight': 240, 'age': 26},
            'DB': {'height': 71, 'weight': 195, 'age': 25},
            'S': {'height': 72, 'weight': 205, 'age': 26},
            'CB': {'height': 71, 'weight': 190, 'age': 25},
            
            # NBA
            'PG': {'height': 74, 'weight': 190, 'age': 26},
            'SG': {'height': 77, 'weight': 205, 'age': 26},
            'SF': {'height': 79, 'weight': 220, 'age': 27},
            'PF': {'height': 81, 'weight': 230, 'age': 27},
            'C': {'height': 83, 'weight': 250, 'age': 28},
        }
    
    def train_imputation_models(self, df: pd.DataFrame, targets: List[str] = None) -> Dict[str, Any]:
        """
        Train imputation models for specified target fields
        
        Args:
            df: Training data (must have no missing values for targets)
            targets: List of fields to train imputation models for
            
        Returns:
            Dictionary with training results
        """
        if not XGBOOST_AVAILABLE:
            logger.error("XGBoost not available. Install with: pip install xgboost")
            return {"error": "XGBoost not installed"}
        
        if targets is None:
            targets = [
                'identity.age',
                'identity.height', 
                'identity.weight',
                'identity.contract_value',
                'identity.years_in_league',
                'brand.instagram_followers',
                'brand.twitter_followers',
                'proof.career_points',
                'proof.career_yards'
            ]
        
        results = {}
        
        for target in targets:
            if target not in df.columns:
                logger.warning(f"Target {target} not in DataFrame, skipping")
                continue
            
            # Skip if too many missing values
            if df[target].isna().sum() / len(df) > 0.5:
                logger.warning(f"Target {target} has >50% missing, skipping training")
                continue
            
            logger.info(f"Training imputation model for {target}...")
            
            try:
                model_result = self._train_single_imputer(df, target)
                results[target] = model_result
                
                # Save model
                model_path = self.models_dir / f"{target.replace('.', '_')}_imputer.pkl"
                with open(model_path, 'wb') as f:
                    pickle.dump({
                        'model': model_result['model'],
                        'features': model_result['features'],
                        'target': target,
                        'performance': model_result['performance'],
                        'is_classifier': model_result['is_classifier']
                    }, f)
                
                logger.info(f"✅ {target} imputer trained: {model_result['performance']}")
                
            except Exception as e:
                logger.error(f"Failed to train imputer for {target}: {e}")
                results[target] = {"error": str(e)}
        
        return results
    
    def _train_single_imputer(self, df: pd.DataFrame, target: str) -> Dict[str, Any]:
        """Train a single imputation model"""
        
        # Get rows where target is not missing
        train_df = df[df[target].notna()].copy()
        
        if len(train_df) < 50:
            raise ValueError(f"Insufficient training data for {target} ({len(train_df)} samples)")
        
        # Determine if regression or classification
        is_classifier = self._is_categorical_target(train_df[target])
        
        # Select features
        features = self._select_features(train_df, target)
        
        if not features:
            raise ValueError(f"No valid features found for {target}")
        
        X = train_df[features].copy()
        y = train_df[target].copy()
        
        # Handle categorical target
        if is_classifier:
            # Encode categorical target
            from sklearn.preprocessing import LabelEncoder
            le = LabelEncoder()
            y = le.fit_transform(y.astype(str))
            label_encoder = le
        else:
            label_encoder = None
        
        # Fill missing values in features (can't train on missing features)
        X = X.fillna(X.median() if not is_classifier else X.mode().iloc[0] if len(X.mode()) > 0 else 0)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train XGBoost model
        if is_classifier:
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                eval_metric='mlogloss'
            )
        else:
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                eval_metric='rmse'
            )
        
        model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = model.predict(X_val)
        
        if is_classifier:
            performance = {
                'accuracy': accuracy_score(y_val, y_pred),
                'samples': len(train_df)
            }
        else:
            performance = {
                'mae': mean_absolute_error(y_val, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_val, y_pred)),
                'samples': len(train_df)
            }
        
        # Get feature importance
        feature_importance = dict(zip(features, model.feature_importances_))
        
        return {
            'model': model,
            'features': features,
            'target': target,
            'performance': performance,
            'feature_importance': feature_importance,
            'is_classifier': is_classifier,
            'label_encoder': label_encoder
        }
    
    def _is_categorical_target(self, series: pd.Series) -> bool:
        """Determine if target is categorical"""
        # Check data type
        if series.dtype == 'object':
            return True
        
        # Check number of unique values
        unique_count = series.nunique()
        if unique_count < 20 and unique_count < len(series) * 0.05:
            return True
        
        return False
    
    def _select_features(self, df: pd.DataFrame, target: str) -> List[str]:
        """
        Intelligently select features for imputation
        
        Selects features that:
        1. Are not the target itself
        2. Have reasonable correlation with target
        3. Have low missing value rate
        """
        # Core features that are usually available
        core_features = [
            'position', 'identity.position',
            'team', 'identity.team',
            'identity.draft_year', 'identity.years_in_league',
            'identity.class_year', 'identity.eligibility_year'
        ]
        
        # Add numeric features with low missingness
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        valid_numeric = [col for col in numeric_cols 
                        if col != target and df[col].notna().sum() / len(df) > 0.7]
        
        # Combine features
        all_candidate_features = core_features + valid_numeric
        
        # Filter to features that actually exist in the DataFrame
        features = [f for f in all_candidate_features if f in df.columns]
        
        # Remove target from features
        features = [f for f in features if f != target]
        
        # Limit features to prevent overfitting
        if len(features) > 50:
            # Calculate correlation with target for numeric features
            correlations = {}
            for feat in features:
                if feat in numeric_cols:
                    try:
                        corr = df[[feat, target]].corr().iloc[0, 1]
                        if not np.isnan(corr):
                            correlations[feat] = abs(corr)
                    except:
                        pass
            
            # Keep top 50 most correlated features + core features
            sorted_feats = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
            top_feats = [f for f, _ in sorted_feats[:40]]
            core_in_df = [f for f in core_features if f in features]
            features = list(set(top_feats + core_in_df))[:50]
        
        return features
    
    def load_models(self):
        """Load all trained imputation models from disk"""
        if not self.models_dir.exists():
            logger.warning(f"Models directory {self.models_dir} does not exist")
            return
        
        model_files = list(self.models_dir.glob("*_imputer.pkl"))
        
        for model_file in model_files:
            try:
                with open(model_file, 'rb') as f:
                    model_data = pickle.load(f)
                    target = model_data['target']
                    self.trained_models[target] = model_data
                    logger.info(f"Loaded imputer for {target}")
            except Exception as e:
                logger.error(f"Failed to load {model_file}: {e}")
        
        logger.info(f"✅ Loaded {len(self.trained_models)} imputation models")
    
    def impute_dataframe(self, df: pd.DataFrame, use_ml: bool = True) -> pd.DataFrame:
        """
        Impute missing values in DataFrame
        
        Args:
            df: DataFrame with missing values
            use_ml: If True, use ML models; if False, use rule-based only
            
        Returns:
            DataFrame with imputed values
        """
        df = df.copy()
        
        if use_ml and XGBOOST_AVAILABLE and self.trained_models:
            logger.info("🤖 Using ML-based imputation...")
            df = self._ml_impute(df)
        else:
            if not XGBOOST_AVAILABLE:
                logger.warning("XGBoost not available, using rule-based imputation")
            logger.info("📏 Using rule-based imputation...")
        
        # Always apply rule-based imputation as backup
        df = self._rule_based_impute(df)
        
        return df
    
    def _ml_impute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply ML-based imputation for all trained models"""
        
        for target, model_data in self.trained_models.items():
            if target not in df.columns:
                continue
            
            # Find rows with missing target
            missing_mask = df[target].isna()
            n_missing = missing_mask.sum()
            
            if n_missing == 0:
                continue
            
            logger.info(f"  Imputing {n_missing} missing values for {target}...")
            
            try:
                # Prepare features
                features = model_data['features']
                X_missing = df.loc[missing_mask, features].copy()
                
                # Fill missing values in features
                X_missing = X_missing.fillna(
                    X_missing.median() if not model_data['is_classifier'] 
                    else X_missing.mode().iloc[0] if len(X_missing.mode()) > 0 else 0
                )
                
                if len(X_missing) > 0:
                    # Predict
                    model = model_data['model']
                    predictions = model.predict(X_missing)
                    
                    # For classifiers, decode labels
                    if model_data['is_classifier'] and model_data.get('label_encoder'):
                        predictions = model_data['label_encoder'].inverse_transform(predictions)
                    
                    # Calculate confidence (for regressors, use std of tree predictions)
                    if hasattr(model, 'get_booster'):
                        # For XGBoost, we can estimate confidence from tree variance
                        # Simplified: use model's prediction as-is with confidence based on performance
                        if model_data['is_classifier']:
                            confidence = model_data['performance'].get('accuracy', 0.5)
                        else:
                            # For regression, confidence based on MAE
                            mae = model_data['performance'].get('mae', float('inf'))
                            # Higher MAE = lower confidence
                            confidence = max(0.1, 1.0 - (mae / 10.0))
                    else:
                        confidence = 0.5
                    
                    # Apply predictions if confidence is high enough
                    if confidence >= self.confidence_threshold:
                        df.loc[missing_mask, target] = predictions
                        logger.info(f"    ✅ ML imputed {n_missing} values (confidence: {confidence:.2f})")
                    else:
                        logger.info(f"    ⚠️  Low confidence ({confidence:.2f}), skipping ML imputation")
                
            except Exception as e:
                logger.error(f"  Failed to ML impute {target}: {e}")
        
        return df
    
    def _rule_based_impute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rule-based imputation as fallback
        
        Uses position-based defaults and simple heuristics
        """
        # CFB-SPECIFIC IMPUTATIONS (applied first for college players)
        # These are deterministic and highly accurate for college data
        df = self._impute_conference_from_team(df)
        df = self._impute_age_from_class_year(df)
        df = self._impute_eligibility_from_class_year(df)
        df = self._impute_cfb_market_value(df)
        
        # NFL-SPECIFIC IMPUTATIONS (for professional players)
        df = self._impute_nfl_conference_from_team(df)
        df = self._impute_nfl_contract_value(df)
        
        # Impute age
        if 'identity.age' in df.columns:
            # From birth_date
            if 'identity.birth_date' in df.columns:
                df.loc[df['identity.age'].isna(), 'identity.age'] = df.loc[df['identity.age'].isna()].apply(
                    lambda row: self._calculate_age_from_birthdate(row.get('identity.birth_date')),
                    axis=1
                )
            
            # From draft_year (professional players)
            if 'identity.draft_year' in df.columns:
                current_year = pd.Timestamp.now().year
                df.loc[df['identity.age'].isna(), 'identity.age'] = df.loc[df['identity.age'].isna()].apply(
                    lambda row: current_year - int(row['identity.draft_year']) + 22 
                    if pd.notna(row.get('identity.draft_year')) and str(row.get('identity.draft_year')).isdigit()
                    else None,
                    axis=1
                )
            
            # Position-based default
            position_col = 'position' if 'position' in df.columns else 'identity.position'
            if position_col in df.columns:
                for pos, defaults in self.position_defaults.items():
                    mask = (df[position_col] == pos) & df['identity.age'].isna()
                    df.loc[mask, 'identity.age'] = defaults['age']
        
        # Impute height
        if 'identity.height' in df.columns:
            position_col = 'position' if 'position' in df.columns else 'identity.position'
            if position_col in df.columns:
                for pos, defaults in self.position_defaults.items():
                    mask = (df[position_col] == pos) & df['identity.height'].isna()
                    df.loc[mask, 'identity.height'] = defaults['height']
        
        # Impute weight
        if 'identity.weight' in df.columns:
            position_col = 'position' if 'position' in df.columns else 'identity.position'
            if position_col in df.columns:
                for pos, defaults in self.position_defaults.items():
                    mask = (df[position_col] == pos) & df['identity.weight'].isna()
                    df.loc[mask, 'identity.weight'] = defaults['weight']
        
        # Impute years_in_league
        if 'identity.years_in_league' in df.columns and 'identity.draft_year' in df.columns:
            current_year = pd.Timestamp.now().year
            df.loc[df['identity.years_in_league'].isna(), 'identity.years_in_league'] = df.loc[
                df['identity.years_in_league'].isna()
            ].apply(
                lambda row: current_year - int(row['identity.draft_year']) 
                if pd.notna(row.get('identity.draft_year')) and str(row.get('identity.draft_year')).isdigit()
                else 0,
                axis=1
            )
        
        # Impute numeric fields with 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if df[col].isna().sum() > 0:
                # Use 0 for counts and stats
                if any(x in col for x in ['count', 'career_', 'games', 'points', 'yards', 'followers']):
                    df[col] = df[col].fillna(0)
                # Use median for rates and percentages
                elif 'pct' in col or 'rate' in col:
                    median_val = df[col].median()
                    if not np.isnan(median_val):
                        df[col] = df[col].fillna(median_val)
                    else:
                        df[col] = df[col].fillna(0)
        
        # Impute categorical fields with 'Unknown'
        categorical_cols = df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            df[col] = df[col].fillna('Unknown')
        
        return df
    
    def _calculate_age_from_birthdate(self, birthdate: Any) -> Optional[int]:
        """Calculate age from birthdate string"""
        if pd.isna(birthdate) or birthdate == '':
            return None
        
        try:
            birth_dt = pd.to_datetime(birthdate)
            today = pd.Timestamp.now()
            age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
            return age if 15 <= age <= 50 else None
        except:
            return None
    
    def _impute_age_from_class_year(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute age based on class_year for college players
        
        Typical ages:
        - Freshman: 18-19
        - Sophomore: 19-20
        - Junior: 20-21
        - Senior: 21-22
        - RS Freshman: 19-20
        - RS Senior: 22-23
        """
        if 'identity.class_year' not in df.columns or 'identity.age' not in df.columns:
            return df
        
        df = df.copy()
        
        # Class year to age mapping (using typical age)
        class_year_age_map = {
            'Freshman': 18,
            'FR': 18,
            'Sophomore': 19,
            'SO': 19,
            'Junior': 20,
            'JR': 20,
            'Senior': 21,
            'SR': 21,
            'Redshirt Freshman': 19,
            'RS FR': 19,
            'Redshirt Sophomore': 20,
            'RS SO': 20,
            'Redshirt Junior': 21,
            'RS JR': 21,
            'Redshirt Senior': 22,
            'RS SR': 22,
            'Fifth Year': 22,
            '5th Year': 22
        }
        
        # Impute age where missing
        missing_age = df['identity.age'].isna()
        
        if missing_age.sum() > 0:
            for class_year, typical_age in class_year_age_map.items():
                mask = missing_age & (df['identity.class_year'].astype(str).str.contains(class_year, case=False, na=False))
                if mask.sum() > 0:
                    df.loc[mask, 'identity.age'] = typical_age
                    logger.info(f"  Imputed age for {mask.sum()} {class_year} players (age={typical_age})")
        
        return df
    
    def _impute_eligibility_from_class_year(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute eligibility_year based on class_year
        
        Eligibility rules:
        - Freshman: 4 years remaining
        - Sophomore: 3 years remaining  
        - Junior: 2 years remaining
        - Senior: 1 year remaining
        - RS players: Same as non-RS (redshirt year doesn't count)
        """
        if 'identity.class_year' not in df.columns or 'identity.eligibility_year' not in df.columns:
            return df
        
        df = df.copy()
        
        # Class year to eligibility mapping
        class_to_eligibility = {
            'Freshman': 4,
            'FR': 4,
            'Redshirt Freshman': 4,
            'RS FR': 4,
            'Sophomore': 3,
            'SO': 3,
            'Redshirt Sophomore': 3,
            'RS SO': 3,
            'Junior': 2,
            'JR': 2,
            'Redshirt Junior': 2,
            'RS JR': 2,
            'Senior': 1,
            'SR': 1,
            'Redshirt Senior': 1,
            'RS SR': 1,
            'Fifth Year': 0,  # Last year
            '5th Year': 0
        }
        
        # Impute eligibility where missing
        missing_eligibility = df['identity.eligibility_year'].isna()
        
        if missing_eligibility.sum() > 0:
            for class_year, eligibility in class_to_eligibility.items():
                mask = missing_eligibility & (df['identity.class_year'].astype(str).str.contains(class_year, case=False, na=False))
                if mask.sum() > 0:
                    df.loc[mask, 'identity.eligibility_year'] = eligibility
                    logger.info(f"  Imputed eligibility for {mask.sum()} {class_year} players (eligibility={eligibility} years)")
        
        return df
    
    def _impute_conference_from_team(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute conference based on team name (deterministic mapping)
        
        Uses official conference membership for 2024-2025 season
        """
        if 'identity.conference' not in df.columns:
            return df
        
        df = df.copy()
        
        # Conference dictionary (comprehensive team mapping)
        TEAM_TO_CONFERENCE = {
            # SEC
            'Alabama': 'SEC', 'ALA': 'SEC', 'Alabama Crimson Tide': 'SEC',
            'Arkansas': 'SEC', 'ARK': 'SEC', 'Arkansas Razorbacks': 'SEC',
            'Auburn': 'SEC', 'AUB': 'SEC', 'Auburn Tigers': 'SEC',
            'Florida': 'SEC', 'FLA': 'SEC', 'Florida Gators': 'SEC',
            'Georgia': 'SEC', 'UGA': 'SEC', 'Georgia Bulldogs': 'SEC',
            'Kentucky': 'SEC', 'UK': 'SEC', 'Kentucky Wildcats': 'SEC',
            'LSU': 'SEC', 'LSU Tigers': 'SEC',
            'Mississippi': 'SEC', 'MISS': 'SEC', 'Ole Miss': 'SEC', 'Ole Miss Rebels': 'SEC',
            'Mississippi State': 'SEC', 'MSST': 'SEC', 'Mississippi State Bulldogs': 'SEC',
            'Missouri': 'SEC', 'MIZZ': 'SEC', 'Missouri Tigers': 'SEC',
            'Oklahoma': 'SEC', 'OKLA': 'SEC', 'Oklahoma Sooners': 'SEC',
            'South Carolina': 'SEC', 'SCAR': 'SEC', 'South Carolina Gamecocks': 'SEC',
            'Tennessee': 'SEC', 'TENN': 'SEC', 'Tennessee Volunteers': 'SEC',
            'Texas': 'SEC', 'TEX': 'SEC', 'Texas Longhorns': 'SEC',
            'Texas A&M': 'SEC', 'TAMU': 'SEC', 'Texas A&M Aggies': 'SEC',
            'Vanderbilt': 'SEC', 'VAN': 'SEC', 'Vanderbilt Commodores': 'SEC',
            
            # Big Ten
            'Illinois': 'Big Ten', 'ILL': 'Big Ten', 'Illinois Fighting Illini': 'Big Ten',
            'Indiana': 'Big Ten', 'IU': 'Big Ten', 'Indiana Hoosiers': 'Big Ten',
            'Iowa': 'Big Ten', 'IOWA': 'Big Ten', 'Iowa Hawkeyes': 'Big Ten',
            'Maryland': 'Big Ten', 'MD': 'Big Ten', 'Maryland Terrapins': 'Big Ten',
            'Michigan': 'Big Ten', 'MICH': 'Big Ten', 'Michigan Wolverines': 'Big Ten',
            'Michigan State': 'Big Ten', 'MSU': 'Big Ten', 'Michigan State Spartans': 'Big Ten',
            'Minnesota': 'Big Ten', 'MINN': 'Big Ten', 'Minnesota Golden Gophers': 'Big Ten',
            'Nebraska': 'Big Ten', 'NEB': 'Big Ten', 'Nebraska Cornhuskers': 'Big Ten',
            'Northwestern': 'Big Ten', 'NW': 'Big Ten', 'Northwestern Wildcats': 'Big Ten',
            'Ohio State': 'Big Ten', 'OSU': 'Big Ten', 'Ohio State Buckeyes': 'Big Ten',
            'Oregon': 'Big Ten', 'ORE': 'Big Ten', 'Oregon Ducks': 'Big Ten',
            'Penn State': 'Big Ten', 'PSU': 'Big Ten', 'Penn State Nittany Lions': 'Big Ten',
            'Purdue': 'Big Ten', 'PUR': 'Big Ten', 'Purdue Boilermakers': 'Big Ten',
            'Rutgers': 'Big Ten', 'RUTG': 'Big Ten', 'Rutgers Scarlet Knights': 'Big Ten',
            'USC': 'Big Ten', 'USC Trojans': 'Big Ten', 'Southern California': 'Big Ten',
            'UCLA': 'Big Ten', 'UCLA Bruins': 'Big Ten',
            'Washington': 'Big Ten', 'WASH': 'Big Ten', 'Washington Huskies': 'Big Ten',
            'Wisconsin': 'Big Ten', 'WIS': 'Big Ten', 'Wisconsin Badgers': 'Big Ten',
            
            # Big 12
            'Arizona': 'Big 12', 'ARIZ': 'Big 12', 'Arizona Wildcats': 'Big 12',
            'Arizona State': 'Big 12', 'ASU': 'Big 12', 'Arizona State Sun Devils': 'Big 12',
            'Baylor': 'Big 12', 'BAY': 'Big 12', 'Baylor Bears': 'Big 12',
            'BYU': 'Big 12', 'BYU Cougars': 'Big 12', 'Brigham Young': 'Big 12',
            'Cincinnati': 'Big 12', 'CIN': 'Big 12', 'Cincinnati Bearcats': 'Big 12',
            'Colorado': 'Big 12', 'COLO': 'Big 12', 'Colorado Buffaloes': 'Big 12',
            'Houston': 'Big 12', 'HOU': 'Big 12', 'Houston Cougars': 'Big 12',
            'Iowa State': 'Big 12', 'ISU': 'Big 12', 'Iowa State Cyclones': 'Big 12',
            'Kansas': 'Big 12', 'KU': 'Big 12', 'Kansas Jayhawks': 'Big 12',
            'Kansas State': 'Big 12', 'KSU': 'Big 12', 'Kansas State Wildcats': 'Big 12',
            'Oklahoma State': 'Big 12', 'OKST': 'Big 12', 'Oklahoma State Cowboys': 'Big 12',
            'TCU': 'Big 12', 'TCU Horned Frogs': 'Big 12',
            'Texas Tech': 'Big 12', 'TTU': 'Big 12', 'Texas Tech Red Raiders': 'Big 12',
            'UCF': 'Big 12', 'UCF Knights': 'Big 12', 'Central Florida': 'Big 12',
            'West Virginia': 'Big 12', 'WVU': 'Big 12', 'West Virginia Mountaineers': 'Big 12',
            
            # ACC
            'Boston College': 'ACC', 'BC': 'ACC', 'Boston College Eagles': 'ACC',
            'Cal': 'ACC', 'CAL': 'ACC', 'California': 'ACC', 'California Golden Bears': 'ACC',
            'Clemson': 'ACC', 'CLEM': 'ACC', 'Clemson Tigers': 'ACC',
            'Duke': 'ACC', 'DUKE': 'ACC', 'Duke Blue Devils': 'ACC',
            'Florida State': 'ACC', 'FSU': 'ACC', 'Florida State Seminoles': 'ACC',
            'Georgia Tech': 'ACC', 'GT': 'ACC', 'Georgia Tech Yellow Jackets': 'ACC',
            'Louisville': 'ACC', 'LOU': 'ACC', 'Louisville Cardinals': 'ACC',
            'Miami': 'ACC', 'MIA': 'ACC', 'Miami Hurricanes': 'ACC', 'Miami (FL)': 'ACC',
            'North Carolina': 'ACC', 'NC': 'ACC', 'UNC': 'ACC', 'North Carolina Tar Heels': 'ACC',
            'NC State': 'ACC', 'NCST': 'ACC', 'NC State Wolfpack': 'ACC', 'North Carolina State': 'ACC',
            'Notre Dame': 'ACC', 'ND': 'ACC', 'Notre Dame Fighting Irish': 'ACC',
            'Pittsburgh': 'ACC', 'PITT': 'ACC', 'Pittsburgh Panthers': 'ACC',
            'SMU': 'ACC', 'SMU Mustangs': 'ACC', 'Southern Methodist': 'ACC',
            'Stanford': 'ACC', 'STAN': 'ACC', 'Stanford Cardinal': 'ACC',
            'Syracuse': 'ACC', 'SYR': 'ACC', 'Syracuse Orange': 'ACC',
            'Virginia': 'ACC', 'UVA': 'ACC', 'Virginia Cavaliers': 'ACC',
            'Virginia Tech': 'ACC', 'VT': 'ACC', 'Virginia Tech Hokies': 'ACC',
            'Wake Forest': 'ACC', 'WAKE': 'ACC', 'Wake Forest Demon Deacons': 'ACC',
        }
        
        # Check both team column and identity.team
        team_col = 'team' if 'team' in df.columns else 'identity.team' if 'identity.team' in df.columns else None
        
        if team_col:
            missing_conf = df['identity.conference'].isna() | (df['identity.conference'] == '') | (df['identity.conference'] == 'Unknown')
            
            if missing_conf.sum() > 0:
                for team_name, conference in TEAM_TO_CONFERENCE.items():
                    # Match team name (case insensitive, partial match)
                    mask = missing_conf & df[team_col].astype(str).str.contains(team_name, case=False, na=False)
                    if mask.sum() > 0:
                        df.loc[mask, 'identity.conference'] = conference
                
                imputed = (missing_conf & df['identity.conference'].notna() & (df['identity.conference'] != '')).sum()
                if imputed > 0:
                    logger.info(f"  Imputed conference for {imputed} players from team names")
        
        return df
    
    def _impute_cfb_market_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute market value for CFB players based on NIL valuations
        
        Uses On3 NIL valuation if available, otherwise estimate from:
        - Social media followers
        - Performance stats
        - Awards/honors
        - Position value
        """
        if 'identity.contract_value' not in df.columns:
            return df
        
        df = df.copy()
        
        # Use NIL valuation as proxy for market value (for college players)
        if 'proof.nil_valuation' in df.columns:
            missing_contract = df['identity.contract_value'].isna() | (df['identity.contract_value'] == 0)
            has_nil = df['proof.nil_valuation'].notna() & (df['proof.nil_valuation'] > 0)
            
            if (missing_contract & has_nil).sum() > 0:
                df.loc[missing_contract & has_nil, 'identity.contract_value'] = df.loc[missing_contract & has_nil, 'proof.nil_valuation']
                logger.info(f"  Used NIL valuation as market value for {(missing_contract & has_nil).sum()} college players")
        
        # Estimate from social media + performance (for players without NIL data)
        missing_value = df['identity.contract_value'].isna() | (df['identity.contract_value'] == 0)
        
        if missing_value.sum() > 0:
            # Simple heuristic model for CFB players
            social_score = pd.Series(0, index=df.index)
            perf_score = pd.Series(0, index=df.index)
            
            if 'brand.total_social_followers' in df.columns:
                social_score = df['brand.total_social_followers'].fillna(0) / 10000  # $1 per 10K followers
            
            if 'proof.all_american_selections' in df.columns:
                perf_score += df['proof.all_american_selections'].fillna(0) * 50000  # $50K per All-American
            
            if 'proof.conference_honors' in df.columns:
                perf_score += df['proof.conference_honors'].fillna(0) * 25000  # $25K per conference honor
            
            if 'proof.heisman_winner' in df.columns:
                perf_score += df['proof.heisman_winner'].fillna(0).astype(int) * 200000  # $200K for Heisman
            
            estimated_value = social_score + perf_score
            
            # Position multipliers (QB, skill positions worth more in NIL)
            position_col = 'position' if 'position' in df.columns else 'identity.position' if 'identity.position' in df.columns else None
            
            if position_col and position_col in df.columns:
                position_multiplier = df[position_col].map({
                    'QB': 1.5,
                    'RB': 1.2,
                    'WR': 1.3,
                    'TE': 1.1,
                    'DB': 1.0,
                    'S': 1.0,
                    'CB': 1.0,
                    'LB': 1.0,
                    'DL': 1.0,
                    'DE': 1.0,
                    'DT': 1.0,
                    'OL': 0.9,
                    'OT': 0.9,
                    'OG': 0.9,
                    'C': 0.9
                }).fillna(1.0)
                
                estimated_value = estimated_value * position_multiplier
            
            # Only impute if we have some basis for estimation
            has_data = (social_score > 0) | (perf_score > 0)
            to_impute = missing_value & has_data
            
            if to_impute.sum() > 0:
                df.loc[to_impute, 'identity.contract_value'] = estimated_value[to_impute]
                logger.info(f"  Estimated market value for {to_impute.sum()} CFB players from performance/social")
        
        return df
    
    def _impute_nfl_conference_from_team(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute NFL conference/division based on team name
        
        Uses official NFL conference/division for 2024-2025 season
        """
        if 'identity.conference' not in df.columns:
            return df
        
        df = df.copy()
        
        # NFL Team to Conference mapping (comprehensive)
        NFL_TEAM_CONFERENCE = {
            # AFC East
            'Buffalo Bills': 'AFC', 'Bills': 'AFC', 'Buffalo': 'AFC',
            'Miami Dolphins': 'AFC', 'Dolphins': 'AFC', 'Miami': 'AFC',
            'New England Patriots': 'AFC', 'Patriots': 'AFC', 'New England': 'AFC',
            'New York Jets': 'AFC', 'Jets': 'AFC', 'NY Jets': 'AFC',
            
            # AFC North
            'Baltimore Ravens': 'AFC', 'Ravens': 'AFC', 'Baltimore': 'AFC',
            'Cincinnati Bengals': 'AFC', 'Bengals': 'AFC', 'Cincinnati': 'AFC',
            'Cleveland Browns': 'AFC', 'Browns': 'AFC', 'Cleveland': 'AFC',
            'Pittsburgh Steelers': 'AFC', 'Steelers': 'AFC', 'Pittsburgh': 'AFC',
            
            # AFC South
            'Houston Texans': 'AFC', 'Texans': 'AFC', 'Houston': 'AFC',
            'Indianapolis Colts': 'AFC', 'Colts': 'AFC', 'Indianapolis': 'AFC',
            'Jacksonville Jaguars': 'AFC', 'Jaguars': 'AFC', 'Jacksonville': 'AFC',
            'Tennessee Titans': 'AFC', 'Titans': 'AFC', 'Tennessee': 'AFC',
            
            # AFC West
            'Denver Broncos': 'AFC', 'Broncos': 'AFC', 'Denver': 'AFC',
            'Kansas City Chiefs': 'AFC', 'Chiefs': 'AFC', 'Kansas City': 'AFC',
            'Las Vegas Raiders': 'AFC', 'Raiders': 'AFC', 'Las Vegas': 'AFC',
            'Los Angeles Chargers': 'AFC', 'Chargers': 'AFC', 'LA Chargers': 'AFC',
            
            # NFC East
            'Dallas Cowboys': 'NFC', 'Cowboys': 'NFC', 'Dallas': 'NFC',
            'New York Giants': 'NFC', 'Giants': 'NFC', 'NY Giants': 'NFC',
            'Philadelphia Eagles': 'NFC', 'Eagles': 'NFC', 'Philadelphia': 'NFC',
            'Washington Commanders': 'NFC', 'Commanders': 'NFC', 'Washington': 'NFC',
            
            # NFC North
            'Chicago Bears': 'NFC', 'Bears': 'NFC', 'Chicago': 'NFC',
            'Detroit Lions': 'NFC', 'Lions': 'NFC', 'Detroit': 'NFC',
            'Green Bay Packers': 'NFC', 'Packers': 'NFC', 'Green Bay': 'NFC',
            'Minnesota Vikings': 'NFC', 'Vikings': 'NFC', 'Minnesota': 'NFC',
            
            # NFC South
            'Atlanta Falcons': 'NFC', 'Falcons': 'NFC', 'Atlanta': 'NFC',
            'Carolina Panthers': 'NFC', 'Panthers': 'NFC', 'Carolina': 'NFC',
            'New Orleans Saints': 'NFC', 'Saints': 'NFC', 'New Orleans': 'NFC',
            'Tampa Bay Buccaneers': 'NFC', 'Buccaneers': 'NFC', 'Tampa Bay': 'NFC', 'Tampa': 'NFC',
            
            # NFC West
            'Arizona Cardinals': 'NFC', 'Cardinals': 'NFC', 'Arizona': 'NFC',
            'San Francisco 49ers': 'NFC', '49ers': 'NFC', 'San Francisco': 'NFC',
            'Los Angeles Rams': 'NFC', 'Rams': 'NFC', 'LA Rams': 'NFC',
            'Seattle Seahawks': 'NFC', 'Seahawks': 'NFC', 'Seattle': 'NFC',
        }
        
        # Also create division mapping
        NFL_TEAM_DIVISION = {
            # AFC East
            'Bills': 'AFC East', 'Dolphins': 'AFC East', 'Patriots': 'AFC East', 'Jets': 'AFC East',
            'Buffalo': 'AFC East', 'Miami': 'AFC East', 'New England': 'AFC East',
            
            # AFC North
            'Ravens': 'AFC North', 'Bengals': 'AFC North', 'Browns': 'AFC North', 'Steelers': 'AFC North',
            'Baltimore': 'AFC North', 'Cincinnati': 'AFC North', 'Cleveland': 'AFC North', 'Pittsburgh': 'AFC North',
            
            # AFC South
            'Texans': 'AFC South', 'Colts': 'AFC South', 'Jaguars': 'AFC South', 'Titans': 'AFC South',
            'Houston': 'AFC South', 'Indianapolis': 'AFC South', 'Jacksonville': 'AFC South', 'Tennessee': 'AFC South',
            
            # AFC West
            'Broncos': 'AFC West', 'Chiefs': 'AFC West', 'Raiders': 'AFC West', 'Chargers': 'AFC West',
            'Denver': 'AFC West', 'Kansas City': 'AFC West', 'Las Vegas': 'AFC West',
            
            # NFC East
            'Cowboys': 'NFC East', 'Giants': 'NFC East', 'Eagles': 'NFC East', 'Commanders': 'NFC East',
            'Dallas': 'NFC East', 'Philadelphia': 'NFC East', 'Washington': 'NFC East',
            
            # NFC North
            'Bears': 'NFC North', 'Lions': 'NFC North', 'Packers': 'NFC North', 'Vikings': 'NFC North',
            'Chicago': 'NFC North', 'Detroit': 'NFC North', 'Green Bay': 'NFC North', 'Minnesota': 'NFC North',
            
            # NFC South
            'Falcons': 'NFC South', 'Panthers': 'NFC South', 'Saints': 'NFC South', 'Buccaneers': 'NFC South',
            'Atlanta': 'NFC South', 'Carolina': 'NFC South', 'New Orleans': 'NFC South', 'Tampa Bay': 'NFC South', 'Tampa': 'NFC South',
            
            # NFC West
            'Cardinals': 'NFC West', '49ers': 'NFC West', 'Rams': 'NFC West', 'Seahawks': 'NFC West',
            'Arizona': 'NFC West', 'San Francisco': 'NFC West', 'Seattle': 'NFC West',
        }
        
        team_col = 'team' if 'team' in df.columns else 'identity.team' if 'identity.team' in df.columns else None
        
        if team_col:
            missing_conf = df['identity.conference'].isna() | (df['identity.conference'] == '') | (df['identity.conference'] == 'Unknown')
            
            if missing_conf.sum() > 0:
                # Impute conference
                for team_name, conference in NFL_TEAM_CONFERENCE.items():
                    mask = missing_conf & df[team_col].astype(str).str.contains(team_name, case=False, na=False, regex=False)
                    if mask.sum() > 0:
                        df.loc[mask, 'identity.conference'] = conference
                
                # Optionally also add division
                if 'identity.division' in df.columns:
                    missing_div = df['identity.division'].isna() | (df['identity.division'] == '')
                    for team_name, division in NFL_TEAM_DIVISION.items():
                        mask = missing_div & df[team_col].astype(str).str.contains(team_name, case=False, na=False, regex=False)
                        if mask.sum() > 0:
                            df.loc[mask, 'identity.division'] = division
                
                imputed = (missing_conf & df['identity.conference'].notna() & (df['identity.conference'] != '')).sum()
                if imputed > 0:
                    logger.info(f"  Imputed conference for {imputed} NFL players from team names")
        
        return df
    
    def _impute_nfl_contract_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Intelligently impute NFL contract value
        
        Uses ML trained on available data, with fallbacks to:
        - Draft position (higher picks = bigger contracts)
        - Performance stats (Pro Bowls, yards, TDs)
        - Years in league (experience)
        - Position (QB >>> others)
        """
        if 'identity.contract_value' not in df.columns:
            return df
        
        df = df.copy()
        
        # Try ML imputation if we have enough training data
        if df['identity.contract_value'].notna().sum() >= 20:
            try:
                from sklearn.ensemble import RandomForestRegressor
                
                feature_cols = []
                
                # Draft features (HUGE predictor)
                if 'identity.draft_round' in df.columns:
                    # Create draft score (higher for early picks)
                    df['_draft_score'] = 0
                    
                    # Convert draft_round to numeric if it's not
                    draft_numeric = pd.to_numeric(df['identity.draft_round'], errors='coerce')
                    
                    df.loc[draft_numeric == 1, '_draft_score'] = 100
                    df.loc[draft_numeric == 2, '_draft_score'] = 70
                    df.loc[draft_numeric == 3, '_draft_score'] = 50
                    df.loc[draft_numeric == 4, '_draft_score'] = 35
                    df.loc[draft_numeric >= 5, '_draft_score'] = 25
                    
                    # Undrafted players
                    df.loc[df['identity.draft_round'] == 'Undrafted', '_draft_score'] = 15
                    
                    feature_cols.append('_draft_score')
                
                # Performance features
                perf_features = [
                    'proof.pro_bowls', 'proof.all_pro_selections', 'proof.super_bowl_wins',
                    'proof.career_yards', 'proof.career_touchdowns', 'proof.career_receptions',
                    'proof.career_sacks', 'proof.career_interceptions',
                    'identity.years_in_league', 'identity.age'
                ]
                feature_cols.extend([f for f in perf_features if f in df.columns])
                
                # Position encoding (QB highest paid)
                if 'position' in df.columns or 'identity.position' in df.columns:
                    pos_col = 'position' if 'position' in df.columns else 'identity.position'
                    position_value = df[pos_col].map({
                        'QB': 100, 'DE': 80, 'WR': 75, 'CB': 70, 'OT': 68, 'LT': 65,
                        'DT': 60, 'LB': 55, 'S': 50, 'RB': 45, 'TE': 40, 'OL': 35,
                        'OG': 33, 'C': 32, 'K': 20, 'P': 18, 'LS': 15
                    }).fillna(30)
                    df['_position_value'] = position_value
                    feature_cols.append('_position_value')
                
                if len(feature_cols) >= 3:
                    # Train on known contracts
                    train_mask = df['identity.contract_value'].notna() & (df['identity.contract_value'] > 0)
                    
                    if train_mask.sum() >= 20:
                        X_train = df.loc[train_mask, feature_cols].fillna(0)
                        y_train = df.loc[train_mask, 'identity.contract_value']
                        
                        # Quick RF model
                        model = RandomForestRegressor(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
                        model.fit(X_train, y_train)
                        
                        # Predict missing
                        missing_mask = df['identity.contract_value'].isna() | (df['identity.contract_value'] == 0)
                        if missing_mask.sum() > 0:
                            X_missing = df.loc[missing_mask, feature_cols].fillna(0)
                            predictions = model.predict(X_missing)
                            
                            # Apply predictions (ensure they're reasonable)
                            predictions = np.clip(predictions, 500000, 60000000)  # $500K to $60M
                            df.loc[missing_mask, 'identity.contract_value'] = predictions
                            
                            logger.info(f"  Imputed {missing_mask.sum()} NFL contract values using ML")
                            
                            # Clean up temp columns
                            if '_draft_score' in df.columns:
                                df.drop('_draft_score', axis=1, inplace=True)
                            if '_position_value' in df.columns:
                                df.drop('_position_value', axis=1, inplace=True)
                            
                            return df
                        
            except Exception as e:
                logger.debug(f"ML contract imputation failed: {e}")
        
        # Fallback: Simple heuristics
        still_missing = df['identity.contract_value'].isna() | (df['identity.contract_value'] == 0)
        
        if still_missing.sum() > 0:
            # Position-based baseline (2024 average APY by position)
            position_baselines = {
                'QB': 35000000,   # $35M
                'WR': 18000000,   # $18M
                'DE': 17000000,   # $17M
                'CB': 15000000,   # $15M
                'OT': 14000000,   # $14M
                'LT': 14500000,
                'DT': 13000000,
                'LB': 11000000,
                'S': 10000000,
                'TE': 9000000,
                'RB': 7000000,
                'OL': 6000000,
                'OG': 6500000,
                'C': 7000000,
                'K': 3000000,
                'P': 2500000,
                'LS': 1500000,
            }
            
            pos_col = 'position' if 'position' in df.columns else 'identity.position' if 'identity.position' in df.columns else None
            
            if pos_col:
                for pos, baseline in position_baselines.items():
                    mask = still_missing & (df[pos_col] == pos)
                    
                    if mask.sum() > 0:
                        # Adjust by draft round if available
                        if 'identity.draft_round' in df.columns:
                            draft_numeric = pd.to_numeric(df.loc[mask, 'identity.draft_round'], errors='coerce')
                            
                            multiplier = draft_numeric.map({
                                1: 1.5, 2: 1.2, 3: 1.0, 4: 0.8, 5: 0.7, 6: 0.6, 7: 0.5
                            }).fillna(0.9)
                            
                            # Undrafted = lower multiplier
                            multiplier.loc[df.loc[mask, 'identity.draft_round'] == 'Undrafted'] = 0.6
                            
                            df.loc[mask, 'identity.contract_value'] = baseline * multiplier
                        else:
                            df.loc[mask, 'identity.contract_value'] = baseline
            
            imputed = (still_missing & df['identity.contract_value'].notna() & (df['identity.contract_value'] > 0)).sum()
            if imputed > 0:
                logger.info(f"  Estimated {imputed} NFL contract values from position/draft data")
        
        return df
    
    def impute_with_confidence(self, df: pd.DataFrame, target: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Impute target field and return confidence scores
        
        Args:
            df: DataFrame
            target: Field to impute
            
        Returns:
            (imputed_df, confidence_series)
        """
        df = df.copy()
        confidence = pd.Series(1.0, index=df.index)  # 1.0 = original data
        
        if target not in self.trained_models:
            logger.warning(f"No trained model for {target}, using rule-based imputation")
            df = self._rule_based_impute(df)
            confidence.loc[df[target].notna()] = 0.5  # Rule-based = medium confidence
            return df, confidence
        
        missing_mask = df[target].isna()
        
        if missing_mask.sum() == 0:
            return df, confidence
        
        # ML imputation with confidence
        model_data = self.trained_models[target]
        features = model_data['features']
        
        X_missing = df.loc[missing_mask, features].copy()
        X_missing = X_missing.fillna(X_missing.median())
        
        predictions = model_data['model'].predict(X_missing)
        
        # Assign predictions
        df.loc[missing_mask, target] = predictions
        
        # Assign confidence based on model performance
        if model_data['is_classifier']:
            conf_score = model_data['performance'].get('accuracy', 0.5)
        else:
            mae = model_data['performance'].get('mae', float('inf'))
            conf_score = max(0.1, 1.0 - (mae / 10.0))
        
        confidence.loc[missing_mask] = conf_score
        
        return df, confidence


# ============================================================================
# SMART IMPUTATION STRATEGIES
# ============================================================================

class SmartImputer:
    """
    Smart imputation strategies for specific field types
    
    Combines ML predictions with domain knowledge
    """
    
    @staticmethod
    def impute_contract_value(df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute contract value using correlated features
        
        Features used:
        - Performance stats (career_yards, career_points, etc.)
        - Awards (pro_bowls, all_star_selections, etc.)
        - Social media followers
        - Years in league
        - Position
        """
        df = df.copy()
        
        target = 'identity.contract_value'
        
        if target not in df.columns or df[target].notna().sum() < 20:
            return df
        
        # Build feature set
        feature_candidates = [
            'identity.years_in_league',
            'proof.career_yards', 'proof.career_points',
            'proof.pro_bowls', 'proof.all_star_selections',
            'proof.super_bowl_wins', 'proof.championships',
            'brand.instagram_followers', 'brand.twitter_followers',
            'identity.age'
        ]
        
        features = [f for f in feature_candidates if f in df.columns]
        
        if not features:
            return df
        
        # Train simple model
        train_df = df[df[target].notna()].copy()
        X_train = train_df[features].fillna(0)
        y_train = train_df[target]
        
        if len(X_train) < 10:
            return df
        
        try:
            from sklearn.ensemble import RandomForestRegressor
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(X_train, y_train)
            
            # Predict missing
            missing_mask = df[target].isna()
            if missing_mask.sum() > 0:
                X_missing = df.loc[missing_mask, features].fillna(0)
                predictions = model.predict(X_missing)
                df.loc[missing_mask, target] = predictions
                logger.info(f"✅ Imputed {missing_mask.sum()} contract values using ML")
        except Exception as e:
            logger.debug(f"ML contract imputation failed: {e}")
        
        return df
    
    @staticmethod
    def impute_social_media(df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute social media followers using cross-platform correlation
        
        If a player has Instagram but no Twitter, estimate Twitter from Instagram
        """
        df = df.copy()
        
        social_platforms = [
            'brand.instagram_followers',
            'brand.twitter_followers',
            'brand.tiktok_followers',
            'brand.youtube_subscribers'
        ]
        
        # Calculate average ratio between platforms
        for source in social_platforms:
            for target in social_platforms:
                if source == target or source not in df.columns or target not in df.columns:
                    continue
                
                # Calculate ratio where both exist
                both_exist = df[source].notna() & df[target].notna() & (df[source] > 0)
                
                if both_exist.sum() < 10:
                    continue
                
                ratio = (df.loc[both_exist, target] / df.loc[both_exist, source]).median()
                
                if np.isnan(ratio) or ratio <= 0:
                    continue
                
                # Impute target where source exists but target is missing
                to_impute = df[source].notna() & (df[source] > 0) & df[target].isna()
                
                if to_impute.sum() > 0:
                    df.loc[to_impute, target] = df.loc[to_impute, source] * ratio
                    logger.info(f"  Imputed {to_impute.sum()} {target} from {source} (ratio: {ratio:.2f})")
        
        return df


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_training_dataset(csv_files: List[str], output_path: str = "training_data.csv"):
    """
    Combine multiple CSV files into training dataset
    
    Args:
        csv_files: List of CSV file paths
        output_path: Where to save combined training data
        
    Returns:
        Combined DataFrame
    """
    dfs = []
    
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            dfs.append(df)
            logger.info(f"Loaded {len(df)} rows from {csv_file}")
        except Exception as e:
            logger.error(f"Failed to load {csv_file}: {e}")
    
    if not dfs:
        raise ValueError("No valid CSV files loaded")
    
    combined = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicates
    if 'player_name' in combined.columns:
        combined = combined.drop_duplicates(subset=['player_name'], keep='last')
    
    combined.to_csv(output_path, index=False)
    logger.info(f"✅ Created training dataset: {len(combined)} players -> {output_path}")
    
    return combined


if __name__ == '__main__':
    # Example usage
    print("""
ML Imputation Layer
===================

Train imputation models:
    from gravity.ml_imputer import MLImputer
    
    imputer = MLImputer()
    df = pd.read_csv('training_data.csv')
    results = imputer.train_imputation_models(df)
    
Use trained models:
    imputer.load_models()
    df_imputed = imputer.impute_dataframe(df_with_missing_values)
    """)

