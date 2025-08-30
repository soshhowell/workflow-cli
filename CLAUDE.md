# Claude Code Development Notes

This file contains important information about the project structure, development workflow, and how to work effectively with this codebase using Claude Code.

## Project Overview

**Workflow CLI** is a Python package that provides a command-line tool for executing workflows defined in JSON files. The tool supports regex-based success validation, configurable retries, and comprehensive error handling.

⚠️ **POC Mode**: This project is currently in Proof of Concept mode. We prioritize rapid feature development and experimentation over backward compatibility. Breaking changes are expected and acceptable during this phase.

## Project Structure

```
workflow-cli/
├── workflow_cli/           # Main package directory
│   ├── __init__.py        # Package initialization
│   ├── main.py            # CLI entry point and argument parsing
│   ├── workflow.py        # Workflow loading, validation, and execution
│   └── executor.py        # Step execution with retry and success validation
├── pyproject.toml         # Package configuration and dependencies
├── README.md              # User-facing documentation
├── ROADMAP.md             # Development roadmap and feature planning
├── CLAUDE.md              # This file - development notes
├── .gitignore             # Git exclusions
├── example_workflow.json  # Comprehensive example demonstrating all features
└── test_retry_workflow.json
```

## Key Components

### 1. CLI Interface (`main.py`)
- Entry point for the `workflow` command
- Handles argument parsing (`--help`, `--run`, `--version`)
- Creates WorkflowRunner and manages execution flow

### 2. Workflow Management (`workflow.py`)
- `WorkflowRunner` class for workflow orchestration
- JSON schema validation using jsonschema
- Memory/state management (currently basic, enhancement planned)
- Sequential step execution with error handling

### 3. Step Execution (`executor.py`) 
- `StepExecutor` class for individual command execution
- **Success validation**: Supports both regex patterns and JSON path validation
  - Regex: `"success": {"regex": "pattern"}` - matches against command output
  - JSON: `"success": {"json": "path.to.field"}` - validates JSON path exists
- **Memory updates**: Extract values from command output using regex or JSON
  - Regex: `"memory_update": [{"regex": "pattern", "variable": "memory.key"}]`
  - JSON: `"memory_update": [{"json": "path.to.value", "variable": "memory.key"}]`
- **Array index support**: JSON paths support array indices (e.g., `items.0`, `users.1.name`)
- Configurable retry mechanism with delays
- Timeout protection (5 minutes per step)
- Comprehensive error handling with try-catch blocks for JSON operations
- Output capture and display

## Development Workflow

### Roadmap Management

We use `ROADMAP.md` to track features and development progress:

1. **Feature Planning**: New features are added as `- [ ]` checkboxes
2. **Implementation**: During development, check off sub-tasks as completed
3. **Completion**: Mark main features as `- [x]` when fully implemented
4. **Version Planning**: Features are grouped into version milestones

#### Current Priority: Memory System Enhancement
The next major feature is enhancing the memory/state management system:
- Initialize workflow memory from JSON schema
- Allow CLI input of partial memory objects
- Update memory on successful step completion
- Persist memory changes between steps

### Testing Strategy

**Automated Testing with pytest:**
- Comprehensive test suite with 20+ tests covering all major functionality
- Unit tests for individual components (WorkflowRunner, StepExecutor)
- Integration tests for end-to-end workflow execution
- Test fixtures for workflow creation and validation

**Testing Commands:**
```bash
# Install in development mode with test dependencies
pip install -e .[test]

# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test categories
pytest tests/test_executor.py      # Step execution tests
pytest tests/test_workflow.py     # Workflow management tests
pytest tests/test_integration.py  # End-to-end tests

# Test comprehensive functionality (manual verification)
workflow -r example_workflow.json

# Test retry functionality (manual verification)
workflow -r test_retry_workflow.json
```

**Test Coverage:**
- JSON/regex success validation
- Memory updates with regex and JSON paths
- Variable substitution with `{{memory.key}}` patterns
- Array index support in JSON paths (`items.0.name`)
- Retry mechanisms and error handling
- Schema validation and file loading

### Example Workflow Maintenance

**`example_workflow.json`** serves as the comprehensive demonstration of all workflow features:

- **Purpose**: Showcase all current functionality in a single, realistic workflow
- **Content**: Demonstrates both regex and JSON parsing, memory management, success validation, retries, and variable substitution
- **Maintenance**: **IMPORTANT** - When adding new features to the workflow system, update this file to include examples of the new functionality
- **Testing**: This should be the primary test case for verifying that all features work together correctly

## Development Guidelines

### Adding New Features

1. **Update Roadmap**: Add or check off items in `ROADMAP.md`
2. **Schema Changes**: Update JSON schema in `workflow.py` if needed
3. **CLI Changes**: Modify argument parsing in `main.py` if adding CLI options
4. **Write Tests**: **REQUIRED** - Add pytest tests for new functionality
   - Unit tests in appropriate test files (`test_workflow.py`, `test_executor.py`)
   - Integration tests in `test_integration.py` for end-to-end features
   - Update fixtures in `conftest.py` if needed
5. **Update Example**: **REQUIRED** - Add examples of new features to `example_workflow.json`
6. **Testing**: Run `pytest` to verify all tests pass, including new functionality
7. **Documentation**: Update `README.md` for user-facing changes

### Code Organization

- **Keep separation of concerns**: CLI parsing, workflow management, and step execution are separate modules
- **Use type hints**: All functions should have proper type annotations
- **Error handling**: Comprehensive error handling with user-friendly messages
- **Logging**: Use print statements for user feedback, avoid excessive debug output

### Version Management

When updating version numbers, update all three locations:
1. `pyproject.toml` - `version = "x.y.z"` in the `[project]` section
2. `workflow_cli/__init__.py` - `__version__ = "x.y.z"`
3. `workflow_cli/main.py` - `version=f"%(prog)s x.y.z"` in the argument parser

After updating, reinstall with `pip install -e .` to see the changes.

### JSON Schema Evolution

When modifying the workflow JSON structure:
1. Update the schema in `WorkflowRunner.WORKFLOW_SCHEMA`
2. Ensure backward compatibility where possible
3. Create example workflows demonstrating new features
4. Update CLI help text if schema changes affect user experience

## Memory System Architecture (Planned)

The upcoming memory enhancement will:

```python
# Workflow JSON structure (enhanced)
{
    "name": "workflow_name",
    "memory": {
        "variables": {...},      # Runtime variables
        "schema": {...},         # JSON schema for validation
        "initial": {...}         # Default/initial values
    },
    "steps": [...]
}

# CLI usage (planned)
workflow -r workflow.json --memory '{"key": "value"}'
workflow -r workflow.json --memory-file memory.json
```

## Integration with Claude Code

### Useful Patterns

- **Batch tool calls**: Use multiple tools in single responses for efficiency
- **Todo tracking**: Use TodoWrite for complex multi-step implementations
- **File organization**: Prefer editing existing files over creating new ones
- **Testing**: Always test functionality after implementation

### Git Workflow

When asked to "commit" changes:
1. **Default behavior**: `git add .` → create appropriate commit message → `git push`
2. **Custom message**: If given a quoted string after "commit", use that exact string as the commit message
3. **Examples**:
   - `commit` → Auto-generated descriptive message
   - `commit "fix memory initialization bug"` → Use exact message provided

### Project-Specific Context

- This is a CLI tool, so user experience is important (clear error messages, helpful output)
- JSON schema validation is critical - malformed workflows should fail gracefully
- Retry mechanisms should be robust and not hang indefinitely
- Memory system is the next major architectural change

## Future Considerations

### Architectural Decisions Needed

1. **Memory Persistence**: How to persist memory between workflow runs?
2. **Plugin System**: Architecture for extending functionality?
3. **Parallel Execution**: How to handle step dependencies and parallel execution?
4. **Performance**: Optimization strategies for large workflows?

### Compatibility

- Maintain Python 3.8+ compatibility
- ⚠️ **POC Mode**: CLI interface and JSON schema may have breaking changes during rapid development
- Focus on innovation and experimentation over stability

---

## Quick Reference

**Install and test:**
```bash
pip install -e .
workflow -r example_workflow.json
```

**Add new feature:**
1. Check ROADMAP.md for context
2. Implement in appropriate module
3. Test with example workflows
4. Update documentation
5. Check off roadmap items

**Common files to modify:**
- `workflow_cli/main.py` - CLI interface changes
- `workflow_cli/workflow.py` - Schema or workflow logic changes  
- `workflow_cli/executor.py` - Step execution changes
- `ROADMAP.md` - Feature tracking
- `README.md` - User documentation
- remember to run pip install . to test