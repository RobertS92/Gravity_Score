#!/usr/bin/env python3
"""
Model Manager
=============

Comprehensive model versioning and registry management:
- Model version control
- Performance tracking
- Model comparison
- Rollback capabilities
- Automated retraining scheduling

Usage:
    python models/model_manager.py list
    python models/model_manager.py compare draft v1.0.0 v1.1.0
    python models/model_manager.py rollback draft v1.0.0
    python models/model_manager.py promote draft v1.1.0

Author: Gravity Score Team
"""

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MODEL REGISTRY
# ============================================================================

class ModelRegistry:
    """
    Model registry for version control and management
    """
    
    def __init__(self, registry_dir: str = "models"):
        """
        Initialize model registry
        
        Args:
            registry_dir: Directory containing models and registry
        """
        self.registry_dir = Path(registry_dir)
        self.registry_file = self.registry_dir / "registry.json"
        self.versions_dir = self.registry_dir / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """Load registry from file"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        else:
            # Create empty registry
            return {
                'last_updated': datetime.now().isoformat(),
                'imputation_models': {},
                'prediction_models': {},
                'version_history': {}
            }
    
    def _save_registry(self):
        """Save registry to file"""
        self.registry['last_updated'] = datetime.now().isoformat()
        
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2)
        
        logger.info(f"✅ Registry saved to {self.registry_file}")
    
    def list_models(self) -> Dict[str, List[str]]:
        """
        List all registered models
        
        Returns:
            Dictionary with model types and their names
        """
        result = {
            'imputation': list(self.registry.get('imputation_models', {}).keys()),
            'prediction': list(self.registry.get('prediction_models', {}).keys())
        }
        
        return result
    
    def get_model_info(self, model_name: str, model_type: str = 'prediction') -> Optional[Dict]:
        """
        Get information about a specific model
        
        Args:
            model_name: Name of the model
            model_type: 'imputation' or 'prediction'
            
        Returns:
            Model information dictionary or None
        """
        key = f'{model_type}_models'
        return self.registry.get(key, {}).get(model_name)
    
    def register_model(
        self, 
        model_name: str, 
        model_path: str,
        model_type: str,
        version: str,
        performance_metrics: Dict[str, Any],
        metadata: Optional[Dict] = None
    ):
        """
        Register a new model version
        
        Args:
            model_name: Name of the model
            model_path: Path to model file
            model_type: 'imputation' or 'prediction'
            version: Version string (e.g., "1.0.0")
            performance_metrics: Performance metrics
            metadata: Additional metadata
        """
        key = f'{model_type}_models'
        
        if key not in self.registry:
            self.registry[key] = {}
        
        # Archive current version if exists
        if model_name in self.registry[key]:
            self._archive_version(model_name, model_type)
        
        # Register new version
        model_info = {
            'version': version,
            'trained_on': datetime.now().isoformat(),
            'path': model_path,
            'performance': performance_metrics,
            'metadata': metadata or {},
            'status': 'active'
        }
        
        self.registry[key][model_name] = model_info
        
        # Add to version history
        if model_name not in self.registry['version_history']:
            self.registry['version_history'][model_name] = []
        
        self.registry['version_history'][model_name].append({
            'version': version,
            'registered_at': datetime.now().isoformat(),
            'performance': performance_metrics
        })
        
        self._save_registry()
        logger.info(f"✅ Registered {model_name} v{version}")
    
    def _archive_version(self, model_name: str, model_type: str):
        """Archive current model version"""
        key = f'{model_type}_models'
        current_info = self.registry[key].get(model_name)
        
        if not current_info:
            return
        
        # Copy model file to versions directory
        current_path = Path(current_info['path'])
        if current_path.exists():
            version = current_info['version']
            archive_name = f"{model_name}_v{version}.pkl"
            archive_path = self.versions_dir / archive_name
            
            shutil.copy2(current_path, archive_path)
            logger.info(f"  📦 Archived {model_name} v{version} to {archive_path}")
    
    def compare_versions(
        self, 
        model_name: str, 
        version1: str, 
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two model versions
        
        Args:
            model_name: Name of the model
            version1: First version
            version2: Second version
            
        Returns:
            Comparison results
        """
        history = self.registry.get('version_history', {}).get(model_name, [])
        
        v1_info = next((v for v in history if v['version'] == version1), None)
        v2_info = next((v for v in history if v['version'] == version2), None)
        
        if not v1_info or not v2_info:
            raise ValueError(f"Version not found for {model_name}")
        
        comparison = {
            'model': model_name,
            'version1': version1,
            'version2': version2,
            'performance_v1': v1_info['performance'],
            'performance_v2': v2_info['performance'],
            'improvements': {}
        }
        
        # Calculate improvements
        for metric in v1_info['performance']:
            if metric in v2_info['performance']:
                v1_val = v1_info['performance'][metric]
                v2_val = v2_info['performance'][metric]
                
                if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)):
                    # For error metrics (lower is better)
                    if metric in ['mae', 'rmse', 'mape']:
                        improvement = ((v1_val - v2_val) / v1_val) * 100
                    # For accuracy metrics (higher is better)
                    else:
                        improvement = ((v2_val - v1_val) / v1_val) * 100
                    
                    comparison['improvements'][metric] = f"{improvement:+.2f}%"
        
        return comparison
    
    def rollback(self, model_name: str, version: str, model_type: str = 'prediction'):
        """
        Rollback to a previous model version
        
        Args:
            model_name: Name of the model
            version: Version to rollback to
            model_type: 'imputation' or 'prediction'
        """
        # Find archived version
        archive_name = f"{model_name}_v{version}.pkl"
        archive_path = self.versions_dir / archive_name
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archived version not found: {archive_path}")
        
        # Get current model info
        key = f'{model_type}_models'
        current_info = self.registry[key].get(model_name)
        
        if not current_info:
            raise ValueError(f"Model not found in registry: {model_name}")
        
        # Archive current version first
        self._archive_version(model_name, model_type)
        
        # Restore archived version
        current_path = Path(current_info['path'])
        shutil.copy2(archive_path, current_path)
        
        # Update registry
        history = self.registry['version_history'].get(model_name, [])
        version_info = next((v for v in history if v['version'] == version), None)
        
        if version_info:
            self.registry[key][model_name]['version'] = version
            self.registry[key][model_name]['performance'] = version_info['performance']
            self.registry[key][model_name]['status'] = 'active'
            self.registry[key][model_name]['rolled_back_at'] = datetime.now().isoformat()
            
            self._save_registry()
            logger.info(f"✅ Rolled back {model_name} to v{version}")
        else:
            logger.error(f"Version info not found in history for {model_name} v{version}")
    
    def promote_version(self, model_name: str, version: str, model_type: str = 'prediction'):
        """
        Promote a specific version to production
        
        Same as rollback but with explicit "promotion" semantics
        """
        self.rollback(model_name, version, model_type)
        
        key = f'{model_type}_models'
        self.registry[key][model_name]['status'] = 'production'
        self.registry[key][model_name]['promoted_at'] = datetime.now().isoformat()
        
        self._save_registry()
        logger.info(f"✅ Promoted {model_name} v{version} to production")
    
    def get_version_history(self, model_name: str) -> List[Dict]:
        """Get version history for a model"""
        return self.registry.get('version_history', {}).get(model_name, [])
    
    def get_best_version(self, model_name: str, metric: str = 'mae') -> Optional[str]:
        """
        Get the best performing version based on a metric
        
        Args:
            model_name: Name of the model
            metric: Metric to optimize (e.g., 'mae', 'accuracy')
            
        Returns:
            Best version string
        """
        history = self.get_version_history(model_name)
        
        if not history:
            return None
        
        # Determine if metric should be minimized or maximized
        minimize_metrics = ['mae', 'rmse', 'mape']
        maximize = metric not in minimize_metrics
        
        best_version = None
        best_value = float('inf') if not maximize else float('-inf')
        
        for version_info in history:
            if metric in version_info['performance']:
                value = version_info['performance'][metric]
                
                if isinstance(value, (int, float)):
                    if maximize:
                        if value > best_value:
                            best_value = value
                            best_version = version_info['version']
                    else:
                        if value < best_value:
                            best_value = value
                            best_version = version_info['version']
        
        return best_version
    
    def cleanup_old_versions(self, keep_latest: int = 5):
        """
        Cleanup old model versions, keeping only the latest N
        
        Args:
            keep_latest: Number of versions to keep
        """
        logger.info(f"Cleaning up old versions (keeping latest {keep_latest})...")
        
        for model_name in self.registry.get('version_history', {}):
            versions = self.registry['version_history'][model_name]
            
            if len(versions) <= keep_latest:
                continue
            
            # Sort by date
            versions_sorted = sorted(versions, key=lambda x: x['registered_at'], reverse=True)
            
            # Remove old versions
            to_remove = versions_sorted[keep_latest:]
            
            for version_info in to_remove:
                version = version_info['version']
                archive_name = f"{model_name}_v{version}.pkl"
                archive_path = self.versions_dir / archive_name
                
                if archive_path.exists():
                    archive_path.unlink()
                    logger.info(f"  🗑️  Removed {archive_name}")
                
                # Remove from history
                self.registry['version_history'][model_name] = [
                    v for v in self.registry['version_history'][model_name]
                    if v['version'] != version
                ]
        
        self._save_registry()
        logger.info("✅ Cleanup complete")


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Model Manager - Version control for ML models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all models
  python models/model_manager.py list
  
  # Get model info
  python models/model_manager.py info draft
  
  # Compare versions
  python models/model_manager.py compare draft 1.0.0 1.1.0
  
  # Rollback to previous version
  python models/model_manager.py rollback draft 1.0.0
  
  # Promote version to production
  python models/model_manager.py promote draft 1.1.0
  
  # View version history
  python models/model_manager.py history draft
  
  # Find best version
  python models/model_manager.py best draft --metric mae
  
  # Cleanup old versions
  python models/model_manager.py cleanup --keep 5
        """
    )
    
    parser.add_argument(
        'command',
        choices=['list', 'info', 'compare', 'rollback', 'promote', 'history', 'best', 'cleanup'],
        help='Command to execute'
    )
    
    parser.add_argument(
        'model',
        nargs='?',
        help='Model name'
    )
    
    parser.add_argument(
        'version1',
        nargs='?',
        help='Version (for rollback/promote) or first version (for compare)'
    )
    
    parser.add_argument(
        'version2',
        nargs='?',
        help='Second version (for compare)'
    )
    
    parser.add_argument(
        '--type',
        choices=['imputation', 'prediction'],
        default='prediction',
        help='Model type (default: prediction)'
    )
    
    parser.add_argument(
        '--metric',
        default='mae',
        help='Metric for best version selection (default: mae)'
    )
    
    parser.add_argument(
        '--keep',
        type=int,
        default=5,
        help='Number of versions to keep during cleanup (default: 5)'
    )
    
    parser.add_argument(
        '--registry-dir',
        default='models',
        help='Registry directory (default: models)'
    )
    
    args = parser.parse_args()
    
    # Initialize registry
    registry = ModelRegistry(registry_dir=args.registry_dir)
    
    # Execute command
    try:
        if args.command == 'list':
            models = registry.list_models()
            print("\n📦 REGISTERED MODELS")
            print("=" * 80)
            print("\nImputation Models:")
            for model in models['imputation']:
                print(f"  • {model}")
            print("\nPrediction Models:")
            for model in models['prediction']:
                print(f"  • {model}")
        
        elif args.command == 'info':
            if not args.model:
                print("Error: model name required")
                return
            
            info = registry.get_model_info(args.model, args.type)
            if info:
                print(f"\n📋 MODEL INFO: {args.model}")
                print("=" * 80)
                print(json.dumps(info, indent=2))
            else:
                print(f"Model not found: {args.model}")
        
        elif args.command == 'compare':
            if not all([args.model, args.version1, args.version2]):
                print("Error: model name and two versions required")
                return
            
            comparison = registry.compare_versions(args.model, args.version1, args.version2)
            print(f"\n🔍 COMPARISON: {args.model}")
            print("=" * 80)
            print(json.dumps(comparison, indent=2))
        
        elif args.command == 'rollback':
            if not all([args.model, args.version1]):
                print("Error: model name and version required")
                return
            
            registry.rollback(args.model, args.version1, args.type)
        
        elif args.command == 'promote':
            if not all([args.model, args.version1]):
                print("Error: model name and version required")
                return
            
            registry.promote_version(args.model, args.version1, args.type)
        
        elif args.command == 'history':
            if not args.model:
                print("Error: model name required")
                return
            
            history = registry.get_version_history(args.model)
            print(f"\n📜 VERSION HISTORY: {args.model}")
            print("=" * 80)
            for version_info in history:
                print(f"\nVersion: {version_info['version']}")
                print(f"Registered: {version_info['registered_at']}")
                print(f"Performance: {version_info['performance']}")
        
        elif args.command == 'best':
            if not args.model:
                print("Error: model name required")
                return
            
            best_version = registry.get_best_version(args.model, args.metric)
            if best_version:
                print(f"\n🏆 BEST VERSION: {args.model}")
                print("=" * 80)
                print(f"Version: {best_version}")
                print(f"Metric: {args.metric}")
            else:
                print(f"No version history found for {args.model}")
        
        elif args.command == 'cleanup':
            registry.cleanup_old_versions(keep_latest=args.keep)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

