#!/usr/bin/env python3
"""
Test runner for the recommendation system
Run all tests or specific test categories
"""

import sys
import pytest
import argparse


def main():
    parser = argparse.ArgumentParser(description='Run recommendation system tests')
    parser.add_argument(
        '--type',
        choices=['unit', 'integration', 'performance', 'metrics', 'all'],
        default='all',
        help='Type of tests to run'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--generate-data',
        action='store_true',
        help='Generate mock data before testing'
    )
    
    args = parser.parse_args()
    
    # Configure pytest arguments
    pytest_args = []
    
    if args.verbose:
        pytest_args.append('-v')
    
    # Add specific test files based on type
    if args.type == 'unit':
        pytest_args.extend([
            'tests/test_linear_svm_recommender.py',
            'tests/test_advanced_neighbors_recommender.py',
            'tests/test_shopping_cart_recommender.py'
        ])
    elif args.type == 'integration':
        pytest_args.append('tests/test_recommendation_integration.py')
    elif args.type == 'performance':
        pytest_args.append('tests/test_performance_benchmarks.py')
    elif args.type == 'metrics':
        pytest_args.append('tests/test_metrics.py')
    else:  # all
        pytest_args.append('tests/')
    
    # Generate mock data if requested
    if args.generate_data:
        print("Generating mock data...")
        from tests.mock_data_generator import MockDataGenerator
        from eshop import create_app
        
        app = create_app()
        with app.app_context():
            generator = MockDataGenerator()
            generator.generate_complete_test_dataset()
            print("Mock data generated successfully!")
    
    # Run tests
    print(f"\nRunning {args.type} tests...")
    exit_code = pytest.main(pytest_args)
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())