# Odyssey CDK Project

A real-time chat infrastructure built with AWS CDK.

## Development Setup

### Prerequisites

- Python 3.10+
- AWS CLI configured
- Node.js (for AWS CDK CLI)

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install development tools:
   ```bash
   pip install pre-commit ruff jsonschema
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

4. Run validation:
   ```bash
   pre-commit run --all-files
   ```

## Configuration Validation

This project uses JSON Schema validation for all configuration files:

- **IDE Support**: VS Code automatically validates JSON files against the schema
- **Pre-commit**: All JSON configs are validated before commits
- **Schema Location**: `schema/` directory

## Project Structure

```
Odyssey/
├── cdk_project/           # CDK infrastructure code
│   ├── configs/          # Configuration files
│   ├── builders/         # Resource builders
│   └── stacks/           # CDK stacks
├── schema/               # JSON Schema definitions
├── scripts/              # Utility scripts
└── src/                  # Frontend source code
```

## Usage

1. Configure your environment in `cdk.json`
2. Deploy the infrastructure:
   ```bash
   cd cdk_project
   cdk deploy
   ```
