# Microservice-Contract-Verifier

Lightweight utility for continuously validating service contracts so API drift is detected quickly.

## Features

- Continuously test contracts with `validate_stream`
- Validate request/response schemas and invariants
- Detect contract violations in real time via listeners

## Quick Example

```python
from contract_verifier import ContractVerifier

verifier = ContractVerifier()
verifier.register_contract(
    "billing",
    "/charge",
    request_schema={"invoice_id": str, "amount": int},
    response_schema={"status": str, "charged_amount": int},
    request_invariants=(lambda payload: payload["amount"] > 0,),
    response_invariants=(lambda payload: payload["charged_amount"] >= 0,),
)

verifier.add_violation_listener(lambda v: print(f"[ALERT] {v.service}{v.endpoint}: {v.message}"))

violations = verifier.validate_interaction(
    "billing",
    "/charge",
    request={"invoice_id": "inv-100", "amount": 50},
    response={"status": "ok", "charged_amount": 50},
)
```

Each violation is stored in `verifier.violations` and emitted to listeners immediately.
