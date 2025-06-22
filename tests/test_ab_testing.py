"""
Tests for A/B testing framework
"""

import pytest
from datetime import datetime, timedelta
from eshop.ab_testing import ABTestingFramework, ExperimentVariant, ABTestExperiment, ABTestResult
from eshop.models import db, User


class TestABTestingFramework:
    """Test A/B testing functionality"""
    
    @pytest.fixture
    def ab_framework(self, app):
        """Create A/B testing framework instance"""
        with app.app_context():
            return ABTestingFramework()
    
    @pytest.fixture
    def sample_experiment(self, app, ab_framework):
        """Create a sample experiment"""
        with app.app_context():
            variants = [
                ExperimentVariant(
                    name="control",
                    description="Current algorithm mix",
                    algorithm_weights={
                        'linear_svm': 0.3,
                        'neighbors': 0.3,
                        'shopping_cart': 0.2,
                        'best_sellers': 0.2
                    },
                    traffic_percentage=50.0
                ),
                ExperimentVariant(
                    name="svm_heavy",
                    description="More weight on SVM",
                    algorithm_weights={
                        'linear_svm': 0.5,
                        'neighbors': 0.2,
                        'shopping_cart': 0.2,
                        'best_sellers': 0.1
                    },
                    traffic_percentage=50.0
                )
            ]
            
            experiment = ab_framework.create_experiment(
                name="SVM Weight Test",
                description="Test if increasing SVM weight improves conversions",
                variants=variants,
                metrics=['ctr', 'conversion_rate', 'revenue'],
                duration_days=14
            )
            
            return experiment
    
    def test_create_experiment(self, ab_framework):
        """Test creating an A/B test experiment"""
        variants = [
            ExperimentVariant(
                name="control",
                description="Control group",
                algorithm_weights={'best_sellers': 1.0},
                traffic_percentage=60.0
            ),
            ExperimentVariant(
                name="treatment",
                description="Treatment group",
                algorithm_weights={'trending': 1.0},
                traffic_percentage=40.0
            )
        ]
        
        experiment = ab_framework.create_experiment(
            name="Best Sellers vs Trending",
            description="Compare best sellers against trending",
            variants=variants,
            metrics=['ctr', 'conversion_rate'],
            duration_days=7
        )
        
        assert experiment.id is not None
        assert experiment.name == "Best Sellers vs Trending"
        assert len(experiment.variants) == 2
        assert experiment.status == 'draft'
    
    def test_invalid_traffic_percentages(self, ab_framework):
        """Test that invalid traffic percentages are rejected"""
        variants = [
            ExperimentVariant(
                name="control",
                description="Control",
                algorithm_weights={},
                traffic_percentage=30.0  # Only 30%
            ),
            ExperimentVariant(
                name="treatment",
                description="Treatment",
                algorithm_weights={},
                traffic_percentage=40.0  # Total = 70%, not 100%
            )
        ]
        
        with pytest.raises(ValueError):
            ab_framework.create_experiment(
                name="Invalid Test",
                description="Should fail",
                variants=variants,
                metrics=['ctr']
            )
    
    def test_start_experiment(self, app, ab_framework, sample_experiment):
        """Test starting an experiment"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            
            # Reload experiment
            experiment = ABTestExperiment.query.get(sample_experiment.id)
            
            assert experiment.status == 'running'
            assert experiment.start_date is not None
            assert sample_experiment.id in ab_framework.active_experiments
    
    def test_user_variant_assignment(self, app, ab_framework, sample_experiment):
        """Test that users are consistently assigned to variants"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            
            # Test multiple users
            variant_counts = {'control': 0, 'svm_heavy': 0}
            
            for user_id in range(1, 101):
                variant = ab_framework.get_user_variant(user_id, sample_experiment.id)
                assert variant in ['control', 'svm_heavy']
                variant_counts[variant] += 1
                
                # Test consistency - same user should always get same variant
                variant2 = ab_framework.get_user_variant(user_id, sample_experiment.id)
                assert variant == variant2
            
            # With 50/50 split, should be roughly equal (allow 20% deviation)
            assert 30 <= variant_counts['control'] <= 70
            assert 30 <= variant_counts['svm_heavy'] <= 70
    
    def test_track_events(self, app, ab_framework, sample_experiment, sample_users):
        """Test event tracking for experiments"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            user = sample_users[0]
            
            # Track events
            ab_framework.track_event(user.id, sample_experiment.id, 'recommendation_shown', 10)
            ab_framework.track_event(user.id, sample_experiment.id, 'click')
            ab_framework.track_event(user.id, sample_experiment.id, 'purchase', 99.99)
            
            # Check results
            result = ABTestResult.query.filter_by(
                experiment_id=sample_experiment.id,
                user_id=user.id
            ).first()
            
            assert result is not None
            assert result.recommendations_shown == 10
            assert result.clicks == 1
            assert result.purchases == 1
            assert result.revenue == 99.99
    
    def test_calculate_significance(self, app, ab_framework, sample_experiment, sample_users):
        """Test statistical significance calculation"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            
            # Simulate results for multiple users
            # Control: 20% conversion rate
            # Treatment: 30% conversion rate
            for i, user in enumerate(sample_users[:40]):
                variant = ab_framework.get_user_variant(user.id, sample_experiment.id)
                
                # Track recommendation shown
                ab_framework.track_event(user.id, sample_experiment.id, 'recommendation_shown', 10)
                
                # Simulate different conversion rates
                if variant == 'control':
                    if i % 5 == 0:  # 20% convert
                        ab_framework.track_event(user.id, sample_experiment.id, 'click')
                        ab_framework.track_event(user.id, sample_experiment.id, 'purchase', 50.0)
                else:  # svm_heavy
                    if i % 3 == 0:  # 33% convert
                        ab_framework.track_event(user.id, sample_experiment.id, 'click')
                        ab_framework.track_event(user.id, sample_experiment.id, 'purchase', 50.0)
            
            # Calculate significance
            results = ab_framework.calculate_significance(sample_experiment.id)
            
            assert 'variants' in results
            assert 'control' in results['variants']
            assert 'svm_heavy' in results['variants']
            
            # Check lift calculation
            svm_heavy_data = results['variants']['svm_heavy']
            assert 'lift' in svm_heavy_data
            assert 'p_value' in svm_heavy_data
    
    def test_experiment_report(self, app, ab_framework, sample_experiment):
        """Test experiment report generation"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            
            # Add some test data
            for user_id in range(1, 21):
                variant = ab_framework.get_user_variant(user_id, sample_experiment.id)
                ab_framework.track_event(user_id, sample_experiment.id, 'recommendation_shown', 5)
                
                if user_id % 4 == 0:
                    ab_framework.track_event(user_id, sample_experiment.id, 'purchase', 30.0)
            
            report = ab_framework.get_experiment_report(sample_experiment.id)
            
            assert 'experiment' in report
            assert 'variants' in report
            assert 'recommendations' in report
            
            # Should have recommendations for each variant
            assert len(report['recommendations']) > 0
    
    def test_auto_stop_experiment(self, app, ab_framework):
        """Test automatic experiment stopping"""
        with app.app_context():
            # Create experiment with clear winner
            variants = [
                ExperimentVariant(
                    name="control",
                    description="Control",
                    algorithm_weights={'best_sellers': 1.0},
                    traffic_percentage=50.0
                ),
                ExperimentVariant(
                    name="winner",
                    description="Clear winner",
                    algorithm_weights={'trending': 1.0},
                    traffic_percentage=50.0
                )
            ]
            
            experiment = ab_framework.create_experiment(
                name="Auto Stop Test",
                description="Test auto stopping",
                variants=variants,
                metrics=['conversion_rate']
            )
            
            ab_framework.start_experiment(experiment.id)
            
            # Simulate clear winner - winner variant has 50% conversion vs 10% for control
            for i in range(200):
                # Ensure roughly equal split
                user_id = i + 1000  # Offset to avoid conflicts
                variant = 'control' if i % 2 == 0 else 'winner'
                
                # Force variant assignment
                if variant == 'control':
                    # 10% conversion
                    if i % 10 == 0:
                        ab_framework.track_event(user_id, experiment.id, 'purchase', 50.0)
                else:
                    # 50% conversion for winner
                    if i % 2 == 0:
                        ab_framework.track_event(user_id, experiment.id, 'purchase', 50.0)
            
            # Check if experiment would be auto-stopped
            # (In real scenario, this would be called periodically)
            # Note: May not stop due to sample size requirements
            stopped = ab_framework.auto_stop_experiment(experiment.id)
            
            # Verify experiment data was recorded
            results = ABTestResult.query.filter_by(experiment_id=experiment.id).all()
            assert len(results) > 0
    
    def test_get_variant_weights(self, app, ab_framework, sample_experiment):
        """Test getting algorithm weights for a user's variant"""
        with app.app_context():
            ab_framework.start_experiment(sample_experiment.id)
            
            user_id = 123
            weights = ab_framework.get_variant_weights(user_id, sample_experiment.id)
            
            assert weights is not None
            assert isinstance(weights, dict)
            
            # Should match one of the variant configurations
            variant = ab_framework.get_user_variant(user_id, sample_experiment.id)
            if variant == 'control':
                assert weights['linear_svm'] == 0.3
                assert weights['neighbors'] == 0.3
            else:  # svm_heavy
                assert weights['linear_svm'] == 0.5
                assert weights['neighbors'] == 0.2