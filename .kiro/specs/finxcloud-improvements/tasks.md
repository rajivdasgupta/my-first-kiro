# Implementation Plan: FinXCloud Improvements

## Overview

Incremental implementation of security hardening, code quality improvements, testing infrastructure, configuration, and documentation across the FinXCloud codebase. Tasks are ordered so each step builds on the previous, with no orphaned code.

## Tasks

- [x] 1. Create shared merge utility and update imports
  - [x] 1.1 Create `finxcloud/utils/__init__.py` and `finxcloud/utils/cost.py` with `merge_cost_data` function
    - Extract the `_merge_cost_data` logic into `finxcloud/utils/cost.py` as a public `merge_cost_data` function
    - Add `__all__ = ["merge_cost_data"]` to the module
    - Create empty `finxcloud/utils/__init__.py`
    - _Requirements: 7.1, 7.4_

  - [x] 1.2 Update `finxcloud/cli.py` to import `merge_cost_data` from shared module
    - Replace local `_merge_cost_data` with `from finxcloud.utils.cost import merge_cost_data`
    - Remove the old `_merge_cost_data` function definition
    - _Requirements: 7.2_

  - [x] 1.3 Update `finxcloud/web/app.py` to import `merge_cost_data` from shared module
    - Replace local `_merge_cost_data` with `from finxcloud.utils.cost import merge_cost_data`
    - Remove the old `_merge_cost_data` function definition
    - _Requirements: 7.3_

  - [ ]* 1.4 Write property tests for merge utility (Property 2, 3, 4)
    - Create `tests/test_merge.py`
    - **Property 2: Merge cost data preserves total cost** — generate random cost data dicts, merge, assert `total_cost_30d` sum equality
    - **Validates: Requirements 7.4**
    - **Property 3: Merge cost data preserves all services** — assert all input services appear in output with correct summed amounts
    - **Validates: Requirements 7.4**
    - **Property 4: Merge cost data aggregates daily trends correctly** — assert per-date sum equality across merged output
    - **Validates: Requirements 7.4**

  - [ ]* 1.5 Write unit tests for merge utility
    - Add example-based tests in `tests/test_merge.py` for single-account passthrough and multi-account merge with known values
    - _Requirements: 11.3_

- [x] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Security hardening — Auth module
  - [x] 3.1 Guard `import jwt` with try/except in `finxcloud/web/auth.py`
    - Wrap `import jwt` in try/except `ImportError`, raise clear error directing user to `pip install finxcloud[web]`
    - _Requirements: 10.1, 10.2_

  - [x] 3.2 Add `is_using_default_credentials()` and `check_default_credentials_startup()` to `finxcloud/web/auth.py`
    - `is_using_default_credentials()` returns `True` when both username and password are `"admin"`
    - `check_default_credentials_startup()` logs a WARNING via module logger when defaults detected; called at module load
    - _Requirements: 1.1, 1.4_

  - [x] 3.3 Modify `authenticate()` to reject default credentials
    - Before issuing token, check `is_using_default_credentials()`; if True, return None with descriptive error message instructing operator to set env vars
    - _Requirements: 1.1, 1.3_

  - [x] 3.4 Add `__all__` to `finxcloud/web/auth.py`
    - `__all__ = ["authenticate", "require_auth", "create_token", "decode_token", "verify_password", "hash_password_for_static", "is_using_default_credentials"]`
    - _Requirements: 8.2_

  - [ ]* 3.5 Write unit tests for auth module
    - Create `tests/test_auth.py`
    - Test `is_using_default_credentials()` with default and custom env vars
    - Test `authenticate()` rejects defaults and accepts custom credentials
    - Test token create/decode round-trip
    - Test startup warning log output
    - _Requirements: 11.4_

- [x] 4. Security hardening — Credential redaction in ScanRequest
  - [x] 4.1 Change credential fields to `SecretStr` in `finxcloud/web/app.py`
    - Change `secret_key`, `session_token`, `azure_client_secret`, `gcp_service_account_json` to `SecretStr` type with `Field(repr=False)`
    - Apply similar changes to `AccountRequest` and `AccountUpdateRequest` for consistency
    - Update any code that accesses these fields to call `.get_secret_value()` where the plaintext is needed
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 4.2 Write property test for credential redaction (Property 1)
    - Create `tests/test_models.py`
    - **Property 1: Credential redaction in serialization and representation** — generate random non-empty strings for credential fields, construct ScanRequest, assert plaintext not in `model_dump()` or `repr()`
    - **Validates: Requirements 4.1, 4.2**

- [x] 5. Security hardening — Secure S3 deployment defaults
  - [x] 5.1 Modify `deploy_to_s3` in `finxcloud/web/deploy.py` to default to private
    - Add `public: bool = False` parameter
    - When `public=False`: skip disabling public access blocks, skip public bucket policy, return S3 console URL
    - When `public=True`: current behavior (disable blocks, set policy, return website URL) plus log a warning
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 5.2 Update CLI `deploy` command to pass `public` flag through to `deploy_to_s3`
    - Add `--public` option to the CLI deploy command
    - Pass the flag to `deploy_to_s3`
    - _Requirements: 2.3_

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Code quality — CLI refactoring
  - [x] 7.1 Move `import boto3` to top-level imports in `finxcloud/cli.py`
    - Remove inline `import boto3` from bottom of file, place at top with other third-party imports
    - _Requirements: 5.1, 5.2_

  - [x] 7.2 Extract helper functions from `scan()` in `finxcloud/cli.py`
    - Extract `_run_resource_scanners(scanners, account_id, console) -> list[dict]`
    - Extract `_run_cost_analysis(session, account_id, days, region_list, skip_utilization, allocation_tags, console) -> dict`
    - Extract `_generate_reports(all_resources, merged_cost_data, utilization_data, output_dir, output_pdf, output_s3_bucket, output_s3_prefix, session, console) -> None`
    - Each helper under 80 lines; `scan()` delegates to them preserving identical behavior
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 7.3 Add `__all__` to `finxcloud/cli.py`
    - `__all__ = ["main"]`
    - _Requirements: 8.4_

- [x] 8. Code quality — Dashboard and storage module exports
  - [x] 8.1 Add `__all__` to `finxcloud/web/app.py`
    - `__all__ = ["app"]`
    - _Requirements: 8.3_

  - [x] 8.2 Add `__all__` to `finxcloud/web/storage.py`
    - `__all__ = ["list_accounts", "get_account", "create_account", "update_account", "delete_account", "save_scan_result", "get_latest_scan", "list_scans"]`
    - _Requirements: 8.1_

- [x] 9. Scan result persistence
  - [x] 9.1 Wire scan persistence into `finxcloud/web/app.py`
    - After scan completes, call `save_scan_result(account_id, result)` from storage module
    - On startup, load recent scans from storage into `_scans` dict
    - In status endpoint, if scan_id not in `_scans`, query storage as fallback
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 9.2 Write unit tests for storage module
    - Create `tests/test_storage.py`
    - Test account CRUD (create, read, update, delete) using in-memory SQLite or tmp path
    - Test scan result persistence and retrieval
    - _Requirements: 11.5_

- [x] 10. Storage module documentation
  - [x] 10.1 Add comprehensive module-level docstring to `finxcloud/web/storage.py`
    - Document Fernet key location (`~/.finxcloud/.fernet.key`)
    - Document file permissions (mode `0o600`)
    - Document key rotation procedure
    - Document impact of key loss on encrypted data
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 11. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Project configuration and tooling
  - [x] 12.1 Update `pyproject.toml` with ruff config, hypothesis dep, and py.typed
    - Add `[tool.ruff.lint]` section with `select = ["E", "F", "I", "UP", "B", "SIM"]` and `ignore = ["E501"]`
    - Add `[tool.ruff.lint.isort]` with `known-first-party = ["finxcloud"]`
    - Add `hypothesis>=6.0` to dev dependencies
    - Add `[tool.setuptools.package-data]` with `finxcloud = ["py.typed"]`
    - _Requirements: 13.1, 13.2, 13.3, 12.2_

  - [x] 12.2 Create `finxcloud/py.typed` marker file
    - Create empty file at `finxcloud/py.typed`
    - _Requirements: 12.1_

  - [x] 12.3 Create `.vscode/settings.json` with recommended editor settings
    - Add formatOnSave, ruff as default formatter, codeActionsOnSave for fixAll and organizeImports, basic type checking
    - _Requirements: 14.2_

  - [x] 12.4 Update `.gitignore` to track `.vscode/settings.json`
    - Replace `.vscode/` with `.vscode/*` and `!.vscode/settings.json`
    - _Requirements: 14.1_

- [x] 13. Test infrastructure setup
  - [x] 13.1 Create `tests/__init__.py` and `tests/conftest.py`
    - Create empty `tests/__init__.py`
    - Create `tests/conftest.py` with shared fixtures (tmp db path, mock env vars for auth)
    - _Requirements: 11.1, 11.2, 11.6_

- [x] 14. Documentation files
  - [x] 14.1 Create `LICENSE` file
    - Add proprietary license text consistent with README's "Proprietary — AICloud Strategist" declaration
    - _Requirements: 15.1, 15.2_

  - [x] 14.2 Update README to reference LICENSE file
    - Update the License section in README.md to reference the LICENSE file
    - _Requirements: 15.3_

  - [x] 14.3 Create `CONTRIBUTING.md`
    - Describe dev install with all extras (`pip install -e ".[dev,web,azure,gcp,pdf]"`)
    - Describe running tests (`pytest`)
    - Describe running linter (`ruff check .`)
    - Describe branch and pull request workflow
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
