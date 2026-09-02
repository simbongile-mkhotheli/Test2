from ui.dashboard import Dashboard


class _AlertListbox:
    """Small Tk Listbox substitute for dashboard alert behavior tests."""

    def __init__(self):
        self.messages: list[str] = []

    def delete(self, _start, _end=None):
        self.messages.clear()

    def insert(self, _index, message: str):
        self.messages.append(message)


def test_dashboard_clears_position_alerts_but_keeps_live_absence_alerts():
    dashboard = Dashboard.__new__(Dashboard)
    dashboard._alert_entries = []
    dashboard._alerts = _AlertListbox()

    dashboard._record_alert("RANGE", "RANGE ALERT | 1-6 is absent.")
    dashboard._record_alert("POSITION_COLOR", "UPCOMING POSITION ALERT | Position 2.")
    dashboard._record_alert("COLOR", "COLOR ALERT | Red is absent.")
    dashboard._clear_position_alerts()

    assert dashboard._alert_entries == [
        ("COLOR", "COLOR ALERT | Red is absent."),
        ("RANGE", "RANGE ALERT | 1-6 is absent."),
    ]
    assert dashboard._alerts.messages == [
        "COLOR ALERT | Red is absent.",
        "RANGE ALERT | 1-6 is absent.",
    ]
