"""
A/B Testing Framework for Recommendation System
Allows running experiments to compare different recommendation strategies
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from .models import db


class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class ExperimentVariant:
    """Represents a variant in an A/B test"""
    name: str
    description: str
    algorithm_weights: Dict[str, float]
    traffic_percentage: float
    

class ABTestExperiment(db.Model):
    """Database model for A/B test experiments"""
    __tablename__ = 'ab_test_experiments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    variants = db.Column(db.JSON)  # Stores variant configurations
    metrics = db.Column(db.JSON)  # Stores which metrics to track
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Results storage
    results = db.relationship('ABTestResult', backref='experiment', lazy='dynamic')


class ABTestResult(db.Model):
    """Stores results for A/B test experiments"""
    __tablename__ = 'ab_test_results'
    
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('ab_test_experiments.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    variant = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Metrics
    recommendations_shown = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    purchases = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)
    
    # Additional metrics stored as JSON
    custom_metrics = db.Column(db.JSON)


class ABTestingFramework:
    """Main A/B testing framework for recommendation experiments"""
    
    def __init__(self):
        self.active_experiments = {}
        self._load_active_experiments()
    
    def _load_active_experiments(self):
        """Load all active experiments from database"""
        active = ABTestExperiment.query.filter_by(status='running').all()
        for exp in active:
            self.active_experiments[exp.id] = exp
    
    def create_experiment(self, name: str, description: str, 
                         variants: List[ExperimentVariant],
                         metrics: List[str],
                         duration_days: int = 14) -> ABTestExperiment:
        """Create a new A/B test experiment"""
        # Validate traffic percentages sum to 100
        total_traffic = sum(v.traffic_percentage for v in variants)
        if abs(total_traffic - 100.0) > 0.01:
            raise ValueError(f"Traffic percentages must sum to 100, got {total_traffic}")
        
        # Create experiment
        experiment = ABTestExperiment(
            name=name,
            description=description,
            status='draft',
            variants=[{
                'name': v.name,
                'description': v.description,
                'algorithm_weights': v.algorithm_weights,
                'traffic_percentage': v.traffic_percentage
            } for v in variants],
            metrics=metrics,
            end_date=datetime.utcnow() + timedelta(days=duration_days)
        )
        
        db.session.add(experiment)
        db.session.commit()
        
        return experiment
    
    def start_experiment(self, experiment_id: int):
        """Start an experiment"""
        experiment = ABTestExperiment.query.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        experiment.status = 'running'
        experiment.start_date = datetime.utcnow()
        db.session.commit()
        
        self.active_experiments[experiment_id] = experiment
    
    def get_user_variant(self, user_id: int, experiment_id: int) -> Optional[str]:
        """Determine which variant a user should see"""
        experiment = self.active_experiments.get(experiment_id)
        if not experiment:
            return None
        
        # Use consistent hashing to ensure user always sees same variant
        hash_input = f"{user_id}-{experiment_id}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        
        # Map hash to variant based on traffic percentages
        bucket = hash_value % 100
        cumulative = 0
        
        for variant in experiment.variants:
            cumulative += variant['traffic_percentage']
            if bucket < cumulative:
                return variant['name']
        
        # Fallback to control
        return experiment.variants[0]['name']
    
    def get_variant_weights(self, user_id: int, experiment_id: int) -> Dict[str, float]:
        """Get algorithm weights for a user's variant"""
        variant_name = self.get_user_variant(user_id, experiment_id)
        if not variant_name:
            return None
        
        experiment = self.active_experiments.get(experiment_id)
        for variant in experiment.variants:
            if variant['name'] == variant_name:
                return variant['algorithm_weights']
        
        return None
    
    def track_event(self, user_id: int, experiment_id: int, 
                   event_type: str, value: float = 1.0):
        """Track an event for the experiment"""
        variant = self.get_user_variant(user_id, experiment_id)
        if not variant:
            return
        
        # Get or create result record for this user/experiment
        result = ABTestResult.query.filter_by(
            experiment_id=experiment_id,
            user_id=user_id,
            variant=variant
        ).first()
        
        if not result:
            result = ABTestResult(
                experiment_id=experiment_id,
                user_id=user_id,
                variant=variant
            )
            db.session.add(result)
        
        # Update metrics
        if event_type == 'recommendation_shown':
            result.recommendations_shown += int(value)
        elif event_type == 'click':
            result.clicks += 1
        elif event_type == 'purchase':
            result.purchases += 1
            result.revenue += value
        else:
            # Custom metric
            if not result.custom_metrics:
                result.custom_metrics = {}
            result.custom_metrics[event_type] = result.custom_metrics.get(event_type, 0) + value
        
        db.session.commit()
    
    def calculate_significance(self, experiment_id: int) -> Dict[str, Any]:
        """Calculate statistical significance of experiment results"""
        from scipy import stats
        
        experiment = ABTestExperiment.query.get(experiment_id)
        if not experiment:
            return None
        
        results = {}
        
        # Get results by variant
        variant_data = {}
        for variant in experiment.variants:
            variant_results = ABTestResult.query.filter_by(
                experiment_id=experiment_id,
                variant=variant['name']
            ).all()
            
            if variant_results:
                variant_data[variant['name']] = {
                    'users': len(variant_results),
                    'clicks': sum(r.clicks for r in variant_results),
                    'purchases': sum(r.purchases for r in variant_results),
                    'revenue': sum(r.revenue for r in variant_results),
                    'ctr': sum(r.clicks for r in variant_results) / max(sum(r.recommendations_shown for r in variant_results), 1),
                    'conversion_rate': sum(r.purchases for r in variant_results) / max(len(variant_results), 1)
                }
        
        # Calculate significance between control and treatment
        if len(variant_data) >= 2:
            control_name = experiment.variants[0]['name']
            control_data = variant_data.get(control_name, {})
            
            for variant_name, variant_stats in variant_data.items():
                if variant_name == control_name:
                    continue
                
                # Chi-squared test for conversion rate
                control_conversions = control_data.get('purchases', 0)
                control_total = control_data.get('users', 1)
                variant_conversions = variant_stats.get('purchases', 0)
                variant_total = variant_stats.get('users', 1)
                
                # Create contingency table
                contingency_table = [
                    [control_conversions, control_total - control_conversions],
                    [variant_conversions, variant_total - variant_conversions]
                ]
                
                chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
                
                # Calculate lift
                control_rate = control_conversions / max(control_total, 1)
                variant_rate = variant_conversions / max(variant_total, 1)
                lift = ((variant_rate - control_rate) / max(control_rate, 0.001)) * 100
                
                variant_stats['p_value'] = p_value
                variant_stats['significant'] = p_value < 0.05
                variant_stats['lift'] = lift
        
        results['variants'] = variant_data
        results['experiment'] = {
            'name': experiment.name,
            'status': experiment.status,
            'start_date': experiment.start_date.isoformat() if experiment.start_date else None,
            'end_date': experiment.end_date.isoformat() if experiment.end_date else None
        }
        
        return results
    
    def get_experiment_report(self, experiment_id: int) -> Dict[str, Any]:
        """Generate comprehensive experiment report"""
        significance = self.calculate_significance(experiment_id)
        if not significance:
            return None
        
        report = {
            'experiment': significance['experiment'],
            'variants': significance['variants'],
            'recommendations': []
        }
        
        # Add recommendations based on results
        control_name = list(significance['variants'].keys())[0]
        control_data = significance['variants'][control_name]
        
        for variant_name, variant_data in significance['variants'].items():
            if variant_name == control_name:
                continue
            
            if variant_data.get('significant') and variant_data.get('lift', 0) > 0:
                report['recommendations'].append({
                    'variant': variant_name,
                    'recommendation': f"Consider adopting {variant_name} - shows {variant_data['lift']:.1f}% lift with p-value {variant_data['p_value']:.4f}"
                })
            elif variant_data.get('significant') and variant_data.get('lift', 0) < 0:
                report['recommendations'].append({
                    'variant': variant_name,
                    'recommendation': f"Avoid {variant_name} - shows {variant_data['lift']:.1f}% decrease with p-value {variant_data['p_value']:.4f}"
                })
            else:
                report['recommendations'].append({
                    'variant': variant_name,
                    'recommendation': f"No significant difference for {variant_name} (p-value: {variant_data.get('p_value', 1.0):.4f})"
                })
        
        return report
    
    def auto_stop_experiment(self, experiment_id: int):
        """Automatically stop experiment if significant results achieved"""
        significance = self.calculate_significance(experiment_id)
        
        if not significance:
            return
        
        # Check if any variant has significant positive lift
        for variant_name, variant_data in significance['variants'].items():
            if (variant_data.get('significant') and 
                variant_data.get('lift', 0) > 10 and  # 10% lift threshold
                variant_data.get('users', 0) > 100):  # Minimum sample size
                
                # Stop experiment
                experiment = ABTestExperiment.query.get(experiment_id)
                experiment.status = 'completed'
                db.session.commit()
                
                # Remove from active experiments
                if experiment_id in self.active_experiments:
                    del self.active_experiments[experiment_id]
                
                return True
        
        return False