from fundamental_event_trader.system_identity import identity


def test_conditional_event_results_do_not_create_a_qualified_primary():
    value = identity()
    assert value["primary"] is None
    assert value["conditional_probes_are_primaries"] is False
    assert value["action_authorized"] is False
