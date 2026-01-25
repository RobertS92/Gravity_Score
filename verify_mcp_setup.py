#!/usr/bin/env python3
"""
Verification script for Feature Testing MCP Server setup.
Tests that all components are properly installed without requiring Google credentials.
"""

import sys
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_header(text):
    """Print section header"""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def check_pass(text):
    """Print success message"""
    print(f"{GREEN}✅ PASS:{RESET} {text}")

def check_fail(text):
    """Print failure message"""
    print(f"{RED}❌ FAIL:{RESET} {text}")

def check_warn(text):
    """Print warning message"""
    print(f"{YELLOW}⚠️  WARN:{RESET} {text}")

def check_module_structure():
    """Verify feature_testing_mcp module structure"""
    print_header("1. Checking Module Structure")
    
    required_files = [
        'feature_testing_mcp/__init__.py',
        'feature_testing_mcp/__main__.py',
        'feature_testing_mcp/server.py',
        'feature_testing_mcp/config.py',
        'feature_testing_mcp/sheets_client.py',
        'feature_testing_mcp/test_executor.py',
        'feature_testing_mcp/test_registry.py',
        'feature_testing_mcp/exceptions.py',
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            check_pass(f"Found {file_path}")
        else:
            check_fail(f"Missing {file_path}")
            all_exist = False
    
    return all_exist

def check_imports():
    """Test that all modules can be imported"""
    print_header("2. Checking Module Imports")
    
    imports_ok = True
    
    # Test individual module imports
    modules = [
        ('feature_testing_mcp.config', 'FeatureTestingConfig'),
        ('feature_testing_mcp.exceptions', 'FeatureTestingError'),
        ('feature_testing_mcp.test_registry', 'TEST_REGISTRY'),
    ]
    
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            check_pass(f"Imported {module_name}.{class_name}")
        except ImportError as e:
            check_fail(f"Failed to import {module_name}: {e}")
            imports_ok = False
        except AttributeError as e:
            check_fail(f"Missing {class_name} in {module_name}: {e}")
            imports_ok = False
    
    return imports_ok

def check_dependencies():
    """Check that required dependencies are installed"""
    print_header("3. Checking Dependencies")
    
    dependencies = [
        'typer',
        'gspread',
        'google.auth',
        'mcp',
        'fastmcp',
    ]
    
    all_installed = True
    for dep in dependencies:
        try:
            __import__(dep.replace('.', '_'))
            check_pass(f"Installed: {dep}")
        except ImportError:
            check_fail(f"Missing: {dep}")
            all_installed = False
    
    return all_installed

def check_test_registry():
    """Verify test registry has tests"""
    print_header("4. Checking Test Registry")
    
    try:
        from feature_testing_mcp.test_registry import TEST_REGISTRY, list_all_tests
        
        tests = list_all_tests()
        if tests:
            check_pass(f"Found {len(tests)} registered tests")
            print(f"\n{BOLD}Available tests:{RESET}")
            for test_name in tests[:5]:  # Show first 5
                print(f"  - {test_name}")
            if len(tests) > 5:
                print(f"  ... and {len(tests) - 5} more")
            return True
        else:
            check_fail("No tests found in registry")
            return False
    except Exception as e:
        check_fail(f"Error checking test registry: {e}")
        return False

def check_cli():
    """Check CLI can be invoked"""
    print_header("5. Checking CLI")
    
    try:
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'feature_testing_mcp', '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and 'Feature Testing MCP Server' in result.stdout:
            check_pass("CLI is functional")
            return True
        else:
            check_fail("CLI not working properly")
            return False
    except Exception as e:
        check_fail(f"Error testing CLI: {e}")
        return False

def check_pyproject():
    """Check pyproject.toml exists and has correct entry point"""
    print_header("6. Checking pyproject.toml")
    
    pyproject_path = Path('pyproject.toml')
    if not pyproject_path.exists():
        check_fail("pyproject.toml not found")
        return False
    
    content = pyproject_path.read_text()
    if 'feature-testing-mcp' in content:
        check_pass("Found feature-testing-mcp script entry point")
        return True
    else:
        check_warn("Script entry point not found in pyproject.toml")
        return False

def main():
    """Run all verification checks"""
    print(f"\n{BOLD}{GREEN}Feature Testing MCP Server - Setup Verification{RESET}")
    print(f"{'='*70}\n")
    
    results = []
    
    # Run all checks
    results.append(('Module Structure', check_module_structure()))
    results.append(('Module Imports', check_imports()))
    results.append(('Dependencies', check_dependencies()))
    results.append(('Test Registry', check_test_registry()))
    results.append(('CLI', check_cli()))
    results.append(('pyproject.toml', check_pyproject()))
    
    # Print summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{status}: {name}")
    
    print(f"\n{BOLD}Results: {passed}/{total} checks passed{RESET}\n")
    
    if passed == total:
        print(f"{GREEN}{BOLD}🎉 All checks passed! MCP server is ready to use.{RESET}\n")
        print(f"{BOLD}Next steps:{RESET}")
        print("1. Set up Google Sheets credentials (see feature_testing_mcp/ENV_CONFIG.md)")
        print("2. Create .env file with your configuration")
        print("3. Start the server: feature-testing-mcp stdio\n")
        return 0
    else:
        print(f"{RED}{BOLD}⚠️  Some checks failed. Please review the errors above.{RESET}\n")
        if not results[2][1]:  # Dependencies check failed
            print(f"{YELLOW}To install dependencies:{RESET}")
            print("  pip install -e .\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

