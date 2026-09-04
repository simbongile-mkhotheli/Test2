from ui.dashboard import Dashboard


class _AlertListbox:
    """Small Tk Listbox substitute for dashboard alert behavior tests."""

    def __init__(self):
        self.messages: list[str] = []

    def delete(self, _start, _end=None):
        self.messages.clear()

    def insert(self, _index, message: str):
        self.messages.append(message)


class _Value:
    """Minimal Tk variable substitute for count-panel tests."""

    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


def test_dashboard_clears_position_alerts_but_keeps_live_absence_alerts():
    dashboard = Dashboard.__new__(Dashboard)
    dashboard._alert_entries = []
    dashboard._alerts = _AlertListbox()

    dashboard._record_alert("RANGE", "RANGE ALERT | 1-6 is absent.")
    dashboard._record_alert("POSITION_COLOR", "UPCOMING POSITION ALERT | Position 2.")
    dashboard._record_alert("POSITION_RANGE", "UPCOMING RANGE ALERT | Position 2.")
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


def test_dashboard_uses_live_history_for_range_and_color_counts():
    dashboard = Dashboard.__new__(Dashboard)
    dashboard._range_vars = {label: _Value() for label in ("1-6", "7-12", "13-18")}
    dashboard._color_vars = {label: _Value() for label in ("Black", "Gray", "Red")}

    dashboard._update_live_counts(
        {
            "range_counts": {"1-6": 12, "7-12": 9, "13-18": 7},
            "color_counts": {"Black": 10, "Gray": 8, "Red": 10},
        }
    )

    assert dashboard._range_vars["1-6"].value == "12"
    assert dashboard._range_vars["13-18"].value == "7"
    assert dashboard._color_vars["Black"].value == "10"
    assert dashboard._color_vars["Gray"].value == "8"
