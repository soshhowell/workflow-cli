# Workflow CLI

A Python CLI tool for executing workflows defined in JSON files.

## Installation

```bash
pip install .
```

## Usage

```bash
# Show help
workflow --help

# Run a workflow from JSON file (quiet mode)
workflow -r workflow.json
workflow --run workflow.json

# Run workflow with detailed output
workflow --run my_workflow.json --verbose

# Run workflow with memory variables
workflow -r workflow.json --memory '{"name": "John", "url": "https://api.example.com"}'

# Run workflow with memory from file
workflow -r workflow.json --memory-file memory.json --verbose

# Create a sample workflow file
workflow --sample-file example.json

# Log workflow output to file
workflow -r workflow.json --log-file workflow.log
workflow -r workflow.json --log-path ./logs/
```

### Command Line Options

```
usage: workflow [-h] [-r FILE] [--memory JSON] [--memory-file FILE]
                [--verbose] [--sample-file FILE] [--log-file FILE]
                [--log-path DIR] [--version]

options:
  -h, --help           show this help message and exit
  -r FILE, --run FILE  Path to JSON file containing workflow definition
  --memory JSON        Memory variables as JSON string
  --memory-file FILE   Path to JSON file containing memory variables
  --verbose            Enable detailed step output and progress information
  --sample-file FILE   Create a sample workflow JSON file at specified path
  --log-file FILE      Path to log file for writing all workflow outputs
  --log-path DIR       Directory path where logs will be saved as {workflow_id}.log
  --version            show program's version number and exit
```

## Workflow JSON Format

A workflow JSON file must contain:

- `name`: The name of the workflow
- `memory`: JSON object for workflow state/variables (with optional schema)
- `steps`: Array of steps to execute

### Basic Example

```json
{
    "name": "simple_workflow",
    "memory": {
        "variables": {"project_name": "my-project"},
        "schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "commit_hash": {"type": "string"}
            }
        }
    },
    "steps": [
        {
            "name": "show_project_info",
            "command": "echo 'Working on project: {memory.project_name}'",
            "timeout": 10
        },
        {
            "name": "get_git_commit",
            "command": "git log -1 --pretty=format:'%H'",
            "max_retries": 2,
            "success": {
                "regex": "^[a-f0-9]{40}$"
            },
            "memory_update": [{
                "regex": "^([a-f0-9]{40})$",
                "variable": "memory.commit_hash"
            }]
        },
        {
            "name": "final_report",
            "command": "echo 'Project {memory.project_name} at commit {memory.commit_hash}'",
            "delay": 1.0
        }
    ]
}
```

### Advanced Example with JSON Processing

```json
{
    "name": "api_monitoring_workflow",
    "memory": {
        "variables": {"api_url": "https://api.example.com"},
        "schema": {
            "type": "object", 
            "properties": {
                "api_url": {"type": "string"},
                "health_status": {"type": "string"},
                "response_time": {"type": "number"}
            }
        }
    },
    "steps": [
        {
            "name": "check_api_health",
            "command": "curl -s {memory.api_url}/health",
            "timeout": 30,
            "max_retries": 3,
            "retryDelay": 5,
            "success": {
                "json": "status"
            },
            "memory_update": [{
                "json": "status",
                "variable": "memory.health_status"
            }, {
                "json": "response_time_ms", 
                "variable": "memory.response_time"
            }]
        },
        {
            "name": "validate_health",
            "command": "echo 'API Status: {memory.health_status} (Response: {memory.response_time}ms)'",
            "success": {
                "regex": "API Status: healthy"
            }
        }
    ]
}
```

### Step Format

Each step in the `steps` array must contain:

- `name`: A descriptive name for the step
- `command`: The shell command to execute with optional `{memory.key}` substitutions

Optional step properties:
- `max_retries`: Maximum retry attempts (default: 0)
- `delay`: Delay in seconds before executing this step
- `retryDelay`: Delay in seconds between retry attempts (default: 1)
- `timeout`: Step execution timeout in seconds (default: 300 seconds)
- `success`: Success validation configuration
  - `regex`: Multiline regex pattern to validate command output
  - `json`: JSON path (e.g., 'home.city') to check for existence in parsed output
- `memory_update`: Array of configurations for extracting values from command output
  - `regex`: Regex pattern with capture group + `variable`: memory path to store value
  - `json`: JSON path to extract + `variable`: memory path to store value

## Features

- ✅ JSON schema validation for workflow files
- ✅ Sequential step execution with comprehensive logging
- ✅ Command output capture and display
- ✅ Error handling and reporting with exit codes
- ✅ Configurable step timeouts (default: 300 seconds)
- ✅ Advanced memory/state management with variable substitution
- ✅ Multiple success validation methods (regex patterns and JSON paths)
- ✅ Configurable retry mechanism with custom delays
- ✅ Memory extraction from command output (regex and JSON)
- ✅ Step execution delays and retry delays
- ✅ Comprehensive workflow logging to files
- ✅ CLI memory injection via JSON strings or files
- ✅ Verbose mode for detailed execution information

## Example Files

- `example_workflow.json` - Comprehensive workflow demonstrating all features (regex/JSON parsing, memory management, timeouts, retries)
- `test_retry_workflow.json` - Simple example focusing on retry functionality

Run the comprehensive example:
```bash
workflow -r example_workflow.json --verbose
```