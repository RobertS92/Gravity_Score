# Environment Configuration

Create a `.env` file in the Gravity_Score project root with the following variables:

```bash
# Google Sheets Configuration
# Get your Sheet ID from the URL: https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_WORKSHEET_NAME=Features

# Project Configuration
# Path to your Gravity Score project root
PROJECT_ROOT=/Users/robcseals/Gravity_Score

# Server Configuration
# Host and port for MCP server (when using HTTP/SSE transport)
FASTMCP_HOST=0.0.0.0
FASTMCP_PORT=8018
```

## Setup Instructions

### 1. Google Cloud Setup
- Go to https://console.cloud.google.com/
- Create a new project or use existing
- Enable "Google Sheets API" and "Google Drive API"

### 2. Service Account Creation
- Go to "IAM & Admin" > "Service Accounts"
- Click "Create Service Account"
- Name it (e.g., "feature-tester")
- Skip role assignment

### 3. Create Credentials
- Click on the service account
- Go to "Keys" tab
- Click "Add Key" > "Create new key"
- Choose "JSON" format
- Save as "credentials.json" in project root

### 4. Share Your Google Sheet
- Open your Google Sheet
- Click "Share" button
- Add the service account email (found in credentials.json)
- Give it "Editor" permissions

### 5. Setup Sheet Format
Your Google Sheet should have these columns (in order):

| Feature Name | Description | Test Function | Status | Last Tested | Notes | Test Result |
|--------------|-------------|---------------|--------|-------------|-------|-------------|

### 6. Install Dependencies

```bash
cd /Users/robcseals/Gravity_Score
pip install -e .
```

This will install all required dependencies including:
- mcp[cli]>=1.10.1
- fastmcp>=2.0.0
- gspread>=5.12.0
- google-auth>=2.23.0
- google-auth-oauthlib>=1.1.0
- typer>=0.16.0

### 7. Test the Installation

```bash
feature-testing-mcp --help
```

You should see:
```
Usage: feature-testing-mcp [OPTIONS] COMMAND [ARGS]...

  Feature Testing MCP Server for Google Sheets

Options:
  --help  Show this message and exit.

Commands:
  sse              Start Feature Testing MCP Server in SSE mode
  stdio            Start Feature Testing MCP Server in stdio mode
  streamable-http  Start Feature Testing MCP Server in streamable HTTP mode
```

