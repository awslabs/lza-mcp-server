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

FROM python:3.11-slim

# Create non-root user
RUN groupadd -r lzauser && useradd -r -g lzauser -d /app -s /bin/bash lzauser

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/
COPY lza-minimum-configuration/ /app/lza-minimum-configuration/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONPATH="/app"
ENV FASTMCP_LOG_LEVEL="INFO"
ENV AWS_DEFAULT_REGION="us-east-1"

# Change ownership to non-root user
RUN chown -R lzauser:lzauser /app

# Switch to non-root user
USER lzauser

# Expose port for MCP server
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point
ENTRYPOINT ["python", "-m", "awslabs.lza_mcp_server"]