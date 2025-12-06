# AI-Powered Test Generation Pipeline with MLOps Observability

> Automated Pytest generation using Llama 3.3 70B with complete MLOps tracking and monitoring

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![MLflow](https://img.shields.io/badge/MLflow-2.14.1-0194E2.svg)](https://mlflow.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

An end-to-end automated pipeline that generates comprehensive Pytest test suites from application code changes using Llama 3.3 70B. The system includes complete MLOps infrastructure for experiment tracking, metrics monitoring, and cost optimization.

### Key Features

- Automated Test Generation - Generates Pytest tests from code changes using LLM
- Experiment Tracking - MLflow integration with PostgreSQL and S3 storage
- Real-time Monitoring - Prometheus + Grafana dashboards for metrics visualization
- Cost Tracking - Real-time LLM API cost and token usage monitoring
- CI/CD Integration - GitHub Actions workflow automation
- Production Ready - Dockerized 7-service architecture on AWS EC2

---

## Architecture

### Components

| Component | Purpose | Port |
|-----------|---------|------|
| MLflow Server | Experiment tracking and artifact storage | 5000 |
| PostgreSQL | MLflow metadata database | 5432 |
| Prometheus | Time-series metrics database | 9090 |
| Pushgateway | GitHub Actions metrics collection | 9091 |
| MLflow Exporter | Custom Prometheus exporter | 9092 |
| Grafana | Metrics visualization dashboards | 3000 |
| Node Exporter | System metrics collection | 9100 |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- AWS Account (for S3 and EC2)
- Groq API Key (Get here: https://console.groq.com)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/ai-test-generator.git
cd ai-test-generator
