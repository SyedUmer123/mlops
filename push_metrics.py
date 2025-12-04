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
            # Skip None or invalid values
            if value is None or value == "":
                continue
                
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
            print(f"📊 Pushed metrics: {list(metrics_dict.keys())}")
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


def load_metrics_from_json():
    """
    Load metrics from the metrics_summary.json file created by generate_tests.py
    """
    metrics = {}
    
    try:
        if os.path.exists("metrics_summary.json"):
            with open("metrics_summary.json", "r") as f:
                data = json.load(f)
                print(f"📊 Loaded metrics from metrics_summary.json: {data}")
                
                # Map metrics to correct names
                metrics["tests_generated"] = data.get("tests_generated", 0)
                metrics["llm_tokens_used"] = data.get("llm_tokens_used", 0)
                metrics["llm_cost_usd"] = data.get("llm_cost_usd", 0)
                metrics["llm_latency_seconds"] = data.get("llm_latency_seconds", 0)
                metrics["prompt_tokens"] = data.get("prompt_tokens", 0)
                metrics["completion_tokens"] = data.get("completion_tokens", 0)
        else:
            print("⚠️  metrics_summary.json not found")
    except Exception as e:
        print(f"❌ Error loading metrics from JSON: {e}")
    
    return metrics


def load_test_results():
    """
    Extract test results from pytest output
    """
    metrics = {}
    
    try:
        if os.path.exists("test_stdout.txt"):
            with open("test_stdout.txt", "r") as f:
                content = f.read()
                import re
                passed = re.search(r"(\d+) passed", content)
                failed = re.search(r"(\d+) failed", content)
                
                if passed:
                    metrics["tests_passed"] = int(passed.group(1))
                else:
                    metrics["tests_passed"] = 0
                    
                if failed:
                    metrics["tests_failed"] = int(failed.group(1))
                else:
                    metrics["tests_failed"] = 0
                    
                print(f"📊 Loaded test results: passed={metrics.get('tests_passed', 0)}, failed={metrics.get('tests_failed', 0)}")
        else:
            print("⚠️  test_stdout.txt not found")
    except FileNotFoundError:
        print("⚠️  test_stdout.txt not found")
    except Exception as e:
        print(f"❌ Error loading test results: {e}")
    
    return metrics


if __name__ == "__main__":
    import sys
    
    pusher = MetricsPusher()
    
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if action == "start":
        print("🚀 Pushing workflow start metrics...")
        pusher.push_workflow_start()
    
    elif action == "end":
        success = sys.argv[2] == "success" if len(sys.argv) > 2 else True
        print(f"🏁 Pushing workflow end metrics (success={success})...")
        pusher.push_workflow_end(success=success)
    
    elif action == "custom":
        print("📊 Pushing custom metrics from workflow...")
        
        # Load metrics from JSON (generated by generate_tests.py)
        metrics = load_metrics_from_json()
        
        # Load test results
        test_metrics = load_test_results()
        metrics.update(test_metrics)
        
        if metrics:
            print(f"📤 Pushing {len(metrics)} metrics to Pushgateway...")
            success = pusher.push_metrics(metrics)
            if success:
                print("✅ Metrics pushed successfully")
            else:
                print("❌ Failed to push metrics")
                sys.exit(1)
        else:
            print("⚠️  No metrics to push")
    
    else:
        print(f"❌ Unknown action: {action}")
        print("Usage: python push_metrics.py [start|end|custom]")
        sys.exit(1)