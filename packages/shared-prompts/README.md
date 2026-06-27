# Shared Prompts Package

This package manages the system prompts, guidelines, and agent instructions.

## Directory Structure
- `/templates`: Contains raw Markdown files representing the system instructions for each of the 12 agents.
- `/utils`: Helper tools for dynamic context injection and placeholder replacement.

## Prompt Lifecycle
- **Version Control**: Changes to system prompts undergo pull request review before merging.
- **Dynamic Context**: System prompts load templates and inject active user requirements, code file trees, database schemas, and current trace reports.
