# NFL Gravity - Modular Content Pipeline

## Overview

NFL Gravity is a production-ready Python package designed to extract, enrich, and analyze NFL player and team data through a sophisticated Modular Content Pipeline (MCP). The system combines web scraping from multiple sources with LLM-powered intelligence to create comprehensive datasets of NFL information.

## System Architecture

The application follows a modular architecture with clear separation of concerns:

```
nfl_gravity/
├── core/           # Configuration, utilities, validation, exceptions
├── extractors/     # Data extraction from various sources
├── llm/           # Language model integration
├── pipeline/      # Orchestration and scheduling
└── storage/       # Data persistence and export
```

**Key Architectural Decisions:**
- **Modular Design**: Each component is independently testable and replaceable
- **Plugin Architecture**: LLM providers and data extractors are pluggable via entry points
- **Configuration-Driven**: Environment variables and Config class control behavior
- **Graceful Degradation**: System continues to function when external services fail

## Key Components

### Core Module (`core/`)
- **Config**: Environment-based configuration management with validation
- **Validators**: Pydantic-based data validation for PlayerData and TeamData models
- **Utils**: Shared utilities for logging, text cleaning, and web scraping helpers
- **Exceptions**: Custom exception hierarchy for structured error handling

### Data Extractors (`extractors/`)
- **WikipediaExtractor**: Automated Wikipedia search, infobox parsing, career highlights
- **SocialMediaExtractor**: Twitter/Instagram handle discovery with follower metrics
- **NFLSitesExtractor**: NFL.com, ESPN, Pro Football Reference roster extraction

### LLM Integration (`llm/`)
- **Multi-Provider Support**: OpenAI GPT-4o, HuggingFace, local models
- **Adapter Pattern**: Common interface for different LLM providers
- **Intelligent Extraction**: LLM-powered social media metrics and biographical data
- **Fallback Strategy**: Continues operation when LLM services unavailable

### Pipeline Orchestration (`pipeline/`)
- **PipelineOrchestrator**: Main coordinator for data extraction workflows
- **SimpleScheduler**: Job scheduling for automated data collection
- **Threaded Execution**: Concurrent processing for improved performance
- **Progress Tracking**: Real-time status monitoring and error recovery

### Storage System (`storage/`)
- **DataWriter**: Multi-format output (Parquet, CSV, JSON)
- **Schema Generation**: Automatic schema documentation and metadata
- **Compression**: Efficient storage with gzip and Parquet optimization
- **Timestamped Organization**: Data organized by extraction date

## Data Flow

1. **Configuration Loading**: Config class loads settings from environment variables
2. **Pipeline Initialization**: MCP class initializes all extractors and validators
3. **Team Processing**: For each NFL team:
   - Extract roster data from NFL sites
   - Enrich player data from Wikipedia
   - Discover social media profiles
   - Apply LLM-powered extraction where needed
4. **Data Validation**: Pydantic models validate and clean extracted data
5. **Storage**: Write validated data to multiple formats with schema documentation

## External Dependencies

### Required APIs:
- **OpenAI API**: For GPT-4o model access (optional, graceful degradation)
- **HuggingFace**: For alternative LLM models (optional)

### Web Sources:
- **Wikipedia**: Player biographical information and career highlights
- **NFL.com**: Official roster and player statistics
- **ESPN**: Team rosters and player data
- **Pro Football Reference**: Historical player statistics
- **Social Media**: Twitter/Instagram profile discovery

### Python Packages:
- **requests**: HTTP client for web scraping
- **beautifulsoup4**: HTML parsing
- **pandas**: Data manipulation
- **pyarrow**: Parquet file support
- **pydantic**: Data validation
- **flask**: Web interface
- **typer**: CLI framework

## Deployment Strategy

### Development Setup:
- Pip-installable package with `pip install -e .`
- CLI access via `nfl-gravity` command
- Web interface via Flask app

### Configuration:
- Environment variables for API keys and settings
- Default configuration supports operation without external APIs
- Logging to both console and files

### Testing:
- Comprehensive test suite with pytest
- Mock fixtures for external API calls
- CI/CD integration ready

### Production Considerations:
- Respectful scraping with robots.txt compliance
- Rate limiting and polite delays
- Error recovery and partial success handling
- Multiple output formats for different use cases

## Changelog

- July 02, 2025. Initial setup
- July 04, 2025. Added PostgreSQL database integration with comprehensive NFL player data storage
- July 17, 2025. Fixed scraper validation issues - now successfully extracts 93 players per team with proper height format and position validation
- July 17, 2025. **MAJOR UPGRADE**: Built comprehensive NFL data collection system with 40+ fields including:
  - Intelligent social media agent that searches internet for Twitter/X, Instagram, TikTok, YouTube profiles
  - Automatic follower/subscriber count extraction across all platforms
  - Career statistics, awards, financial data, Wikipedia profiles
  - Real-time web search for profile discovery with automatic link clicking and data extraction
  - Complete database schema supporting all required fields
  - Excel-like data viewing interface with filtering and export capabilities
  - Comprehensive test suite validating all functionality
- July 17, 2025. **CRITICAL FIX**: Resolved pipeline bottleneck limiting extraction to 20 players per team
  - Fixed NFL Gravity MCP orchestrator to process complete rosters (93+ players per team)
  - Integrated enhanced NFL scraper for comprehensive roster extraction
  - Confirmed successful extraction of 93 players from 49ers (previously limited to 20)
  - System now ready to collect all ~2,700 NFL players across 32 teams
- July 17, 2025. **COMPREHENSIVE DATA COLLECTION SYSTEM COMPLETE**: Built and integrated full 40+ field data collection pipeline
  - Created EnhancedComprehensiveCollector with parallel processing for social media, Wikipedia, career stats, and contract data
  - Integrated comprehensive collector into both MCP orchestrator and Flask API endpoints
  - Successfully processes all 93 players per team with comprehensive data collection in 13 seconds
  - System now extracts complete rosters with social media profiles, career statistics, awards, and biographical information
  - Pipeline supports both fast mode (basic fields) and comprehensive mode (all 40+ fields)
  - Ready for production deployment to collect comprehensive data for all ~2,700 NFL players

- July 17, 2025. **ENHANCED AGE COLLECTION & DATABASE VERSIONING**: Implemented advanced age collection with Wikipedia fallback and full database versioning
  - Built EnhancedAgeCollector with multi-source fallback: NFL.com → ESPN → Wikipedia → birth date calculation
  - Implemented DatabaseVersioning system with full historical tracking of all player data changes
  - Database stores current data in main table, historical versions in separate history table
  - All 74 fields tracked with timestamps, change detection, and version numbering
  - Web interface always shows latest data while preserving complete historical record
  - System handles player updates by creating historical snapshots before applying new data
  - Age collection tries official sources first, falls back to Wikipedia biographical data extraction

- July 18, 2025. **PROFESSIONAL NAVIGATION SYSTEM & COMPLETE DATA INTEGRATION**: Built comprehensive web interface with professional navigation
  - Added responsive navigation bar with system status monitoring and professional design
  - Created dedicated "Data Collection" page with all three scraper modes and real-time progress tracking
  - Built advanced "View Data" page with Excel-like filtering by team, position, experience, age, college, social media, and data quality
  - Fixed data loading issue - dashboard now displays actual collected data (2,910 players from all 32 NFL teams)
  - All scraper modes fully operational: Standard (11 fields), Comprehensive (70+ fields), Firecrawl (AI-powered with paid API)
  - Integrated sortable columns, pagination, search functionality, and CSV export capabilities
  - System successfully collected complete NFL dataset with 24 data fields per player across all teams
  - Fixed comprehensive mode to use fast SimpleComprehensiveCollector (10x faster than old system)
  - Comprehensive mode now collects full rosters (91-92 players per team) with 70 fields each
  - Processing time: ~2 minutes per team with 2.9/5 average data quality score
  - Firecrawl mode operational but experiences rate limiting with heavy API usage (expected behavior)

## User Preferences

Preferred communication style: Simple, everyday language.

## Project Evolution Request (July 04, 2025)

User has requested a complete architectural shift from the current modular web application to a single-cell data pipeline approach:

**New Requirements:**
- Single Python script (not web app)
- Firecrawl API for intelligent page discovery
- Direct parsing (BeautifulSoup) with AI fallback only when needed
- Focus on social media analytics (Instagram, Twitter, TikTok, YouTube)
- Open-source Mistral for fallback parsing
- Comprehensive player data: Wikipedia bio, PFR stats, Spotrac earnings, news mentions
- Output: Single CSV with all enriched data

**Key Shift:** From modular, extensible architecture to focused, efficient pipeline optimized for cost and speed.