# MADA – MuleSoft AI Developer Assistant

## Overview

MADA (MuleSoft AI Developer Assistant) is an AI-powered development assistant designed to help MuleSoft developers understand, analyze, debug, design and develop MuleSoft applications.

The goal of MADA is to simplify MuleSoft development by combining AI capabilities with static code analysis, project context understanding, runtime log analysis and controlled code generation.

MADA is being developed as an Eclipse-based plugin that can integrate with Anypoint Studio, supported by a Python AI backend.

## Vision

Build an intelligent MuleSoft development assistant that can:

- Read and understand existing MuleSoft projects.
- Identify potential errors, configuration issues and code-quality problems.
- Analyze Mule runtime logs and assist with debugging.
- Explain Mule flows, connectors, DataWeave and error handling.
- Understand new project requirements written in natural language.
- Propose API-led architecture and implementation plans.
- Generate Mule XML, RAML, DataWeave and configuration files.
- Ask for developer approval before creating or modifying project files.
- Validate generated applications through Maven and MUnit.

## Architecture

MADA consists of the following major components:

1. **Eclipse Plugin:** Developer-facing interface integrated with the Eclipse ecosystem.
2. **Python Backend:** Handles API requests, AI providers and application services.
3. **AI Orchestrator:** Understands developer requests and coordinates specialized agents.
4. **Analysis Agents:** Inspect Mule XML, connectors, DataWeave and error handling.
5. **Debugging Agents:** Analyze runtime logs and identify potential root causes.
6. **Code Generation Agents:** Generate MuleSoft implementation artifacts.
7. **Controlled Tool Layer:** Provides safe project scanning, file generation, validation and testing.

## Technology Stack

| Technology | Purpose |
|---|---|
| Java | Eclipse plugin development |
| Eclipse PDE | Plugin development framework |
| SWT / JFace | Desktop user interface |
| Python | AI backend |
| XML / ElementTree | Mule XML parsing |
| DataWeave | MuleSoft data transformation |
| Ollama | Local AI model integration |
| Groq / Gemini / Hugging Face | Cloud AI provider integrations |
| Maven | Mule project build and validation |
| MUnit | Mule application testing |
| Git / GitHub | Version control |

## Current Features

- AI provider selection and configuration.
- Chat-based MuleSoft assistance.
- MuleSoft-specific system prompt.
- Existing Eclipse project scanning.
- Project-aware AI conversations.
- Mule XML static analysis.
- Flow and subflow analysis.
- Connector analysis.
- DataWeave analysis.
- Error handling analysis.
- Unified Mule project analysis.
- Markdown analysis report generation.
- AI-powered analysis explanations.
- Analysis report saving.

## Development Progress

| Phase | Feature | Status |
|---|---|---|
| 1 | Python backend and AI provider integration | Completed |
| 2 | Eclipse plugin and chat interface | Completed |
| 3 | Project scanning and project-aware chat | Completed |
| 4 | Mule XML and project static analysis | Completed |
| 5 | AI-powered project analysis explanation | Completed |
| 6 | Evidence-based issue detection | Planned |
| 7 | Mule runtime log analysis and debugging | Planned |
| 8 | Natural-language requirement understanding | Planned |
| 9 | Architecture and implementation planning | Planned |
| 10 | Approval-based Mule project generation | Planned |
| 11 | Maven and MUnit validation | Planned |
| 12 | Anypoint Platform integration | Planned |

## Development Principles

- Follow Mule 4 and MuleSoft development standards.
- Prefer official MuleSoft documentation for technical guidance.
- Clearly distinguish static warnings from confirmed runtime failures.
- Protect credentials and sensitive project information.
- Require developer approval before modifying project files.
- Maintain backups and reviewable changes.
- Require separate approval for deployment.
- Keep the architecture modular and extensible.

## Project Status

**Development stage:** Active development

MADA is currently in its early development stage. Core backend services, Eclipse plugin integration, project scanning and initial AI-powered analysis capabilities have been implemented and tested.

## Future Goal

Create an intelligent MuleSoft development environment where developers can describe requirements in natural language, understand existing applications, troubleshoot errors and generate MuleSoft implementations with developer-controlled approval.
