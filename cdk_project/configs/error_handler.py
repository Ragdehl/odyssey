"""
Centralized error handling for Odyssey CDK project.

This module provides a comprehensive error handling system with validation
decorators and utility methods for common validation scenarios. It ensures
consistent error messages, reduces code duplication, and makes validation
logic reusable and maintainable across the entire CDK project.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps

class ErrorHandler:
    """
    Centralized error handling for Odyssey CDK project.
    
    Provides decorators and utility methods for common validation scenarios.
    """
    
    @staticmethod
    def validate_path_exists(
            path: Union[str, Path], 
            path_type: str = "Path"
        ) -> None:
        """
        Validate that a path exists and is a directory.
        
        Args:
            path: Path to validate
            path_type: Type description for error messages
            
        Raises:
            FileNotFoundError: If path does not exist or is not a directory
        """
        if not Path(path).is_dir():
            raise FileNotFoundError(f"{path_type} not found: {path}")
    
    @staticmethod
    def validate_file_exists(
            file_path: Union[str, Path], 
            file_type: str = "File"
        ) -> None:
        """
        Validate that a file exists.
        
        Args:
            file_path: File path to validate
            file_type: Type description for error messages
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        if not Path(file_path).is_file():
            raise FileNotFoundError(f"{file_type} not found: {file_path}")
    
    @staticmethod
    def validate_required_fields(
            data: Dict[str, Any], 
            required_fields: List[str], 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that all required fields are present in a dictionary.
        
        Args:
            data: Dictionary to validate
            required_fields: List of field names that must be present
            context: Context description for error messages
            
        Raises:
            ValueError: If any required fields are missing
        """
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"{context} missing required fields: {', '.join(missing_fields)}")
    
    @staticmethod
    def validate_field_structure(
            data: Dict[str, Any], 
            field_name: str, 
            required_subfields: List[str], 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a field has the required subfields.
        
        Args:
            data: Dictionary containing the field to validate
            field_name: Name of the field to validate
            required_subfields: List of subfield names that must be present
            context: Context description for error messages
            
        Raises:
            ValueError: If field is missing or lacks required subfields
        """
        if field_name not in data:
            raise ValueError(f"{context} missing required field '{field_name}'")
        
        field_data = data[field_name]
        if not isinstance(field_data, dict):
            raise ValueError(f"{context} field '{field_name}' must be a dictionary")
        
        missing_subfields = [subfield for subfield in required_subfields if subfield not in field_data]
        if missing_subfields:
            raise ValueError(f"{context} field '{field_name}' missing required subfields: {', '.join(missing_subfields)}")
    
    @staticmethod
    def validate_enum_value(
            value: Any, 
            valid_values: List[Any], 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is one of the allowed enum values.
        
        Args:
            value: Value to validate
            valid_values: List of allowed values
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not in the allowed list
        """
        if value not in valid_values:
            raise ValueError(f"{context} field '{field_name}' must be one of: {', '.join(map(str, valid_values))}")
    
    @staticmethod
    def validate_not_empty(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is not empty (None, empty string, empty list, etc.).
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is empty
        """
        if value is None or value == "" or (isinstance(value, (list, dict)) and len(value) == 0):
            raise ValueError(f"{context} field '{field_name}' cannot be empty")
    
    @staticmethod
    def validate_type(
            value: Any, 
            expected_type: type, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is of the expected type.
        
        Args:
            value: Value to validate
            expected_type: Expected type class
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            TypeError: If value is not of the expected type
        """
        if not isinstance(value, expected_type):
            raise TypeError(f"{context} field '{field_name}' must be of type {expected_type.__name__}, got {type(value).__name__}")
    
    @staticmethod
    def validate_positive_integer(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is a positive integer.
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{context} field '{field_name}' must be a positive integer")
    
    @staticmethod
    def validate_boolean(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is a boolean.
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not a boolean
        """
        if not isinstance(value, bool):
            raise ValueError(f"{context} field '{field_name}' must be a boolean")
    
    @staticmethod
    def validate_string_not_empty(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is a non-empty string.
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not a non-empty string
        """
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(f"{context} field '{field_name}' must be a non-empty string")
    
    @staticmethod
    def validate_list_not_empty(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is a non-empty list.
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not a non-empty list
        """
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError(f"{context} field '{field_name}' must be a non-empty list")
    
    @staticmethod
    def validate_dict_not_empty(
            value: Any, 
            field_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a value is a non-empty dictionary.
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            context: Context description for error messages
            
        Raises:
            ValueError: If value is not a non-empty dictionary
        """
        if not isinstance(value, dict) or len(value) == 0:
            raise ValueError(f"{context} field '{field_name}' must be a non-empty dictionary")
    
    @staticmethod
    def validate_key_exists(
            key: Any, 
            container: Dict[str, Any], 
            key_name: str, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a key exists in a dictionary.
        
        Args:
            key: Key to look for
            container: Dictionary to search in
            key_name: Name of the key for error messages
            context: Context description for error messages
            
        Raises:
            KeyError: If key is not found in container
        """
        if key not in container:
            raise KeyError(f"{context} key '{key_name}' not found in container")
    
    @staticmethod
    def validate_lambda_exists(
            lambda_name: str, 
            lambdas: Dict[str, Any], 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that a lambda function exists in the lambdas dictionary.
        
        Args:
            lambda_name: Name of the lambda function
            lambdas: Dictionary of lambda functions
            context: Context description for error messages
            
        Raises:
            KeyError: If lambda function is not found
        """
        if lambda_name not in lambdas:
            raise KeyError(f"{context} lambda '{lambda_name}' not found in lambdas map")
    
    @staticmethod
    def validate_config_files_provided(
            config_files: Any, 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that config files are provided.
        
        Args:
            config_files: Config files to validate
            context: Context description for error messages
            
        Raises:
            ValueError: If config files are not provided
        """
        if not config_files:
            raise ValueError(f"No config_files provided to {context}")
    
    @staticmethod
    def validate_configs_found(
            configs: List[Any], 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that configurations were found.
        
        Args:
            configs: List of configurations to validate
            context: Context description for error messages
            
        Raises:
            ValueError: If no configurations were found
        """
        if not configs:
            raise ValueError(f"No {context} configurations found")
    
    @staticmethod
    def validate_context_keys(
            missing_keys: List[str], 
            context: str = "Configuration"
        ) -> None:
        """
        Validate that required context keys are present.
        
        Args:
            missing_keys: List of missing key names
            context: Context description for error messages
            
        Raises:
            ValueError: If any required keys are missing
        """
        if missing_keys:
            raise ValueError(f"Missing required context keys in {context}: {', '.join(missing_keys)}")


class ValidationDecorators:
    """
    Decorators for common validation patterns.
    """
    
    @staticmethod
    def validate_path_exists(
            path_param: str, 
            path_type: str = "Path"
        ):
        """
        Decorator to validate that a path parameter exists and is a directory.
        
        Args:
            path_param: Name of the path parameter to validate
            path_type: Type description for error messages
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get the path value from function arguments
                if path_param in kwargs:
                    path_value = kwargs[path_param]
                else:
                    # Try to get from positional arguments (assuming it's the first argument after self)
                    if len(args) > 1:
                        path_value = args[1]  # Skip self
                    else:
                        raise ValueError(f"Path parameter '{path_param}' not found in function arguments")
                
                ErrorHandler.validate_path_exists(path_value, path_type)
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def validate_file_exists(
            file_param: str, 
            file_type: str = "File"
        ):
        """
        Decorator to validate that a file parameter exists.
        
        Args:
            file_param: Name of the file parameter to validate
            file_type: Type description for error messages
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get the file value from function arguments
                if file_param in kwargs:
                    file_value = kwargs[file_param]
                else:
                    # Try to get from positional arguments
                    if len(args) > 1:
                        file_value = args[1]  # Skip self
                    else:
                        raise ValueError(f"File parameter '{file_param}' not found in function arguments")
                
                ErrorHandler.validate_file_exists(file_value, file_type)
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def validate_required_config_fields(
            required_fields: List[str], 
            config_param: str = "conf", 
            context: str = "Configuration"
        ):
        """
        Decorator to validate that a configuration dictionary has all required fields.
        
        Args:
            required_fields: List of required field names
            config_param: Name of the config parameter to validate
            context: Context description for error messages
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get the config value from function arguments
                if config_param in kwargs:
                    config_value = kwargs[config_param]
                else:
                    # Try to get from positional arguments
                    if len(args) > 2:  # Skip self and logical_name
                        config_value = args[2]
                    else:
                        raise ValueError(f"Config parameter '{config_param}' not found in function arguments")
                
                ErrorHandler.validate_required_fields(config_value, required_fields, context)
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def validate_service_name(
            service_param: str = "service_name"
        ):
        """
        Decorator to validate that a service name is valid.
        
        Args:
            service_param: Name of the service parameter to validate
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get the service name from function arguments
                if service_param in kwargs:
                    service_value = kwargs[service_param]
                else:
                    # Try to get from positional arguments
                    if len(args) > 1:
                        service_value = args[1]  # Skip self
                    else:
                        raise ValueError(f"Service parameter '{service_param}' not found in function arguments")
                
                valid_services = ["policies", "dynamodb", "ws_apis", "ws_routes", "lambda_configs", "defaults"]
                ErrorHandler.validate_enum_value(service_value, valid_services, service_param, "Service")
                return func(*args, **kwargs)
            return wrapper
        return decorator


# Convenience functions for common validation patterns
def validate_lambda_root(code_root: str) -> None:
    """
    Validate that the Lambda code root directory exists.
    
    Args:
        code_root: Path to the Lambda code root directory
        
    Raises:
        FileNotFoundError: If the directory does not exist
    """
    ErrorHandler.validate_path_exists(code_root, "Lambda root")

def validate_config_directory(config_dir: str) -> None:
    """
    Validate that a configuration directory exists.
    
    Args:
        config_dir: Path to the configuration directory
        
    Raises:
        FileNotFoundError: If the directory does not exist
    """
    ErrorHandler.validate_path_exists(config_dir, "Config directory")

def validate_config_file(file_path: str) -> None:
    """
    Validate that a configuration file exists.
    
    Args:
        file_path: Path to the configuration file
        
    Raises:
        FileNotFoundError: If the file does not exist
    """
    ErrorHandler.validate_file_exists(file_path, "Config file")

def validate_table_config(
        conf: Dict[str, Any], 
        table_name: str
    ) -> None:
    """
    Validate that a table configuration has all required fields.
    
    Args:
        conf: Table configuration dictionary
        table_name: Name of the table for error messages
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["table_name", "partition_key", "billing_mode", "pitr", "kms_alias"]
    ErrorHandler.validate_required_fields(conf, required_fields, f"Table configuration for {table_name}")
    
    # Validate partition_key structure
    ErrorHandler.validate_field_structure(
        conf, 
        "partition_key", 
        ["name", "type"], 
        f"Table configuration for {table_name}"
    )
    
    # Validate sort_key structure if present
    if "sort_key" in conf:
        ErrorHandler.validate_field_structure(
            conf, 
            "sort_key", 
            ["name", "type"], 
            f"Table configuration for {table_name}"
        )

def validate_lambda_config(
        conf: Dict[str, Any], 
        lambda_name: str
    ) -> None:
    """
    Validate that a Lambda configuration has all required fields.
    
    Args:
        conf: Lambda configuration dictionary
        lambda_name: Name of the lambda for error messages
        
    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["name", "runtime", "memory", "timeout", "handler"]
    ErrorHandler.validate_required_fields(conf, required_fields, f"Lambda configuration for {lambda_name}")

def validate_websocket_api_config(
        conf: Dict[str, Any], 
        api_name: str
    ) -> None:
    """
    Validate that a WebSocket API configuration has all required fields.
    
    Args:
        conf: WebSocket API configuration dictionary
        api_name: Name of the API for error messages
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["name", "route_selection_expression", "stage"]
    ErrorHandler.validate_required_fields(conf, required_fields, f"WebSocket API configuration for {api_name}")
    
    # Validate stage structure
    ErrorHandler.validate_field_structure(
        conf, 
        "stage", 
        ["name", "auto_deploy"], 
        f"WebSocket API configuration for {api_name}"
    )

def validate_route_config(
        conf: Dict[str, Any], 
        route_file: str
    ) -> None:
    """
    Validate that a route configuration has all required fields.
    
    Args:
        conf: Route configuration dictionary
        route_file: Name of the route file for error messages
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["route_key", "integration"]
    ErrorHandler.validate_required_fields(conf, required_fields, f"Route configuration in {route_file}")
    
    # Validate integration structure
    ErrorHandler.validate_field_structure(
        conf, 
        "integration", 
        ["type", "lambda_name"], 
        f"Route configuration in {route_file}"
    )
    
    # Validate integration type
    ErrorHandler.validate_enum_value(
        conf["integration"]["type"], 
        ["lambda"], 
        "type", 
        f"Route integration in {route_file}"
    )