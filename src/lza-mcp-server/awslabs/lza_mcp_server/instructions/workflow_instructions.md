
## Typical Workflows

### Deployment Workflow
1. Check AWS connectivity with `checkAwsConnectivity`
2. Generate configuration with `getMinimumConfiguration`
3. Upload to S3 with `putLzaConfiguration`
4. Deploy with `startDeployment`
5. Monitor with `getDeploymentStatus`
6. If `getDeploymentStatus` returns `approval_pending: true`, review the `review_diff` and use `submitManualApproval` with the returned `approval_token`, `approval_stage_name`, and `approval_action_name` to approve or reject

### Schema Query Workflow
When working with LZA schemas, use this recommended workflow:
1. Call `getDeployedLzaVersion` to get the currently deployed LZA version
2. Use the returned version as the `lza_version` parameter in `searchJsonSchema` or `getFullSchema`
3. This ensures schema queries match your deployed environment

Alternatively, use `listLzaSupportedVersions` to see all available schema versions.

### UC Merge Workflow
1. `getLzaConfiguration` — retrieve LZA config into a workspace (returns workspace_id)
2. `validateLzaForUcMerge(workspace_id)` — verify the installation is fresh
3. `get_uc_releases` — discover available UC versions
4. `get_uc_network_models` — select a network model
5. `start_uc_merge_session` — create a UC workspace (returns workspace_id)
6. Customize via `readResource` / `writeWorkspaceFile` on the UC workspace
7. `copyUcToLzaConfig(uc_workspace_id, lza_workspace_id)` — merge UC into LZA workspace
8. `putLzaConfiguration` — upload the merged configuration

For detailed usage instructions, see the individual tool documentation.
