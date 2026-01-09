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

"""Property-based tests for next_steps inclusion in UC merge tools.

Feature: uc-merge, Property 30: Universal next_steps inclusion
Validates: Requirements 10.1

This test file verifies that ALL UC merge tools include a next_steps field
in their responses, regardless of success or failure. This ensures consistent
workflow guidance for agents using these tools.
"""

import pytest
import os
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st, settings, HealthCheck

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_releases import tool_get_uc_releases
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_models import (
    tool_get_uc_network_models,
)
from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)
from awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file import (
    read_lza_config_file,
)
from awslabs.lza_mcp_server.tools.uc_merge.read_uc_file import read_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.update_uc_file import update_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    get_uc_network_customization_guide,
)
from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.fixture
def temp_uc_structure(tmp_path):
    """Create a temporary UC repository structure."""
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    # Create a release directory
    release_dir = uc_base / "v1.0.0"
    release_dir.mkdir()

    # Create network model directories
    hub_spoke = release_dir / "hub-and-spoke"
    hub_spoke.mkdir()

    shared_vpc = release_dir / "shared-vpc"
    shared_vpc.mkdir()

    # Create some config files
    (hub_spoke / "accounts-config.yaml").write_text("test: config")
    (hub_spoke / "replacements-config.yaml").write_text("test: replacements")

    return uc_base


@pytest.fixture
def temp_lza_config(tmp_path):
    """Create a temporary LZA config directory."""
    lza_config = tmp_path / "lza-config"
    lza_config.mkdir(exist_ok=True)

    # Create a retrieved config directory
    retrieved = lza_config / "retrieved-config"
    retrieved.mkdir(exist_ok=True)

    # Create some config files
    (retrieved / "accounts-config.yaml").write_text("test: lza-config")
    (retrieved / "global-config.yaml").write_text("homeRegion: us-east-1")

    return retrieved


@pytest.fixture
def temp_session(tmp_path):
    """Create a temporary session directory."""
    session_dir = tmp_path / "lza-config" / "uc-session-test"
    session_dir.mkdir(parents=True)

    # Create session metadata
    import json

    metadata = {
        "session_id": "uc-session-test",
        "network_model": "hub-and-spoke",
        "uc_release": "v1.0.0",
        "created_at": "2025-01-27T14:30:22",
    }
    (session_dir / ".session_metadata.json").write_text(json.dumps(metadata))

    # Create some config files
    (session_dir / "accounts-config.yaml").write_text("test: session-config")
    (session_dir / "replacements-config.yaml").write_text("test: session-replacements")

    return session_dir


# Feature: uc-merge, Property 30: Universal next_steps inclusion
# Validates: Requirements 10.1
@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    # Generate various scenarios that might trigger different code paths
    scenario=st.sampled_from(["success", "not_found"])
)
async def test_property_get_uc_releases_includes_next_steps(
    mock_ctx, temp_uc_structure, scenario
):
    """Property: get_uc_releases always includes next_steps in response."""
    import os
    import shutil

    # Set environment variable to point to temp structure
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        if scenario == "not_found":
            # Make the directory not exist
            shutil.rmtree(temp_uc_structure)

        result = await tool_get_uc_releases(mock_ctx)

        # Property: All responses must include next_steps
        assert "next_steps" in result, (
            "get_uc_releases response missing next_steps field"
        )
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    uc_release=st.one_of(
        st.just("v1.0.0"),  # Valid
        st.just(""),  # Missing
        st.just("invalid"),  # Invalid format
        st.just("v99.99.99"),  # Not found
    )
)
async def test_property_get_uc_network_models_includes_next_steps(
    mock_ctx, temp_uc_structure, uc_release
):
    """Property: get_uc_network_models always includes next_steps in response."""
    # Set environment variable to point to temp structure
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        result = await tool_get_uc_network_models(mock_ctx, uc_release)

        # Property: All responses must include next_steps
        assert "next_steps" in result, (
            "get_uc_network_models response missing next_steps field"
        )
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    uc_release=st.one_of(
        st.just("v1.0.0"),  # Valid
        st.just(""),  # Missing
        st.just("invalid"),  # Invalid
    ),
    network_model=st.one_of(
        st.just("hub-and-spoke"),  # Valid
        st.just(""),  # Missing
        st.just("nonexistent"),  # Not found
    ),
)
async def test_property_start_uc_merge_session_includes_next_steps(
    mock_ctx, temp_uc_structure, uc_release, network_model
):
    """Property: start_uc_merge_session always includes next_steps in response."""
    with patch(
        "awslabs.lza_mcp_server.tools.uc_merge.common.UC_BASE_PATH", temp_uc_structure
    ):
        with patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release:
            with patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
            ) as mock_model:
                # Set up paths
                if uc_release == "v1.0.0":
                    mock_release.return_value = temp_uc_structure / uc_release
                else:
                    mock_release.return_value = temp_uc_structure / "nonexistent"

                if network_model == "hub-and-spoke":
                    mock_model.return_value = (
                        temp_uc_structure / "v1.0.0" / network_model
                    )
                else:
                    mock_model.return_value = (
                        temp_uc_structure / "v1.0.0" / "nonexistent"
                    )

                result = await tool_start_uc_merge_session(
                    mock_ctx, uc_release, network_model
                )

                # Property: All responses must include next_steps
                assert "next_steps" in result, (
                    "start_uc_merge_session response missing next_steps field"
                )
                assert isinstance(result["next_steps"], str), (
                    "next_steps must be a string"
                )
                assert len(result["next_steps"]) > 0, "next_steps must not be empty"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    file_path=st.one_of(
        st.just("accounts-config.yaml"),  # Valid
        st.just(""),  # Missing
        st.just("../etc/passwd"),  # Path traversal
        st.just("nonexistent.yaml"),  # Not found
    )
)
async def test_property_read_lza_config_file_includes_next_steps(
    mock_ctx, temp_lza_config, file_path
):
    """Property: read_lza_config_file always includes next_steps in response."""
    with patch(
        "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.LZA_CONFIG_BASE_PATH",
        temp_lza_config.parent,
    ):
        result = await read_lza_config_file(mock_ctx, file_path)

        # Property: All responses must include next_steps
        assert "next_steps" in result, (
            "read_lza_config_file response missing next_steps field"
        )
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    session_id=st.one_of(
        st.just("uc-session-test"),  # Valid
        st.just(""),  # Missing
        st.just("invalid-session"),  # Not found
    ),
    file_path=st.one_of(
        st.just("accounts-config.yaml"),  # Valid
        st.just(""),  # Missing
        st.just("../etc/passwd"),  # Path traversal
        st.just("nonexistent.yaml"),  # Not found
    ),
)
async def test_property_read_uc_file_includes_next_steps(
    mock_ctx, temp_session, session_id, file_path
):
    """Property: read_uc_file always includes next_steps in response."""
    with patch.dict(os.environ, {"LZA_CONFIG_BASE_PATH": str(temp_session.parent)}):
        result = await read_uc_file(mock_ctx, session_id, file_path)

        # Property: All responses must include next_steps
        assert "next_steps" in result, "read_uc_file response missing next_steps field"
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    session_id=st.one_of(
        st.just("uc-session-test"),  # Valid
        st.just(""),  # Missing
        st.just("invalid-session"),  # Not found
    ),
    file_path=st.one_of(
        st.just("replacements-config.yaml"),  # Valid
        st.just(""),  # Missing
        st.just("nonexistent.yaml"),  # Not found
    ),
    updates=st.one_of(
        st.just({"HomeRegionIngressCidr": "10.0.0.0/16"}),  # Valid
        st.just({}),  # Empty
        st.just({"InvalidCidr": "not-a-cidr"}),  # Invalid value
    ),
)
async def test_property_update_uc_file_includes_next_steps(
    mock_ctx, temp_session, session_id, file_path, updates
):
    """Property: update_uc_file always includes next_steps in response."""
    with patch.dict(os.environ, {"LZA_CONFIG_BASE_PATH": str(temp_session.parent)}):
        result = await update_uc_file(session_id, file_path, updates)

        # Property: All responses must include next_steps
        assert "next_steps" in result, (
            "update_uc_file response missing next_steps field"
        )
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    session_id=st.one_of(
        st.just("uc-session-test"),  # Valid
        st.just(""),  # Missing
        st.just("invalid-session"),  # Not found
    )
)
async def test_property_get_uc_network_customization_guide_includes_next_steps(
    mock_ctx, temp_session, session_id
):
    """Property: get_uc_network_customization_guide always includes next_steps in response."""
    with patch.dict(os.environ, {"LZA_CONFIG_BASE_PATH": str(temp_session.parent)}):
        result = get_uc_network_customization_guide(session_id)

        # Property: All responses must include next_steps
        assert "next_steps" in result, (
            "get_uc_network_customization_guide response missing next_steps field"
        )
        assert isinstance(result["next_steps"], str), "next_steps must be a string"
        assert len(result["next_steps"]) > 0, "next_steps must not be empty"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    session_id=st.one_of(
        st.just("uc-session-test"),  # Valid
        st.just(""),  # Missing
        st.just("invalid-session"),  # Not found
    )
)
async def test_property_copy_uc_to_lza_config_includes_next_steps(
    mock_ctx, temp_session, temp_lza_config, session_id
):
    """Property: copy_uc_to_lza_config always includes next_steps in response."""
    with patch.dict(os.environ, {"LZA_CONFIG_BASE_PATH": str(temp_session.parent)}):
        with patch(
            "awslabs.lza_mcp_server.tools.uc_merge.common.LZA_CONFIG_BASE_PATH",
            temp_lza_config.parent,
        ):
            result = await copy_uc_to_lza_config(mock_ctx, session_id)

            # Property: All responses must include next_steps
            assert "next_steps" in result, (
                "copy_uc_to_lza_config response missing next_steps field"
            )
            assert isinstance(result["next_steps"], str), "next_steps must be a string"
            assert len(result["next_steps"]) > 0, "next_steps must not be empty"


# Additional test: Verify next_steps provides meaningful guidance
@pytest.mark.unit
@pytest.mark.asyncio
async def test_next_steps_provides_meaningful_guidance(mock_ctx, temp_uc_structure):
    """Verify that next_steps contains actionable guidance, not just placeholder text."""
    # Set environment variable to point to temp structure
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        result = await tool_get_uc_releases(mock_ctx)

        next_steps = result["next_steps"]

        # Check for meaningful content (not just "next steps" or empty)
        assert len(next_steps) > 20, "next_steps should contain substantial guidance"

        # Should mention what to do next
        assert any(
            word in next_steps.lower()
            for word in ["call", "present", "select", "retry", "contact"]
        ), "next_steps should contain actionable verbs"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]


# Test that error responses also include next_steps
@pytest.mark.unit
@pytest.mark.asyncio
async def test_error_responses_include_next_steps(mock_ctx):
    """Verify that error responses also include next_steps for recovery guidance."""
    # Test with missing parameter
    result = await tool_get_uc_network_models(mock_ctx, "")

    assert result["success"] is False, "Should be an error response"
    assert "next_steps" in result, "Error responses must include next_steps"
    assert isinstance(result["next_steps"], str), "next_steps must be a string"
    assert len(result["next_steps"]) > 0, "next_steps must not be empty"

    # next_steps should provide recovery guidance
    assert "get_uc_releases" in result["next_steps"], (
        "Error next_steps should guide user to correct action"
    )
