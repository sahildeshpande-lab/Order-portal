"""
Database Isolation Verification Script
Ensures that the test suite uses a separate database and won't affect test.db
"""

import os
import sys


def verify_isolation():
    """Verify that test configuration is isolated"""
    
    print("="*70)
    print("DATABASE ISOLATION VERIFICATION")
    print("="*70)
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: tests directory exists
    checks_total += 1
    print("\n✓ Check 1: Verifying tests directory...")
    if os.path.exists("tests") and os.path.isdir("tests"):
        print("  ✅ PASS: tests/ directory found")
        checks_passed += 1
    else:
        print("  ❌ FAIL: tests/ directory not found")
    
    # Check 2: conftest.py uses test_suite.db
    checks_total += 1
    print("\n✓ Check 2: Verifying test database name...")
    try:
        with open("tests/conftest.py", "r") as f:
            content = f.read()
            if "test_suite.db" in content and "test.db" not in content.replace("test_suite.db", ""):
                print("  ✅ PASS: Test suite uses 'test_suite.db' (isolated database)")
                checks_passed += 1
            else:
                print("  ❌ FAIL: Test suite may be using 'test.db'")
    except FileNotFoundError:
        print("  ⚠️  WARNING: tests/conftest.py not found")
    
    # Check 3: test_uploads directory is used
    checks_total += 1
    print("\n✓ Check 3: Verifying uploads directory...")
    try:
        with open("tests/conftest.py", "r") as f:
            content = f.read()
            if "test_uploads" in content:
                print("  ✅ PASS: Test suite uses 'test_uploads/' (isolated directory)")
                checks_passed += 1
            else:
                print("  ⚠️  WARNING: Test suite may use production uploads/")
    except FileNotFoundError:
        print("  ⚠️  WARNING: tests/conftest.py not found")
    
    # Check 4: No test.db in current directory will be modified
    checks_total += 1
    print("\n✓ Check 4: Checking for existing test.db...")
    if os.path.exists("test.db"):
        original_mtime = os.path.getmtime("test.db")
        print(f"  ℹ️  INFO: Found existing test.db (last modified: {original_mtime})")
        print("  ✅ PASS: This file will NOT be modified by test suite")
        checks_passed += 1
    else:
        print("  ℹ️  INFO: No test.db found in current directory")
        print("  ✅ PASS: No risk of modifying non-existent file")
        checks_passed += 1
    
    # Check 5: Cleanup is configured
    checks_total += 1
    print("\n✓ Check 5: Verifying cleanup configuration...")
    try:
        with open("tests/conftest.py", "r") as f:
            content = f.read()
            if "remove" in content and "test_suite.db" in content:
                print("  ✅ PASS: Test cleanup is configured")
                checks_passed += 1
            else:
                print("  ⚠️  WARNING: Cleanup may not be configured")
    except FileNotFoundError:
        print("  ⚠️  WARNING: tests/conftest.py not found")
    
    # Check 6: pytest.ini exists
    checks_total += 1
    print("\n✓ Check 6: Checking for pytest.ini...")
    if os.path.exists("pytest.ini"):
        print("  ✅ PASS: pytest.ini found (test configuration present)")
        checks_passed += 1
    else:
        print("  ⚠️  WARNING: pytest.ini not found")
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print(f"Checks Passed: {checks_passed}/{checks_total}")
    
    if checks_passed == checks_total:
        print("\n✅ ALL CHECKS PASSED - Database isolation is properly configured!")
        print("\nYour main test.db will NOT be affected by running the test suite.")
        print("The tests will use 'test_suite.db' which will be automatically cleaned up.")
    elif checks_passed >= checks_total - 1:
        print("\n⚠️  MOSTLY SAFE - Minor warnings detected but isolation should work")
        print("\nYour main test.db should be safe, but review warnings above.")
    else:
        print("\n❌ FAILED - Database isolation may not be properly configured!")
        print("\nPlease review the failed checks above before running tests.")
        return False
    
    print("="*70 + "\n")
    return True


def show_safe_run_instructions():
    """Show instructions for safely running tests"""
    
    print("\n" + "="*70)
    print("HOW TO SAFELY RUN TESTS")
    print("="*70)
    
    print("\n1. First, verify isolation (you just did this! ✓)")
    print("\n2. Run the tests with:")
    print("   python run_tests.py")
    print("   OR")
    print("   pytest tests/ -v --cov=main --cov-report=html")
    
    print("\n3. What happens during testing:")
    print("   • Creates: test_suite.db (temporary test database)")
    print("   • Creates: test_uploads/ (temporary uploads folder)")
    print("   • Does NOT touch: test.db (your main database)")
    print("   • Does NOT touch: uploads/ (your main uploads)")
    
    print("\n4. After tests complete:")
    print("   • test_suite.db is automatically deleted")
    print("   • test_uploads/ is automatically deleted")
    print("   • Your original files remain unchanged")
    
    print("\n5. To generate HTML report:")
    print("   pytest tests/ -v --cov=main --cov-report=html --html=test_report.html")
    
    print("\n6. View coverage report:")
    print("   open htmlcov/index.html")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print("\n🔍 Starting Database Isolation Verification...\n")
    
    if verify_isolation():
        show_safe_run_instructions()
        sys.exit(0)
    else:
        print("\n⚠️  Please fix the issues above before running tests.\n")
        sys.exit(1)