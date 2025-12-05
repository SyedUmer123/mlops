#!/usr/bin/env python3
"""
Check MLflow exporter metrics in Prometheus
"""
import requests
import json

PROMETHEUS_URL = "http://44.221.50.201:9090"

def query_prometheus(query):
    """Query Prometheus"""
    url = f"{PROMETHEUS_URL}/api/v1/query"
    params = {"query": query}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error querying '{query}': {e}")
        return None

def check_mlflow_metrics():
    """Check MLflow-specific metrics"""
    print("=" * 70)
    print("MLflow Exporter Metrics Check")
    print("=" * 70)
    
    # Check if mlflow_exporter is up
    print("\n1. Checking MLflow Exporter Status...")
    result = query_prometheus('up{job="mlflow_exporter"}')
    
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        if data:
            status = data[0].get('value', ['', 'unknown'])[-1]
            if status == '1':
                print(f"   ✅ MLflow Exporter is UP")
            else:
                print(f"   ❌ MLflow Exporter is DOWN")
        else:
            print(f"   ⚠️  No data for mlflow_exporter")
    else:
        print(f"   ❌ Failed to query mlflow_exporter status")
    
    # Check all mlflow_ metrics
    print("\n2. Listing all mlflow_ metrics...")
    result = query_prometheus('{__name__=~"mlflow_.*"}')
    
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        
        metrics_found = {}
        for series in data:
            metric_name = series.get('metric', {}).get('__name__', 'unknown')
            if metric_name not in metrics_found:
                metrics_found[metric_name] = []
            metrics_found[metric_name].append(series)
        
        print(f"   Found {len(metrics_found)} unique mlflow_ metrics:\n")
        
        for metric_name in sorted(metrics_found.keys()):
            series_list = metrics_found[metric_name]
            print(f"   📊 {metric_name} ({len(series_list)} series)")
            
            # Show sample values
            for series in series_list[:2]:  # Show first 2 series
                value = series.get('value', ['', 'N/A'])[-1]
                labels = series.get('metric', {})
                label_str = ', '.join([f'{k}="{v}"' for k, v in labels.items() if k != '__name__'])
                print(f"      └─ {{{label_str}}} = {value}")
    
    # Check API request duration metrics specifically
    print("\n3. Checking MLflow API Request Duration Metrics...")
    
    queries = {
        "Duration Sum": "mlflow_api_request_duration_seconds_sum",
        "Duration Count": "mlflow_api_request_duration_seconds_count",
        "Duration Bucket": "mlflow_api_request_duration_seconds_bucket",
        "Average Latency": "rate(mlflow_api_request_duration_seconds_sum[5m]) / rate(mlflow_api_request_duration_seconds_count[5m])",
        "Request Rate": "rate(mlflow_api_request_duration_seconds_count[5m])"
    }
    
    for name, query in queries.items():
        result = query_prometheus(query)
        if result and result.get('status') == 'success':
            data = result.get('data', {}).get('result', [])
            if data:
                print(f"   ✅ {name}: Found {len(data)} series")
                for series in data[:2]:
                    value = series.get('value', ['', 'N/A'])[-1]
                    labels = series.get('metric', {})
                    operation = labels.get('operation', 'N/A')
                    print(f"      └─ operation={operation}, value={value}")
            else:
                print(f"   ⚠️  {name}: Metric exists but NO DATA")
                print(f"      This means MLflow hasn't received any API requests yet")
        else:
            print(f"   ❌ {name}: Query failed or metric not found")
    
    # Check if there's any activity
    print("\n4. Checking for Recent MLflow Activity...")
    result = query_prometheus('mlflow_server_up')
    
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        if data:
            value = data[0].get('value', ['', '0'])[-1]
            print(f"   📊 MLflow Server Up: {value}")
    
    # Check experiments and runs
    result = query_prometheus('mlflow_experiments_total')
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        if data:
            value = data[0].get('value', ['', '0'])[-1]
            print(f"   📊 Total Experiments: {value}")
    
    result = query_prometheus('mlflow_runs_total')
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        if data:
            total_runs = sum(float(s.get('value', ['', '0'])[-1]) for s in data)
            print(f"   📊 Total Runs: {int(total_runs)}")
    
    print("\n" + "=" * 70)
    print("Diagnosis:")
    print("=" * 70)
    
    # Determine the issue
    result = query_prometheus('mlflow_api_request_duration_seconds_count')
    if result and result.get('status') == 'success':
        data = result.get('data', {}).get('result', [])
        if not data:
            print("""
⚠️  MLflow API metrics exist but have NO DATA.

This is expected if:
1. MLflow exporter just started (no API calls scraped yet)
2. No one has accessed MLflow UI or API recently
3. GitHub Actions hasn't logged any runs to MLflow recently

Solution:
- Access MLflow UI at http://44.221.50.201:5000
- OR trigger a GitHub Actions workflow run
- OR wait for the exporter to scrape (every 30 seconds)
- Then check Grafana again in 1-2 minutes

The metrics will populate automatically once MLflow receives API requests.
""")
        else:
            print("""
✅ MLflow API metrics have data!

If Grafana still shows "No data":
1. Check the time range in Grafana (try "Last 24 hours")
2. Verify the query syntax in the panel
3. Try refreshing the dashboard
4. Check if there are any query errors in the panel inspector
""")

if __name__ == "__main__":
    check_mlflow_metrics()