"""Command-line interface for NFL Gravity."""

import argparse
import logging
import sys
import os
from typing import List

from .core.config import Config
from .core.utils import setup_logging
from .core.exceptions import NFLGravityError
from .mcp import MCP


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog='nfl_gravity',
        description='NFL Gravity - Modular Content Pipeline for NFL Data Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scrape --teams chiefs patriots --out data/
  %(prog)s scrape --teams all --fast --out data/weekly/
  %(prog)s status
  %(prog)s list-teams
        """
    )
    
    # Global options
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--config-file',
        type=str,
        help='Path to configuration file'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scrape command
    scrape_parser = subparsers.add_parser(
        'scrape',
        help='Run the data scraping pipeline'
    )
    
    scrape_parser.add_argument(
        '--teams',
        type=str,
        required=True,
        help='Comma-separated team names or "all" for all teams'
    )
    
    scrape_parser.add_argument(
        '--out',
        type=str,
        default='data',
        help='Output directory (default: data)'
    )
    
    scrape_parser.add_argument(
        '--fast',
        action='store_true',
        help='Enable fast mode (skip heavy LLM processing)'
    )
    
    scrape_parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Maximum number of concurrent workers (default: 5)'
    )
    
    scrape_parser.add_argument(
        '--formats',
        type=str,
        default='parquet,csv',
        help='Output formats: parquet,csv (default: parquet,csv)'
    )
    
    # Status command
    status_parser = subparsers.add_parser(
        'status',
        help='Show pipeline status and recent runs'
    )
    
    # List teams command
    list_teams_parser = subparsers.add_parser(
        'list-teams',
        help='List all supported NFL teams'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate configuration and dependencies'
    )
    
    # Data info command
    data_info_parser = subparsers.add_parser(
        'data-info',
        help='Show information about stored data'
    )
    
    return parser


def parse_teams(teams_arg: str, all_teams: List[str]) -> List[str]:
    """Parse teams argument into list of team names."""
    if teams_arg.lower() == 'all':
        return all_teams
    
    # Split by comma and clean up
    teams = [team.strip().lower() for team in teams_arg.split(',')]
    
    # Validate teams
    invalid_teams = [team for team in teams if team not in all_teams]
    if invalid_teams:
        raise ValueError(f"Invalid teams: {', '.join(invalid_teams)}")
    
    return teams


def handle_scrape(args, config: Config) -> int:
    """Handle the scrape command."""
    try:
        # Parse teams
        teams = parse_teams(args.teams, config.nfl_teams)
        
        # Parse output formats
        formats = [fmt.strip() for fmt in args.formats.split(',')]
        config.output_formats = formats
        
        print(f"🏈 Starting NFL Gravity pipeline...")
        print(f"   Teams: {', '.join(teams)} ({len(teams)} total)")
        print(f"   Output: {args.out}")
        print(f"   Fast mode: {'Yes' if args.fast else 'No'}")
        print(f"   Formats: {', '.join(formats)}")
        print()
        
        # Initialize and run MCP
        mcp = MCP(config)
        
        results = mcp.run_pipeline(
            teams=teams,
            fast_mode=args.fast,
            output_dir=args.out
        )
        
        # Display results
        print(f"✅ Pipeline completed successfully!")
        print(f"   Teams processed: {results['teams_processed']}")
        print(f"   Players extracted: {results['total_players']}")
        print(f"   Duration: {results.get('duration', 0):.1f} seconds")
        print(f"   Output directory: {results['output_dir']}")
        
        if results.get('errors'):
            print(f"⚠️  Warnings/Errors: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"     - {error}")
            if len(results['errors']) > 3:
                print(f"     ... and {len(results['errors']) - 3} more")
        
        return 0
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return 1


def handle_status(args, config: Config) -> int:
    """Handle the status command."""
    try:
        mcp = MCP(config)
        status = mcp.get_status()
        
        print("📊 NFL Gravity Status")
        print("=" * 40)
        print(f"State: {status.get('state', 'Unknown')}")
        print(f"Last run: {status.get('last_run', 'Never')}")
        print(f"Total runs: {status.get('total_runs', 0)}")
        
        # Check dependencies
        print("\n🔧 Dependencies:")
        
        # LLM availability
        from .llm.adapter import LLMAdapter
        llm = LLMAdapter(config)
        provider_info = llm.get_provider_info()
        
        print(f"   LLM Provider: {provider_info['primary_provider'] or 'None available'}")
        print(f"   Available providers: {', '.join(provider_info['available_providers']) or 'None'}")
        
        # Data directory
        print(f"   Data directory: {config.data_dir} ({'exists' if os.path.exists(config.data_dir) else 'missing'})")
        print(f"   Log directory: {config.log_dir} ({'exists' if os.path.exists(config.log_dir) else 'missing'})")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        return 1


def handle_list_teams(args, config: Config) -> int:
    """Handle the list-teams command."""
    print("🏈 Supported NFL Teams")
    print("=" * 40)
    
    # Group teams by division (simplified)
    afc_teams = ['bills', 'dolphins', 'jets', 'patriots',  # AFC East
                'bengals', 'browns', 'ravens', 'steelers',  # AFC North
                'colts', 'jaguars', 'texans', 'titans',    # AFC South
                'broncos', 'chargers', 'chiefs', 'raiders'] # AFC West
    
    nfc_teams = ['cowboys', 'eagles', 'giants', 'commanders',  # NFC East
                'bears', 'lions', 'packers', 'vikings',       # NFC North
                'falcons', 'panthers', 'saints', 'buccaneers', # NFC South
                '49ers', 'cardinals', 'rams', 'seahawks']     # NFC West
    
    print("AFC:")
    for i, team in enumerate(afc_teams, 1):
        print(f"  {i:2d}. {team}")
    
    print("\nNFC:")
    for i, team in enumerate(nfc_teams, 1):
        print(f"  {i:2d}. {team}")
    
    print(f"\nTotal: {len(config.nfl_teams)} teams")
    print("\nUsage: --teams chiefs,patriots or --teams all")
    
    return 0


def handle_validate(args, config: Config) -> int:
    """Handle the validate command."""
    print("🔍 Validating NFL Gravity Configuration")
    print("=" * 50)
    
    # Validate configuration
    validation_messages = config.validate()
    
    if validation_messages:
        print("⚠️  Configuration Issues:")
        for msg in validation_messages:
            print(f"   - {msg}")
    else:
        print("✅ Configuration is valid")
    
    # Check dependencies
    print("\n📦 Dependency Check:")
    
    dependencies = [
        ('requests', 'Web scraping'),
        ('beautifulsoup4', 'HTML parsing'),
        ('pandas', 'Data processing'),
        ('pyarrow', 'Parquet support'),
        ('pydantic', 'Data validation'),
        ('trafilatura', 'Text extraction')
    ]
    
    for package, description in dependencies:
        try:
            __import__(package)
            print(f"   ✅ {package} - {description}")
        except ImportError:
            print(f"   ❌ {package} - {description} (missing)")
    
    # Check optional dependencies
    print("\n🔧 Optional Dependencies:")
    
    optional_deps = [
        ('openai', 'OpenAI LLM integration'),
        ('transformers', 'HuggingFace models'),
        ('torch', 'PyTorch for local models')
    ]
    
    for package, description in optional_deps:
        try:
            __import__(package)
            print(f"   ✅ {package} - {description}")
        except ImportError:
            print(f"   ⚪ {package} - {description} (optional)")
    
    return 0


def handle_data_info(args, config: Config) -> int:
    """Handle the data-info command."""
    try:
        from .storage.writer import DataWriter
        
        writer = DataWriter(config)
        info = writer.get_data_info()
        
        print("📁 NFL Gravity Data Information")
        print("=" * 40)
        print(f"Data directory: {info['data_directory']}")
        
        if info.get('latest_extraction'):
            print(f"Latest extraction: {info['latest_extraction']}")
            print(f"Total files: {info['total_files']}")
            
            if info.get('latest_files'):
                print("\nLatest files:")
                for file in sorted(info['latest_files']):
                    file_path = os.path.join(info['data_directory'], info['latest_extraction'], file)
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                        print(f"   - {file} ({size_str})")
        else:
            print("No data files found")
        
        if info.get('available_dates'):
            print(f"\nAvailable extractions: {len(info['available_dates'])}")
            for date in sorted(info['available_dates'])[-5:]:  # Show last 5
                print(f"   - {date}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error getting data info: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize configuration
    try:
        config = Config()
        
        # Override log level from command line
        if hasattr(args, 'log_level'):
            config.log_level = args.log_level
        
        # Set up logging
        logger = setup_logging(
            log_level=config.log_level,
            log_file=config.get_log_file()
        )
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return 1
    
    # Route to command handlers
    try:
        if args.command == 'scrape':
            return handle_scrape(args, config)
        elif args.command == 'status':
            return handle_status(args, config)
        elif args.command == 'list-teams':
            return handle_list_teams(args, config)
        elif args.command == 'validate':
            return handle_validate(args, config)
        elif args.command == 'data-info':
            return handle_data_info(args, config)
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏸️  Operation cancelled by user")
        return 130
    except NFLGravityError as e:
        print(f"❌ NFL Gravity error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if config.log_level == 'DEBUG':
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
