# Feature Testing MCP Server

A Model Context Protocol (MCP) server that connects to Google Sheets to manage and execute automated feature tests for the Gravity Score project.

## Overview

This MCP server allows AI agents to:
- Read feature lists from Google Sheets
- Execute tests for each feature
- Update Google Sheets with test results automatically
- Track test status (PASS/FAIL/PENDING) over time

## Architecture

```
AI Agent (Claude/GPT/etc)
    ↓ [MCP Protocol]
Feature Testing MCP Server
    ↓ [Google Sheets API]
Google Sheets (Feature List)
    ↓ [Subprocess Execution]
Test Scripts (NFL/NBA scrapers, pipelines, etc)
```

## Features

- **Google Sheets Integration**: Read/write feature test data
- **Test Registry**: Maps features to test implementations
- **Automated Testing**: Runs tests and captures results
- **Status Tracking**: PASS/FAIL/PENDING with timestamps
- **Multi-Transport**: Supports stdio, SSE, and HTTP transports
- **Production Ready**: Proper logging, error handling, timeouts

## Installation

1. Install dependencies:
```bash
cd /Users/robcseals/Gravity_Score
pip install -e .
```

2. Set up Google Sheets credentials (see [ENV_CONFIG.md](ENV_CONFIG.md))

3. Create `.env` file with configuration

4. Verify installation:
```bash
feature-testing-mcp --help
```

## Usage

### Start the Server

**Stdio Mode** (for local AI agents like Claude Desktop):
```bash
feature-testing-mcp stdio
```

**HTTP Mode** (for remote AI agents):
```bash
feature-testing-mcp streamable-http
```

**SSE Mode** (deprecated but available):
```bash
feature-testing-mcp sse
```

### Configure AI Agent

Add to your MCP client configuration:

**For stdio (Claude Desktop, etc):**
```json
{
  "mcpServers": {
    "feature-testing": {
      "command": "feature-testing-mcp",
      "args": ["stdio"],
      "env": {
        "GOOGLE_SHEET_ID": "your_sheet_id",
        "GOOGLE_CREDENTIALS_PATH": "/path/to/credentials.json"
      }
    }
  }
}
```

**For HTTP (remote agents):**
```json
{
  "mcpServers": {
    "feature-testing": {
      "url": "http://localhost:8018/mcp"
    }
  }
}
```

## Available MCP Tools

The server exposes these tools to AI agents:

### 1. `read_features`
Read all features from the Google Sheet with their current status.

**Returns:** Formatted list of features with status, description, last tested time

### 2. `test_feature`
Test a specific feature by name.

**Arguments:**
- `feature_name` (string): Name of feature to test

**Returns:** Test result with PASS/FAIL status and details

### 3. `test_all_features`
Run tests for all features (or filter by status).

**Arguments:**
- `status_filter` (optional string): PENDING, PASS, or FAIL

**Returns:** Summary of all test results

### 4. `update_feature_status`
Manually update a feature's status without running tests.

**Arguments:**
- `feature_name` (string): Name of feature
- `status` (string): PASS, FAIL, or PENDING
- `notes` (optional string): Notes about the update

**Returns:** Confirmation message

### 5. `list_available_tests`
List all registered tests that can be executed.

**Returns:** List of test names with descriptions and availability

## Test Registry

Tests are registered in `test_registry.py`. Scrapers and ML training run in other repositories; the registry currently exposes:

- `test_recruiting_collector` — in-repo recruiting smoke script (`test_recruiting_collector.py`)

## Google Sheets Format

Your sheet should have these columns (in order):

| Column | Description |
|--------|-------------|
| Feature Name | Name of the feature to test |
| Description | Brief description of the feature |
| Test Function | Optional - specific test name from registry |
| Status | PASS/FAIL/PENDING (updated by server) |
| Last Tested | Timestamp of last test (updated by server) |
| Notes | Test result notes (updated by server) |
| Test Result | Detailed JSON result (updated by server) |

## Example Workflow

1. User adds features to Google Sheet
2. AI agent reads features: `read_features()`
3. AI agent tests all pending features: `test_all_features(status_filter="PENDING")`
4. Server executes tests and updates sheet with results
5. User reviews results in Google Sheet
6. AI agent can re-test failed features: `test_feature("Feature Name")`

## Development

### Project Structure

```
feature_testing_mcp/
├── __init__.py           - Package init
├── __main__.py           - CLI entry point
├── server.py             - MCP server with tools
├── config.py             - Configuration
├── sheets_client.py      - Google Sheets operations
├── test_executor.py      - Test execution logic
├── test_registry.py      - Test mapping
├── exceptions.py         - Custom exceptions
├── ENV_CONFIG.md         - Setup instructions
└── README.md             - This file
```

### Adding New Tests

1. Add test script to Gravity_Score project
2. Register in `test_registry.py`:
```python
TEST_REGISTRY['test_my_feature'] = {
    'script': 'path/to/test_script.py',
    'args': ['arg1', 'arg2'],
    'description': 'What this test does',
    'timeout': 180
}
```
3. Add keywords for auto-detection:
```python
KEYWORD_MAPPING['test_my_feature'] = ['keyword1', 'keyword2']
```

## Troubleshooting

### "Failed to connect to Google Sheets"
- Check GOOGLE_CREDENTIALS_PATH points to valid credentials.json
- Verify GOOGLE_SHEET_ID is correct
- Ensure service account has access to the sheet

### "Test script not found"
- Verify PROJECT_ROOT is set correctly
- Check test script exists at specified path
- Ensure test script is executable

### "Permission denied"
- Check file permissions on test scripts
- Verify service account has Editor access to sheet
- Check credentials.json file permissions

## Logs

Server logs are written to:
```
/Users/robcseals/Gravity_Score/feature-testing-mcp.log
```

Monitor logs:
```bash
tail -f /Users/robcseals/Gravity_Score/feature-testing-mcp.log
```

## License

Part of the Gravity Score project.

