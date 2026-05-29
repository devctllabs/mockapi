from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import MemoryFileSystem, PROJECT_ROOT, profile_toml

from mockapi_runtime.quality import check_generated_quality, format_quality_result


PACKAGE_ROOT = PROJECT_ROOT / "mock-server"


def diagnostic_ids(diagnostics: list[dict[str, str]]) -> set[str]:
    return {diagnostic["id"] for diagnostic in diagnostics}


class GeneratedQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fs = MemoryFileSystem()

    def check(self, profile_path: Path | None = None):
        return check_generated_quality(
            self.fs,
            PACKAGE_ROOT,
            profile_path=profile_path,
        )

    def add_package_file(self, relative_path: str, content: str) -> None:
        self.fs.add_file(PACKAGE_ROOT / relative_path, content)

    def add_profile(self, profile: str) -> None:
        self.fs.add_file(PROJECT_ROOT / ".mockapi/profile.toml", profile)

    def test_errors_when_allocator_used_without_id_counters(self) -> None:
        self.add_package_file(
            "src/features/workspaces/service.ts",
            "const ids = newIdAllocator(state.getSlice('idCounters'))\n",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.idCounters.missingState", diagnostic_ids(result.errors))

    def test_accepts_allocator_when_generated_admin_state_declares_id_counters(self) -> None:
        self.fs.add_file(PACKAGE_ROOT / "openapi/admin.yaml", "components:\n  schemas:\n    MockState:\n      properties:\n        idCounters: {}\n")
        self.add_package_file(
            "src/features/workspaces/service.ts",
            "const ids = newIdAllocator(state.getSlice('idCounters'))\n",
        )

        result = self.check()

        self.assertNotIn("quality.idCounters.missingState", diagnostic_ids(result.errors))

    def test_errors_for_hardcoded_base_path_when_option_exists(self) -> None:
        self.add_package_file(
            "src/app.ts",
            """type Options = { basePath?: string }
export const newApp = ({ basePath = "/api/v1" }: Options = {}) => {
  registerRoutes(app, controllers, { basePath: "/api/v1" })
}
""",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.basePath.ignoredOption", diagnostic_ids(result.errors))

    def test_forgives_malformed_profile_and_still_checks_files(self) -> None:
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        self.fs.add_file(profile_path, "schemaVersion =")
        self.add_package_file(
            "src/app.ts",
            """type Options = { basePath?: string }
export const newApp = ({ basePath = "/api/v1" }: Options = {}) => {
  registerRoutes(app, controllers, { basePath: "/api/v1" })
}
""",
        )

        result = self.check(profile_path)

        self.assertFalse(result.ok)
        self.assertIn("quality.basePath.ignoredOption", diagnostic_ids(result.errors))

    def test_errors_when_final_admin_openapi_contains_external_refs(self) -> None:
        self.fs.add_file(
            PACKAGE_ROOT / "openapi/admin.yaml",
            """openapi: 3.1.0
components:
  schemas:
    WorkspaceRecord:
      $ref: "../../openapi.yaml#/components/schemas/Workspace"
""",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.adminOpenapi.externalRefs", diagnostic_ids(result.errors))

    def test_allows_external_refs_in_admin_openapi_source(self) -> None:
        self.fs.add_file(
            PACKAGE_ROOT / "openapi/admin.source.yaml",
            """openapi: 3.1.0
components:
  schemas:
    WorkspaceRecord:
      $ref: "../../openapi.yaml#/components/schemas/Workspace"
""",
        )

        result = self.check()

        self.assertNotIn("quality.adminOpenapi.externalRefs", diagnostic_ids(result.errors))

    def test_errors_for_remaining_feature_todo(self) -> None:
        self.add_package_file(
            "src/features/workspaces/controllers/createWorkspace.ts",
            "throw new Error('TODO mockapi: implement createWorkspace')\n",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.todo.remaining", diagnostic_ids(result.errors))

    def test_reports_incomplete_implementation_phase_first_for_scaffold(self) -> None:
        self.add_package_file(
            "src/features/workspaces/controllers/createWorkspace.ts",
            "throw new Error('TODO mockapi: implement createWorkspace')\n",
        )
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({ workspaces: [] })
""",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["id"], "quality.phase.incompleteImplementation")
        self.assertIn("quality.todo.remaining", diagnostic_ids(result.errors))
        self.assertIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_errors_when_stateful_completed_feature_has_no_repository(self) -> None:
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({ workspaces: [] })
""",
        )
        self.add_package_file("src/features/workspaces/service.ts", "export class WorkspaceService {}\n")

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.repository.missingFeatureRepository", diagnostic_ids(result.errors))

    def test_accepts_id_counter_only_shared_seed_without_repository(self) -> None:
        self.add_package_file(
            "src/features/shared/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedShared = (): Pick<MockState, "idCounters"> => ({ idCounters: {} })
""",
        )
        self.add_package_file("src/features/shared/service.ts", "export class SharedService {}\n")

        result = self.check()

        self.assertNotIn("quality.repository.missingFeatureRepository", diagnostic_ids(result.errors))

    def test_errors_for_direct_product_slice_access_in_feature_behavior(self) -> None:
        self.add_package_file(
            "src/features/workspaces/service.ts",
            "const workspaces = stateRepository.getSlice('workspaces')\nstateRepository.setSlice('activeWorkspace', {})\n",
        )

        result = self.check()

        self.assertFalse(result.ok)
        self.assertIn("quality.stateAccess.directSliceAccess", diagnostic_ids(result.errors))

    def test_accepts_direct_id_counter_slice_access_in_feature_behavior(self) -> None:
        self.fs.add_file(PACKAGE_ROOT / "openapi/admin.yaml", "idCounters: {}\n")
        self.add_package_file(
            "src/features/workspaces/service.ts",
            "const ids = newIdAllocator(stateRepository.getSlice('idCounters'))\n",
        )

        result = self.check()

        self.assertNotIn("quality.stateAccess.directSliceAccess", diagnostic_ids(result.errors))
        self.assertNotIn("quality.idCounters.missingState", diagnostic_ids(result.errors))

    def test_accepts_clear_style_service_and_repository(self) -> None:
        self.fs.add_file(PACKAGE_ROOT / "openapi/admin.yaml", "idCounters: {}\n")
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({
  workspaces: [{ id: 'workspace-1', title: 'Default Workspace' }],
})
""",
        )
        self.add_package_file(
            "src/features/workspaces/repository.ts",
            """export class WorkspaceRepository {
  constructor(private readonly stateStore: MockStateRepository) {}
  visible() { return this.stateStore.getSlice('workspaces') }
  create(workspace: WorkspaceRecord) { this.stateStore.setSlice('workspaces', [workspace, ...this.visible()]) }
}
""",
        )
        self.add_package_file(
            "src/features/workspaces/service.ts",
            """export class WorkspaceService {
  constructor(private readonly stateStore: MockStateRepository, private readonly workspaces: WorkspaceRepository) {}
  create(draft: WorkspaceDraft) {
    return this.stateStore.transaction(() => {
      const ids = newIdAllocator(this.stateStore.getSlice('idCounters'))
      this.workspaces.create({ ...draft, id: ids.next('workspace'), updatedAt: this.stateStore.now() })
    })
  }
}
""",
        )

        result = self.check()
        ids = diagnostic_ids(result.errors)

        self.assertNotIn("quality.repository.missingFeatureRepository", ids)
        self.assertNotIn("quality.stateAccess.directSliceAccess", ids)
        self.assertNotIn("quality.idCounters.missingState", ids)

    def test_errors_when_seed_enabled_and_product_seed_is_empty(self) -> None:
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({
  workspaces: [
    // generated stub left empty
  ],
})
""",
        )

        result = self.check()

        self.assertIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_accepts_empty_product_seed_when_profile_disables_seed(self) -> None:
        self.add_profile(profile_toml().replace("[state]\nschemaVersion = 1", "[state]\nschemaVersion = 1\nseed = false"))
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({ workspaces: [] })
""",
        )

        result = self.check()

        self.assertNotIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_accepts_non_literal_product_seed_initializer(self) -> None:
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
const seededWorkspaces = () => []
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({
  workspaces: seededWorkspaces(),
})
""",
        )

        result = self.check()

        self.assertNotIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_accepts_nested_product_seed_literal(self) -> None:
        self.add_package_file(
            "src/features/workspaces/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({
  workspaces: [
    {
      id: 'workspace-1',
      folders: [],
    },
  ],
})
""",
        )

        result = self.check()

        self.assertNotIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_accepts_empty_infrastructure_seed(self) -> None:
        self.add_package_file(
            "src/features/shared/seed.ts",
            """import type { MockState } from '../../generated/mock-admin/contract/index.ts'
export const seedShared = (): Pick<MockState, 'idCounters'> => ({ idCounters: {} })
""",
        )

        result = self.check()

        self.assertNotIn("quality.seed.emptyProductSeed", diagnostic_ids(result.errors))

    def test_warns_for_slug_helper_code(self) -> None:
        self.add_package_file("src/lib/domain.ts", "export const slugify = (value: string) => value\n")

        result = self.check()

        self.assertTrue(result.ok)
        self.assertIn("quality.slugIdHelper.present", diagnostic_ids(result.warnings))

    def test_warns_for_oversized_domain_module(self) -> None:
        self.add_package_file("src/lib/domain.ts", "\n".join(f"export const value{i} = {i}" for i in range(251)))

        result = self.check()

        self.assertIn("quality.domainModule.oversized", diagnostic_ids(result.warnings))

    def test_warns_for_snapshot_set_all_and_as_any(self) -> None:
        self.add_package_file(
            "src/features/workspaces/service.ts",
            "const state = repo.snapshot()\nrepo.setAll(state.workspaces)\nconst value = input as any\n",
        )

        result = self.check()

        ids = diagnostic_ids(result.warnings)
        self.assertIn("quality.stateAccess.snapshotSetAll", ids)
        self.assertIn("quality.unsafeCast.asAny", ids)

    def test_warns_when_no_smoke_tests_exist(self) -> None:
        result = self.check()

        warning = next(diagnostic for diagnostic in result.warnings if diagnostic["id"] == "quality.tests.missingSmoke")
        self.assertEqual(warning["path"], "src/app.test.ts")
        self.assertIn("src/app.test.ts", warning["message"])

    def test_warns_when_tests_miss_base_path_smoke(self) -> None:
        self.add_package_file("src/app.test.ts", "test('health', () => {})\n")

        result = self.check()

        warning = next(diagnostic for diagnostic in result.warnings if diagnostic["id"] == "quality.tests.missingBasePathSmoke")
        self.assertEqual(warning["path"], "src/app.test.ts")
        self.assertIn("basePath", warning["message"])

    def test_accepts_base_path_smoke_coverage(self) -> None:
        self.add_package_file("src/app.test.ts", "test('custom basePath', () => {})\n")

        result = self.check()

        self.assertNotIn("quality.tests.missingBasePathSmoke", diagnostic_ids(result.warnings))

    def test_formats_every_error_and_warning(self) -> None:
        self.add_package_file(
            "src/app.ts",
            """type Options = { basePath?: string }
export const newApp = ({ basePath = "/api/v1" }: Options = {}) => {
  registerRoutes(app, controllers, { basePath: "/api/v1" })
}
""",
        )

        output = format_quality_result(self.check())

        self.assertIn("Errors:", output)
        self.assertIn("- quality.basePath.ignoredOption src/app.ts:", output)
        self.assertIn("Warnings:", output)
        self.assertIn("- quality.tests.missingSmoke", output)


if __name__ == "__main__":
    unittest.main()
