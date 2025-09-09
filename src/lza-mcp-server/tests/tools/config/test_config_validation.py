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

"""Tests for configuration validation functionality."""

import pytest
import yaml
from typing import Dict, Any, List


class TestConfigurationValidation:
    """Test cases for configuration validation logic."""
    
    @pytest.fixture
    def valid_accounts_config(self):
        """Valid accounts configuration for testing."""
        return {
            'mandatoryAccounts': [
                {
                    'name': 'Management',
                    'description': 'Management account',
                    'email': 'management@example.com',
                    'organizationalUnit': 'Root',
                    'warm': False
                },
                {
                    'name': 'LogArchive',
                    'description': 'Log Archive account',
                    'email': 'logarchive@example.com',
                    'organizationalUnit': 'Security',
                    'warm': False
                },
                {
                    'name': 'Audit',
                    'description': 'Audit account',
                    'email': 'audit@example.com',
                    'organizationalUnit': 'Security',
                    'warm': False
                }
            ],
            'workloadAccounts': []
        }
    
    @pytest.fixture
    def valid_global_config(self):
        """Valid global configuration for testing."""
        return {
            'homeRegion': 'us-east-1',
            'enabledRegions': ['us-east-1', 'us-west-2'],
            'managementAccountAccessRole': 'AWSControlTowerExecution',
            'terminationProtection': True,
            'cloudwatchLogRetentionInDays': 365
        }
    
    @pytest.fixture
    def invalid_accounts_config(self):
        """Invalid accounts configuration for testing."""
        return {
            'mandatoryAccounts': [
                {
                    'name': 'Management',
                    'description': 'Management account',
                    'email': 'invalid-email-format',  # Invalid email
                    'organizationalUnit': 'Root',
                    'warm': False
                },
                {
                    'name': 'LogArchive',
                    # Missing required fields: description, email, organizationalUnit
                    'warm': False
                }
                # Missing Audit account entirely
            ],
            'workloadAccounts': []
        }
    
    def test_validate_mandatory_accounts_complete(self, valid_accounts_config):
        """Test validation of complete mandatory accounts."""
        mandatory_accounts = valid_accounts_config.get('mandatoryAccounts', [])
        account_names = [acc['name'] for acc in mandatory_accounts]
        
        required_accounts = ['Management', 'LogArchive', 'Audit']
        for required in required_accounts:
            assert required in account_names
    
    def test_validate_mandatory_accounts_missing(self, invalid_accounts_config):
        """Test validation of missing mandatory accounts."""
        mandatory_accounts = invalid_accounts_config.get('mandatoryAccounts', [])
        account_names = [acc['name'] for acc in mandatory_accounts]
        
        required_accounts = ['Management', 'LogArchive', 'Audit']
        missing_accounts = [acc for acc in required_accounts if acc not in account_names]
        
        assert len(missing_accounts) > 0  # Should have missing accounts
        assert 'Audit' in missing_accounts
    
    def test_validate_email_format_valid(self, valid_accounts_config):
        """Test validation of valid email formats."""
        for account in valid_accounts_config['mandatoryAccounts']:
            email = account.get('email', '')
            assert '@' in email
            assert '.' in email.split('@')[1]  # Domain should have a dot
    
    def test_validate_email_format_invalid(self, invalid_accounts_config):
        """Test validation of invalid email formats."""
        invalid_emails = []
        for account in invalid_accounts_config['mandatoryAccounts']:
            email = account.get('email', '')
            if email and ('@' not in email or '.' not in email.split('@')[-1]):
                invalid_emails.append(email)
        
        assert len(invalid_emails) > 0  # Should have invalid emails
        assert 'invalid-email-format' in invalid_emails
    
    def test_validate_required_fields_present(self, valid_accounts_config):
        """Test validation of required fields presence."""
        required_fields = ['name', 'description', 'email', 'organizationalUnit', 'warm']
        
        for account in valid_accounts_config['mandatoryAccounts']:
            for field in required_fields:
                assert field in account
                assert account[field] is not None
    
    def test_validate_required_fields_missing(self, invalid_accounts_config):
        """Test validation of missing required fields."""
        required_fields = ['name', 'description', 'email', 'organizationalUnit']
        
        missing_field_accounts = []
        for account in invalid_accounts_config['mandatoryAccounts']:
            missing_fields = [field for field in required_fields if field not in account]
            if missing_fields:
                missing_field_accounts.append((account, missing_fields))
        
        assert len(missing_field_accounts) > 0  # Should have accounts with missing fields
    
    def test_validate_global_config_structure(self, valid_global_config):
        """Test validation of global configuration structure."""
        required_fields = ['homeRegion', 'enabledRegions', 'managementAccountAccessRole', 'terminationProtection']
        
        for field in required_fields:
            assert field in valid_global_config
            assert valid_global_config[field] is not None
        
        # Validate specific field types
        assert isinstance(valid_global_config['homeRegion'], str)
        assert isinstance(valid_global_config['enabledRegions'], list)
        assert isinstance(valid_global_config['terminationProtection'], bool)
    
    def test_validate_region_consistency(self, valid_global_config):
        """Test validation of region consistency."""
        home_region = valid_global_config['homeRegion']
        enabled_regions = valid_global_config['enabledRegions']
        
        # Home region should be in enabled regions
        assert home_region in enabled_regions
    
    def test_yaml_parsing_valid_config(self, valid_accounts_config):
        """Test parsing valid YAML configuration."""
        yaml_content = yaml.dump(valid_accounts_config, default_flow_style=False)
        
        # Parse the YAML content
        parsed_config = yaml.safe_load(yaml_content)
        
        # Verify parsing was successful
        assert isinstance(parsed_config, dict)
        assert 'mandatoryAccounts' in parsed_config
        assert isinstance(parsed_config['mandatoryAccounts'], list)
        assert len(parsed_config['mandatoryAccounts']) == 3
    
    def test_yaml_parsing_invalid_syntax(self):
        """Test parsing YAML with invalid syntax."""
        invalid_yaml = "invalid: yaml: content: [unclosed bracket"
        
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(invalid_yaml)
    
    def test_yaml_parsing_empty_content(self):
        """Test parsing empty YAML content."""
        empty_yaml = ""
        parsed_config = yaml.safe_load(empty_yaml)
        
        assert parsed_config is None
    
    def test_configuration_cross_reference_validation(self, valid_accounts_config):
        """Test validation of cross-references between configuration sections."""
        org_config = {
            'organizationalUnits': [
                {'name': 'Security', 'parent': 'Root'},
                {'name': 'Workloads', 'parent': 'Root'}
            ]
        }
        
        # Extract organizational units from accounts
        account_ous = set()
        for account in valid_accounts_config['mandatoryAccounts'] + valid_accounts_config['workloadAccounts']:
            account_ous.add(account['organizationalUnit'])
        
        # Extract organizational units from organization config
        org_ous = set()
        for ou in org_config['organizationalUnits']:
            org_ous.add(ou['name'])
        org_ous.add('Root')  # Root is implicit
        
        # Validate that all account OUs exist in organization config
        missing_ous = account_ous - org_ous
        assert len(missing_ous) == 0, f"Accounts reference non-existent OUs: {missing_ous}"


class TestConfigurationErrorDetection:
    """Test cases for configuration error detection and reporting."""
    
    def test_detect_missing_mandatory_accounts(self):
        """Test detection of missing mandatory accounts."""
        config = {
            'mandatoryAccounts': [
                {'name': 'Management', 'email': 'mgmt@example.com', 'organizationalUnit': 'Root', 'warm': False}
                # Missing LogArchive and Audit accounts
            ],
            'workloadAccounts': []
        }
        
        mandatory_accounts = config.get('mandatoryAccounts', [])
        account_names = [acc['name'] for acc in mandatory_accounts]
        
        required_accounts = ['Management', 'LogArchive', 'Audit']
        missing_accounts = [acc for acc in required_accounts if acc not in account_names]
        
        # Should detect missing accounts
        assert len(missing_accounts) > 0
        assert 'LogArchive' in missing_accounts
        assert 'Audit' in missing_accounts
        
        # Generate error report
        error_report = {
            'missing_mandatory_accounts': missing_accounts,
            'found_accounts': account_names,
            'severity': 'error',
            'message': f"Missing required mandatory accounts: {', '.join(missing_accounts)}"
        }
        
        assert error_report['severity'] == 'error'
        assert len(error_report['missing_mandatory_accounts']) == 2
    
    def test_detect_invalid_field_values(self):
        """Test detection of invalid field values."""
        config = {
            'mandatoryAccounts': [
                {
                    'name': 'Management',
                    'description': 'Management account',
                    'email': 'invalid-email-format',  # Invalid email
                    'organizationalUnit': 'Root',
                    'warm': False
                }
            ]
        }
        
        email_errors = []
        for account in config.get('mandatoryAccounts', []):
            email = account.get('email', '')
            if email and ('@' not in email or '.' not in email.split('@')[-1]):
                email_errors.append({
                    'account_name': account.get('name', 'Unknown'),
                    'invalid_email': email,
                    'error': 'Invalid email format'
                })
        
        # Should detect invalid emails
        assert len(email_errors) > 0
        
        # Verify error details
        for error in email_errors:
            assert 'invalid_email' in error
            assert 'error' in error
            assert error['invalid_email'] == 'invalid-email-format'
    
    def test_comprehensive_error_reporting(self):
        """Test comprehensive error reporting for multiple validation issues."""
        problematic_config = {
            'mandatoryAccounts': [
                {
                    'name': 'Management',
                    'description': 'Management account',
                    'email': 'invalid-email-format',  # Invalid email
                    'organizationalUnit': 'Root',
                    'warm': False
                },
                {
                    'name': 'LogArchive',
                    # Missing description, email, organizationalUnit
                    'warm': False
                }
                # Missing Audit account entirely
            ],
            'workloadAccounts': []
        }
        
        # Comprehensive validation
        validation_errors = []
        
        # Check mandatory accounts count
        if len(problematic_config['mandatoryAccounts']) < 3:
            validation_errors.append({
                'type': 'missing_accounts',
                'severity': 'error',
                'message': 'Insufficient mandatory accounts'
            })
        
        # Check individual account fields
        for i, account in enumerate(problematic_config['mandatoryAccounts']):
            required_fields = ['name', 'description', 'email', 'organizationalUnit', 'warm']
            missing_fields = [field for field in required_fields if field not in account]
            
            if missing_fields:
                validation_errors.append({
                    'type': 'missing_fields',
                    'severity': 'error',
                    'account_index': i,
                    'missing_fields': missing_fields
                })
            
            # Check email format
            email = account.get('email', '')
            if email and '@' not in email:
                validation_errors.append({
                    'type': 'invalid_format',
                    'severity': 'error',
                    'field': 'email',
                    'value': email,
                    'account_index': i
                })
        
        # Should have multiple validation errors
        assert len(validation_errors) >= 3  # At least missing account, missing fields, invalid email
        
        # Verify error types are captured
        error_types = [error['type'] for error in validation_errors]
        assert 'missing_accounts' in error_types
        assert 'missing_fields' in error_types
        assert 'invalid_format' in error_types


class TestConfigurationMerging:
    """Test cases for configuration merging and transformation logic."""
    
    def test_merge_configurations_simple(self):
        """Test merging simple configurations."""
        base_config = {'key1': 'value1', 'key2': {'nested': 'value'}}
        override_config = {'key2': {'nested': 'new_value'}, 'key3': 'value3'}
        
        # Simple merge logic (override wins)
        merged_config = {**base_config, **override_config}
        
        assert merged_config['key1'] == 'value1'
        assert merged_config['key2']['nested'] == 'new_value'
        assert merged_config['key3'] == 'value3'
    
    def test_deep_merge_configurations(self):
        """Test deep merging of nested configurations."""
        base_config = {
            'accounts': {
                'mandatory': ['Management'],
                'workload': []
            },
            'settings': {
                'region': 'us-east-1',
                'logging': True
            }
        }
        
        override_config = {
            'accounts': {
                'workload': ['Development']
            },
            'settings': {
                'region': 'us-west-2'
            }
        }
        
        def deep_merge(base, override):
            """Simple deep merge implementation for testing."""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        merged_config = deep_merge(base_config, override_config)
        
        # Verify deep merge behavior
        assert merged_config['accounts']['mandatory'] == ['Management']
        assert merged_config['accounts']['workload'] == ['Development']
        assert merged_config['settings']['region'] == 'us-west-2'
        assert merged_config['settings']['logging'] is True
    
    def test_transform_configuration_structure(self):
        """Test transformation of configuration structure."""
        source_config = {
            'mandatoryAccounts': [
                {'name': 'Management', 'email': 'mgmt@example.com', 'organizationalUnit': 'Root'},
                {'name': 'LogArchive', 'email': 'log@example.com', 'organizationalUnit': 'Security'},
                {'name': 'Audit', 'email': 'audit@example.com', 'organizationalUnit': 'Security'}
            ],
            'workloadAccounts': []
        }
        
        # Transform to different structure
        transformed_config = {
            'account_list': [],
            'metadata': {
                'total_accounts': 0,
                'mandatory_count': 0,
                'workload_count': 0
            }
        }
        
        # Transform mandatory accounts
        for account in source_config.get('mandatoryAccounts', []):
            transformed_account = {
                'account_name': account['name'],
                'account_email': account['email'],
                'account_type': 'mandatory',
                'organizational_unit': account['organizationalUnit']
            }
            transformed_config['account_list'].append(transformed_account)
            transformed_config['metadata']['mandatory_count'] += 1
        
        # Transform workload accounts
        for account in source_config.get('workloadAccounts', []):
            transformed_account = {
                'account_name': account['name'],
                'account_email': account['email'],
                'account_type': 'workload',
                'organizational_unit': account['organizationalUnit']
            }
            transformed_config['account_list'].append(transformed_account)
            transformed_config['metadata']['workload_count'] += 1
        
        transformed_config['metadata']['total_accounts'] = len(transformed_config['account_list'])
        
        # Verify transformation
        assert len(transformed_config['account_list']) == 3  # 3 mandatory accounts
        assert transformed_config['metadata']['mandatory_count'] == 3
        assert transformed_config['metadata']['workload_count'] == 0
        assert transformed_config['metadata']['total_accounts'] == 3