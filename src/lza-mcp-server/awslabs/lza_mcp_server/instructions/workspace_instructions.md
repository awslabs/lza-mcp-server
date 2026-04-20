

## Workspaces

Workspaces provide isolated virtual filesystems for working with files. Each workspace has a unique ID and acts as a sandboxed directory where you can create, read, update, and delete files and folders.

Use workspaces to:
- Store and manipulate LZA configuration files retrieved from S3
- Extract templates into a clean working area
- Prepare configuration changes before uploading them back
- Keep multiple configuration variants separate

Workspace tools: `createWorkspace`, `deleteWorkspace`, `writeWorkspaceFile`, `deleteWorkspaceFile`, `createWorkspaceFolder`, `deleteWorkspaceFolder`, `zipWorkspaceFiles`.

UC merge sessions also use workspaces. The `start_uc_merge_session` tool creates a workspace for UC configuration files, and `copyUcToLzaConfig` merges between UC and LZA workspaces.
