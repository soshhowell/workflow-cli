"""Step executor for running command line operations."""

import json
import logging
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import jsonschema


class StepExecutor:
    """Executes individual workflow steps."""
    
    def __init__(self, quiet: bool = False, workflow_id: str = None, logger: Optional[logging.Logger] = None):
        """Initialize the step executor."""
        self.step_count = 0
        self.quiet = quiet
        self.workflow_id = workflow_id
        self.logger = logger
        
    def execute_step(self, step_name: str, step_type: str, command: str, workflow_file: str, memory_input: Dict[str, Any], memory: Dict[str, Any], success_config: Dict[str, Any] = None, memory_update_config: Dict[str, Any] = None, step_index: int = 1, delay: float = 0, retry_delay: float = 1, max_retries: int = 0, timeout: Optional[float] = None) -> Tuple[int, Dict[str, Any]]:
        """Execute a single workflow step with retry and success validation.
        
        Args:
            step_name: Name of the step being executed
            step_type: Type of step ('command' or 'workflow_call')
            command: Command line to execute (for command steps)
            workflow_file: Path to workflow file to execute (for workflow_call steps)
            memory_input: Memory input for workflow calls
            memory: Workflow memory/state for variable substitution
            success_config: Success validation configuration with regex, json patterns, and value matching
            memory_update_config: Memory update configuration with pattern and capture_groups
            step_index: Index of the current step (1-based)
            delay: Delay in seconds before executing this step
            retry_delay: Delay in seconds between retry attempts
            max_retries: Maximum number of retry attempts (default: 0)
            timeout: Step execution timeout in seconds (default: 300 seconds if None)
            
        Returns:
            Tuple of (exit_code, updated_memory) where exit_code is 0 for success
        """
        self.step_count += 1
        success_config = success_config or {}
        memory_update_config = memory_update_config or {}
        success_regex = success_config.get('regex')
        success_json = success_config.get('json')
        success_value = success_config.get('value')
        
        # Apply delay before step execution
        if delay > 0:
            if self.logger:
                self.logger.info(f"Waiting {delay} seconds before execution...")
            time.sleep(delay)
        
        # Branch execution based on step type
        if step_type == 'workflow_call':
            return self._execute_workflow_call(
                step_name, workflow_file, memory_input, memory, success_config, 
                memory_update_config, retry_delay, max_retries
            )
        
        # Handle command steps (existing logic)
        # Perform variable substitution on the command
        try:
            processed_command = self._substitute_variables(command, memory)
            if processed_command != command:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.info(f"Command after substitution: {processed_command}")
        except Exception as e:
            # Status messages only go to logs in verbose mode
            if self.logger:
                self.logger.error(f"Variable substitution failed: {e}")
            return 1, memory
        
        attempt = 0
        while attempt <= max_retries:
            if attempt > 0:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.info(f"Retry attempt {attempt}/{max_retries}")
                time.sleep(retry_delay)
            
            try:
                # Execute the processed command
                result = subprocess.run(
                    processed_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout if timeout is not None else 300  # Use step timeout or default to 5 minutes
                )
                
                # Capture output and log it
                full_output = ""
                if result.stdout:
                    # Status messages only go to logs in verbose mode
                    if self.logger:
                        self.logger.info("Command stdout:")
                        self.logger.info(result.stdout.rstrip())
                    full_output += result.stdout
                
                if result.stderr:
                    # Status messages only go to logs in verbose mode
                    if self.logger:
                        self.logger.info("Command stderr:")
                        self.logger.info(result.stderr.rstrip())
                    full_output += result.stderr
                
                # Determine success based on regex/JSON validation or exit code
                success = self._validate_success(result.returncode, full_output, success_regex, success_json, success_value)
                
                if success:
                    # Extract memory updates from output if configured
                    updated_memory = self._extract_memory_updates(memory, full_output, memory_update_config, step_name)
                    
                    # In verbose mode, output step completion JSON
                    if not self.quiet:
                        step_result = {
                            "step": {
                                "name": step_name,
                                "status": "completed",
                                "exit_code": result.returncode,
                                "workflow_id": self.workflow_id if self.workflow_id else None
                            }
                        }
                        if updated_memory != memory:
                            step_result["step"]["memory_updated"] = True
                        print(json.dumps(step_result, indent=2))
                    
                    if self.logger:
                        self.logger.info(f"✓ Step '{step_name}' completed successfully (exit code: {result.returncode})")
                        if updated_memory != memory:
                            self.logger.info(f"Memory updated after step '{step_name}'")
                    
                    return 0, updated_memory
                else:
                    # In verbose mode, output step failure JSON
                    if not self.quiet:
                        step_result = {
                            "step": {
                                "name": step_name,
                                "status": "failed",
                                "exit_code": result.returncode,
                                "validation_type": "regex" if success_regex else ("json" if success_json else "exit_code")
                            }
                        }
                        if attempt < max_retries:
                            step_result["step"]["retry_in_seconds"] = retry_delay
                        print(json.dumps(step_result, indent=2))
                    
                    if self.logger:
                        if success_regex:
                            self.logger.error(f"✗ Step '{step_name}' failed regex validation (exit code: {result.returncode})")
                        elif success_json:
                            self.logger.error(f"✗ Step '{step_name}' failed JSON validation (exit code: {result.returncode})")
                        else:
                            self.logger.error(f"✗ Step '{step_name}' failed with exit code {result.returncode}")
                        
                        if attempt < max_retries:
                            self.logger.info(f"Will retry in {retry_delay} second{'s' if retry_delay != 1 else ''}...")
                    
                    if attempt >= max_retries:
                        if self.logger:
                            self.logger.error(f"Step '{step_name}' failed after {max_retries} retries")
                        return result.returncode if result.returncode != 0 else 1, memory
                
            except subprocess.TimeoutExpired:
                timeout_duration = timeout if timeout is not None else 300
                # In verbose mode, output timeout JSON
                if not self.quiet:
                    step_result = {
                        "step": {
                            "name": step_name,
                            "status": "timeout",
                            "timeout_seconds": timeout_duration
                        }
                    }
                    if attempt < max_retries:
                        step_result["step"]["retry_in_seconds"] = retry_delay
                    print(json.dumps(step_result, indent=2))
                    
                if self.logger:
                    self.logger.error(f"✗ Step '{step_name}' timed out after {timeout_duration} seconds")
                    if attempt < max_retries:
                        self.logger.info(f"Will retry in {retry_delay} second{'s' if retry_delay != 1 else ''}...")
                if attempt >= max_retries:
                    if self.logger:
                        self.logger.error(f"Step '{step_name}' timed out after {max_retries} retries")
                    return 124, memory  # Standard timeout exit code
            except Exception as e:
                # In verbose mode, output error JSON
                if not self.quiet:
                    step_result = {
                        "step": {
                            "name": step_name,
                            "status": "error",
                            "error": str(e)
                        }
                    }
                    if attempt < max_retries:
                        step_result["step"]["retry_in_seconds"] = retry_delay
                    print(json.dumps(step_result, indent=2))
                    
                if self.logger:
                    self.logger.error(f"✗ Step '{step_name}' failed with error: {e}")
                    if attempt < max_retries:
                        self.logger.info(f"Will retry in {retry_delay} second{'s' if retry_delay != 1 else ''}...")
                if attempt >= max_retries:
                    if self.logger:
                        self.logger.error(f"Step '{step_name}' failed with exception after {max_retries} retries")
                    return 1, memory
            
            attempt += 1
        
        return 1, memory  # Should not reach here, but return failure if we do
    
    def _validate_success(self, exit_code: int, output: str, success_regex: str = None, success_json: str = None, success_value: Any = None) -> bool:
        """Validate if the step was successful.
        
        Args:
            exit_code: Command exit code
            output: Combined stdout and stderr output
            success_regex: Optional regex pattern to match against output
            success_json: Optional JSON path to check for existence in parsed output
            success_value: Optional expected value at the JSON path
            
        Returns:
            True if successful, False otherwise
        """
        # If JSON path is specified, try JSON validation
        if success_json:
            try:
                parsed_output = json.loads(output.strip())
                # Get the value at the JSON path
                value = self._get_nested_value(parsed_output, success_json)
                
                # If success_value is specified, check for exact match
                if success_value is not None:
                    return value == success_value
                else:
                    # Default behavior: check if the path exists (value is not None)
                    return value is not None
            except json.JSONDecodeError as e:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.warning(f"JSON parsing failed for success validation: {e}")
                return False
            except Exception as e:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.warning(f"JSON path validation failed: {e}")
                return False
        
        # If regex pattern is specified, use regex validation
        if success_regex:
            try:
                pattern = re.compile(success_regex, re.MULTILINE | re.DOTALL)
                match = pattern.search(output)
                return match is not None
            except re.error as e:
                print(f"Invalid regex pattern: {e}", file=sys.stderr)
                # Fallback to exit code validation
                return exit_code == 0
        
        # If no validation pattern specified, use exit code only
        return exit_code == 0
    
    def _substitute_variables(self, command: str, memory: Dict[str, Any]) -> str:
        """Substitute {memory.key.path} variables in the command with actual values.
        
        Args:
            command: Command string with optional {memory.key} patterns
            memory: Memory dictionary for variable lookups
            
        Returns:
            Command string with variables substituted
            
        Raises:
            ValueError: If a referenced memory key is not found
        """
        # Don't return early if memory is empty - we still need to check for variable patterns
        # If there are {{memory.key}} patterns but no memory, that should be an error
        
        # Find all {{memory.key.path}} patterns
        pattern = r'\{\{memory\.([^}]+)\}\}'
        matches = re.findall(pattern, command)
        
        result = command
        for match in matches:
            key_path = match
            value = self._get_nested_value(memory, key_path)
            
            if value is None:
                raise ValueError(f"Memory key '{key_path}' not found")
            
            # Convert value to string
            str_value = str(value)
            result = result.replace(f'{{{{memory.{key_path}}}}}', str_value)
        
        return result
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get nested value from dictionary using dot notation, supporting array indices.
        
        Args:
            data: Dictionary to search in
            key_path: Dot-separated key path (e.g., 'person.name', 'items.0', 'data.users.0.name')
            
        Returns:
            Value at the specified path, or None if not found
        """
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list):
                # Handle array indices
                try:
                    index = int(key)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    return None
            else:
                return None
        
        return current
    
    def _execute_workflow_call(self, step_name: str, workflow_file: str, memory_input: Dict[str, Any], memory: Dict[str, Any], success_config: Dict[str, Any], memory_update_config: List[Dict[str, Any]], retry_delay: float, max_retries: int) -> Tuple[int, Dict[str, Any]]:
        """Execute a workflow call step with retry support.
        
        Args:
            step_name: Name of the step
            workflow_file: Path to the workflow JSON file to execute
            memory_input: Memory values to pass to the called workflow
            memory: Current workflow memory for variable substitution
            success_config: Success validation configuration
            memory_update_config: Memory update configuration
            retry_delay: Delay between retry attempts
            max_retries: Maximum number of retries
            
        Returns:
            Tuple of (exit_code, updated_memory)
        """
        # Import WorkflowRunner here to avoid circular imports
        from .workflow import WorkflowRunner
        from pathlib import Path
        
        # Perform variable substitution on workflow_file path
        try:
            processed_workflow_file = self._substitute_variables(workflow_file, memory)
        except Exception as e:
            # Status messages only go to logs in verbose mode
            if self.logger:
                self.logger.error(f"Variable substitution failed for workflow file path: {e}")
            return 1, memory
        
        # Perform variable substitution on memory_input values
        try:
            processed_memory_input = {}
            for key, value in memory_input.items():
                if isinstance(value, str):
                    processed_memory_input[key] = self._substitute_variables(value, memory)
                else:
                    processed_memory_input[key] = value
        except Exception as e:
            # Status messages only go to logs in verbose mode
            if self.logger:
                self.logger.error(f"Variable substitution failed for memory input: {e}")
            return 1, memory
        
        attempt = 0
        while attempt <= max_retries:
            if attempt > 0:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.info(f"Retry attempt {attempt}/{max_retries}")
                time.sleep(retry_delay)
            
            try:
                # Check if workflow file exists
                workflow_path = Path(processed_workflow_file)
                if not workflow_path.exists():
                    if not workflow_path.is_absolute():
                        # Try relative to current working directory
                        import os
                        workflow_path = Path(os.getcwd()) / processed_workflow_file
                        if not workflow_path.exists():
                            raise FileNotFoundError(f"Workflow file not found: {processed_workflow_file}")
                
                # Create sub-workflow runner with memory input
                memory_input_json = json.dumps(processed_memory_input) if processed_memory_input else None
                
                # Capture the output of the sub-workflow
                import io
                import contextlib
                
                # Redirect stdout to capture the JSON result
                captured_output = io.StringIO()
                
                sub_runner = WorkflowRunner(
                    workflow_path=workflow_path,
                    memory_input=memory_input_json,
                    quiet=True,  # Sub-workflows run quietly to avoid cluttering output
                    log_file=None  # Don't create separate log files for sub-workflows
                )
                
                # Load and execute the sub-workflow
                sub_runner.load_workflow()
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.info(f"Executing sub-workflow: {workflow_path.name}")
                
                # Execute with captured output
                with contextlib.redirect_stdout(captured_output):
                    exit_code = sub_runner.execute()
                
                # Parse the captured JSON output
                workflow_output = captured_output.getvalue().strip()
                
                # If we didn't capture valid JSON, construct it from the final state
                try:
                    json.loads(workflow_output)  # Validate it's valid JSON
                except (json.JSONDecodeError, ValueError):
                    # Fallback: create JSON from final memory state
                    final_memory = getattr(sub_runner, '_final_memory', {})
                    workflow_output = json.dumps({
                        "workflow_result": {
                            "status": "success" if exit_code == 0 else "failed",
                            "workflow_id": getattr(sub_runner, 'workflow_id', 'unknown'),
                            "workflow_name": sub_runner.workflow_data.get('name', 'unknown') if sub_runner.workflow_data else 'unknown',
                            "memory": final_memory
                        }
                    })
                
                # Validate success
                success = self._validate_success(exit_code, workflow_output, 
                                               success_config.get('regex'), 
                                               success_config.get('json'), 
                                               success_config.get('value'))
                
                if success:
                    # Extract memory updates from workflow output
                    updated_memory = self._extract_memory_updates(memory, workflow_output, memory_update_config, step_name)
                    
                    # In verbose mode, output step completion JSON
                    if not self.quiet:
                        step_result = {
                            "step": {
                                "name": step_name,
                                "status": "completed",
                                "type": "workflow_call",
                                "exit_code": exit_code,
                                "workflow_id": self.workflow_id if self.workflow_id else None
                            }
                        }
                        if updated_memory != memory:
                            step_result["step"]["memory_updated"] = True
                        print(json.dumps(step_result, indent=2))
                    
                    if self.logger:
                        self.logger.info(f"✓ Step '{step_name}' (workflow call) completed successfully (exit code: {exit_code})")
                        if updated_memory != memory:
                            self.logger.info(f"Memory updated after step '{step_name}'")
                    
                    return 0, updated_memory
                else:
                    # In verbose mode, output step failure JSON
                    if not self.quiet:
                        step_result = {
                            "step": {
                                "name": step_name,
                                "status": "failed",
                                "type": "workflow_call",
                                "exit_code": exit_code,
                                "validation_failed": True
                            }
                        }
                        if attempt < max_retries:
                            step_result["step"]["retry_in_seconds"] = retry_delay
                        print(json.dumps(step_result, indent=2))
                    
                    if self.logger:
                        self.logger.error(f"✗ Step '{step_name}' (workflow call) failed validation (exit code: {exit_code})")
                        if attempt < max_retries:
                            self.logger.info(f"Will retry in {retry_delay} second{'s' if retry_delay != 1 else ''}...")
                    
                    if attempt >= max_retries:
                        return exit_code if exit_code != 0 else 1, memory
                
            except FileNotFoundError as e:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.error(f"✗ Step '{step_name}' failed: {e}")
                return 1, memory
            except Exception as e:
                # In verbose mode, output error JSON
                if not self.quiet:
                    step_result = {
                        "step": {
                            "name": step_name,
                            "status": "error",
                            "type": "workflow_call",
                            "error": str(e)
                        }
                    }
                    if attempt < max_retries:
                        step_result["step"]["retry_in_seconds"] = retry_delay
                    print(json.dumps(step_result, indent=2))
                    
                if self.logger:
                    self.logger.error(f"✗ Step '{step_name}' (workflow call) failed with error: {e}")
                    if attempt < max_retries:
                        self.logger.info(f"Will retry in {retry_delay} second{'s' if retry_delay != 1 else ''}...")
                if attempt >= max_retries:
                    return 1, memory
            
            attempt += 1
        
        return 1, memory
    
    def get_step_count(self) -> int:
        """Get the number of steps executed."""
        return self.step_count
    
    def _extract_memory_updates(self, memory: Dict[str, Any], output: str, memory_update_config: List[Dict[str, Any]], step_name: str) -> Dict[str, Any]:
        """Extract values from command output and update memory using array of regex/json and variable pairs.
        
        Args:
            memory: Current memory state
            output: Command output (stdout + stderr)
            memory_update_config: Array of memory update configurations with regex/json and variable fields
            step_name: Name of the step (for error reporting)
            
        Returns:
            Updated memory dictionary
        """
        if not memory_update_config:
            return memory
        
        # Create a copy of memory to modify
        updated_memory = memory.copy()
        
        # Process each memory update configuration
        for update_config in memory_update_config:
            try:
                regex_pattern = update_config.get('regex')
                json_path = update_config.get('json')
                variable_path = update_config.get('variable', '')
                
                if not variable_path:
                    # Status messages only go to logs in verbose mode
                    if self.logger:
                        self.logger.warning(f"Invalid memory update config - missing variable")
                    continue
                
                if not regex_pattern and not json_path:
                    # Status messages only go to logs in verbose mode
                    if self.logger:
                        self.logger.warning(f"Invalid memory update config - missing regex or json field")
                    continue
                
                # Remove "memory." prefix from variable path for internal processing
                memory_path = variable_path.replace('memory.', '', 1)
                extracted_value = None
                
                # Handle JSON path extraction
                if json_path:
                    try:
                        parsed_output = json.loads(output.strip())
                        extracted_value = self._get_nested_value(parsed_output, json_path)
                        if extracted_value is not None:
                            # Set the value in memory using dot notation
                            self._set_nested_value(updated_memory, memory_path, extracted_value)
                            # Status messages only go to logs in verbose mode
                            if self.logger:
                                self.logger.info(f"Memory update (JSON): {memory_path} = {extracted_value}")
                        else:
                            # Status messages only go to logs in verbose mode
                            if self.logger:
                                self.logger.warning(f"JSON path '{json_path}' not found in output for step '{step_name}'")
                    except json.JSONDecodeError as e:
                        # Status messages only go to logs in verbose mode
                        if self.logger:
                            self.logger.warning(f"JSON parsing failed for memory update in step '{step_name}': {e}")
                        continue
                
                # Handle regex extraction (if no JSON path specified)
                elif regex_pattern:
                    # Apply regex pattern with multiline and dotall flags
                    regex = re.compile(regex_pattern, re.MULTILINE | re.DOTALL)
                    match = regex.search(output)
                    
                    if not match:
                        # Status messages only go to logs in verbose mode
                        if self.logger:
                            self.logger.warning(f"Memory update regex '{regex_pattern}' did not match output for step '{step_name}'")
                        continue
                    
                    # Extract value from first capture group
                    if len(match.groups()) > 0:
                        extracted_value = match.group(1)
                        if extracted_value is not None:
                            # Set the value in memory using dot notation
                            self._set_nested_value(updated_memory, memory_path, extracted_value)
                            # Status messages only go to logs in verbose mode
                            if self.logger:
                                self.logger.info(f"Memory update (regex): {memory_path} = {extracted_value}")
                        else:
                            # Status messages only go to logs in verbose mode
                            if self.logger:
                                self.logger.warning(f"First capture group is None for memory path '{memory_path}'")
                    else:
                        # Status messages only go to logs in verbose mode
                        if self.logger:
                            self.logger.warning(f"No capture groups found in regex '{regex_pattern}' for memory path '{memory_path}'")
                        
            except re.error as e:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.warning(f"Invalid memory update regex pattern '{regex_pattern}': {e}")
                continue
            except Exception as e:
                # Status messages only go to logs in verbose mode
                if self.logger:
                    self.logger.warning(f"Failed to extract memory update for '{variable_path}': {e}")
                continue
        
        return updated_memory
    
    def _set_nested_value(self, data: Dict[str, Any], key_path: str, value: Any) -> None:
        """Set nested value in dictionary using dot notation.
        
        Args:
            data: Dictionary to modify
            key_path: Dot-separated key path (e.g., 'person.name')
            value: Value to set
        """
        keys = key_path.split('.')
        current = data
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # If we encounter a non-dict value, replace it with a dict
                current[key] = {}
            current = current[key]
        
        # Set the final value
        final_key = keys[-1]
        current[final_key] = value