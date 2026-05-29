from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import PROJECT_ROOT, profile_model, profile_toml

from mockapi_runtime.context import create_generate_context, feature_operations
from mockapi_runtime.diagnostics import (
    ProfileSummary,
    ValidationFailureResult,
    ValidationSuccessResult,
    format_validation_result,
    validation_result_to_payload,
)
from mockapi_runtime.models import ProfileApi, ProfileFeature, ProfileOperation, ProfileStateSlice
from mockapi_runtime.paths import is_http_url, relative_file_path, to_camel_case, to_identifier
from mockapi_runtime.render_utils import (
    api_module_name,
    contract_output,
    openapi_input_from_package,
    operation_factory_name,
    operation_file_name,
    operation_method_name,
    quote,
    runtime_output,
    state_slice_property_type,
    state_type_name,
)


class HelperTests(unittest.TestCase):
    def test_diagnostics_formatting(self) -> None:
        self.assertEqual(
            format_validation_result(
                ValidationSuccessResult(
                    errors=[],
                    warnings=[],
                    profile=ProfileSummary(operationCount=2, schemaVersion=1),
                )
            ),
            "Result: ok: true, operationCount: 2, no errors, no warnings.",
        )
        self.assertIn(
            "profile summary unavailable",
            format_validation_result(ValidationFailureResult(errors=[{"id": "test.error", "message": "error"}], warnings=[{"id": "test.warning", "message": "warning"}])),
        )
        formatted_failure = format_validation_result(
            ValidationFailureResult(
                errors=[{"id": "test.error", "message": "error", "path": "profile.toml"}],
                warnings=[{"id": "test.warning", "message": "warning"}],
            )
        )
        self.assertIn("Errors:\n- test.error profile.toml: error", formatted_failure)
        self.assertIn("Warnings:\n- test.warning: warning", formatted_failure)

    def test_validation_result_payload_omits_missing_profile(self) -> None:
        payload = validation_result_to_payload(ValidationFailureResult(errors=[], warnings=[]))

        self.assertFalse(payload["ok"])
        self.assertNotIn("profile", payload)

    def test_path_helpers(self) -> None:
        self.assertTrue(is_http_url("HTTPS://example.test/openapi.yaml"))
        self.assertFalse(is_http_url("/openapi.yaml"))
        self.assertEqual(relative_file_path(Path("/project/out"), Path("/project/out/src/app.ts")), "./src/app.ts")
        self.assertEqual(to_identifier("product api"), "ProductApi")
        self.assertEqual(to_identifier(" ! "), "Value")
        self.assertEqual(to_camel_case("product api"), "productApi")

    def test_render_utils(self) -> None:
        profile = profile_model()
        api = ProfileApi(name="Product API", openapi="openapi.yaml")
        operation = ProfileOperation(operationId="list-workspaces", api="product-api", feature="workspaces", method="GET", path="/workspaces")
        state_slice = profile.state.slices[0]

        self.assertEqual(quote("a\nb"), '"a\\nb"')
        self.assertEqual(api_module_name(api), "Product-API")
        self.assertEqual(runtime_output(api), "src/generated/Product-API/mock-runtime.ts")
        self.assertEqual(contract_output(api), "src/generated/Product-API/contract")
        self.assertEqual(openapi_input_from_package(api, PROJECT_ROOT, PROJECT_ROOT / "mock-server"), "../openapi.yaml")
        self.assertEqual(
            openapi_input_from_package(
                profile_model(
                    """\
                    schemaVersion = 1

                    [generator]
                    name = "mockapi"
                    version = "0.1.0"

                    [project]
                    root = "."

                    [project.target]
                    packagePath = "mock-server"
                    packageName = "@local/mock-server"
                    serverName = "Mock API"

                    [[apis]]
                    name = "product-api"
                    openapi = "https://example.test/openapi.yaml"

                    [state]
                    schemaVersion = 1
                    """
                ).apis[0],
                PROJECT_ROOT,
                PROJECT_ROOT,
            ),
            "https://example.test/openapi.yaml",
        )
        self.assertEqual(state_type_name(state_slice), "WorkspaceRecord")
        self.assertEqual(state_slice_property_type(state_slice), "WorkspaceRecord[]")
        self.assertEqual(state_slice_property_type(ProfileStateSlice(name="config", recordType="Record<string, unknown>", array=False)), "Record<string, unknown>")
        self.assertEqual(operation_method_name(operation), "list_workspaces")
        self.assertEqual(operation_file_name(operation), "list_workspaces.ts")
        self.assertEqual(operation_factory_name(operation), "newListWorkspacesController")

        create_operation = ProfileOperation(
            operationId="createFolder",
            api="product-api",
            feature="folders",
            method="POST",
            path="/folders",
        )
        self.assertEqual(operation_factory_name(create_operation), "newCreateFolderController")

    def test_context_groups_operations_by_feature(self) -> None:
        profile = profile_model(
            """\
            schemaVersion = 1

            [generator]
            name = "mockapi"
            version = "0.1.0"

            [project]
            root = "."

            [project.target]
            packagePath = "mock-server"
            packageName = "@local/mock-server"
            serverName = "Mock API"

            [[features]]
            name = "workspaces"

            [[operations]]
            operationId = "listWorkspaces"
            api = "product-api"
            feature = "workspaces"
            method = "GET"
            path = "/workspaces"

            [[operations]]
            operationId = "getWorkspace"
            api = "product-api"
            feature = "workspaces"
            method = "GET"
            path = "/workspaces/{id}"

            [state]
            schemaVersion = 1
            """
        )

        context = create_generate_context(profile, PROJECT_ROOT)

        self.assertEqual(context.outRoot, PROJECT_ROOT / "mock-server")
        self.assertEqual([operation.operationId for operation in feature_operations(context, profile.features[0])], ["listWorkspaces", "getWorkspace"])
        self.assertEqual(feature_operations(context, ProfileFeature(name="missing")), [])

    def test_profile_fixture_remains_parseable_toml_text(self) -> None:
        self.assertIn("schemaVersion = 1", profile_toml())


if __name__ == "__main__":
    unittest.main()
