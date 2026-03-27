# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tool descriptions for pipeline MCP tools.

Each entry maps a tool name to its standard (guidance-enabled) and disable_guidance
(guidance-disabled) description strings. The manage module selects the
appropriate variant at registration time via tool_description().
"""

DESCRIPTIONS = {
    "startDeployment": {
        "standard": (
            "Start an LZA deployment — supports standard pipeline, external CodePipeline, and ECS container deployments. "
            "Call checkAwsConnectivity first to determine deployment type and qualifier. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier from checkAwsConnectivity. "
            "When a qualifier is provided, both CodePipeline ({qualifier}-pipeline) and "
            "SSM Automation ({qualifier}-RunEngine) are checked and started automatically."
        ),
        "disable_guidance": (
            "Start an LZA deployment — supports standard pipeline, external CodePipeline, and ECS container deployments. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier. "
            "When a qualifier is provided, both CodePipeline ({qualifier}-pipeline) and "
            "SSM Automation ({qualifier}-RunEngine) are checked and started automatically."
        ),
    },
    "getDeploymentStatus": {
        "standard": (
            "Get current deployment status and execution progress for LZA deployments. "
            "Returns a structured summary: deployment phase, stage progression, error detection, and the specific error message if failed. "
            "Use this as the primary tool for monitoring deployments and identifying failures. "
            "For standard CodePipeline deployments: returns stage-by-stage progress (current stage, completed stages, current action). "
            "For ECS container deployments: checks ECS task status first (detects PROVISIONING/PENDING states), "
            "then analyzes CloudWatch Logs for deployment phase, status, and errors. "
            "Does NOT return full deployment logs — use diagnoseDeploymentErrors for complete log output. "
            "Call checkAwsConnectivity first to determine deployment type and qualifier. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier from checkAwsConnectivity."
        ),
        "disable_guidance": (
            "Get current deployment status and execution progress for LZA deployments. "
            "Returns a structured summary: deployment phase, stage progression, error detection, and the specific error message if failed. "
            "For standard CodePipeline deployments: returns stage-by-stage progress (current stage, completed stages, current action). "
            "For ECS container deployments: checks ECS task status first (detects PROVISIONING/PENDING states), "
            "then analyzes CloudWatch Logs for deployment phase, status, and errors. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier."
        ),
    },
    "diagnoseDeploymentErrors": {
        "standard": (
            "Deep-dive diagnosis of failed LZA deployments with complete log output. "
            "Use after getDeploymentStatus confirms a failure and you need full context to understand root cause. "
            "For standard CodePipeline deployments: finds the most recent FAILED execution, identifies failed actions, "
            "retrieves CodeBuild logs, and extracts CloudFormation CREATE_FAILED errors with stack traces. "
            "For ECS container deployments: finds the most recent deployment log stream, paginates through all log events "
            "(up to 50,000), and returns the complete truncated deployment log alongside error extraction. "
            "Returns significantly more data than getDeploymentStatus — includes full deployment logs, rollback sequences, "
            "and complete error chains. "
            "IMPORTANT: For ECS deployments, this tool targets the most recent log stream by LastEventTime. "
            "Run this BEFORE starting a new deployment to ensure it captures the correct failure. "
            "Call checkAwsConnectivity first to determine deployment type and qualifier. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier from checkAwsConnectivity."
        ),
        "disable_guidance": (
            "Deep-dive diagnosis of failed LZA deployments with complete log output. "
            "For standard CodePipeline deployments: finds the most recent FAILED execution, identifies failed actions, "
            "retrieves CodeBuild logs, and extracts CloudFormation CREATE_FAILED errors with stack traces. "
            "For ECS container deployments: finds the most recent deployment log stream, paginates through all log events "
            "(up to 50,000), and returns the complete truncated deployment log alongside error extraction. "
            "Returns full deployment logs, rollback sequences, and complete error chains. "
            "For ECS deployments, targets the most recent log stream by LastEventTime. "
            "For standard deployments, omit the qualifier. "
            "For external pipeline deployments, pass the qualifier."
        ),
    },
}
