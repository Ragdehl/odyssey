from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any, Mapping, Dict, List, Optional, Union
from aws_cdk import Stack
from cdk_project.configs.odyssey_cfg import get_cfg
from cdk_project.configs.error_handler import ErrorHandler, ValidationDecorators

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

class ConfigManager:
    """
    Centralized configuration management for Odyssey CDK project.
    
    Simplified API with unified methods for all configuration loading scenarios.
    """
    
    # Root config directory
    CONFIG_ROOT = "cdk_project/configs"
    
    # Config type mappings to subdirectories
    CONFIG_PATHS = {
        "policies": "iam/policies",
        "dynamodb": "tables", 
        "ws_apis": "apis/ws",
        "ws_routes": "apis/ws/routes",
        "lambda_configs": "lambda_configs",
        "defaults": "defaults"
    }
    
    def __init__(self, stack: Stack):
        self.stack = stack
        self.cfg = get_cfg(stack)
        self.vars = self.cfg.vars(stack)
    
    def expand_placeholders(self, obj: Any, vars: Mapping[str, str] = None) -> Any:
        """
        Recursively expand ${VAR} placeholders in strings, lists, and dicts.
        
        Args:
            obj: Object to expand placeholders in
            vars: Variables to substitute (uses stack vars if None)
            
        Returns:
            Object with placeholders expanded
        """
        if vars is None:
            vars = self.vars
            
        if isinstance(obj, str):
            return _VAR.sub(lambda m: str(vars.get(m.group(1), m.group(0))), obj)
        if isinstance(obj, list):
            return [self.expand_placeholders(x, vars) for x in obj]
        if isinstance(obj, dict):
            return {k: self.expand_placeholders(v, vars) for k, v in obj.items()}
        return obj
    
    @ValidationDecorators.validate_service_name()
    def load_config(self, service_name: str, file_name: Optional[str] = None, expand_vars: bool = True, defaults_file: Optional[str] = None) -> Union[dict, List[dict], List[tuple[str, dict]]]:
        """
        Unified method to load configurations for any service.
        
        Args:
            service_name: Type of service (policies, tables, ws_apis, etc.)
            file_name: Optional specific file to load. If None, loads all files in directory
            expand_vars: Whether to expand placeholders
            defaults_file: Optional defaults file to merge with each config
            
        Returns:
            - Single dict if file_name is provided
            - List of dicts if loading all files from directory
            - List of tuples (filepath, dict) for tables with defaults
        """
        base_path = os.path.join(self.CONFIG_ROOT, self.CONFIG_PATHS[service_name])
        
        # Load defaults if provided
        defaults: dict = {}
        if defaults_file:
            defaults_path = os.path.join(base_path, defaults_file)
            if os.path.isfile(defaults_path):
                with open(defaults_path, "r", encoding="utf-8") as f:
                    defaults = json.load(f)
                    if expand_vars:
                        defaults = self.expand_placeholders(defaults)
        
        # Load specific file
        if file_name:
            file_path = os.path.join(base_path, file_name)
            ErrorHandler.validate_file_exists(file_path, "Config file")
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if expand_vars:
                data = self.expand_placeholders(data)
            
            # Merge with defaults if provided
            if defaults:
                data = {**defaults, **data}
            
            return data
        
        # Load all files in directory
        ErrorHandler.validate_path_exists(base_path, "Config directory")
        
        files = sorted(Path(base_path).glob("*.json"))
        if defaults_file:
            files = [f for f in files if f.name != defaults_file]
        
        if not files:
            return []
        
        # Standard handling for all services
        configs = []
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if expand_vars:
                data = self.expand_placeholders(data)
            if defaults:
                data = {**defaults, **data}
            configs.append(data)
        
        return configs
    
    @ValidationDecorators.validate_path_exists("code_root", "Lambda root")
    def find_lambda_dirs(self, code_root: str = "lambda_src") -> List[Path]:
        """
        Find all lambda directories that contain app.py.
        
        Args:
            code_root: Root directory to search in
            
        Returns:
            List of Path objects for lambda directories
        """
        lambda_dirs = []
        for d in sorted(p for p in Path(code_root).iterdir() if p.is_dir()):
            if (d / "app.py").is_file():
                lambda_dirs.append(d)
                
        return lambda_dirs
    
    def load_lambda_config(self, folder: Path, extra_vars: Dict[str, str] = None) -> dict:
        """
        Load lambda configuration from a folder.
        
        Args:
            folder: Lambda folder path
            extra_vars: Additional variables for placeholder expansion
            
        Returns:
            Merged lambda configuration
        """
        # Gather config JSONs
        config_files = sorted(folder.glob("config*.json"))
        conf: dict = {}
        
        # Merge in lexicographic order (later files override earlier ones)
        for cf in config_files:
            with open(cf, "r", encoding="utf-8") as f:
                data = json.load(f)
            conf.update(data)
        
        # Validate required fields
        required_fields = ["name", "runtime", "memory", "timeout", "handler"]
        ErrorHandler.validate_required_fields(conf, required_fields, f"Lambda configuration in {folder}")
        
        # Add code path
        conf["code_path"] = str(folder.resolve())
        
        # Expand placeholders with extra vars
        vars_to_use = self.vars.copy()
        if extra_vars:
            vars_to_use.update(extra_vars)
            
        conf = self.expand_placeholders(conf, vars_to_use)
        
        return conf
    
    @ValidationDecorators.validate_service_name()
    def find_api_dirs(self, service_name: str = "ws_apis") -> List[Path]:
        """
        Find API directories for a service.
        
        Args:
            service_name: Service type (ws_apis, etc.)
            
        Returns:
            List of Path objects for API directories
        """
        apis_dir = Path(os.path.join(self.CONFIG_ROOT, self.CONFIG_PATHS[service_name]))
        ErrorHandler.validate_path_exists(apis_dir, "APIs directory")
            
        api_dirs = []
        for d in sorted(p for p in apis_dir.iterdir() if p.is_dir()):
            api_json = d / "api.json"
            routes_dir = d / "routes"
            
            if api_json.is_file() and routes_dir.is_dir():
                api_dirs.append(d)
                
        return api_dirs
    
    @ValidationDecorators.validate_service_name()
    def find_route_files(self, api_name: str, service_name: str = "ws_apis") -> List[Path]:
        """
        Find route files for an API.
        
        Args:
            api_name: Name of the API
            service_name: Service type (ws_apis, etc.)
            
        Returns:
            List of Path objects for route files
        """
        routes_dir = Path(os.path.join(self.CONFIG_ROOT, self.CONFIG_PATHS[service_name])) / api_name / "routes"
        ErrorHandler.validate_path_exists(routes_dir, "Routes directory")
            
        route_files = sorted(routes_dir.glob("**/*.json"))
        return route_files
