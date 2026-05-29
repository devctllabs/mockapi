from __future__ import annotations

from pathlib import Path

from .models import GenerateContext, Profile, ProfileFeature, ProfileOperation


def create_generate_context(profile: Profile, root: Path, out: str | None = None) -> GenerateContext:
    resolved_root = root.resolve()
    out_root = (resolved_root / (out or profile.project.target.packagePath)).resolve()
    operations_by_feature: dict[str, list[ProfileOperation]] = {}

    for feature in profile.features:
        operations_by_feature[feature.name] = []

    for operation in profile.operations:
        operations_by_feature.setdefault(operation.feature, []).append(operation)

    return GenerateContext(
        operationsByFeature={feature: tuple(operations) for feature, operations in operations_by_feature.items()},
        outRoot=out_root,
        profile=profile,
        root=resolved_root,
    )


def feature_operations(context: GenerateContext, feature: ProfileFeature) -> list[ProfileOperation]:
    return list(context.operationsByFeature.get(feature.name, ()))
