# Requirements Document

## Introduction

This document captures the requirements for resolving 19 identified issues in the FinXCloud multi-cloud cost optimization tool. The issues span security hardening, code quality improvements, missing dependencies, testing infrastructure, configuration gaps, and documentation. Two issues (3 and 11, both about `python-dotenv`) are already fixed and excluded from scope.

## Glossary

- **Dashboard**: The FastAPI-based web application in `finxcloud/web/app.py` that provides an interactive UI for triggering scans and viewing results
- **CLI**: The Click-based command-line interface in `finxcloud/cli.py` used to run scans and generate reports
- **Auth_Module**: The JWT authentication module in `finxcloud/web/auth.py` that handles login and token management
- **Deploy_Module**: The S3 deployment module in `finxcloud/web/deploy.py` that publishes static dashboards to S3 buckets
- **Storage_Module**: The SQLite + Fernet encryption module in `finxcloud/web/storage.py` that persists accounts and scan results
- **ScanRequest_Model**: The Pydantic model in `finxcloud/web/app.py` that carries scan parameters including cloud credentials during the request lifecycle
- **Merge_Utility**: The `_merge_cost_data` function that combines cost data from multiple accounts into a single dict
- **Project_Config**: The `pyproject.toml` file that defines project metadata, dependencies, and tool configuration

## Requirements

### Requirement 1: Enforce Default Credential Change on First Use

**User Story:** As a security-conscious operator, I want the system to require changing default admin credentials on first login, so that the dashboard is not left exposed with well-known credentials.

#### Acceptance Criteria

1. WHEN the Auth_Module detects that ADMIN_USERNAME is "admin" and ADMIN_PASSWORD is "admin", THE Auth_Module SHALL return a response indicating that a password change is required before granting access
2. WHEN the operator provides a new password during the forced change flow, THE Auth_Module SHALL accept the new credentials and issue a valid JWT token
3. IF the operator attempts to authenticate with default credentials without changing the password, THEN THE Auth_Module SHALL reject the login and return a descriptive error message instructing the operator to set custom credentials via environment variables
4. THE Auth_Module SHALL log a warning at startup when default credentials are detected

### Requirement 2: Secure S3 Deployment Configuration

**User Story:** As a DevOps engineer, I want the S3 deployment to use secure defaults, so that sensitive cost data is not accidentally exposed to the public internet.

#### Acceptance Criteria

1. THE Deploy_Module SHALL keep S3 public access blocks enabled by default
2. THE Deploy_Module SHALL not set a public bucket policy by default
3. WHERE the operator provides a `--public` flag, THE Deploy_Module SHALL disable public access blocks and set the public read policy
4. WHEN the `--public` flag is used, THE Deploy_Module SHALL log a warning that the bucket will be publicly accessible
5. WHEN the `--public` flag is not used, THE Deploy_Module SHALL configure the bucket with a private policy and provide the S3 console URL instead of a public website URL

### Requirement 3: Document Fernet Encryption Key Management

**User Story:** As a developer or operator, I want clear documentation on how the Fernet encryption key is managed, so that I understand the security model and can rotate keys when needed.

#### Acceptance Criteria

1. THE Storage_Module documentation SHALL describe where the Fernet key file is stored (`~/.finxcloud/.fernet.key`)
2. THE Storage_Module documentation SHALL describe the file permissions applied to the key file (mode 0o600)
3. THE Storage_Module documentation SHALL describe the procedure for key rotation
4. THE Storage_Module documentation SHALL describe the impact of key loss on encrypted data

### Requirement 4: Prevent Plaintext Credential Exposure in Request Model

**User Story:** As a security engineer, I want credentials to be handled securely during the request lifecycle, so that sensitive values are not inadvertently logged or serialized.

#### Acceptance Criteria

1. THE ScanRequest_Model SHALL mark all credential fields (secret_key, session_token, azure_client_secret, gcp_service_account_json) as excluded from default serialization using Pydantic `repr=False`
2. WHEN the ScanRequest_Model is converted to a string representation, THE ScanRequest_Model SHALL redact all credential field values
3. THE ScanRequest_Model SHALL use `SecretStr` from Pydantic for credential fields so that values are masked in logs and repr output

### Requirement 5: Move Misplaced Import to Top of File

**User Story:** As a developer, I want all imports at the top of the module, so that the code follows Python conventions and is easier to read.

#### Acceptance Criteria

1. THE CLI SHALL place the `import boto3` statement at the top of `cli.py` with the other third-party imports
2. THE CLI SHALL remove the inline `import boto3` statement from the bottom of the file

### Requirement 6: Break Down Large CLI Scan Function

**User Story:** As a developer, I want the scan command broken into smaller helper functions, so that the code is easier to understand, test, and maintain.

#### Acceptance Criteria

1. THE CLI SHALL extract resource scanning logic into a dedicated helper function
2. THE CLI SHALL extract cost analysis logic into a dedicated helper function
3. THE CLI SHALL extract report generation logic into a dedicated helper function
4. WHEN the scan command is invoked, THE CLI SHALL delegate to the extracted helper functions while preserving identical behavior
5. THE CLI SHALL keep each extracted helper function under 80 lines of code

### Requirement 7: Extract Shared Merge Utility

**User Story:** As a developer, I want the duplicated `_merge_cost_data` function consolidated into a single shared module, so that changes only need to be made in one place.

#### Acceptance Criteria

1. THE Merge_Utility SHALL exist in a single shared module accessible to both the CLI and the Dashboard
2. THE CLI SHALL import the Merge_Utility from the shared module instead of defining a local copy
3. THE Dashboard SHALL import the Merge_Utility from the shared module instead of defining a local copy
4. WHEN the Merge_Utility is called with cost data from multiple accounts, THE Merge_Utility SHALL produce identical output to the current implementations

### Requirement 8: Add Module-Level `__all__` Exports

**User Story:** As a developer, I want explicit `__all__` exports in public modules, so that the public API surface is clear and tools like linters can flag unintended exports.

#### Acceptance Criteria

1. THE Storage_Module SHALL define an `__all__` list containing all public function names
2. THE Auth_Module SHALL define an `__all__` list containing all public function names
3. THE Dashboard SHALL define an `__all__` list containing the FastAPI `app` instance and public model names
4. THE CLI SHALL define an `__all__` list containing the `main` entry point

### Requirement 9: Persist Scan Results Across Restarts

**User Story:** As a dashboard user, I want scan results to survive server restarts, so that I do not lose historical scan data.

#### Acceptance Criteria

1. WHEN a scan completes, THE Dashboard SHALL persist the scan result to the Storage_Module (SQLite database) instead of only storing it in the in-memory `_scans` dict
2. WHEN the Dashboard starts, THE Dashboard SHALL load pending and completed scan statuses from the Storage_Module
3. WHEN a user requests scan status, THE Dashboard SHALL check the Storage_Module if the scan is not found in the in-memory cache

### Requirement 10: Fix PyJWT Dependency Declaration

**User Story:** As a developer, I want `pyjwt` available whenever the auth module is imported, so that the web application does not crash with an ImportError.

#### Acceptance Criteria

1. THE Auth_Module SHALL guard the `import jwt` statement with a try/except that raises a clear error message directing the user to install the `[web]` extra
2. IF `pyjwt` is not installed and the Auth_Module is imported, THEN THE Auth_Module SHALL raise an ImportError with a message stating that the `[web]` extra is required

### Requirement 11: Create Test Infrastructure

**User Story:** As a developer, I want a test directory with initial unit tests, so that I can verify correctness and prevent regressions.

#### Acceptance Criteria

1. THE project SHALL contain a `tests/` directory with an `__init__.py` file
2. THE project SHALL contain a `tests/conftest.py` file with shared fixtures
3. THE project SHALL contain at least one test file for the Merge_Utility that verifies merge behavior with single-account and multi-account data
4. THE project SHALL contain at least one test file for the Auth_Module that verifies token creation, token decoding, and default credential detection
5. THE project SHALL contain at least one test file for the Storage_Module that verifies account CRUD and scan result persistence using an in-memory SQLite database
6. WHEN `pytest` is run from the project root, THE test suite SHALL discover and execute all tests in the `tests/` directory

### Requirement 12: Add `py.typed` Marker

**User Story:** As a developer using type checkers, I want a `py.typed` marker file, so that type checkers recognize FinXCloud as a typed package.

#### Acceptance Criteria

1. THE project SHALL contain a `finxcloud/py.typed` file (empty marker file)
2. THE Project_Config SHALL include `finxcloud/py.typed` in the package data

### Requirement 13: Expand Ruff Linter Configuration

**User Story:** As a developer, I want comprehensive linter rules configured, so that code quality is enforced consistently across the project.

#### Acceptance Criteria

1. THE Project_Config SHALL configure Ruff with a `select` list that includes at minimum: E (pycodestyle errors), F (pyflakes), I (isort), UP (pyupgrade), B (flake8-bugbear), and SIM (flake8-simplify)
2. THE Project_Config SHALL configure Ruff with an `ignore` list for any intentionally suppressed rules
3. THE Project_Config SHALL configure Ruff isort settings with a known first-party package of `finxcloud`

### Requirement 14: Share Useful VS Code Settings with Contributors

**User Story:** As a contributor, I want recommended VS Code settings available in the repository, so that I can quickly set up a consistent development environment.

#### Acceptance Criteria

1. THE `.gitignore` SHALL exclude `.vscode/*` but include an exception for `.vscode/settings.json`
2. THE `.vscode/settings.json` file SHALL be tracked in version control with editor formatting settings

### Requirement 15: Add LICENSE File

**User Story:** As a user or contributor, I want a LICENSE file in the repository root, so that the legal terms of use are clear.

#### Acceptance Criteria

1. THE project SHALL contain a `LICENSE` file in the repository root
2. THE `LICENSE` file SHALL contain the proprietary license text consistent with the README's "Proprietary — AICloud Strategist" declaration
3. THE README SHALL reference the `LICENSE` file in its License section

### Requirement 16: Add Contributing Guide

**User Story:** As a new contributor, I want a CONTRIBUTING.md file, so that I know how to set up the development environment and submit changes.

#### Acceptance Criteria

1. THE project SHALL contain a `CONTRIBUTING.md` file in the repository root
2. THE `CONTRIBUTING.md` SHALL describe how to install the project in development mode with all extras
3. THE `CONTRIBUTING.md` SHALL describe how to run the test suite
4. THE `CONTRIBUTING.md` SHALL describe how to run the linter
5. THE `CONTRIBUTING.md` SHALL describe the branch and pull request workflow
