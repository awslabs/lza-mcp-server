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

# ============================================
# STAGE 1: Builder - Full OS with build tools
# ============================================
FROM public.ecr.aws/docker/library/python:3.11-slim AS builder

# Build arguments for LZA release versions
ARG LZA_MIN_VERSION="v1.12.0"
ARG LZA_MAX_VERSION=""
ARG LZA_REPO_URL="https://github.com/awslabs/landing-zone-accelerator-on-aws.git"

# Build arguments for LZA Universal Configuration
ARG LZA_UC_RELEASE=""
ARG LZA_UC_REPO_URL="https://github.com/aws/lza-universal-configuration.git"

# Set environment variables for build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH="/build"

# Set shell with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set working directory
WORKDIR /build

# Install build-time packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    unzip \
    zip \
    ca-certificates \
    jq && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /build/

# Explicitly copy lza-minimum-configuration directory
COPY lza-minimum-configuration/ /build/lza-minimum-configuration/

# Install the runtime dependencies pinned in poetry.lock, with hashes, so the
# image ships the same versions CI tests. Poetry is used only to export the
# lock and is not copied into the runtime stage. Keep POETRY_VERSION in step
# with .gitlab-ci.yml and .github/workflows/ci.yml.
ARG POETRY_VERSION="2.5.1"
ARG POETRY_PLUGIN_EXPORT_VERSION="1.10.1"
RUN pip install --no-cache-dir --upgrade pip && \
    python -m venv /opt/poetry && \
    /opt/poetry/bin/pip install --no-cache-dir \
      "poetry==${POETRY_VERSION}" "poetry-plugin-export==${POETRY_PLUGIN_EXPORT_VERSION}" && \
    /opt/poetry/bin/poetry check --lock && \
    /opt/poetry/bin/poetry export --only main --format requirements.txt --output /tmp/requirements.txt && \
    pip install --no-cache-dir --require-hashes --target /build/deps -r /tmp/requirements.txt && \
    rm -rf /opt/poetry /tmp/requirements.txt

# Install the application package
RUN pip install --no-cache-dir --target /build/deps --no-deps -e .

# Download and process multiple LZA releases for schema generation
# Note: The script expects to run from /app, so we need to adjust paths or run from there
RUN chmod +x /build/docker-json-schema.sh && \
    chmod +x /build/download-lza-versions.sh && \
    chmod +x /build/generate-schema-checksums.sh && \
    cd /build && \
    # Create symlink so script's /app paths work from /build
    ln -s /build /app && \
    /build/download-lza-versions.sh "$LZA_MIN_VERSION" "$LZA_MAX_VERSION" "$LZA_REPO_URL" && \
    # Generate checksums for schema integrity validation
    /build/generate-schema-checksums.sh /app/json-schemas /app/json-schemas/checksums.sha256

# Download and extract LZA Universal Configuration release artifacts
# Note: Script expects /app paths, use symlink approach
RUN ln -s /build /app && \
    mkdir -p /build/lza-uc && \
    if [ -z "$LZA_UC_RELEASE" ]; then \
      echo "No LZA_UC_RELEASE specified, fetching latest release..." && \
      LZA_UC_RELEASE=$(curl -s https://api.github.com/repos/aws/lza-universal-configuration/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/') && \
      echo "Using latest UC release: $LZA_UC_RELEASE"; \
    else \
      echo "Using specified LZA UC release: $LZA_UC_RELEASE"; \
    fi && \
    # Create version directory
    mkdir -p "/build/lza-uc/$LZA_UC_RELEASE" && \
    # Download all ZIP artifacts from the release
    echo "Downloading Universal Configuration artifacts for $LZA_UC_RELEASE..." && \
    DOWNLOAD_URLS=$(curl -s "https://api.github.com/repos/aws/lza-universal-configuration/releases/tags/$LZA_UC_RELEASE" | grep '"browser_download_url":.*\.zip"' | sed 's/.*"browser_download_url": "\(.*\)".*/\1/') && \
    if [ -z "$DOWNLOAD_URLS" ]; then \
      echo "Error: No ZIP files found in release $LZA_UC_RELEASE" >&2 && \
      exit 1; \
    fi && \
    for URL in $DOWNLOAD_URLS; do \
      FILENAME=$(basename "$URL") && \
      CONFIG_NAME=$(echo "$FILENAME" | sed -E 's/lza-universal-config-(.*)-(v[0-9]+\.[0-9]+\.[0-9]+)\.zip/\1/') && \
      echo "Downloading $FILENAME..." && \
      curl -sL "$URL" -o "/tmp/$FILENAME" && \
      echo "Extracting to /build/lza-uc/$LZA_UC_RELEASE/$CONFIG_NAME..." && \
      mkdir -p "/build/lza-uc/$LZA_UC_RELEASE/$CONFIG_NAME" && \
      unzip -q "/tmp/$FILENAME" -d "/tmp/extract" && \
      if [ -d "/tmp/extract/config" ]; then \
        mv /tmp/extract/config/* "/build/lza-uc/$LZA_UC_RELEASE/$CONFIG_NAME/"; \
      else \
        mv /tmp/extract/* "/build/lza-uc/$LZA_UC_RELEASE/$CONFIG_NAME/"; \
      fi && \
      rm -rf /tmp/extract "/tmp/$FILENAME"; \
    done && \
    echo "Universal Configuration artifacts extracted successfully" && \
    # Download source code and extract docs folder
    echo "Downloading source code for documentation..." && \
    SOURCE_URL="https://github.com/aws/lza-universal-configuration/archive/refs/tags/$LZA_UC_RELEASE.zip" && \
    curl -sL "$SOURCE_URL" -o "/tmp/source.zip" && \
    unzip -q "/tmp/source.zip" -d "/tmp/source" && \
    SOURCE_DIR=$(find /tmp/source -maxdepth 1 -type d -name "lza-universal-configuration-*" | head -1) && \
    if [ -d "$SOURCE_DIR/docs" ]; then \
      echo "Extracting docs to /build/lza-uc/$LZA_UC_RELEASE/docs..." && \
      mv "$SOURCE_DIR/docs" "/build/lza-uc/$LZA_UC_RELEASE/docs"; \
    else \
      echo "Warning: No docs directory found in source archive"; \
    fi && \
    rm -rf /tmp/source "/tmp/source.zip"

# Clean up temporary files but keep /app symlink for COPY in next stage
RUN rm -rf /build/lza-temp

# Create writable directory for runtime operations with proper ownership
# This will be copied to the distroless stage
RUN mkdir -p /build/lza-config && chmod 755 /build/lza-config

# ============================================
# STAGE 2: Runtime - Distroless (minimal attack surface)
# ============================================
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set environment variables
ENV PYTHONPATH="/app:/app/deps"
ENV FASTMCP_LOG_LEVEL="INFO"
ENV AWS_DEFAULT_REGION="us-east-1"
ENV LZA_MIN_CONFIG_DIR="/app/lza-minimum-configuration"
ENV WORKSPACE_DIR="/tmp/workspaces"

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /build/deps /app/deps

# Copy application code from builder
COPY --from=builder /build/awslabs /app/awslabs

# Copy json-schema utilities (needed for schema search functionality)
COPY --from=builder /build/json-schema /app/json-schema

# Copy static resources from builder (note: scripts create in /app via symlink)
COPY --from=builder /app/json-schemas /app/json-schemas
COPY --from=builder /build/lza-minimum-configuration /app/lza-minimum-configuration
COPY --from=builder /build/lza-uc /app/lza-uc

# Copy writable directory for runtime operations (config extraction and UC sessions)
# Note: distroless runs as nonroot user (uid=65532) by default
COPY --from=builder --chown=65532:65532 /build/lza-config /app/lza-config

# Expose port for MCP server
EXPOSE 8000

# Entry point (no shell available in distroless)
ENTRYPOINT ["python", "-m", "awslabs.lza_mcp_server"]
