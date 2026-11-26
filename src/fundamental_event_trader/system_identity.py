"""A conditional research probe is never an admitted event specialist."""
from __future__ import annotations

import json


def identity():
    return {"schema_version": 1, "system": "fundamental-event-trader", "role": "company_events",
        "primary": None, "configuration_consistent": True,
        "primary_source": "no_broad_data_qualified_primary_admitted",
        "native_clock": "acceptance_known_then_next_adjusted_open",
        "conditional_probes_are_primaries": False, "configuration_sha256": {},
        "action_authorized": False, "portfolio_allocation_allowed": False}


if __name__ == "__main__":
    print(json.dumps(identity(), sort_keys=True))
