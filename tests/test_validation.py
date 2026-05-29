from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path

from tests.support import PROJECT_ROOT, MemoryFileSystem, profile_toml, write_project

from mockapi_runtime.profile import ProfileValidatorService


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fs = MemoryFileSystem()
        self.validator = ProfileValidatorService(self.fs)

    def test_validates_profile_with_operation_behavior_section(self) -> None:
        profile_path = write_project(self.fs)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)
        self.assertTrue(result.ok)
        self.assertEqual(result.profile.operationCount, 1)

    def test_profile_state_seed_defaults_to_true(self) -> None:
        profile_path = write_project(self.fs)

        profile = self.validator.load_profile_model(profile_path)

        self.assertTrue(profile.state.seed)

    def test_profile_state_seed_can_disable_product_seed_data(self) -> None:
        profile_path = write_project(
            self.fs,
            profile=profile_toml().replace("[state]\nschemaVersion = 1", "[state]\nschemaVersion = 1\nseed = false"),
        )

        profile = self.validator.load_profile_model(profile_path)

        self.assertFalse(profile.state.seed)

    def test_errors_for_non_boolean_state_seed(self) -> None:
        profile_path = write_project(
            self.fs,
            profile=profile_toml().replace("[state]\nschemaVersion = 1", '[state]\nschemaVersion = 1\nseed = "yes"'),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.seed.invalid")

    def test_requires_behavior_anchor_section(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "sidecar.behavior.missingAnchor")

    def test_errors_for_duplicate_behavior_anchor_sections(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: inferred

                ## operation:listWorkspaces
                Status: inferred
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "sidecar.behavior.duplicateAnchor")

    def test_warns_for_extra_behavior_anchor_sections(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: inferred

                ## operation:getWorkspace
                Status: inferred
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)
        self.assertTrue(result.ok)
        self.assertEqual(result.warnings[0]["id"], "sidecar.behavior.extraAnchor")

    def test_warns_when_generated_id_behavior_lacks_id_counters_slice(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: confirmed
                Response objects use generated ids with workspace prefix.
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.warnings}
        self.assertTrue(result.ok)
        self.assertIn("sidecar.behavior.idCountersMissing", ids)

    def test_accepts_generated_id_behavior_with_id_counters_slice(self) -> None:
        profile = (
            profile_toml()
            + textwrap.dedent(
                """\

                [[state.slices]]
                name = "idCounters"
                recordType = "Record<string, number>"
                array = false
                """
            )
        )
        profile_path = write_project(
            self.fs,
            profile=profile,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: confirmed
                Response objects use generated ids with workspace prefix.
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.warnings}
        self.assertTrue(result.ok)
        self.assertNotIn("sidecar.behavior.idCountersMissing", ids)

    def test_warns_for_unconfirmed_slug_id_behavior(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: confirmed
                The response uses slug-style generated ids.
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.warnings}
        self.assertTrue(result.ok)
        self.assertIn("sidecar.behavior.slugIdPolicyUnconfirmed", ids)

    def test_accepts_explicit_slug_id_behavior(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: confirmed
                Slug-style ids are explicitly required by product behavior.
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.warnings}
        self.assertTrue(result.ok)
        self.assertNotIn("sidecar.behavior.slugIdPolicyUnconfirmed", ids)

    def test_errors_for_invalid_behavior_anchor_sections(self) -> None:
        profile_path = write_project(
            self.fs,
            behavior=textwrap.dedent(
                """\
                # Mock Behavior

                ## operation:listWorkspaces
                Status: inferred

                ## operation:list*workspaces
                Status: inferred
                """
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "sidecar.behavior.invalidAnchor")

    def test_errors_for_missing_local_openapi_file(self) -> None:
        profile_path = write_project(self.fs, openapi=None)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.api.openapi.missingLocalFile")

    def test_profile_only_skips_sidecars(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        self.fs.add_file(PROJECT_ROOT / "openapi.yaml", "openapi: 3.1.0\ninfo: {}\npaths: {}\ncomponents:\n  schemas:\n    Workspace: {}\n")
        self.fs.add_file(profile_path, profile_toml())

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertTrue(result.ok)

    def test_errors_for_missing_sidecar_files(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        self.fs.add_file(PROJECT_ROOT / "openapi.yaml", "openapi: 3.1.0\ninfo: {}\npaths: {}\ncomponents:\n  schemas:\n    Workspace: {}\n")
        self.fs.add_file(profile_path, profile_toml())

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.errors}
        self.assertEqual(ids, {"sidecar.behavior.missingFile"})

    def test_parse_failure_returns_profile_parse_error(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        self.fs.add_file(profile_path, "schemaVersion =")

        result = self.validator.validate(profile_path, cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.parse.failed")

    def test_validates_json_profile(self) -> None:
        profile = {
            "schemaVersion": 1,
            "generator": {"name": "mockapi", "version": "0.1.0"},
            "project": {"root": ".", "target": {"packagePath": "mock-server", "packageName": "@local/mock-server", "serverName": "Mock API"}},
            "apis": [{"name": "product-api", "openapi": "https://example.test/openapi.yaml"}],
            "features": [],
            "state": {"schemaVersion": 1, "slices": []},
            "operations": [],
        }
        profile_path = PROJECT_ROOT / ".mockapi/profile.json"
        self.fs.add_file(profile_path, json.dumps(profile))
        self.fs.add_file(PROJECT_ROOT / ".mockapi/behavior.md", "# Behavior\n")

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_errors_for_non_object_json_profile(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.json"
        self.fs.add_file(profile_path, "[]")

        result = self.validator.validate(profile_path, cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.parse.failed")

    def test_errors_for_missing_required_profile_fields(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        self.fs.add_file(profile_path, "schemaVersion = 2\n")

        result = self.validator.validate(profile_path, cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.errors}
        self.assertIn("profile.schemaVersion.invalid", ids)
        self.assertIn("profile.missingGenerator", ids)
        self.assertIn("profile.missingProject", ids)

    def test_errors_for_duplicate_operation_unknown_api_and_feature(self) -> None:
        profile = (
            profile_toml()
            + textwrap.dedent(
                """\

                [[operations]]
                operationId = "listWorkspaces"
                api = "missing-api"
                feature = "missing-feature"
                method = "GET"
                path = "/other"
                """
            )
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        ids = {diagnostic["id"] for diagnostic in result.errors}
        self.assertIn("profile.operation.duplicateOperationId", ids)
        self.assertIn("profile.operation.unknownApi", ids)
        self.assertIn("profile.operation.unknownFeature", ids)

    def test_accepts_state_slice_schema_ref_with_multiple_apis(self) -> None:
        profile = (
            profile_toml()
            .replace(
                'basePath = "/api/v1"\n',
                textwrap.dedent(
                    """\
                    basePath = "/api/v1"

                    [[apis]]
                    name = "other-api"
                    openapi = "https://example.test/openapi.yaml"
                    """
                ),
            )
            .replace(
                'recordType = "Workspace"\n',
                'recordType = "Workspace"\nschemaRef = "product-api#/components/schemas/Workspace"\n',
            )
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_accepts_state_slice_schema_ref_with_local_file(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "product-api:./domains/workspaces.yaml#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)
        self.fs.add_file(
            PROJECT_ROOT / "domains/workspaces.yaml",
            "components:\n  schemas:\n    Workspace:\n      type: object\n",
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_accepts_state_slice_schema_ref_with_json_openapi(self) -> None:
        profile = profile_toml().replace('openapi = "openapi.yaml"', 'openapi = "openapi.json"')
        profile_path = write_project(self.fs, profile=profile, openapi=None)
        self.fs.add_file(PROJECT_ROOT / "openapi.json", '{"components":{"schemas":{"Workspace":{"type":"object"}}}}')

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_errors_for_invalid_state_slice_schema_ref_syntax(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "product-api/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.invalidSchemaRef")

    def test_errors_for_unknown_schema_ref_api(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "missing-api#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.unknownSchemaRefApi")

    def test_errors_for_remote_schema_ref_api(self) -> None:
        profile = profile_toml().replace(
            'openapi = "openapi.yaml"',
            'openapi = "https://example.test/openapi.yaml"',
        )
        profile = profile.replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "product-api#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile, openapi=None)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.remoteSchemaRefUnsupported")

    def test_errors_for_missing_file_qualified_schema_ref_source(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "product-api:./domains/workspaces.yaml#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.schemaRefFileMissing")

    def test_errors_for_unresolved_local_schema_ref_target(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "TrashItem"\nschemaRef = "product-api#/components/schemas/TrashItem"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT, profile_only=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.unresolvedSchemaRef")

    def test_accepts_admin_builtin_state_record_type_without_schema_ref(self) -> None:
        profile = (
            profile_toml()
            .replace(
                'basePath = "/api/v1"\n',
                textwrap.dedent(
                    """\
                    basePath = "/api/v1"

                    [[apis]]
                    name = "other-api"
                    openapi = "https://example.test/openapi.yaml"
                    """
                ),
            )
            .replace(
                'recordType = "Workspace"\n',
                'recordType = "Workspace"\nschemaRef = "product-api#/components/schemas/Workspace"\n',
            )
            + textwrap.dedent(
                """\

                [[state.slices]]
                name = "mockClock"
                recordType = "MockClock"
                array = false
                """
            )
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_accepts_ts_union_state_record_type_without_schema_ref(self) -> None:
        profile = (
            profile_toml()
            .replace(
                'basePath = "/api/v1"\n',
                textwrap.dedent(
                    """\
                    basePath = "/api/v1"

                    [[apis]]
                    name = "other-api"
                    openapi = "https://example.test/openapi.yaml"
                    """
                ),
            )
            .replace(
                'recordType = "Workspace"\n',
                'recordType = "Workspace"\nschemaRef = "product-api#/components/schemas/Workspace"\n',
            )
            + textwrap.dedent(
                """\

                [[state.slices]]
                name = "activeWorkspaceId"
                recordType = "Id | null"
                array = false
                """
            )
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_accepts_ts_scalar_state_record_type_without_schema_ref(self) -> None:
        profile = (
            profile_toml()
            .replace(
                'basePath = "/api/v1"\n',
                textwrap.dedent(
                    """\
                    basePath = "/api/v1"

                    [[apis]]
                    name = "other-api"
                    openapi = "https://example.test/openapi.yaml"
                    """
                ),
            )
            .replace(
                'recordType = "Workspace"\n',
                'recordType = "Workspace"\nschemaRef = "product-api#/components/schemas/Workspace"\n',
            )
            + textwrap.dedent(
                """\

                [[state.slices]]
                name = "activeWorkspaceId"
                recordType = "string"
                array = false
                """
            )
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertTrue(result.ok)

    def test_errors_for_duplicate_feature_state_slice_ownership(self) -> None:
        profile = profile_toml().replace(
            'operations = ["listWorkspaces"]\n',
            textwrap.dedent(
                """\
                operations = ["listWorkspaces"]

                [[features]]
                name = "search"
                stateSlices = ["workspaces"]
                """
            ),
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.feature.duplicateStateSlice")

    def test_errors_for_state_slice_name_that_is_not_typescript_identifier(self) -> None:
        profile = profile_toml().replace('name = "workspaces"\nrecordType = "Workspace"', 'name = "review-sessions"\nrecordType = "Workspace"')
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.invalidName")

    def test_requires_state_slice_schema_ref_when_multiple_apis_are_ambiguous(self) -> None:
        profile = profile_toml().replace(
            'basePath = "/api/v1"\n',
            textwrap.dedent(
                """\
                basePath = "/api/v1"

                [[apis]]
                name = "other-api"
                openapi = "https://example.test/openapi.yaml"
                """
            ),
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.missingSchemaRef")

    def test_errors_for_state_slice_schema_ref_unknown_api(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "missing-api#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.unknownSchemaRefApi")

    def test_errors_for_state_slice_schema_ref_shape(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.invalidSchemaRef")

    def test_errors_for_state_slice_schema_ref_missing_in_root_openapi(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "TrashItem"\nschemaRef = "product-api#/components/schemas/TrashItem"\n',
        )
        profile_path = write_project(
            self.fs,
            profile=profile,
            openapi=(
                "openapi: 3.1.0\n"
                "info:\n"
                "  title: Test API\n"
                "  version: 1.0.0\n"
                "paths: {}\n"
                "components:\n"
                "  schemas:\n"
                "    TrashState:\n"
                "      $ref: './domains/trash.yaml#/components/schemas/TrashState'\n"
            ),
        )

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.unresolvedSchemaRef")
        self.assertIn("components/schemas/TrashItem", result.errors[0]["message"])

    def test_errors_for_state_slice_schema_ref_missing_local_file(self) -> None:
        profile = profile_toml().replace(
            'recordType = "Workspace"\n',
            'recordType = "Workspace"\nschemaRef = "product-api:./domains/missing.yaml#/components/schemas/Workspace"\n',
        )
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.schemaRefFileMissing")

    def test_errors_for_remote_state_slice_schema_source(self) -> None:
        profile = profile_toml().replace('openapi = "openapi.yaml"', 'openapi = "https://example.test/openapi.yaml"')
        profile_path = write_project(self.fs, profile=profile)

        result = self.validator.validate(profile_path, root=Path("."), cwd=PROJECT_ROOT)

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "profile.state.slice.remoteSchemaRefUnsupported")

if __name__ == "__main__":
    unittest.main()
