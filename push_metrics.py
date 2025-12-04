"""
Push custom metrics from GitHub Actions to Prometheus Pushgateway
"""
import os
import requests
import json
from datetime import datetime

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://your-ec2-ip:9091")
JOB_NAME = "github_actions_test_generator"

class MetricsPusher:
    def __init__(self, workflow_run_id=None):
        self.workflow_run_id = workflow_run_id or os.getenv("GITHUB_RUN_ID", "local")
        self.commit_sha = os.getenv("GITHUB_SHA", "unknown")[:7]
        self.branch = os.getenv("GITHUB_REF_NAME", "unknown")
        
    def push_metrics(self, metrics_dict):
        """
        Push metrics to Prometheus Pushgateway
        
        metrics_dict format:
        {
            "tests_generated": 5,
            "tests_passed": 4,
            "tests_failed": 1,
            "llm_tokens_used": 1234,
            "workflow_duration": 45.2,
            "llm_cost_usd": 0.05,
            "llm_latency_seconds": 2.3
        }
        """
        # Build Prometheus format
        labels = f'workflow_run_id="{self.workflow_run_id}",commit="{self.commit_sha}",branch="{self.branch}"'
        
        payload = ""
        for metric_name, value in metrics_dict.items():
            payload += f"# TYPE {metric_name} gauge\n"
            payload += f"{metric_name}{{{labels}}} {value}\n"
        
        # Push to Pushgateway
        url = f"{PUSHGATEWAY_URL}/metrics/job/{JOB_NAME}/instance/{self.workflow_run_id}"
        
        try:
            response = requests.post(
                url,
                data=payload,
                headers={"Content-Type": "text/plain; charset=utf-8"}
            )
            response.raise_for_status()
            print(f"✅ Pushed metrics to Pushgateway: {url}")
            return True
        except Exception as e:
            print(f"❌ Failed to push metrics: {e}")
            return False
    
    def push_workflow_start(self):
        """Mark workflow start"""
        self.push_metrics({
            "workflow_started": 1,
            "workflow_timestamp": int(datetime.now().timestamp())
        })
    
    def push_workflow_end(self, success=True):
        """Mark workflow completion"""
        self.push_metrics({
            "workflow_completed": 1 if success else 0,
            "workflow_failed": 0 if success else 1,
            "workflow_timestamp": int(datetime.now().timestamp())
        })


def load_mlflow_metrics():
    """
    Extract metrics from MLflow run (if available locally)
    This reads from the latest run artifacts
    """
    metrics = {}
    
    # Try to read from test results
    try:
        with open("test_stdout.txt", "r") as f:
            content = f.read()
            import re
            passed = re.search(r"(\d+) passed", content)
            failed = re.search(r"(\d+) failed", content)
            
            if passed:
                metrics["tests_passed"] = int(passed.group(1))
            if failed:
                metrics["tests_failed"] = int(failed.group(1))
    except FileNotFoundError:
        pass
    
    return metrics


if __name__ == "__main__":
    import sys
    
    pusher = MetricsPusher()
    
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if action == "start":
        pusher.push_workflow_start()
    
    elif action == "end":
        success = sys.argv[2] == "success" if len(sys.argv) > 2 else True
        pusher.push_workflow_end(success=success)
    
    elif action == "custom":
        # Load custom metrics from MLflow/local files
        metrics = load_mlflow_metrics()
        
        # Add any additional metrics
        if os.path.exists("generated_test.py"):
            with open("generated_test.py", "r") as f:
                test_lines = len([l for l in f if l.strip().startswith("def test_")])
                metrics["tests_generated"] = test_lines
        
        pusher.push_metrics(metrics)
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)