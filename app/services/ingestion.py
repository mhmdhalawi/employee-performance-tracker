import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from app.core.config import get_settings
from app.core.errors import SchemaValidationError
from app.schemas.kpi import BatchResult
from app.schemas.mapping import AgentMappingProposal, MappingMode, ResolvedMapping
from app.services.file_processor import column_previews, load_frame, normalize_frame
from app.services.kpi_engine import calculate_batch_kpis
from app.services.mapping_agent import propose_mapping
from app.services.profiles import (
    ColumnMapping,
    RoleProfile,
    build_column_mapping,
    detect_profile,
    get_profile,
)


@dataclass
class IngestionOutcome:
    batch: BatchResult
    profile_detected: bool
    mapping_mode_used: MappingMode
    resolved_mappings: list[ResolvedMapping] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ai_notes: str | None = None


@dataclass
class _Resolution:
    profile: RoleProfile
    mapping: ColumnMapping
    profile_detected: bool
    mode_used: MappingMode
    resolved: list[ResolvedMapping] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ai_notes: str | None = None


def _alias_resolved(mapping: ColumnMapping) -> list[ResolvedMapping]:
    resolved = [
        ResolvedMapping(column=column, field=metric, source="alias")
        for metric, column in mapping.metric_columns.items()
    ]
    for column, label in (
        (mapping.id_column, "employee_id"),
        (mapping.name_column, "employee_name"),
        (mapping.period_column, "period"),
    ):
        if column:
            resolved.append(ResolvedMapping(column=column, field=label, source="alias"))
    return resolved


async def resolve_mapping(
    frame: pd.DataFrame,
    profile_key: str | None,
    mode: MappingMode,
) -> _Resolution:
    """Decide which column feeds which canonical field.

    ``aliases`` uses only the declared alias tables. ``hybrid`` runs the alias tables first and
    asks the agent about whatever is left over. ``ai`` hands every column to the agent. Both AI
    modes degrade to ``aliases`` when no model is configured, and the mode actually used is
    reported back.
    """
    headers = [str(c) for c in frame.columns]

    if profile_key:
        profile = get_profile(profile_key)
        detected = False
        matched = len(build_column_mapping(headers, profile).metric_columns)
    else:
        profile, matched = detect_profile(headers)
        detected = True

    use_agent = mode in ("hybrid", "ai")

    if mode == "ai":
        # Every column goes to the agent; alias tables are not consulted at all.
        mapping = ColumnMapping(unmapped=headers.copy())
        resolved: list[ResolvedMapping] = []
    else:
        mapping = build_column_mapping(headers, profile)
        resolved = _alias_resolved(mapping)

    if not use_agent:
        if matched == 0:
            raise SchemaValidationError(
                "Could not match any known metric columns to a role profile. Send an explicit "
                "'profile', use mapping_mode='hybrid' to let the AI agent map the columns, or "
                "rename the columns.",
                {"headers": headers, "available_profiles": sorted(("support", "developer"))},
            )
        return _Resolution(profile, mapping, detected, "aliases", resolved)

    proposal = await propose_mapping(
        previews=column_previews(frame),
        candidate_columns=mapping.unmapped.copy(),
        profile_hint=profile.key if matched else None,
    )

    if proposal is None:
        if matched == 0:
            raise SchemaValidationError(
                "No metric columns matched the alias tables and AI mapping is unavailable "
                "(set OPENAI_API_KEY or send an explicit 'profile').",
                {"headers": headers},
            )
        return _Resolution(profile, mapping, detected, "aliases", resolved)

    # The agent may re-pick the profile, but only when header matching found nothing and the
    # caller did not name one — an explicit profile always wins.
    if profile_key is None and not matched:
        profile = get_profile(proposal.profile)
        detected = True

    return _merge_proposal(profile, mapping, resolved, proposal, detected, mode)


def _merge_proposal(
    profile: RoleProfile,
    mapping: ColumnMapping,
    resolved: list[ResolvedMapping],
    proposal: AgentMappingProposal,
    detected: bool,
    mode: MappingMode,
) -> _Resolution:
    settings = get_settings()
    warnings: list[str] = []
    valid_metrics = profile.metric_names()

    for suggestion in proposal.mappings:
        if suggestion.metric not in valid_metrics:
            # Possible when the agent switched profile mid-run; skip rather than mis-score.
            warnings.append(
                f"Ignored AI mapping {suggestion.source_column!r} -> {suggestion.metric!r}: "
                f"not a metric of profile {profile.key!r}."
            )
            continue
        if suggestion.metric in mapping.metric_columns:
            continue  # alias matching already owns this metric
        if suggestion.source_column not in mapping.unmapped:
            continue

        mapping.metric_columns[suggestion.metric] = suggestion.source_column
        mapping.unmapped.remove(suggestion.source_column)
        resolved.append(
            ResolvedMapping(
                column=suggestion.source_column,
                field=suggestion.metric,
                source="ai",
                confidence=suggestion.confidence,
                reasoning=suggestion.reasoning,
            )
        )
        if suggestion.confidence < settings.ai_mapping_low_confidence:
            warnings.append(
                f"Low-confidence AI mapping ({suggestion.confidence:.2f}): "
                f"{suggestion.source_column!r} -> {suggestion.metric!r}. "
                f"Reason given: {suggestion.reasoning}"
            )

    for column, label, attr in (
        (proposal.identifier_column, "employee_id", "id_column"),
        (proposal.name_column, "employee_name", "name_column"),
        (proposal.period_column, "period", "period_column"),
    ):
        if not column or getattr(mapping, attr) is not None:
            continue
        if column not in mapping.unmapped:
            continue
        setattr(mapping, attr, column)
        mapping.unmapped.remove(column)
        resolved.append(ResolvedMapping(column=column, field=label, source="ai"))

    if mapping.id_column is None:
        raise SchemaValidationError(
            "No employee identifier column could be identified, by aliases or by the AI agent.",
            {"expected_any_of": list(profile.id_aliases), "columns": mapping.unmapped},
        )
    if not mapping.metric_columns:
        raise SchemaValidationError(
            "No column could be mapped to a scorable metric.",
            {"columns": mapping.unmapped},
        )

    return _Resolution(
        profile=profile,
        mapping=mapping,
        profile_detected=detected,
        mode_used=mode,
        resolved=resolved,
        warnings=warnings,
        ai_notes=proposal.notes,
    )


async def ingest_file(
    filename: str,
    content: bytes,
    profile_key: str | None = None,
    mode: MappingMode = "hybrid",
) -> IngestionOutcome:
    """Full ingestion: parse, resolve the column mapping, normalize, score.

    Raises AppError subclasses for unusable files; row-level problems land in
    ``outcome.batch.issues``.
    """
    frame = load_frame(filename, content)
    resolution = await resolve_mapping(frame, profile_key, mode)

    records, issues = normalize_frame(frame, resolution.profile, resolution.mapping)
    employees = calculate_batch_kpis(records, resolution.profile, resolution.mapping)

    batch = BatchResult(
        batch_id=uuid.uuid4().hex,
        created_at=datetime.now(UTC),
        filename=filename,
        profile=resolution.profile.key,
        row_count=len(frame.index),
        scored_count=len(employees),
        employees=employees,
        issues=issues,
    )

    return IngestionOutcome(
        batch=batch,
        profile_detected=resolution.profile_detected,
        mapping_mode_used=resolution.mode_used,
        resolved_mappings=resolution.resolved,
        unmapped_columns=resolution.mapping.unmapped,
        warnings=resolution.warnings,
        ai_notes=resolution.ai_notes,
    )
