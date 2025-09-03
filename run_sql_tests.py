#!/usr/bin/env python3
"""
Test runner for the SQL class test suite.
Run this script to execute all SQL class tests with proper error handling.
"""

import unittest
import sys
import os

# Add the current directory to the path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_sql_tests():
    """Run all SQL tests and provide a summary."""
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('test_sql')
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("SQL TEST SUITE SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILED TESTS ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\nERROR TESTS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    if not result.failures and not result.errors:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. See details above.")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_sql_tests()
    sys.exit(0 if success else 1)