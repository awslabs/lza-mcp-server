
## Typical Workflows

### Deployment Workflow
1. Check AWS connectivity with `checkAwsConnectivity`
2. Generate configuration with `getMinimumConfiguration`
3. Upload to S3 with `putLzaConfiguration`
4. Deploy with `startDeployment`
5. Monitor with `getDeploymentStatus`

### Schema Query Workflow
When working with LZA schemas, use this recommended workflow:
1. Call `getDeployedLzaVersion` to get the currently deployed LZA version
2. Use the returned version as the `lza_version` parameter in `searchJsonSchema` or `getFullSchema`
3. This ensures schema queries match your deployed environment

Alternatively, use `listLzaSupportedVersions` to see all available schema versions.

For detailed usage instructions, see the individual tool documentation.
