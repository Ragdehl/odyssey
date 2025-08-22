from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any, Mapping, Dict, List, Optional
from aws_cdk import Stack
from cdk_project.configs.odyssey_cfg import get_cfg

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

class ConfigManager:
    """
    Centralized configuration management for Odyssey CDK project.
    
    Handles:
    - Path resolution for different config types (policies, tables, APIs, etc.)
    - JSON file loading with placeholder expansion
    - Default file merging
    - Directory scanning for config files
    """
    
    # Root config directory
    CONFIG_ROOT = "cdk_project/configs"
    
    # Config type mappings to subdirectories
    CONFIG_PATHS = {
        "policies": "iam/policies",
        "tables": "tables", 
        "ws_apis": "apis/ws",
        "ws_routes": "apis/ws/routes",
        "lambda_configs": "lambda_configs",
        "defaults": "defaults"
    }
    
    def __init__(self, stack: Stack):
        self.stack = stack
        self.cfg = get_cfg(stack)
        self.vars = self.cfg.vars(stack)
    
    def get_config_path(self, config_type: str, filename: str = None) -> str:
        """
        Get the full path to a config file.
        
        Args:
            config_type: Type of config (policies, tables, ws_apis, etc.)
            filename: Optional filename, if None returns the directory path
            
        Returns:
            Full path to the config file or directory
        """
        if config_type not in self.CONFIG_PATHS:
            raise ValueError(f"Unknown config type: {config_type}")
        
        base_path = os.path.join(self.CONFIG_ROOT, self.CONFIG_PATHS[config_type])
        
        if filename:
            return os.path.join(base_path, filename)
        return base_path
    
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
    
    def load_json(self, filepath: str, expand_vars: bool = True) -> dict:
        """
        Load and parse a JSON file, optionally expanding placeholders.
        
        Args:
            filepath: Path to the JSON file
            expand_vars: Whether to expand placeholders in the loaded JSON
            
        Returns:
            Parsed JSON as dict
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if expand_vars:
            data = self.expand_placeholders(data)
            
        return data
    
    def load_config(self, config_type: str, filename: str, expand_vars: bool = True) -> dict:
        """
        Load a config file by type and filename.
        
        Args:
            config_type: Type of config (policies, tables, etc.)
            filename: Name of the config file
            expand_vars: Whether to expand placeholders
            
        Returns:
            Parsed JSON config
        """
        filepath = self.get_config_path(config_type, filename)
        return self.load_json(filepath, expand_vars)
    
    def load_config_with_defaults(self, config_type: str, filename: str, defaults_file: str = None) -> dict:
        """
        Load a config file and merge with defaults if provided.
        
        Args:
            config_type: Type of config
            filename: Name of the config file
            defaults_file: Optional defaults file to merge
            
        Returns:
            Merged config dict
        """
        config = self.load_config(config_type, filename)
        
        if defaults_file:
            defaults = self.load_config(config_type, defaults_file)
            config = {**defaults, **config}  # Config overrides defaults
            
        return config
    
    def list_config_files(self, config_type: str, exclude: Optional[set[str]] = None) -> List[str]:
        """
        List all JSON files in a config directory.
        
        Args:
            config_type: Type of config directory
            exclude: Set of filenames to exclude
            
        Returns:
            List of full file paths
        """
        config_dir = self.get_config_path(config_type)
        p = Path(config_dir)
        
        if not p.is_dir():
            raise FileNotFoundError(f"Config directory not found: {config_dir}")
            
        files = sorted(str(fp) for fp in p.glob("*.json"))
        
        if exclude:
            files = [f for f in files if Path(f).name not in exclude]
            
        return files
    
    def find_lambda_dirs(self, code_root: str = "lambda_src") -> List[Path]:
        """
        Find all lambda directories that contain app.py.
        
        Args:
            code_root: Root directory to search in
            
        Returns:
            List of Path objects for lambda directories
        """
        root = Path(code_root)
        if not root.is_dir():
            raise FileNotFoundError(f"Lambda root not found: {code_root}")
            
        lambda_dirs = []
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            if (d / "app.py").is_file():
                lambda_dirs.append(d)
                
        return lambda_dirs
    
    def load_lambda_config_from_folder(self, folder: Path, extra_vars: Dict[str, str] = None) -> dict:
        """
        Load and merge all config*.json files from a lambda folder.
        
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
            data = self.load_json(str(cf), expand_vars=False)  # Don't expand yet
            conf.update(data)
        
        # Apply defaults
        conf.setdefault("name", folder.name)
        conf.setdefault("runtime", "python3.12")
        conf.setdefault("memory", 256)
        conf.setdefault("timeout", 10)
        conf.setdefault("handler", "app.handler")
        
        # Add code path
        conf["code_path"] = str(folder.resolve())
        
        # Expand placeholders with extra vars
        vars_to_use = self.vars.copy()
        if extra_vars:
            vars_to_use.update(extra_vars)
            
        conf = self.expand_placeholders(conf, vars_to_use)
        
        return conf
    
    def resolve_policy_file(self, policy_file: Optional[str], base_folder: Path = None) -> Optional[str]:
        """
        Resolve a policy file path, checking local folder first, then configs.
        
        Args:
            policy_file: Policy file name or path
            base_folder: Base folder to check for local policy files
            
        Returns:
            Resolved policy file path or None
        """
        if not policy_file:
            return None
            
        p = Path(policy_file)
        
        if not p.is_absolute():
            # Try local folder first
            if base_folder:
                local = base_folder / policy_file
                if local.is_file():
                    return str(local)
                    
            # Fall back to configs directory
            alt = Path(self.get_config_path("policies", policy_file))
            if alt.is_file():
                return str(alt)
                
        return str(p)
    
    def find_route_files(self, api_name: str) -> List[Path]:
        """
        Find all route JSON files for a specific WebSocket API.
        
        Args:
            api_name: Name of the API (folder name under configs/apis/ws/)
            
        Returns:
            List of Path objects for route JSON files
        """
        routes_dir = Path(self.get_config_path("ws_apis")) / api_name / "routes"
        
        if not routes_dir.is_dir():
            raise FileNotFoundError(f"Routes directory not found: {routes_dir}")
            
        route_files = sorted(routes_dir.glob("**/*.json"))
        return route_files
    
    def load_route_config(self, route_file: Path) -> dict:
        """
        Load a route configuration file with placeholder expansion.
        
        Args:
            route_file: Path to the route JSON file
            
        Returns:
            Parsed route configuration
        """
        return self.load_json(str(route_file))
    
    def find_api_directories(self) -> List[Path]:
        """
        Find all WebSocket API directories.
        
        Returns:
            List of Path objects for API directories
        """
        apis_dir = Path(self.get_config_path("ws_apis"))
        
        if not apis_dir.is_dir():
            raise FileNotFoundError(f"WebSocket APIs directory not found: {apis_dir}")
            
        api_dirs = []
        for d in sorted(p for p in apis_dir.iterdir() if p.is_dir()):
            api_json = d / "api.json"
            routes_dir = d / "routes"
            
            if api_json.is_file() and routes_dir.is_dir():
                api_dirs.append(d)
                
        return api_dirs
    
    def load_api_config(self, api_dir: Path) -> dict:
        """
        Load an API configuration file.
        
        Args:
            api_dir: Path to the API directory
            
        Returns:
            Parsed API configuration
        """
        api_json = api_dir / "api.json"
        return self.load_json(str(api_json))
    
    def load_table_configs(self, config_files: Optional[List[str]] = None, defaults_file: Optional[str] = None) -> List[tuple[str, dict]]:
        """
        Load table configurations with optional defaults.
        
        Args:
            config_files: Optional list of specific table config filenames
            defaults_file: Optional defaults filename to merge with each config
            
        Returns:
            List of tuples (filepath, config_dict)
        """
        # Load defaults if provided
        defaults: dict = {}
        if defaults_file:
            defaults = self.load_config("tables", defaults_file) or {}
        
        # Gather table config files
        files: List[str] = []
        if config_files:
            # Load specific files
            for filename in config_files:
                filepath = self.get_config_path("tables", filename)
                files.append(filepath)
        else:
            # Load all files in tables directory
            exclude = {defaults_file} if defaults_file else set()
            files = self.list_config_files("tables", exclude=exclude)
        
        # Load and merge configurations
        configs = []
        for filepath in files:
            conf = self.load_json(filepath)
            merged = {**defaults, **conf}
            configs.append((filepath, merged))
        
        return configs
