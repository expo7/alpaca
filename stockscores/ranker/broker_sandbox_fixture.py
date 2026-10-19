"""Fictional applicant data for the superuser-only Broker sandbox demo."""

from uuid import uuid4

from django.utils import timezone


def synthetic_application(*, options=False):
    suffix = uuid4().hex[:12]
    # Sandbox-only fictional data. Alpaca rejects 666 as an SSN area number.
    # Use the 119 area shown in Alpaca's published sandbox examples with a unique suffix.
    tax_id = f"119-{int(suffix[:2], 16) % 90 + 10:02d}-{int(suffix[2:6], 16) % 9000 + 1000:04d}"
    signed_at = timezone.now().isoformat()
    agreements = [{"agreement": "customer_agreement", "signed_at": signed_at, "ip_address": "127.0.0.1"}]
    if options:
        agreements.append({"agreement": "options_agreement", "signed_at": signed_at, "ip_address": "127.0.0.1"})
    identity = {
        "given_name": "Quantelle", "family_name": f"Sandbox{suffix}",
        "date_of_birth": "1990-01-01", "tax_id_type": "USA_SSN", "tax_id": tax_id,
        "country_of_citizenship": "USA", "country_of_birth": "USA", "country_of_tax_residence": "USA",
        "funding_source": ["employment_income"],
    }
    if options:
        identity.update({
            "annual_income_min": "100000", "annual_income_max": "150000",
            "total_net_worth_min": "100000", "total_net_worth_max": "150000",
            "liquid_net_worth_min": "100000", "liquid_net_worth_max": "150000",
            "investment_experience_with_stocks": "over_5_years",
            "investment_experience_with_options": "over_5_years",
            "marital_status": "SINGLE", "number_of_dependents": 0,
        })
    return {
        "account_type": "trading", "enabled_assets": ["us_equity", "us_option"] if options else ["us_equity"],
        "contact": {
            "email_address": f"quantelle-sandbox-{suffix}@example.com", "phone_number": "650-555-0100",
            "street_address": ["20 N San Mateo Dr"], "city": "San Mateo", "state": "CA",
            "postal_code": "94401", "country": "USA",
        },
        "identity": identity,
        "disclosures": {"is_control_person": False, "is_affiliated_exchange_or_finra": False,
                        "is_affiliated_exchange_or_iiroc": False, "is_politically_exposed": False,
                        "immediate_family_exposed": False, "is_discretionary": False},
        "agreements": agreements,
        **({"liquidity_needs": "does_not_matter", "risk_tolerance": "moderate",
            "investment_objective": "market_speculation", "investment_time_horizon": "more_than_10_years"} if options else {}),
    }
