import unittest

from contract_verifier import ContractVerifier


class ContractVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = ContractVerifier()
        self.verifier.register_contract(
            "billing",
            "/charge",
            request_schema={"invoice_id": str, "amount": int},
            response_schema={"status": str, "charged_amount": int},
            request_invariants=(lambda payload: payload["amount"] > 0,),
            response_invariants=(lambda payload: payload["charged_amount"] >= 0,),
        )

    def test_valid_contract_interaction_has_no_violations(self) -> None:
        violations = self.verifier.validate_interaction(
            "billing",
            "/charge",
            request={"invoice_id": "inv-1", "amount": 100},
            response={"status": "ok", "charged_amount": 100},
        )

        self.assertEqual([], violations)

    def test_request_contract_violation_is_detected_in_real_time(self) -> None:
        seen = []
        self.verifier.add_violation_listener(lambda violation: seen.append(violation))

        violations = self.verifier.validate_interaction(
            "billing",
            "/charge",
            request={"invoice_id": "inv-1"},
            response={"status": "ok", "charged_amount": 100},
        )

        self.assertEqual(1, len(violations))
        self.assertEqual(1, len(seen))
        self.assertIn("Missing required field 'amount'", violations[0].message)

    def test_stream_validation_detects_response_invariant_violations(self) -> None:
        violations = self.verifier.validate_stream(
            [
                {
                    "service": "billing",
                    "endpoint": "/charge",
                    "request": {"invoice_id": "inv-1", "amount": 100},
                    "response": {"status": "ok", "charged_amount": 100},
                },
                {
                    "service": "billing",
                    "endpoint": "/charge",
                    "request": {"invoice_id": "inv-2", "amount": 100},
                    "response": {"status": "ok", "charged_amount": -100},
                },
            ]
        )

        self.assertEqual(1, len(violations))
        self.assertEqual("response", violations[0].stage)
        self.assertIn("failed", violations[0].message)


if __name__ == "__main__":
    unittest.main()
