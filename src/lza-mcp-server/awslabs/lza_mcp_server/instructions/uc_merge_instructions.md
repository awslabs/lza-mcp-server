
### UC Merge Tools (Universal Configuration)
- **validateLzaForUcMerge**: Validate LZA installation compatibility with UC merge (requires workspace_id from getLzaConfiguration)
- **get_uc_releases**: Discover available UC release versions
- **get_uc_network_models**: Get network deployment model comparison
- **start_uc_merge_session**: Initialize a UC merge session (returns workspace_id)
- **getUcNetworkCustomizationGuide**: Get customization guidance (requires workspace_id from start_uc_merge_session)
- **copyUcToLzaConfig**: Copy UC configuration from UC workspace to LZA workspace (requires uc_workspace_id and lza_workspace_id)

Use **readResource** and **writeWorkspaceFile** to read and modify UC configuration files within the workspace.
