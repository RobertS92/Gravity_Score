# NFL Gravity 🏈

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NFL Gravity** is a production-ready Modular Content Pipeline (MCP) for scraping, enriching, and analyzing NFL player and team data with LLM-powered intelligence and modular architecture.

## ✨ Features

- **🔧 Modular Architecture**: Pluggable extractors, validators, and storage backends
- **🤖 LLM Integration**: OpenAI GPT-4o, HuggingFace, and local model support
- **📊 Multi-Source Data**: NFL.com, ESPN, Pro Football Reference, Wikipedia, social media
- **✅ Data Validation**: Pydantic-based schema enforcement with quality monitoring
- **💾 Multiple Formats**: Parquet, CSV, JSON with compression and timestamping
- **🌐 Web Interface**: Real-time dashboard with progress tracking
- **⚡ CLI Tool**: Command-line interface for automated workflows
- **🧪 Comprehensive Testing**: 90%+ test coverage with CI/CD integration
- **🤝 Respectful Scraping**: robots.txt compliance, polite delays, rotating user agents

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (when published)
pip install nfl-gravity

# Or install from source
git clone https://github.com/nfl-gravity/nfl-gravity.git
cd nfl-gravity
pip install -e .
