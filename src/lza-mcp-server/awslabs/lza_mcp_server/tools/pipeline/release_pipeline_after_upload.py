from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.constants import DEFAULT_PIPELINE_NAME
from awslabs.lza_mcp_server.orchestration.core.pipeline_release_manager import (
    PipelineReleaseManager,
)
from awslabs.lza_mcp_server.error_categories import ErrorCategory


async def tool_release_pipeline_after_upload(
    ctx: Context, pipeline_name: str = DEFAULT_PIPELINE_NAME
) -> Dict[str, Any]:
    """
    Release the LZA pipeline after successful configuration upload.

    This tool integrates with the existing releasePipeline functionality to provide
    a seamless workflow from configuration upload to pipeline deployment. It reuses
    all existing pipeline validation, error handling, and user confirmation patterns.

    Args:
        ctx: MCP context for logging and user feedback
        pipeline_name: Name of the CodePipeline to execute (defaults to "AWSAccelerator-Pipeline")

    Returns:
        Dict containing:
        - success: Boolean indicating if the pipeline release succeeded
        - execution_id: The unique ID of the started pipeline execution
        - pipeline_name: Name of the pipeline that was started
        - message: Success or error message
        - error: Error details if the operation failed
        - troubleshooting: List of troubleshooting steps if there was an error

    Requirements Addressed:
        - 1.3: Pipeline release functionality after successful upload

    Example Usage:
        # Release default pipeline
        result = await release_pipeline_after_upload(ctx)

        # Release specific pipeline
        result = await release_pipeline_after_upload(ctx, "MyCustomPipeline")
    """
    try:
        # Initialize the pipeline release manager
        pipeline_manager = PipelineReleaseManager()

        # Execute pipeline release with user confirmation workflow
        result = await pipeline_manager.release_pipeline_with_confirmation(
            ctx=ctx, pipeline_name=pipeline_name
        )

        # Log the final result
        if result["success"]:
            await ctx.info(
                f"Pipeline '{pipeline_name}' released successfully: {result.get('execution_id', 'N/A')}"
            )
        else:
            await ctx.error(
                f"Pipeline release failed: {result.get('error', 'Unknown error')}"
            )

        return result

    except Exception as e:
        error_message = f"Unexpected error in releasePipelineAfterUpload: {str(e)}"
        await ctx.error(error_message)

        # Create structured error response for unexpected errors
        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="UNEXPECTED_PIPELINE_ERROR",
            troubleshooting=[
                "Check AWS credentials configuration",
                "Verify the pipeline name is correct",
                "Ensure you have CodePipeline permissions",
                "Check that the pipeline exists in your AWS region",
                "Review application logs for more details",
            ],
            context={
                "tool": "releasePipelineAfterUpload",
                "pipeline_name": pipeline_name,
                "error_type": type(e).__name__,
            },
            operation="pipeline_release",
        )
