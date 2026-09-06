"""
Assessment processing service for the EQi-30 AI service.

Pipeline position::

    API route handler
         ↓  receives ``AssessmentRequest`` (wire schema)
    AssessmentService.process()
         ↓  validates, transforms
    AssessmentResult (domain value object)
         ↓  optionally passed to
    ScoringService.score_assessment()
         ↓  delegates to ``ScoringStrategy``
    AssessmentResponse (wire schema)

This service is responsible for:

1. Validating the wire-level ``AssessmentRequest`` against domain rules.
2. Checking instrument version support.
3. Detecting duplicate answers.
4. Validating item references when an item catalogue is available.
5. Validating answer values against instrument-defined ranges.
6. Producing a structured ``AssessmentResult`` for downstream consumption.

It contains **zero** psychometric logic.  It does **not** score.
"""

from __future__ import annotations

from typing import List, Optional

from Apps.ai.core.logging import get_logger
from Apps.ai.domain.assessment import (
    AssessmentAnswer,
    AssessmentInput,
    AssessmentResult,
    AssessmentStatus,
    AssessmentValidationError,
    AssessmentVersionNotSupported,
    DuplicateAnswerError,
    InstrumentRegistry,
    InstrumentVersionConfig,
    InvalidAnswerError,
    UnknownItemReferenceError,
    get_instrument_registry,
)
from Apps.ai.schemas.assessment import AssessmentRequest

logger = get_logger(__name__)


class AssessmentService:
    """Validates and transforms assessment requests into domain objects.

    This class sits between the API layer and the scoring layer.  It
    owns input validation and the construction of the intermediate
    ``AssessmentResult``.  It does **not** score.
    """

    def __init__(
        self,
        instrument_registry: Optional[InstrumentRegistry] = None,
    ) -> None:
        self._instruments = instrument_registry or get_instrument_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, request: AssessmentRequest) -> AssessmentResult:
        """Validate an ``AssessmentRequest`` and produce an ``AssessmentResult``.

        Steps:
        1. Resolve instrument version.
        2. Validate no duplicate item_ids.
        3. Validate individual answers (value range, item reference).
        4. Transform wire responses into domain ``AssessmentAnswer`` objects.
        5. Package into ``AssessmentResult``.

        Raises:
            AssessmentVersionNotSupported: instrument version not registered.
            DuplicateAnswerError: duplicate item_ids in the responses.
            InvalidAnswerError: an answer value is outside the instrument range.
            UnknownItemReferenceError: an item_id is not in the instrument catalogue.
        """
        warnings: List[str] = []

        # 1. Resolve instrument version
        instrument_config = self._resolve_instrument(
            request.instrument_version, warnings
        )

        # 2. Check for duplicate item_ids
        self._check_duplicates(request)

        # 3 & 4. Validate and transform answers
        answers = self._validate_and_transform_answers(
            request, instrument_config, warnings
        )

        # 5. Package into AssessmentInput → AssessmentResult
        assessment_input = AssessmentInput(
            user_ref=request.user_ref,
            instrument_version=request.instrument_version,
            scoring_version=request.scoring_version,
            answers=answers,
            request_id=request.request_id,
            metadata=dict(request.metadata),
        )

        result = AssessmentResult(
            assessment_input=assessment_input,
            status=AssessmentStatus.VALIDATED,
            validation_warnings=warnings,
        )

        logger.info(
            f"Assessment validated: user_ref={request.user_ref!r}, "
            f"instrument={request.instrument_version!r}, "
            f"answers={len(answers)}, "
            f"warnings={len(warnings)}"
        )

        return result

    # ------------------------------------------------------------------
    # Private validation steps
    # ------------------------------------------------------------------

    def _resolve_instrument(
        self,
        instrument_version: str,
        warnings: List[str],
    ) -> Optional[InstrumentVersionConfig]:
        """Look up instrument config or handle empty registry gracefully.

        When no instrument versions have been registered at all (e.g.
        early development before the backend supplies a catalogue), the
        service accepts the request with a warning rather than rejecting
        it.  When at least one version is registered, unrecognised
        versions are rejected.
        """
        if self._instruments.is_empty:
            warnings.append(
                f"No instrument versions registered.  Skipping instrument-level "
                f"validation for version '{instrument_version}'.  Register the "
                f"instrument specification to enable full validation."
            )
            return None

        return self._instruments.get(instrument_version)

    def _check_duplicates(self, request: AssessmentRequest) -> None:
        """Raise ``DuplicateAnswerError`` if any item_id appears more than once."""
        seen: set[str] = set()
        duplicates: list[str] = []
        for r in request.responses:
            if r.item_id in seen and r.item_id not in duplicates:
                duplicates.append(r.item_id)
            seen.add(r.item_id)
        if duplicates:
            raise DuplicateAnswerError(duplicates)

    def _validate_and_transform_answers(
        self,
        request: AssessmentRequest,
        instrument_config: Optional[InstrumentVersionConfig],
        warnings: List[str],
    ) -> List[AssessmentAnswer]:
        """Validate each answer and transform into domain objects."""
        answers: List[AssessmentAnswer] = []

        for response in request.responses:
            # Value range validation (if instrument defines bounds)
            if instrument_config is not None:
                self._validate_value_range(
                    response.item_id,
                    response.value,
                    instrument_config,
                )

                # Item reference validation (if catalogue provided)
                if instrument_config.known_item_ids is not None:
                    if response.item_id not in instrument_config.known_item_ids:
                        raise UnknownItemReferenceError(
                            item_id=response.item_id,
                            instrument_version=request.instrument_version,
                        )
                else:
                    # Only warn once per request
                    if not any("item catalogue" in w for w in warnings):
                        warnings.append(
                            f"Item catalogue not available for instrument "
                            f"'{instrument_config.version}'.  "
                            f"Item reference validation skipped."
                        )

            answers.append(
                AssessmentAnswer(
                    item_id=response.item_id,
                    value=response.value,
                )
            )

        # Item count validation (if instrument defines expected count)
        if (
            instrument_config is not None
            and instrument_config.expected_item_count is not None
        ):
            if len(answers) != instrument_config.expected_item_count:
                raise AssessmentValidationError(
                    message=(
                        f"Expected {instrument_config.expected_item_count} answers "
                        f"for instrument '{instrument_config.version}', "
                        f"got {len(answers)}."
                    ),
                    details={
                        "expected": instrument_config.expected_item_count,
                        "received": len(answers),
                        "instrument_version": instrument_config.version,
                    },
                )

        return answers

    @staticmethod
    def _validate_value_range(
        item_id: str,
        value: float,
        config: InstrumentVersionConfig,
    ) -> None:
        """Raise ``InvalidAnswerError`` if value is outside instrument bounds."""
        if config.value_min is not None and value < config.value_min:
            raise InvalidAnswerError(
                item_id=item_id,
                reason=(
                    f"Value {value} is below the minimum {config.value_min} "
                    f"for instrument '{config.version}'."
                ),
            )
        if config.value_max is not None and value > config.value_max:
            raise InvalidAnswerError(
                item_id=item_id,
                reason=(
                    f"Value {value} exceeds the maximum {config.value_max} "
                    f"for instrument '{config.version}'."
                ),
            )


__all__ = [
    "AssessmentService",
]
