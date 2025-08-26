"""Workflow parser and runner with JSON validation."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

from .executor import StepExecutor


class WorkflowRunner:
    """Manages workflow execution from JSON definitions."""
    
    WORKFLOW_SCHEMA = {
        "type": "object",
        "required": ["name", "memory", "steps"],
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the workflow"
            },
            "memory": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "object",
                        "description": "Runtime variables accessible via {memory.key} substitution"
                    },
                    "schema": {
                        "type": "object",
                        "description": "JSON schema for validating memory variables"
                    },
                    "initial": {
                        "type": "object",
                        "description": "Default/initial values for memory variables"
                    }
                },
                "description": "Memory/state management with variables, schema, and defaults"
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "command"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the step"
                        },
                        "command": {
                            "type": "string",
                            "description": "Command line to execute"
                        },
                        "max_retries": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 0,
                            "description": "Maximum number of retry attempts (default: 0)"
                        },
                        "success": {
                            "type": "object",
                            "description": "Success validation configuration",
                            "properties": {
                                "regex": {
                                    "type": "string",
                                    "description": "Multiline regex pattern to match against command output for success validation"
                                },
                                "json": {
                                    "type": "string",
                                    "description": "JSON path (e.g., 'home.city') to check for existence in JSON-parsed command output"
                                }
                            }
                        },
                        "memory_update": {
                            "type": "array",
                            "description": "Array of memory update configurations for extracting values from command output",
                            "items": {
                                "type": "object",
                                "anyOf": [
                                    {
                                        "required": ["regex", "variable"],
                                        "properties": {
                                            "regex": {
                                                "type": "string",
                                                "description": "Regex pattern with single capture group to extract value from command output"
                                            },
                                            "variable": {
                                                "type": "string",
                                                "pattern": "^memory\\.[a-zA-Z_][a-zA-Z0-9_]*(\\.([a-zA-Z_][a-zA-Z0-9_]*))*$",
                                                "description": "Memory variable path (e.g., 'memory.url', 'memory.system.version') to store extracted value"
                                            }
                                        }
                                    },
                                    {
                                        "required": ["json", "variable"],
                                        "properties": {
                                            "json": {
                                                "type": "string",
                                                "description": "JSON path (e.g., 'home.city') to extract value from JSON-parsed command output"
                                            },
                                            "variable": {
                                                "type": "string",
                                                "pattern": "^memory\\.[a-zA-Z_][a-zA-Z0-9_]*(\\.([a-zA-Z_][a-zA-Z0-9_]*))*$",
                                                "description": "Memory variable path (e.g., 'memory.url', 'memory.system.version') to store extracted value"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "delay": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Delay in seconds before executing this step (supports decimal values like 0.5)"
                        },
                        "retryDelay": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Delay in seconds between retry attempts (supports decimal values like 0.5)"
                        },
                        "timeout": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Step execution timeout in seconds (default: no timeout)"
                        }
                    }
                },
                "minItems": 1,
                "description": "Array of workflow steps to execute"
            }
        }
    }
    
    def __init__(self, workflow_path: Path, memory_input: Optional[str] = None, memory_file: Optional[str] = None, quiet: bool = False, log_file: Optional[str] = None, log_path: Optional[str] = None):
        """Initialize with workflow file path and optional memory input."""
        self.workflow_path = workflow_path
        self.workflow_data = None
        self.memory_input = memory_input
        self.memory_file = memory_file
        self.quiet = quiet
        self.log_file = log_file
        self.log_path = log_path
        self.workflow_id = str(uuid.uuid4())
        self.logger = self._setup_logging()
        self.executor = StepExecutor(quiet=quiet, workflow_id=self.workflow_id, logger=self.logger)
        
    def load_workflow(self) -> Dict[str, Any]:
        """Load and validate workflow from JSON file."""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in workflow file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read workflow file: {e}")
        
        # Validate against schema
        try:
            jsonschema.validate(workflow_data, self.WORKFLOW_SCHEMA)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Workflow validation failed: {e.message}")
        
        self.workflow_data = workflow_data
        return workflow_data
    
    def _load_user_memory(self) -> Dict[str, Any]:
        """Load memory from CLI input or file."""
        user_memory = {}
        
        # Load from memory file if provided
        if self.memory_file:
            try:
                memory_path = Path(self.memory_file)
                if not memory_path.exists():
                    raise ValueError(f"Memory file '{self.memory_file}' not found")
                
                with open(memory_path, 'r', encoding='utf-8') as f:
                    file_memory = json.load(f)
                user_memory.update(file_memory)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in memory file: {e}")
            except Exception as e:
                raise ValueError(f"Failed to read memory file: {e}")
        
        # Load from memory string if provided (overrides file)
        if self.memory_input:
            try:
                string_memory = json.loads(self.memory_input)
                user_memory.update(string_memory)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in memory input: {e}")
        
        return user_memory
    
    def _initialize_memory(self) -> Dict[str, Any]:
        """Initialize and merge memory from workflow and user input."""
        # Get workflow memory structure
        workflow_memory = self.workflow_data.get('memory', {})
        variables = workflow_memory.get('variables', {})
        initial = workflow_memory.get('initial', {})
        schema = workflow_memory.get('schema', {})
        
        # Start with workflow initial values
        memory = initial.copy()
        memory.update(variables)  # Override with workflow variables
        
        # Load and merge user memory
        user_memory = self._load_user_memory()
        memory.update(user_memory)  # User input has highest priority
        
        # Validate against schema if provided
        if schema:
            try:
                jsonschema.validate(memory, schema)
            except jsonschema.ValidationError as e:
                raise ValueError(f"Memory validation failed: {e.message}")
        
        return memory
    
    def _setup_logging(self) -> Optional[logging.Logger]:
        """Setup file logging if log_file or log_path is specified."""
        if not self.log_file and not self.log_path:
            return None
        
        # Determine log file path
        if self.log_file:
            log_file_path = Path(self.log_file)
        else:
            # Handle log_path with optional trailing slash
            log_dir = Path(self.log_path.rstrip('/'))
            log_file_path = log_dir / f"{self.workflow_id}.log"
        
        # Create directories if they don't exist
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create log directory: {e}")
            return None
        
        # Setup logger
        logger = logging.getLogger(f"workflow_{self.workflow_id}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # File handler
        try:
            file_handler = logging.FileHandler(log_file_path, mode='w')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Log initial setup
            logger.info(f"=== Workflow Logging Started ===")
            logger.info(f"Workflow ID: {self.workflow_id}")
            logger.info(f"Workflow file: {self.workflow_path}")
            logger.info(f"Log file: {log_file_path}")
            
            return logger
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
            return None
    
    def execute(self) -> int:
        """Execute the workflow and return exit code."""
        if not self.workflow_data:
            self.load_workflow()
        
        # Initialize memory from workflow and user input
        memory = self._initialize_memory()
        
        if not self.quiet:
            print(f"Starting workflow: {self.workflow_data['name']}")
            print(f"Workflow ID: {self.workflow_id}")
            print(f"Steps to execute: {len(self.workflow_data['steps'])}")
            if memory:
                print(f"Memory initialized with {len(memory)} variables")
            print("-" * 50)
        
        # Log workflow start
        if self.logger:
            self.logger.info(f"Starting workflow: {self.workflow_data['name']}")
            self.logger.info(f"Steps to execute: {len(self.workflow_data['steps'])}")
            if memory:
                self.logger.info(f"Memory initialized with {len(memory)} variables: {list(memory.keys())}")
            self.logger.info("-" * 50)
        
        # Execute steps sequentially
        completed_steps = 0
        failed_step = None
        
        for i, step in enumerate(self.workflow_data['steps'], 1):
            step_name = step['name']
            command = step['command']
            success_config = step.get('success', {})
            memory_update_config = step.get('memory_update', {})
            delay = step.get('delay', 0)
            retry_delay = step.get('retryDelay', 1)  # Default to 1 second for backward compatibility
            max_retries = step.get('max_retries', 0)
            timeout = step.get('timeout', None)  # No default timeout
            
            if not self.quiet:
                print(f"\n[{i}/{len(self.workflow_data['steps'])}] Executing step: {step_name}")
                print(f"Command: {command}")
                
                if delay > 0:
                    print(f"Delay before execution: {delay} seconds")
                if success_config.get('regex'):
                    print(f"Success validation: Using regex pattern")
                if success_config.get('json'):
                    print(f"Success validation: Using JSON path '{success_config['json']}'")
                if max_retries > 0:
                    print(f"Max retries: {max_retries}")
                    if retry_delay != 1:
                        print(f"Retry delay: {retry_delay} seconds")
                if memory_update_config:
                    print(f"Memory update: Will extract {len(memory_update_config)} values")
                if timeout:
                    print(f"Step timeout: {timeout} seconds")
            
            # Log step start
            if self.logger:
                self.logger.info(f"[{i}/{len(self.workflow_data['steps'])}] Starting step: {step_name}")
                self.logger.info(f"Command: {command}")
                if delay > 0:
                    self.logger.info(f"Delay before execution: {delay} seconds")
                if success_config.get('regex'):
                    self.logger.info(f"Success validation: Using regex pattern")
                if success_config.get('json'):
                    self.logger.info(f"Success validation: Using JSON path '{success_config['json']}'")
                if max_retries > 0:
                    self.logger.info(f"Max retries: {max_retries}")
                    if retry_delay != 1:
                        self.logger.info(f"Retry delay: {retry_delay} seconds")
                if memory_update_config:
                    self.logger.info(f"Memory update: Will extract {len(memory_update_config)} values")
                if timeout:
                    self.logger.info(f"Step timeout: {timeout} seconds")
            
            # Execute the step with success configuration, memory, memory update configuration, delay settings, and timeout
            exit_code, updated_memory = self.executor.execute_step(step_name, command, memory, success_config, memory_update_config, i, delay, retry_delay, max_retries, timeout)
            
            # Update memory for next steps
            if updated_memory:
                memory = updated_memory
            
            if exit_code != 0:
                failed_step = step_name
                if not self.quiet:
                    print(f"\nWorkflow failed at step '{step_name}' with exit code {exit_code}")
                
                # Log failure
                if self.logger:
                    self.logger.error(f"Workflow failed at step '{step_name}' with exit code {exit_code}")
                
                # Output final JSON result on failure
                result = {
                    "workflow_result": {
                        "status": "failed",
                        "workflow_id": self.workflow_id,
                        "workflow_name": self.workflow_data['name'],
                        "completed_steps": completed_steps,
                        "total_steps": len(self.workflow_data['steps']),
                        "failed_step": failed_step,
                        "memory": memory
                    }
                }
                print(json.dumps(result, indent=2))
                
                # Log final result
                if self.logger:
                    self.logger.info("Final workflow result:")
                    self.logger.info(json.dumps(result, indent=2))
                    self.logger.info("=== Workflow Logging Ended ===")
                
                return exit_code
            
            completed_steps += 1
        
        # Output final JSON result on success
        result = {
            "workflow_result": {
                "status": "success",
                "workflow_id": self.workflow_id,
                "workflow_name": self.workflow_data['name'],
                "completed_steps": completed_steps,
                "total_steps": len(self.workflow_data['steps']),
                "memory": memory
            }
        }
        
        if not self.quiet:
            print(f"\n{'='*50}")
            print(f"Workflow '{self.workflow_data['name']}' completed successfully!")
        
        print(json.dumps(result, indent=2))
        
        # Log successful completion
        if self.logger:
            self.logger.info(f"Workflow '{self.workflow_data['name']}' completed successfully!")
            self.logger.info("Final workflow result:")
            self.logger.info(json.dumps(result, indent=2))
            self.logger.info("=== Workflow Logging Ended ===")
        
        return 0