from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Mapping, Sequence


SchemaType = Mapping[str, type | tuple[type, ...]]
Invariant = Callable[[Mapping[str, object]], bool]
ViolationListener = Callable[["ContractViolation"], None]


@dataclass(frozen=True)
class ServiceContract:
    request_schema: SchemaType
    response_schema: SchemaType
    request_invariants: Sequence[Invariant]
    response_invariants: Sequence[Invariant]


@dataclass(frozen=True)
class ContractViolation:
    service: str
    endpoint: str
    stage: str
    message: str
    timestamp: datetime


class ContractVerifier:
    def __init__(self) -> None:
        self._contracts: Dict[tuple[str, str], ServiceContract] = {}
        self._listeners: List[ViolationListener] = []
        self.violations: List[ContractViolation] = []

    def register_contract(
        self,
        service: str,
        endpoint: str,
        *,
        request_schema: SchemaType,
        response_schema: SchemaType,
        request_invariants: Iterable[Invariant] = (),
        response_invariants: Iterable[Invariant] = (),
    ) -> None:
        self._contracts[(service, endpoint)] = ServiceContract(
            request_schema=request_schema,
            response_schema=response_schema,
            request_invariants=tuple(request_invariants),
            response_invariants=tuple(response_invariants),
        )

    def add_violation_listener(self, listener: ViolationListener) -> None:
        self._listeners.append(listener)

    def validate_interaction(
        self,
        service: str,
        endpoint: str,
        *,
        request: Mapping[str, object],
        response: Mapping[str, object],
    ) -> list[ContractViolation]:
        contract = self._contracts.get((service, endpoint))
        if contract is None:
            return [
                self._record_violation(
                    service,
                    endpoint,
                    "contract",
                    "No registered contract for service endpoint.",
                )
            ]

        violations: list[ContractViolation] = []
        request_violations = self._validate_payload(service, endpoint, "request", request, contract.request_schema)
        response_violations = self._validate_payload(service, endpoint, "response", response, contract.response_schema)

        violations.extend(request_violations)
        violations.extend(response_violations)

        if not request_violations:
            violations.extend(self._validate_invariants(service, endpoint, "request", request, contract.request_invariants))
        if not response_violations:
            violations.extend(self._validate_invariants(service, endpoint, "response", response, contract.response_invariants))
        return violations

    def validate_stream(self, interactions: Iterable[Mapping[str, object]]) -> list[ContractViolation]:
        violations: list[ContractViolation] = []
        for interaction in interactions:
            violations.extend(
                self.validate_interaction(
                    str(interaction["service"]),
                    str(interaction["endpoint"]),
                    request=interaction["request"],  # type: ignore[arg-type]
                    response=interaction["response"],  # type: ignore[arg-type]
                )
            )
        return violations

    def _validate_payload(
        self,
        service: str,
        endpoint: str,
        stage: str,
        payload: Mapping[str, object],
        schema: SchemaType,
    ) -> list[ContractViolation]:
        violations: list[ContractViolation] = []
        for field, expected_type in schema.items():
            if field not in payload:
                violations.append(
                    self._record_violation(
                        service,
                        endpoint,
                        stage,
                        f"Missing required field '{field}'.",
                    )
                )
                continue

            value = payload[field]
            if not isinstance(value, expected_type):
                violations.append(
                    self._record_violation(
                        service,
                        endpoint,
                        stage,
                        f"Field '{field}' expected {expected_type} but got {type(value)}.",
                    )
                )
        return violations

    def _validate_invariants(
        self,
        service: str,
        endpoint: str,
        stage: str,
        payload: Mapping[str, object],
        invariants: Iterable[Invariant],
    ) -> list[ContractViolation]:
        violations: list[ContractViolation] = []
        for invariant in invariants:
            try:
                is_valid = bool(invariant(payload))
            except Exception as exc:
                is_valid = False
                message = f"Invariant '{invariant.__name__}' raised {exc.__class__.__name__}: {exc}"
            else:
                message = f"Invariant '{invariant.__name__}' failed."

            if not is_valid:
                violations.append(self._record_violation(service, endpoint, stage, message))
        return violations

    def _record_violation(self, service: str, endpoint: str, stage: str, message: str) -> ContractViolation:
        violation = ContractViolation(
            service=service,
            endpoint=endpoint,
            stage=stage,
            message=message,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.violations.append(violation)
        for listener in self._listeners:
            listener(violation)
        return violation
