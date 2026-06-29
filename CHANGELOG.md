# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.1.0]

### Added

**External Pipeline Deployment Support**
* Support for external CodePipeline deployments with Accelerator Qualifier-based resource resolution
* Support for ECS container deployments (Fargate tasks triggered via SSM Automation)
* Automatic deployment type detection via SSM Parameter Store scanning — `checkAwsConnectivity` now reports deployment type and available qualifiers
* Qualifier-based S3 bucket resolution for external pipeline configuration storage (`{qualifier}-config-{account_id}-{region}`)
* Three new least-privilege IAM policies:
  - `standard-codepipeline-policy.json` — standard management account deployments
  - `external-codepipeline-policy.json` — external CodePipeline deployments
  - `external-ecs-container-policy.json` — external ECS container deployments

**CodeCommit Configuration Source**
* `getLzaConfiguration` and `putLzaConfiguration` automatically detect and use CodeCommit when the pipeline's source action is CodeCommit
* Explicit `repository_name` and `branch` parameters for direct CodeCommit targeting
* Single-commit write path (`CreateCommit`) for clean repository history
* No additional configuration required — auto-detection via `codepipeline:GetPipeline`

**Workspace Infrastructure**
* Isolated workspace-based file management replacing session-scoped temp directories
* Workspace tools: `createWorkspace`, `deleteWorkspace`, `writeWorkspaceFile`, `deleteWorkspaceFile`, `createWorkspaceFolder`, `deleteWorkspaceFolder`, `zipWorkspaceFiles`
* MCP resource handlers for workspace discovery (`workspace://list`, `workspace://{id}/files`, `workspace://{id}/file/{path}`)
* Pluggable storage adapter interface (local filesystem and S3 backends)
* Replaces legacy config file tools (`readLzaConfigFile`, `createLzaConfigFile`, `updateLzaConfigFile`) — use `writeWorkspaceFile` and `readResource` instead
* `listResources` and `readResource` fallback tools for MCP clients that don't support native resources (disable with `DISABLE_RESOURCE_TOOLS=true`)

**Pipeline Manual Approval**
* `submitManualApproval` tool to approve or reject pending CodePipeline Review stage gates
* `getDeploymentStatus` now detects pending approval actions and returns approval token, stage name, action name, and CDK diff context from CodeBuild logs
* Optional S3 diff retrieval for a planned future LZA feature (enable with `ENABLE_S3_DIFF=true`)

**LLM Guidance Toggle**
* `DISABLE_LLM_GUIDANCE` environment variable strips guidance keys (`llm_instructions`, `next_steps`, `hint`, `required_action`, `instructions_for_assistant`, `example`, `troubleshooting`, `usage_hint`) from all tool responses
* Also disables server-level `instructions` passed to FastMCP, returning an empty string
* Designed for deployments where an external orchestrator owns workflow logic

**Observability**
* User-agent instrumentation on all AWS API calls (`md/lza-mcp-server#1.1 md/tool#{toolName}`)

**Developer Experience**
* `make test-file FILE=tests/path/to/test.py` for targeted single-file test runs
* Configurable `LZA_PREFIX` environment variable for custom LZA resource naming

### Changed

* **Tool renames** (breaking for existing automation):
  | Old Name | New Name |
  |----------|----------|
  | `releasePipeline` | `startDeployment` |
  | `getPipelineStatus` | `getDeploymentStatus` |
  | `diagnosePipelineErrors` | `diagnoseDeploymentErrors` |
  | `uploadConfigurationToS3` | `putLzaConfiguration` |
  | `getConfigurationFromS3` | `getLzaConfiguration` |
* `getDeployedLzaVersion` rewritten to support both standard and qualifier-scoped SSM version parameters via deployment type detection
* `getMinimumConfiguration` now writes files into a workspace instead of a local directory (`save_to_directory` parameter removed, `workspace_id` added)
* UC merge workflow refactored to use workspace-based operations (`session_id` → `workspace_id`)
* `checkAwsConnectivity` now includes deployment type detection and qualifier enumeration in its response
* mypy type checking now runs in strict mode (previously used `--ignore-missing-imports --no-strict-optional`)
* Test coverage threshold increased from 59% to 97%
* Centralized input validation — `validate_qualifier`, `validate_aws_region`, `validate_pipeline_name` consolidated into `utils/input_validation.py`

### Fixed

* Sanitized user input echoed in error responses — prevents reflected XSS, log injection, and response splitting when responses traverse HTTP Streamable transport
* Removed internal container paths (`/app/...`) from error messages and troubleshooting guidance
* Removed AWS region, CLI command suggestions, and environment variable names from error responses (information disclosure)
* Sanitized environment expansion strings from pipeline/qualifier error messages
* Fixed EUSC (External Unified Service Client) connection error handling

### Security

* Comprehensive input sanitization across all tool error paths (5 separate security fixes)
* Centralized input validation module (`utils/input_validation.py`) consolidating scattered validators
* Workspace isolation narrows blast radius for file operations — prevents cross-session file access
* Path traversal validation in CodeCommit write path (`commit_files`)
* `pip-audit` CVE-2026-4539 suppression for pygments 2.19.2 (dev-only transitive dependency via pytest/rich, no fix available — tracked for removal once patched)

### Removed

* `readLzaConfigFile`, `createLzaConfigFile`, `updateLzaConfigFile` tools (superseded by workspace tools: `writeWorkspaceFile`, `readResource`)
* `readUcFile`, `updateUcFile` tools (superseded by workspace `readResource`/`writeWorkspaceFile`)
* `session_manager.py` (replaced by `workspace_manager.py`)
* `pipeline/validation.py` (consolidated into `utils/input_validation.py`)

#### Migration Guide (v1.0 → v1.1)

**Tool name changes** — update any scripts referencing the old names. Note: `autoApprove` lists are optional and nothing breaks if not updated — the old tool names simply won't match.

**Recommended `autoApprove` list** — all read-only tools that don't modify AWS resources or local state:

```json
{
  "autoApprove": [
    "checkAwsConnectivity",
    "getDeployedLzaVersion",
    "listLzaSupportedVersions",
    "searchJsonSchema",
    "getFullSchema",
    "getDeploymentStatus",
    "getLzaConfiguration",
    "getMinimumConfiguration",
    "listResources",
    "readResource"
  ]
}
```

**Configuration file editing** — use workspace tools instead of the removed config file tools:

```
1. getLzaConfiguration()          → extracts into workspace, returns workspace_id
2. readResource(uri)              → read files from workspace
3. writeWorkspaceFile(...)        → modify files in workspace
4. putLzaConfiguration(...)       → upload back to S3/CodeCommit
```

**External pipeline users** — run `checkAwsConnectivity` first to discover qualifiers, then pass `qualifier` to `getLzaConfiguration`, `putLzaConfiguration`, and `startDeployment`.

#### IAM Policy Updates

If upgrading from v1.0, update your IAM policy to the appropriate file in `iam-policies/`:

| Deployment Type | Policy File |
|----------------|-------------|
| Standard (management account) | `standard-codepipeline-policy.json` |
| External pipeline (CodePipeline) | `external-codepipeline-policy.json` |
| External pipeline (ECS container) | `external-ecs-container-policy.json` |

For manual approval support, add the supplementary `codepipeline:GetPipelineState` and `codepipeline:PutApprovalResult` permissions as documented in the README.

## [v1.0.0]

### Added
- Initial release of LZA MCP Server
- AWS connectivity verification tools
- Configuration management (generate, upload, retrieve)
- Pipeline management and monitoring
- Schema search and discovery for multiple LZA versions
- Universal Configuration merge workflow support
- Comprehensive security validation and input sanitization
- Container-based deployment with Docker/Finch support
- Support for IAM Identity Center (SSO) authentication
- Automated schema generation during build process

### Security
- Comprehensive input validation preventing injection attacks
- Container security hardening with read-only filesystem
- Least-privilege IAM policy recommendations
- SHA-256 schema integrity validation

## Release Notes
# ***Requires update***
For detailed release information, see the [GitHub Releases](https://github.com/awslabs/lza-mcp-server/releases) page.
