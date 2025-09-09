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

FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy project files
COPY . ${LAMBDA_TASK_ROOT}/
COPY lza-minimum-configuration/ ${LAMBDA_TASK_ROOT}/lza-minimum-configuration/
COPY json-output/ ${LAMBDA_TASK_ROOT}/json-output/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}"
ENV FASTMCP_LOG_LEVEL="INFO"
ENV AWS_DEFAULT_REGION="us-east-1"

# Expose port for MCP server
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point
ENTRYPOINT ["python", "-m", "awslabs.lza_mcp_server"]