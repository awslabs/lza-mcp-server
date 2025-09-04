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

"""Integration tests for validation tools."""

import pytest
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.tools.validation import register_validation_tools
from awslabs.lza_mcp_server.tools.validation.common import validate_configuration_impl
from awslabs.lza_mcp_server.tools.validation.validation_configuration_s3 import (
    tool_validate_configuration_from_s3,
)
from awslabs.lza_mcp_server.tools.validation.validate_configuration_share import (
    tool_validate_configuration_from_share,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class MockSTSClient:
    """Mock STS client for testing."""

    def __init__(self, account_id="123456789012"):
        self.account_id = account_id

    def get_caller_identity(self):
        return {"Account": self.account_id}


class TestValidationToolsIntegration:
    """Integration tests for validation tools."""

    def test_complete_tool_registration(self):
        """Test that all validation tools are properly registered."""
        mock_mcp = Mock()

        register_validation_tools(mock_mcp)

        # Verify all expected tools are registered
        assert mock_mcp.tool.call_count == 3

        tool_calls = mock_mcp.tool.call_args_list
        tool_names = [call[1]["name"] for call in tool_calls]

        expected_tools = [
            "validateConfigurationFromS3",
            "validateConfigurationFromShare",
            "cleanupValidationZip",
        ]

        for tool in expected_tools:
            assert tool in tool_names

    def test_create_complete_lza_configuration(self):
        """Test validation with complete LZA configuration structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complete LZA configuration structure
            (temp_path / "accounts-config.yaml").write_text("""
mandatoryAccounts:
  - name: Management
    description: Management account
    email: management@example.com
    organizationalUnit: Root
""")

            (temp_path / "global-config.yaml").write_text("""
homeRegion: us-east-1
enabledRegions:
  - us-east-1
managementAccountAccessRole: AWSControlTowerExecution
""")

            (temp_path / "organization-config.yaml").write_text("""
enable: true
organizationalUnits:
  - name: Root
    accounts:
      - Management
""")

            # Create subdirectories with policies
            policies_dir = temp_path / "iam-policies"
            policies_dir.mkdir()
            (policies_dir / "sample-policy.json").write_text(
                '{"Version": "2012-10-17"}'
            )

            result = validate_configuration_impl(str(temp_path), _test_mode=False)

            assert result["valid"] is True
            assert result["message"] == "Configuration validation successful"

    @pytest.mark.asyncio
    async def test_end_to_end_s3_validation_workflow(self):
        """Test complete S3 validation workflow."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a complete LZA configuration ZIP
            zip_path = os.path.join(temp_dir, "config.zip")

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("accounts-config.yaml", "mandatoryAccounts: []")
                zf.writestr("global-config.yaml", "homeRegion: us-east-1")
                zf.writestr("organization-config.yaml", "enable: true")
                zf.writestr("iam-policies/policy.json", '{"Version": "2012-10-17"}')

            def mock_download(bucket, key, local_path):
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                    side_effect=mock_download,
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/config.zip"
                )

                assert result["valid"] is True
                assert "s3_upload_integration" in result

                # Verify context interactions
                mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_end_to_end_share_validation_workflow(self):
        """Test complete share validation workflow."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ZIP file in temp directory
            zip_path = os.path.join(temp_dir, "config.zip")

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("accounts-config.yaml", "mandatoryAccounts: []")
                zf.writestr("global-config.yaml", "homeRegion: us-east-1")
                zf.writestr("organization-config.yaml", "enable: true")

            mock_sts_client = MockSTSClient()

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
                ) as mock_session,
                patch.dict(os.environ, {"LZA_CONFIG_CONTAINER_PATH": temp_dir}),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_session_obj = Mock()
                mock_session_obj.client.return_value = mock_sts_client
                mock_session.return_value = mock_session_obj

                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_share(mock_ctx)

                assert result["valid"] is True
                assert "steps_completed" in result
                assert "validation_completed" in result["steps_completed"]

    def test_validation_error_handling_consistency(self):
        """Test that error handling is consistent across validation functions."""
        # Test with invalid YAML in all validation paths
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid YAML file
            (temp_path / "invalid.yaml").write_text("key: value\n  invalid: yaml")

            result = validate_configuration_impl(str(temp_path), _test_mode=True)

            # Verify error structure is consistent
            assert result["valid"] is False
            assert "errors" in result
            assert len(result["errors"]) > 0

            error = result["errors"][0]
            assert "message" in error
            assert "severity" in error
            assert error["severity"] == "error"

    def test_validation_with_complex_directory_structure(self):
        """Test validation with complex nested directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complex directory structure
            (temp_path / "accounts-config.yaml").write_text("mandatoryAccounts: []")
            (temp_path / "global-config.yaml").write_text("homeRegion: us-east-1")
            (temp_path / "organization-config.yaml").write_text("enable: true")

            # Create nested directories
            iam_dir = temp_path / "iam-policies" / "custom"
            iam_dir.mkdir(parents=True)
            (iam_dir / "policy1.json").write_text('{"Version": "2012-10-17"}')

            scp_dir = temp_path / "service-control-policies" / "quarantine"
            scp_dir.mkdir(parents=True)
            (scp_dir / "quarantine.json").write_text('{"Version": "2012-10-17"}')

            # Create empty directory (should be handled gracefully)
            empty_dir = temp_path / "empty"
            empty_dir.mkdir()

            result = validate_configuration_impl(str(temp_path), _test_mode=False)

            assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validation_tools_error_message_quality(self):
        """Test that validation tools provide helpful error messages."""
        mock_ctx = MockContext()

        # Test S3 validation with local path (common user error)
        result = await tool_validate_configuration_from_s3(
            mock_ctx, "/local/path/config.zip"
        )

        assert result["valid"] is False
        assert "workflow_correction" in result
        assert "CRITICAL WORKFLOW ERROR" in result["workflow_correction"]
        assert "checkAwsConnectivity" in result["workflow_correction"]

        # Verify helpful instructions are provided
        assert "setupS3Bucket" in result["workflow_correction"]

    def test_validation_performance_with_large_config(self):
        """Test validation performance with larger configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create larger configuration files
            accounts_config = """
mandatoryAccounts:
  - name: Management
    description: Management account
    email: management@example.com
    organizationalUnit: Root
workloadAccounts:
"""

            # Add many workload accounts
            for i in range(50):
                accounts_config += f"""
  - name: Workload{i:02d}
    description: Workload account {i}
    email: workload{i:02d}@example.com
    organizationalUnit: Workloads
"""

            (temp_path / "accounts-config.yaml").write_text(accounts_config)
            (temp_path / "global-config.yaml").write_text(
                "homeRegion: us-east-1\nenabledRegions: [us-east-1, us-west-2]"
            )
            (temp_path / "organization-config.yaml").write_text("enable: true")

            # Create many policy files
            policies_dir = temp_path / "iam-policies"
            policies_dir.mkdir()

            for i in range(20):
                (policies_dir / f"policy{i:02d}.json").write_text(
                    '{"Version": "2012-10-17"}'
                )

            import time

            start_time = time.time()

            result = validate_configuration_impl(str(temp_path), _test_mode=False)

            end_time = time.time()
            validation_time = end_time - start_time

            assert result["valid"] is True
            # Validation should complete in reasonable time (less than 5 seconds)
            assert validation_time < 5.0

    def test_validation_tools_module_imports(self):
        """Test that all validation tool modules can be imported successfully."""
        # Test imports don't raise exceptions
        from awslabs.lza_mcp_server.tools.validation.common import (
            validate_configuration_impl,
        )
        from awslabs.lza_mcp_server.tools.validation.cleanup_validation_zip import (
            tool_cleanup_validation_zip,
        )
        from awslabs.lza_mcp_server.tools.validation.manage_validation_tools import (
            register_validation_tools,
        )
        from awslabs.lza_mcp_server.tools.validation.validate_configuration_share import (
            tool_validate_configuration_from_share,
        )
        from awslabs.lza_mcp_server.tools.validation.validation_configuration_s3 import (
            tool_validate_configuration_from_s3,
        )

        # Verify functions are callable
        assert callable(validate_configuration_impl)
        assert callable(tool_cleanup_validation_zip)
        assert callable(register_validation_tools)
        assert callable(tool_validate_configuration_from_share)
        assert callable(tool_validate_configuration_from_s3)
