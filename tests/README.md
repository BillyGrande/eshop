# Recommendation System Testing Framework

## Overview
This testing framework provides comprehensive testing for the e-shop recommendation system, including unit tests, integration tests, performance benchmarks, and accuracy metrics.

## Test Structure

### Unit Tests
- `test_linear_svm_recommender.py` - Tests for Linear SVM algorithm
- `test_advanced_neighbors_recommender.py` - Tests for collaborative filtering
- `test_shopping_cart_recommender.py` - Tests for market basket analysis

### Integration Tests
- `test_recommendation_integration.py` - End-to-end recommendation pipeline tests

### Performance Tests
- `test_performance_benchmarks.py` - Performance and scalability tests

### Metrics Tests
- `test_metrics.py` - Recommendation accuracy and quality metrics

### Utilities
- `conftest.py` - Pytest fixtures and configuration
- `mock_data_generator.py` - Generate realistic test data

## Running Tests

### Run all tests:
```bash
python run_tests.py
```

### Run specific test types:
```bash
# Unit tests only
python run_tests.py --type unit

# Integration tests
python run_tests.py --type integration

# Performance benchmarks
python run_tests.py --type performance

# Metrics tests
python run_tests.py --type metrics
```

### Generate mock data:
```bash
python run_tests.py --generate-data --type all
```

### Verbose output:
```bash
python run_tests.py -v --type all
```

## Test Fixtures

### Sample Data
- `sample_users` - 4 users (new, casual, active, VIP)
- `sample_products` - 50 products across 5 categories
- `sample_interactions` - User interactions for different segments
- `sample_orders` - Orders with product associations
- `analytics_engine` - Pre-calculated analytics

### Mock Data Generator
Generates larger datasets for comprehensive testing:
- 100 users with behavior patterns
- 500 diverse products
- 5000 realistic interactions
- 200 orders with buying patterns
- 50 guest sessions

## Metrics Calculated

### Accuracy Metrics
- **Precision@k**: Fraction of recommended items that are relevant
- **Recall@k**: Fraction of relevant items that are recommended
- **Diversity**: Category diversity in recommendations
- **Coverage**: Percentage of catalog recommended

### Performance Metrics
- Algorithm execution time
- Memory usage
- Concurrent user handling
- Training time for ML models

## Test Scenarios

### Guest Users
1. Initial visit (no interactions)
2. After browsing (3+ interactions)
3. Cold start recommendations
4. Session persistence

### Authenticated Users
1. New user (< 5 interactions)
2. Minimal data (5-20 interactions)
3. Established user (20+ interactions)
4. Purchase history influence

### Algorithm Testing
1. Linear SVM training and prediction
2. Neighbor similarity calculation
3. Shopping cart associations
4. Hybrid weight application

### Performance Testing
1. Single user response time
2. Concurrent users (10 simultaneous)
3. Large dataset handling (500 products, 100 users)
4. Memory usage monitoring

## Expected Performance

### Response Times
- New user recommendations: < 100ms
- Established user (hybrid): < 1s
- Cart recommendations: < 200ms

### Accuracy Targets
- Precision@10: > 0.2 for established users
- Diversity: > 0.3 (at least 3 categories in 10 items)
- Coverage: > 10% of catalog recommended

## Continuous Integration

To add to CI/CD pipeline:
```yaml
test:
  script:
    - pip install -r requirements-dev.txt
    - python run_tests.py --type unit
    - python run_tests.py --type integration
    - python run_tests.py --type metrics
```

## Debugging Failed Tests

1. Check fixtures are created properly
2. Verify database migrations are up to date
3. Ensure mock data is generated if needed
4. Run with `-v` for detailed output
5. Check individual test files for specific requirements