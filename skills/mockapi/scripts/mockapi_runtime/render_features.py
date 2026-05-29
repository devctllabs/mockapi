from __future__ import annotations

from pathlib import Path

from .context import feature_operations
from .filesystem import FileSystem
from .files import planned_write
from .models import GenerateContext, PlannedWrite, ProfileFeature, ProfileOperation, ProfileStateSlice
from .render_utils import (
    STARTER_HEADER,
    feature_seed_function_name,
    operation_factory_name,
    operation_file_name,
    quote,
)
from .templates import TemplateService


def feature_root(context: GenerateContext, feature: ProfileFeature) -> Path:
    return context.outRoot / "src/features" / feature.name


def operation_controller_path(
    context: GenerateContext,
    feature: ProfileFeature,
    operation: ProfileOperation,
) -> Path:
    return feature_root(context, feature) / "controllers" / operation_file_name(operation)


def feature_seed_path(context: GenerateContext, feature: ProfileFeature) -> Path:
    return feature_root(context, feature) / "seed.ts"


def render_operation_controller(operation: ProfileOperation, template_service: TemplateService) -> str:
    behavior_anchor = f"operation:{operation.operationId}"
    todo_message = (
        f"TODO mockapi: wire {operation.operationId} to feature service/repository behavior from "
        f".mockapi/behavior.md anchor {behavior_anchor}"
    )
    controller_methods = "\n".join(
        [
            f"  {operation.operationId}: async (_input, _context) => {{",
            f"    throw new Error({quote(todo_message)})",
            "  },",
        ]
    )
    return template_service.render(
        "operation-controller.ts.tpl",
        {
            "CONTROLLER_METHODS": controller_methods,
            "FACTORY_NAME": operation_factory_name(operation),
            "PICK_KEYS": quote(operation.operationId),
            "STARTER_HEADER": STARTER_HEADER,
        },
    )


def seed_value_for_slice(state_slice: ProfileStateSlice) -> str:
    if state_slice.array is False:
        return f"{{}} as MockState[{quote(state_slice.name)}]"
    return "[]"


def render_feature_seed(feature: ProfileFeature, state_slices: tuple[ProfileStateSlice, ...], template_service: TemplateService) -> str:
    slice_seeds = "\n".join(
        f"  {state_slice.name}: {seed_value_for_slice(state_slice)},"
        for state_slice in state_slices
    )
    pick_keys = " | ".join(quote(state_slice.name) for state_slice in state_slices)
    return template_service.render(
        "feature-seed.ts.tpl",
        {
            "FUNCTION_NAME": feature_seed_function_name(feature),
            "PICK_KEYS": pick_keys,
            "SLICE_SEEDS": slice_seeds,
            "STARTER_HEADER": STARTER_HEADER,
        },
    )


class FeatureRenderService:
    def __init__(self, fs: FileSystem, template_service: TemplateService) -> None:
        self.fs = fs
        self.template_service = template_service

    def planned_writes(self, context: GenerateContext) -> list[PlannedWrite]:
        writes: list[PlannedWrite] = []
        state_slices_by_name = {state_slice.name: state_slice for state_slice in context.profile.state.slices}
        for feature in context.profile.features:
            feature_state_slices = tuple(state_slices_by_name[name] for name in feature.stateSlices if name in state_slices_by_name)
            seed_path = feature_seed_path(context, feature)
            if feature_state_slices and not self.fs.is_file(seed_path):
                writes.append(planned_write(seed_path, render_feature_seed(feature, feature_state_slices, self.template_service), overwrite=False))
            for operation in feature_operations(context, feature):
                controller_path = operation_controller_path(context, feature, operation)
                if not self.fs.is_file(controller_path):
                    writes.append(
                        planned_write(controller_path, render_operation_controller(operation, self.template_service), overwrite=False)
                    )
        return writes
