"""
Automated test report generator for recommendation system
Generates HTML reports with metrics, performance data, and visualizations
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template


class TestReportGenerator:
    """Generate comprehensive test reports for recommendation system"""
    
    def __init__(self, output_dir='test_reports'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.report_data = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'performance': {},
            'coverage': {},
            'errors': []
        }
    
    def add_metric_result(self, metric_name: str, value: float, details: Dict = None):
        """Add a metric result to the report"""
        self.report_data['metrics'][metric_name] = {
            'value': value,
            'details': details or {}
        }
    
    def add_performance_result(self, test_name: str, duration: float, 
                             passed: bool, details: Dict = None):
        """Add performance test result"""
        self.report_data['performance'][test_name] = {
            'duration': duration,
            'passed': passed,
            'details': details or {}
        }
    
    def add_coverage_data(self, coverage_type: str, percentage: float):
        """Add test coverage data"""
        self.report_data['coverage'][coverage_type] = percentage
    
    def add_error(self, test_name: str, error_message: str, stack_trace: str = None):
        """Add test error to report"""
        self.report_data['errors'].append({
            'test': test_name,
            'message': error_message,
            'stack_trace': stack_trace
        })
    
    def generate_performance_chart(self):
        """Generate performance comparison chart"""
        if not self.report_data['performance']:
            return None
        
        plt.figure(figsize=(10, 6))
        
        # Extract data
        test_names = []
        durations = []
        colors = []
        
        for test, data in self.report_data['performance'].items():
            test_names.append(test.replace('_', ' ').title())
            durations.append(data['duration'])
            colors.append('green' if data['passed'] else 'red')
        
        # Create bar chart
        bars = plt.bar(test_names, durations, color=colors, alpha=0.7)
        
        # Add value labels
        for bar, duration in zip(bars, durations):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{duration:.3f}s', ha='center', va='bottom')
        
        plt.xlabel('Test Name')
        plt.ylabel('Duration (seconds)')
        plt.title('Performance Test Results')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'performance_chart.png')
        plt.savefig(chart_path, dpi=150)
        plt.close()
        
        return chart_path
    
    def generate_metrics_chart(self):
        """Generate recommendation metrics visualization"""
        if not self.report_data['metrics']:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('Recommendation System Metrics', fontsize=16)
        
        # Metric names and values
        metrics = list(self.report_data['metrics'].keys())
        values = [data['value'] for data in self.report_data['metrics'].values()]
        
        # 1. Bar chart of all metrics
        ax1 = axes[0, 0]
        bars = ax1.bar(metrics, values, color='skyblue')
        ax1.set_ylabel('Value')
        ax1.set_title('Overall Metrics')
        ax1.set_ylim(0, 1.1)
        
        # Add value labels
        for bar, value in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{value:.3f}', ha='center', va='bottom')
        
        # 2. Precision/Recall trade-off (if available)
        ax2 = axes[0, 1]
        precision_data = [v for k, v in self.report_data['metrics'].items() 
                         if 'precision' in k.lower()]
        recall_data = [v for k, v in self.report_data['metrics'].items() 
                      if 'recall' in k.lower()]
        
        if precision_data and recall_data:
            k_values = [5, 10, 20]  # Assuming these k values
            ax2.plot(k_values[:len(precision_data)], 
                    [d['value'] for d in precision_data], 
                    'o-', label='Precision', linewidth=2)
            ax2.plot(k_values[:len(recall_data)], 
                    [d['value'] for d in recall_data], 
                    's-', label='Recall', linewidth=2)
            ax2.set_xlabel('k')
            ax2.set_ylabel('Score')
            ax2.set_title('Precision/Recall @k')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, 'No Precision/Recall data', 
                    ha='center', va='center', transform=ax2.transAxes)
        
        # 3. Coverage pie chart
        ax3 = axes[1, 0]
        if self.report_data['coverage']:
            coverage_values = list(self.report_data['coverage'].values())
            coverage_labels = list(self.report_data['coverage'].keys())
            ax3.pie(coverage_values, labels=coverage_labels, autopct='%1.1f%%')
            ax3.set_title('Test Coverage')
        else:
            ax3.text(0.5, 0.5, 'No Coverage data', 
                    ha='center', va='center', transform=ax3.transAxes)
        
        # 4. Error summary
        ax4 = axes[1, 1]
        if self.report_data['errors']:
            error_counts = {}
            for error in self.report_data['errors']:
                test_type = error['test'].split('_')[0]
                error_counts[test_type] = error_counts.get(test_type, 0) + 1
            
            ax4.bar(error_counts.keys(), error_counts.values(), color='red', alpha=0.7)
            ax4.set_ylabel('Error Count')
            ax4.set_title('Errors by Test Type')
        else:
            ax4.text(0.5, 0.5, 'No Errors! ✓', 
                    ha='center', va='center', transform=ax4.transAxes,
                    fontsize=20, color='green')
        
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'metrics_chart.png')
        plt.savefig(chart_path, dpi=150)
        plt.close()
        
        return chart_path
    
    def generate_html_report(self):
        """Generate comprehensive HTML report"""
        # Generate charts
        perf_chart = self.generate_performance_chart()
        metrics_chart = self.generate_metrics_chart()
        
        # HTML template
        template = Template('''
<!DOCTYPE html>
<html>
<head>
    <title>Recommendation System Test Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1, h2 {
            color: #333;
        }
        .summary {
            background-color: #e7f3ff;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .metric {
            display: inline-block;
            margin: 10px 20px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        .error {
            background-color: #fee;
            border: 1px solid #fcc;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .success {
            color: green;
            font-weight: bold;
        }
        .failure {
            color: red;
            font-weight: bold;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .chart {
            text-align: center;
            margin: 20px 0;
        }
        .chart img {
            max-width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Recommendation System Test Report</h1>
        <p><strong>Generated:</strong> {{ timestamp }}</p>
        
        <div class="summary">
            <h2>Summary</h2>
            <div class="metric">
                <div>Total Tests</div>
                <div class="metric-value">{{ total_tests }}</div>
            </div>
            <div class="metric">
                <div>Passed</div>
                <div class="metric-value success">{{ passed_tests }}</div>
            </div>
            <div class="metric">
                <div>Failed</div>
                <div class="metric-value failure">{{ failed_tests }}</div>
            </div>
            <div class="metric">
                <div>Avg Performance</div>
                <div class="metric-value">{{ avg_performance }}s</div>
            </div>
        </div>
        
        <h2>Recommendation Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Status</th>
            </tr>
            {% for metric, data in metrics.items() %}
            <tr>
                <td>{{ metric }}</td>
                <td>{{ "%.3f"|format(data.value) }}</td>
                <td class="{{ 'success' if data.value > 0.2 else 'failure' }}">
                    {{ 'Good' if data.value > 0.2 else 'Needs Improvement' }}
                </td>
            </tr>
            {% endfor %}
        </table>
        
        {% if metrics_chart %}
        <div class="chart">
            <h2>Metrics Visualization</h2>
            <img src="{{ metrics_chart }}" alt="Metrics Chart">
        </div>
        {% endif %}
        
        <h2>Performance Tests</h2>
        <table>
            <tr>
                <th>Test</th>
                <th>Duration (s)</th>
                <th>Status</th>
                <th>Details</th>
            </tr>
            {% for test, data in performance.items() %}
            <tr>
                <td>{{ test }}</td>
                <td>{{ "%.3f"|format(data.duration) }}</td>
                <td class="{{ 'success' if data.passed else 'failure' }}">
                    {{ 'Passed' if data.passed else 'Failed' }}
                </td>
                <td>{{ data.details }}</td>
            </tr>
            {% endfor %}
        </table>
        
        {% if perf_chart %}
        <div class="chart">
            <h2>Performance Comparison</h2>
            <img src="{{ perf_chart }}" alt="Performance Chart">
        </div>
        {% endif %}
        
        {% if errors %}
        <h2>Errors</h2>
        {% for error in errors %}
        <div class="error">
            <strong>Test:</strong> {{ error.test }}<br>
            <strong>Error:</strong> {{ error.message }}
            {% if error.stack_trace %}
            <pre>{{ error.stack_trace }}</pre>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}
        
        <h2>Test Coverage</h2>
        <table>
            <tr>
                <th>Coverage Type</th>
                <th>Percentage</th>
            </tr>
            {% for type, percentage in coverage.items() %}
            <tr>
                <td>{{ type }}</td>
                <td>{{ "%.1f"|format(percentage) }}%</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
        ''')
        
        # Calculate summary statistics
        total_tests = len(self.report_data['performance'])
        passed_tests = sum(1 for p in self.report_data['performance'].values() if p['passed'])
        failed_tests = total_tests - passed_tests
        avg_performance = (sum(p['duration'] for p in self.report_data['performance'].values()) / 
                          total_tests if total_tests > 0 else 0)
        
        # Render template
        html_content = template.render(
            timestamp=self.report_data['timestamp'],
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            avg_performance=f"{avg_performance:.3f}",
            metrics=self.report_data['metrics'],
            performance=self.report_data['performance'],
            coverage=self.report_data['coverage'],
            errors=self.report_data['errors'],
            perf_chart=os.path.basename(perf_chart) if perf_chart else None,
            metrics_chart=os.path.basename(metrics_chart) if metrics_chart else None
        )
        
        # Save HTML report
        report_path = os.path.join(self.output_dir, 'test_report.html')
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        # Save JSON data
        json_path = os.path.join(self.output_dir, 'test_data.json')
        with open(json_path, 'w') as f:
            json.dump(self.report_data, f, indent=2)
        
        return report_path