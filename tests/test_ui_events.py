from ui.events import EventBus


def test_event_bus_delivers_events_in_publish_order():
    events = EventBus()
    events.publish("status", message="Connecting")
    events.publish("connected")

    drained = events.drain()

    assert [(event.kind, event.payload) for event in drained] == [
        ("status", {"message": "Connecting"}),
        ("connected", {}),
    ]
    assert events.drain() == []
