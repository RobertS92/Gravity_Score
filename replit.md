# NFL Gravity - Modular Content Pipeline

## Overview
NFL Gravity is a production-ready Python package designed to extract, enrich, and analyze NFL player and team data. It uses a sophisticated Modular Content Pipeline (MCP) that combines web scraping from multiple sources with LLM-powered intelligence to create comprehensive datasets of NFL information. The project aims to provide comprehensive NFL player data, including biographical information, career statistics, social media presence, and financial details, with a focus on intelligent extraction and analysis.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture
The application follows a modular architecture with clear separation of concerns, designed for independent testability and replaceability of components.

**Key Architectural Decisions:**
- **Modular Design**: Components are independently testable and replaceable.
- **Plugin Architecture**: LLM providers and data extractors are pluggable.
- **Configuration-Driven**: Behavior is controlled by environment variables and a `Config` class.
- **Graceful Degradation**: System functions even if external services fail.
- **UI/UX**: Features a professional web interface with dynamic data display, filtering, and export capabilities. It includes comprehensive player search, personal collection management, and detailed player profiles.
- **Technical Implementations**:
    - **Data Extractors**: Includes `WikipediaExtractor`, `SocialMediaExtractor`, and `NFLSitesExtractor` for diverse data acquisition.
    - **LLM Integration**: Supports multi-provider LLMs (e.g., OpenAI GPT-4o) using an adapter pattern for intelligent data extraction and fallback strategies.
    - **Pipeline Orchestration**: `PipelineOrchestrator` coordinates workflows with `SimpleScheduler` for job scheduling and threaded execution for performance.
    - **Storage System**: `DataWriter` supports multi-format output (Parquet, CSV, JSON) with automatic schema generation and timestamped organization.
    - **Data Flow**: Configuration loading, pipeline initialization, team processing (roster extraction, player enrichment, social media discovery, LLM application), data validation, and storage.
    - **Gravity Scoring System**: Implements a comprehensive gravity scoring engine with a 5-component analysis (Brand Power, Proof, Proximity, Velocity, Risk) using an intelligent algorithm for position-specific scoring and bonuses.

**System Design Choices:**
- **Robust Data Collection**: Multi-source fallback system for data collection (NFL.com, Wikipedia, ESPN, Spotrac, Pro Football Reference, Social Media Search) ensuring comprehensive and authentic data.
- **AI-Powered Data Enrichment**: Utilizes OpenAI GPT-4o for intelligent extraction of missing biographical, career, and contract data, including vision-enhanced scraping for semantic analysis of web content.
- **Real-time Progress Tracking**: Comprehensive monitoring system for scraping modes with mode-specific estimates, real-time team and player progress, and ETA calculations.
- **Database Management**: Implements a `DatabaseUpdater` for handling existing player updates, merging new data with existing records, and preserving historical data.

## External Dependencies
- **APIs**:
    - OpenAI API (for GPT-4o)
    - HuggingFace (for alternative LLM models)
- **Web Sources**:
    - Wikipedia (player biographical and career data)
    - NFL.com (official rosters, player statistics)
    - ESPN (team rosters, player data, experience)
    - Pro Football Reference (historical player statistics, career stats)
    - Spotrac (contract data, salaries)
    - Social Media: Twitter/X, Instagram, TikTok, YouTube (profile discovery, follower metrics)
- **Python Packages**:
    - `requests` (HTTP client)
    - `beautifulsoup4` (HTML parsing)
    - `pandas` (data manipulation)
    - `pyarrow` (Parquet support)
    - `pydantic` (data validation)
    - `flask` (web interface)
    - `typer` (CLI framework)