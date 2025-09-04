# Odyssey CDK Project - Coding Standards

## Overview

This document defines the coding standards, architecture, and formatting guidelines for the Odyssey CDK project. These standards ensure consistency, readability, and maintainability across the entire codebase.

## File Structure

```
Odyssey/
├── cdk_project/
│   ├── configs/           # Configuration management
│   │   ├── config_manager.py    # Centralized config loading
│   │   ├── error_handler.py     # Centralized error handling
│   │   └── odyssey_cfg.py       # Project configuration
│   ├── builders/          # Resource builders
│   │   ├── dynamodb_builder.py  # DynamoDB table builders
│   │   ├── lambda_builder.py    # Lambda function builders
│   │   ├── policy_builder.py    # IAM policy builders
│   │   └── ws_api_builder.py    # WebSocket API builders
│   ├── stacks/            # CDK stacks
│   │   ├── chat_backend_stack.py # Main backend stack
│   │   └── pipeline_stack.py     # CI/CD pipeline stack
│   └── lambda_src/        # Lambda function source code
└── src/                   # Frontend source code
```

## Code Formatting Standards

### 1. Function Definitions

#### Type Annotations
- **Always** include type annotations for all parameters and return types
- Use `from __future__ import annotations` for forward references
- Import types from `typing` module when needed

#### Parameter Alignment
- If function has more than one parameter, indent each parameter on a new line
- Align all colons (`:`) of the same function
- Use trailing comma for the last parameter

#### Example:
```python
def load_lambda_config(
        self, 
        folder: Path,
        extra_vars: Dict[str, str] = None
    ) -> dict:
    """
    Load lambda configuration from a folder.
    
    Args:
        folder: Lambda folder path
        extra_vars: Additional variables for placeholder expansion
        
    Returns:
        Merged lambda configuration
    """
```

### 2. Function Calls

#### Multi-Parameter Calls
- If function call has more than one parameter, indent each parameter on a new line
- Align parameters for readability

#### Example:
```python
# Single parameter - inline
result = func(param)

# Multiple parameters - indented
result = func(
    param1,
    param2,
    param3=value
)
```

### 3. Docstrings

#### File-Level Docstrings
- Every `.py` file must start with a docstring describing the file's purpose
- Include a brief summary of what the file contains

#### Function Docstrings
- **Always** include docstrings for all functions
- Start with a brief description of what the function does
- Include `Args:` section for parameters
- Include `Returns:` section for return values
- Add additional details for complex functions

#### Example:
```python
"""
Configuration management for Odyssey CDK project.

This module provides centralized configuration loading, validation,
and error handling for all CDK resources.
"""

def validate_config(
        config: Dict[str, Any],
        required_fields: List[str]
    ) -> None:
    """
    Validate that a configuration has all required fields.
    
    This function checks that all specified required fields are present
    in the configuration dictionary and raises appropriate errors if
    any are missing.
    
    Args:
        config: Configuration dictionary to validate
        required_fields: List of field names that must be present
        
    Returns:
        None
        
    Raises:
        ValueError: If any required fields are missing
    """
```

### 4. Comments

#### Code Comments
- Add comments to explain **why** code does something, not **what** it does
- Keep comments concise and necessary
- Comment complex logic or business rules
- Avoid obvious comments

#### Example:
```python
# Merge configurations in lexicographic order (later files override earlier ones)
for config_file in sorted(config_files):
    data = json.load(config_file)
    config.update(data)

# Apply embedded defaults to ensure consistency
merged_config = {**self.DEFAULT_CONFIG, **config}
```

### 5. Import Organization

#### Import Order
1. Standard library imports
2. Third-party imports
3. Local application imports

#### Import Formatting
```python
from __future__ import annotations

# Standard library
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party
from aws_cdk import Stack, RemovalPolicy
from constructs import Construct

# Local imports
from cdk_project.configs.config_manager import ConfigManager
from cdk_project.configs.error_handler import ErrorHandler
```

## Architecture Principles

### 1. Centralized Configuration Management
- All configuration loading is handled by `ConfigManager`
- No hardcoded paths or direct file access
- Consistent placeholder expansion across all configs

### 2. Centralized Error Handling
- All validation and error handling uses `ErrorHandler`
- Consistent error messages and formats
- Decorator-based validation for clean code

### 3. Separation of Concerns
- **Builders**: Handle resource construction logic
- **Configs**: Handle configuration management
- **Stacks**: Orchestrate resource deployment
- **Error Handler**: Handle all validation and error scenarios

### 4. Explicit Configuration
- No default values in `.get()` calls
- All required fields must be explicitly provided
- Fail fast on missing or invalid configuration

### 5. Type Safety
- Full type annotations throughout the codebase
- Use of modern Python typing features
- Runtime type validation where appropriate

## Naming Conventions

### 1. Files and Directories
- Use snake_case for file and directory names
- Be descriptive and indicate purpose
- Use consistent suffixes (e.g., `_builder.py`, `_stack.py`)

### 2. Classes
- Use PascalCase for class names
- Be descriptive and indicate purpose
- Use consistent prefixes (e.g., `ConfigManager`, `ErrorHandler`)

### 3. Functions and Variables
- Use snake_case for function and variable names
- Be descriptive and indicate purpose
- Use consistent prefixes for related functions

### 4. Constants
- Use UPPER_SNAKE_CASE for constants
- Group related constants in classes or modules

## Error Handling Standards

### 1. Use Centralized Error Handler
- All validation must use `ErrorHandler` methods
- No inline validation code
- Consistent error message formats

### 2. Error Message Format
```python
# Good
ErrorHandler.validate_required_fields(config, ["name"], "Table configuration")

# Bad
if "name" not in config:
    raise ValueError("Missing name field")
```

### 3. Exception Types
- Use appropriate exception types (`ValueError`, `KeyError`, `FileNotFoundError`)
- Provide meaningful error messages with context
- Include relevant information for debugging

## Testing Standards

### 1. Test Organization
- Create test files for each module
- Use descriptive test function names
- Test both success and failure scenarios

### 2. Test Cleanup
- Remove test files after verification
- Use temporary files/directories when needed
- Clean up any created resources

## Documentation Standards

### 1. Code Documentation
- Every file, class, and function must have docstrings
- Include examples for complex functions
- Document any special behavior or side effects

### 2. Architecture Documentation
- Document design decisions and rationale
- Keep architecture documentation up to date
- Include diagrams for complex relationships

## Best Practices

### 1. Code Quality
- Write self-documenting code
- Use meaningful variable and function names
- Keep functions focused and single-purpose
- Avoid deep nesting and complex logic

### 2. Performance
- Use appropriate data structures
- Avoid unnecessary computations
- Cache expensive operations when appropriate
- Use lazy loading for large datasets

### 3. Security
- Validate all inputs
- Use least privilege principles
- Sanitize user inputs
- Follow AWS security best practices

### 4. Maintainability
- Write code for future maintainers
- Use consistent patterns throughout
- Refactor when patterns emerge
- Keep dependencies minimal and up to date

## Tools and Automation

### 1. Code Formatting
- Use consistent formatting tools
- Automate formatting where possible
- Include formatting checks in CI/CD

### 2. Type Checking
- Use mypy or similar tools for type checking
- Include type checking in CI/CD pipeline
- Fix type errors promptly

### 3. Linting
- Use pylint or similar tools for code quality
- Configure linting rules consistently
- Address linting warnings promptly

This document serves as the definitive guide for all code written in the Odyssey CDK project. All team members should follow these standards to ensure consistency and maintainability.
