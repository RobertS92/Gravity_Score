"""Feature Testing MCP Server"""

import logging
import os
import json
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import FeatureTestingConfig
from .sheets_client import GoogleSheetsClient
from .test_executor import TestExecutor
from .exceptions import (
    FeatureTestingError,
    SheetsError,
    TestExecutionError,
    ConfigurationError,
)

# Get project root directory path for log file
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT_DIR, "feature-testing-mcp.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # File-based logging to avoid breaking stdio mode
        logging.FileHandler(LOG_FILE)
    ],
)
logger = logging.getLogger("feature-testing-mcp")

# Initialize configuration
config = FeatureTestingConfig()

# Initialize FastMCP server
mcp = FastMCP(
    "feature-testing-mcp",
    host=config.FASTMCP_HOST,
    port=config.FASTMCP_PORT,
    instructions="MCP server for automated feature testing with Google Sheets. "
                 "Connects to Google Sheets to read feature lists, runs tests, and updates results."
)

# Global clients (initialized on first use)
sheets_client: Optional[GoogleSheetsClient] = None
test_executor: Optional[TestExecutor] = None


def ensure_initialized():
    """Ensure clients are initialized"""
    global sheets_client, test_executor
    
    if sheets_client is None:
        sheets_client = GoogleSheetsClient(config)
        success, message = sheets_client.connect()
        if not success:
            raise SheetsError(f"Failed to connect to Google Sheets: {message}")
        logger.info("Google Sheets client initialized")
    
    if test_executor is None:
        test_executor = TestExecutor(config.PROJECT_ROOT)
        logger.info("Test executor initialized")


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read Features from Google Sheet",
        readOnlyHint=True,
    ),
)
def read_features() -> str:
    """
    Read all features from the Google Sheet and return them as formatted text.
    
    Returns a list of all features with their current status, description, and last test date.
    """
    try:
        ensure_initialized()
        
        features, error = sheets_client.read_features()
        
        if error:
            logger.error(f"Failed to read features: {error}")
            return f"Error: {error}"
        
        if not features:
            return "No features found in the sheet"
        
        # Format as readable text
        result = f"Found {len(features)} features:\n\n"
        for i, feature in enumerate(features, 1):
            result += f"{i}. {feature['feature_name']}\n"
            result += f"   Status: {feature['current_status']}\n"
            if feature.get('description'):
                result += f"   Description: {feature['description']}\n"
            if feature.get('test_function'):
                result += f"   Test Function: {feature['test_function']}\n"
            if feature.get('last_tested'):
                result += f"   Last Tested: {feature['last_tested']}\n"
            if feature.get('notes'):
                result += f"   Notes: {feature['notes'][:100]}...\n" if len(feature['notes']) > 100 else f"   Notes: {feature['notes']}\n"
            result += "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in read_features: {e}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="Test a Specific Feature",
        destructiveHint=True,
    ),
)
def test_feature(feature_name: str) -> str:
    """
    Run a test for a specific feature by name and update the sheet with results.
    
    Args:
        feature_name: Name of the feature to test (must match exactly)
    
    Returns:
        Test result message with status and details
    """
    try:
        ensure_initialized()
        
        logger.info(f"Testing feature: {feature_name}")
        
        # Find the feature
        feature = sheets_client.find_feature_by_name(feature_name)
        if not feature:
            return f"Feature '{feature_name}' not found in sheet"
        
        # Determine which test to run
        test_function = feature.get('test_function', '').strip()
        
        if test_function:
            # Use specified test function
            logger.info(f"Using specified test function: {test_function}")
            success, notes, test_result = test_executor.run_test(test_function)
        else:
            # Infer test from feature name and description
            logger.info(f"Inferring test for: {feature_name}")
            success, notes, test_result = test_executor.run_inferred_test(
                feature['feature_name'],
                feature.get('description', '')
            )
        
        # Update the sheet
        status = "PASS" if success else "FAIL"
        update_success, update_error = sheets_client.update_feature_result(
            feature['row_number'],
            status,
            notes,
            test_result
        )
        
        if not update_success:
            logger.error(f"Failed to update sheet: {update_error}")
            return f"Test completed ({status}) but failed to update sheet: {update_error}"
        
        # Build result message
        result = f"✅ Test completed for '{feature_name}': {status}\n\n"
        result += f"Notes: {notes}\n"
        if test_result:
            result += f"\nDetails:\n"
            for key, value in test_result.items():
                result += f"  - {key}: {value}\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in test_feature: {e}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="Test All Features",
        destructiveHint=True,
    ),
)
def test_all_features(status_filter: Optional[str] = None) -> str:
    """
    Run tests for all features, optionally filtering by status.
    
    Args:
        status_filter: Optional filter (PENDING, PASS, or FAIL). If not provided, tests all features.
    
    Returns:
        Summary of test results for all features
    """
    try:
        ensure_initialized()
        
        logger.info(f"Testing all features (filter: {status_filter or 'none'})")
        
        # Read features
        features, error = sheets_client.read_features()
        if error:
            return f"Error reading features: {error}"
        
        if not features:
            return "No features found in the sheet"
        
        # Filter by status if specified
        if status_filter:
            status_filter_upper = status_filter.upper()
            if status_filter_upper not in ['PENDING', 'PASS', 'FAIL']:
                return f"Invalid status filter: {status_filter}. Must be PENDING, PASS, or FAIL"
            features = [f for f in features if f['current_status'].upper() == status_filter_upper]
            logger.info(f"Filtered to {len(features)} features with status: {status_filter}")
        
        if not features:
            return f"No features found with status: {status_filter}"
        
        # Run tests for each feature
        results = {
            'passed': 0,
            'failed': 0,
            'total': len(features),
            'details': []
        }
        
        for i, feature in enumerate(features, 1):
            feature_name = feature['feature_name']
            logger.info(f"[{i}/{len(features)}] Testing: {feature_name}")
            
            # Determine which test to run
            test_function = feature.get('test_function', '').strip()
            
            if test_function:
                success, notes, test_result = test_executor.run_test(test_function)
            else:
                success, notes, test_result = test_executor.run_inferred_test(
                    feature_name,
                    feature.get('description', '')
                )
            
            # Update sheet
            status = "PASS" if success else "FAIL"
            sheets_client.update_feature_result(
                feature['row_number'],
                status,
                notes,
                test_result
            )
            
            # Track results
            if success:
                results['passed'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'feature': feature_name,
                'status': status,
                'notes': notes[:100]
            })
        
        # Build summary
        summary = f"\n{'='*60}\n"
        summary += f"TEST SUMMARY\n"
        summary += f"{'='*60}\n"
        summary += f"Total: {results['total']}\n"
        summary += f"Passed: {results['passed']} ✅\n"
        summary += f"Failed: {results['failed']} ❌\n"
        summary += f"{'='*60}\n\n"
        
        summary += "Details:\n"
        for detail in results['details']:
            status_icon = "✅" if detail['status'] == "PASS" else "❌"
            summary += f"{status_icon} {detail['feature']}: {detail['status']}\n"
            if detail['status'] == "FAIL":
                summary += f"   {detail['notes']}\n"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in test_all_features: {e}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="Update Feature Status Manually",
        destructiveHint=True,
    ),
)
def update_feature_status(feature_name: str, status: str, notes: str = "") -> str:
    """
    Manually update a feature's status in the sheet without running tests.
    
    Args:
        feature_name: Name of the feature to update
        status: New status (PASS, FAIL, or PENDING)
        notes: Optional notes about the status change
    
    Returns:
        Confirmation message
    """
    try:
        ensure_initialized()
        
        # Validate status
        status_upper = status.upper()
        if status_upper not in ['PASS', 'FAIL', 'PENDING']:
            return f"Invalid status: {status}. Must be PASS, FAIL, or PENDING"
        
        # Find the feature
        feature = sheets_client.find_feature_by_name(feature_name)
        if not feature:
            return f"Feature '{feature_name}' not found in sheet"
        
        # Update
        success, error = sheets_client.update_feature_result(
            feature['row_number'],
            status_upper,
            notes
        )
        
        if not success:
            return f"Failed to update: {error}"
        
        return f"✅ Updated '{feature_name}' status to {status_upper}"
        
    except Exception as e:
        logger.error(f"Error in update_feature_status: {e}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Available Tests",
        readOnlyHint=True,
    ),
)
def list_available_tests() -> str:
    """
    List all available test functions that can be run.
    
    Returns:
        List of all registered tests with descriptions
    """
    try:
        ensure_initialized()
        
        tests = test_executor.list_available_tests()
        
        result = f"Available Tests ({len(tests)} total):\n\n"
        for test_name, test_info in tests.items():
            available_icon = "✅" if test_info['available'] else "❌"
            result += f"{available_icon} {test_name}\n"
            result += f"   Description: {test_info['description']}\n"
            result += f"   Script: {test_info['script']}\n"
            result += f"   Timeout: {test_info['timeout']}s\n"
            if not test_info['available']:
                result += f"   ⚠️  Script not found at: {test_info['script_path']}\n"
            result += "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in list_available_tests: {e}", exc_info=True)
        return f"Error: {str(e)}"


# Transport mode functions

def run_sse():
    """Run Feature Testing MCP server in SSE mode."""
    try:
        logger.info("Starting Feature Testing MCP server with SSE transport")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")


def run_streamable_http():
    """Run Feature Testing MCP server in streamable HTTP mode."""
    try:
        logger.info("Starting Feature Testing MCP server with streamable HTTP transport")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")


def run_stdio():
    """Run Feature Testing MCP server in stdio mode."""
    try:
        logger.info("Starting Feature Testing MCP server with stdio transport")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")

