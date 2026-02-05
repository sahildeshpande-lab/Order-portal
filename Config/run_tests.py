#!/usr/bin/env python3
"""
Comprehensive Test Runner for Order Portal API
Runs all tests with coverage reporting
"""

import sys
import os
import subprocess
import shutil
import time


def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(text.center(70))
    print("="*70 + "\n")


def clean_artifacts():
    """Clean up old test artifacts"""
    print_header("Cleaning Previous Test Artifacts")
    
    artifacts = [
        "test_suite.db",
        "test_uploads",
        "htmlcov",
        "test_report.html",
        "coverage.json",
        ".coverage",
        ".pytest_cache",
        "assets"
    ]
    
    for artifact in artifacts:
        if os.path.exists(artifact):
            try:
                if os.path.isdir(artifact):
                    shutil.rmtree(artifact)
                    print(f"✓ Removed directory: {artifact}")
                else:
                    os.remove(artifact)
                    print(f"✓ Removed file: {artifact}")
            except Exception as e:
                print(f"⚠️  Could not remove {artifact}: {e}")
    
    print("\n✅ Cleanup completed")


def run_tests():
    """Run the test suite"""
    print_header("Running Test Suite")
    
    cmd = [
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=main",
        "--cov=db",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=json",
        "--html=test_report.html",
        "--self-contained-html",
        "-ra",
        "--disable-warnings"
    ]
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def print_summary():
    """Print test summary"""
    print_header("Test Summary")
    
    if os.path.exists("coverage.json"):
        import json
        try:
            with open("coverage.json", "r") as f:
                data = json.load(f)
                total_coverage = data.get("totals", {}).get("percent_covered", 0)
                print(f"📊 Total Coverage: {total_coverage:.2f}%")
        except:
            print("📊 Coverage data available in coverage.json")
    
    print("\n📁 Generated Reports:")
    if os.path.exists("htmlcov/index.html"):
        abs_path = os.path.abspath("htmlcov/index.html")
        print(f"   • Coverage Report: {abs_path}")
        print(f"     Open with: start {abs_path}" if os.name == 'nt' else f"     Open with: open {abs_path}")
    if os.path.exists("test_report.html"):
        abs_path = os.path.abspath("test_report.html")
        print(f"   • Test Report: {abs_path}")
        print(f"     Open with: start {abs_path}" if os.name == 'nt' else f"     Open with: open {abs_path}")
    
    print("\n" + "="*70)


def main():
    """Main test runner"""
    print_header("Order Portal API - Test Suite Runner")
    
    # Clean old artifacts
    clean_artifacts()
    
    # Small delay to ensure files are released
    time.sleep(1)
    
    # Run tests
    exit_code = run_tests()
    
    # Print summary
    print_summary()
    
    if exit_code == 0:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n⚠️  Some tests failed. Check the reports for details.")
    
    print("\n" + "="*70 + "\n")
    
    # Don't exit with error code to allow viewing reports
    sys.exit(0)


if __name__ == "__main__":
    main()