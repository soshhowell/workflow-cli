#!/usr/bin/env python3
"""Main CLI entry point for workflow command."""

import argparse
import json
import sys
from pathlib import Path

from .workflow import WorkflowRunner


def create_parser():
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        prog="workflow",
        description="Execute workflows defined in JSON files with {{memory.key}} variable substitution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Variable Substitution:
  Use double brackets {{memory.key}} in commands to substitute memory variables.
  Examples: {{memory.api_url}}, {{memory.user_id}}, {{memory.config.timeout}}

Example workflow JSON format:
{
    "name": "example_workflow",
    "memory": {
        "variables": {"api_url": "https://api.example.com", "timeout": 30}
    },
    "steps": [
        {
            "name": "api_call",
            "command": "curl -s {{memory.api_url}}/status",
            "timeout": {{memory.timeout}},
            "success": {"json": "status"},
            "memory_update": [{"json": "response_time", "variable": "memory.response_ms"}]
        },
        {
            "name": "report_status",
            "command": "echo 'API responded in {{memory.response_ms}}ms'"
        }
    ]
}

Usage examples:
  workflow --help                              Show this help message
  workflow -r workflow.json                    Run workflow (quiet mode - final JSON only)
  workflow --run workflow.json --verbose       Run workflow with JSON output mode
  workflow --sample-file example.json          Create sample workflow file
  workflow -r workflow.json --memory '{"api_url": "https://myapi.com"}'
  workflow -r workflow.json --memory-file memory.json --verbose --log-file workflow.log
        """
    )
    
    parser.add_argument(
        "-r", "--run",
        metavar="FILE",
        help="Path to JSON file containing workflow definition"
    )
    
    parser.add_argument(
        "--memory",
        metavar="JSON",
        help="Memory variables as JSON string for {{memory.key}} substitution (e.g., '{\"name\": \"value\"}')"
    )
    
    parser.add_argument(
        "--memory-file",
        metavar="FILE",
        help="Path to JSON file containing memory variables for {{memory.key}} substitution"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable JSON output mode: outputs step JSON during execution and final result JSON, with status messages sent to logs if configured"
    )
    
    parser.add_argument(
        "--sample-file",
        metavar="FILE",
        help="Create a sample workflow JSON file at the specified path"
    )
    
    parser.add_argument(
        "--log-file",
        metavar="FILE",
        help="Path to log file for writing all workflow outputs and progress"
    )
    
    parser.add_argument(
        "--log-path",
        metavar="DIR",
        help="Directory path where logs will be saved as {workflow_id}.log"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s 0.2.1"
    )
    
    return parser


def create_sample_workflow(file_path: str) -> None:
    """Create a sample workflow file at the specified path."""
    # Read the current example_workflow.json content
    current_dir = Path(__file__).parent.parent
    example_file = current_dir / "example_workflow.json"
    
    try:
        with open(example_file, 'r') as f:
            example_content = f.read()
        
        # Write to the specified path
        output_path = Path(file_path)
        with open(output_path, 'w') as f:
            f.write(example_content)
        
        print(f"Sample workflow created at: {output_path.absolute()}")
        
    except FileNotFoundError:
        # Fallback: create a basic example if example_workflow.json is not found
        sample_workflow = {
            "name": "sample_workflow",
            "memory": {
                "variables": {
                    "project_name": "my-project",
                    "author": "Your Name"
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string"},
                        "author": {"type": "string"},
                        "current_dir": {"type": "string"}
                    }
                }
            },
            "steps": [
                {
                    "name": "show_current_directory",
                    "command": "pwd",
                    "memory_update": [{
                        "regex": "^(.+?)\\s*$",
                        "variable": "memory.current_dir"
                    }]
                },
                {
                    "name": "list_files_with_retry",
                    "command": "ls -la",
                    "max_retries": 2,
                    "success": {
                        "regex": "total"
                    },
                    "delay": 1.0
                },
                {
                    "name": "show_project_info", 
                    "command": "echo 'Project: {{memory.project_name}} by {{memory.author}} in {{memory.current_dir}}'"
                }
            ]
        }
        
        output_path = Path(file_path)
        with open(output_path, 'w') as f:
            json.dump(sample_workflow, f, indent=4)
        
        print(f"Sample workflow created at: {output_path.absolute()}")


def main():
    """Main entry point for the workflow CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle sample file creation
    if args.sample_file:
        try:
            create_sample_workflow(args.sample_file)
            return 0
        except Exception as e:
            print(f"Error creating sample file: {e}", file=sys.stderr)
            return 1
    
    if not args.run:
        parser.print_help()
        return 0
    
    workflow_path = Path(args.run)
    if not workflow_path.exists():
        print(f"Error: Workflow file '{workflow_path}' not found.", file=sys.stderr)
        return 1
    
    try:
        runner = WorkflowRunner(
            workflow_path, 
            memory_input=args.memory, 
            memory_file=args.memory_file, 
            quiet=not args.verbose,
            log_file=args.log_file,
            log_path=args.log_path
        )
        return runner.execute()
    except Exception as e:
        if args.verbose:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())