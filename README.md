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

# Run a workflow from JSON file
workflow -r workflow.json
workflow --run workflow.json
```

## Workflow JSON Format

A workflow JSON file must contain:

- `name`: The name of the workflow
- `memory`: JSON object for workflow state/variables (with optional schema)
- `steps`: Array of steps to execute

### Example Workflow

```json
{
    "name": "example_workflow",
    "memory": {
        "variables": {},
        "schema": {}
    },
    "steps": [
        {
            "name": "list_files",
            "command": "ls -la"
        },
        {
            "name": "show_date",
            "command": "date",
            "max_retries": 1,
            "success": {
                "regex": "202[0-9]"
            }
        }
    ]
}
```

### Step Format

Each step in the `steps` array must contain:

- `name`: A descriptive name for the step
- `command`: The shell command to execute
- `max_retries` (optional): Maximum retry attempts (default: 0)
- `success` (optional): Success validation configuration
  - `regex` (optional): Multiline regex pattern to validate command output

## Features

- ✅ JSON schema validation
- ✅ Sequential step execution
- ✅ Command output capture
- ✅ Error handling and reporting
- ✅ Timeout protection (5 minutes per step)
- ✅ Memory/state management structure
- ✅ Regex-based success validation
- ✅ Configurable retry mechanism with delays
- ✅ Multiline pattern matching

## Examples

- `example_workflow.json` - Basic workflow example
- `example_advanced_workflow.json` - Advanced workflow with success validation and retries
- `test_retry_workflow.json` - Example demonstrating retry functionality