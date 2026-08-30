"""Tkinter dashboard for displaying the live tracker session."""

from __future__ import annotations

import tkinter as tk
from threading import Event
from tkinter import ttk

from config import SESSION_DRAW_COUNT
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_COLORS,
    number_band,
    number_color,
)
from ui.events import DashboardEvent, EventBus


class Dashboard:
    """Own all Tk widgets and consume events produced by the tracker worker."""

    _POLL_INTERVAL_MS = 100
    _MAX_LOG_LINES = 250

    def __init__(
        self,
        events: EventBus,
        stop_event: Event,
        start_event: Event,
    ) -> None:
        self.events = events
        self.stop_event = stop_event
        self.start_event = start_event
        self._closing = False

        self.root = tk.Tk()
        self.root.title("BetGames Tracker")
        self.root.minsize(1040, 740)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._connection_var = tk.StringVar(value="Starting browser…")
        self._session_var = tk.StringVar(value="No active session")
        self._progress_var = tk.StringVar(value=f"0 / {SESSION_DRAW_COUNT}")
        self._latest_draw_var = tk.StringVar(value="-")
        self._latest_result_var = tk.StringVar(value="-")
        self._status_var = tk.StringVar(
            value="Open Wheel Of Fortune in the browser, then start tracking."
        )
        self._range_vars = {label: tk.StringVar(value="0") for label, _ in NUMBER_BANDS}
        self._color_vars = {
            label: tk.StringVar(value="0") for label, _ in NUMBER_COLORS
        }
        self._build()
        self._poll_events()

    def run(self) -> None:
        """Run the Tk event loop on the main thread."""
        self.root.mainloop()

    def _build(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)
        container.rowconfigure(4, weight=1)

        self._build_header(container)
        self._build_summary(container)
        self._build_counts(container)
        self._build_results(container)
        self._build_activity(container)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="BetGames Tracker", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, textvariable=self._connection_var).grid(
            row=0, column=1, sticky="e", padx=(12, 0)
        )
        self._start_button = ttk.Button(
            header,
            text="Start tracking",
            command=self._start_tracking,
            state="disabled",
        )
        self._start_button.grid(row=0, column=2, padx=(16, 8))
        ttk.Button(header, text="Stop", command=self._close).grid(row=0, column=3)

        ttk.Label(header, textvariable=self._status_var).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

    def _build_summary(self, parent: ttk.Frame) -> None:
        summary = ttk.LabelFrame(parent, text="Session", padding=12)
        summary.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        for column in range(4):
            summary.columnconfigure(column, weight=1)

        self._summary_value(summary, "Connection", self._connection_var, 0)
        self._summary_value(summary, "Session", self._session_var, 1)
        self._summary_value(summary, "Progress", self._progress_var, 2)
        self._summary_value(summary, "Latest draw", self._latest_draw_var, 3)

        ttk.Label(summary, text="Latest result", foreground="#555555").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            summary,
            textvariable=self._latest_result_var,
            font=("Segoe UI", 16, "bold"),
        ).grid(row=3, column=0, columnspan=4, sticky="w")

    @staticmethod
    def _summary_value(
        parent: ttk.LabelFrame,
        title: str,
        variable: tk.StringVar,
        column: int,
    ) -> None:
        ttk.Label(parent, text=title, foreground="#555555").grid(
            row=0, column=column, sticky="w"
        )
        ttk.Label(parent, textvariable=variable, font=("Segoe UI", 11, "bold")).grid(
            row=1, column=column, sticky="w"
        )

    def _build_counts(self, parent: ttk.Frame) -> None:
        counts = ttk.Frame(parent)
        counts.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        counts.columnconfigure(0, weight=1)
        counts.columnconfigure(1, weight=1)
        counts.columnconfigure(2, weight=2)

        self._build_count_panel(counts, "Range counts", self._range_vars, 0)
        self._build_count_panel(counts, "Color counts", self._color_vars, 1)

        alerts = ttk.LabelFrame(counts, text="Alerts", padding=8)
        alerts.grid(row=0, column=2, sticky="nsew", padx=(16, 0))
        alerts.columnconfigure(0, weight=1)
        alerts.rowconfigure(0, weight=1)
        self._alerts = tk.Listbox(alerts, height=5, activestyle="none")
        self._alerts.grid(row=0, column=0, sticky="nsew")

    @staticmethod
    def _build_count_panel(
        parent: ttk.Frame,
        title: str,
        variables: dict[str, tk.StringVar],
        column: int,
    ) -> None:
        panel = ttk.LabelFrame(parent, text=title, padding=8)
        panel.grid(row=0, column=column, sticky="nsew")
        for row, (label, variable) in enumerate(variables.items()):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w")
            ttk.Label(panel, textvariable=variable, font=("Segoe UI", 11, "bold")).grid(
                row=row, column=1, sticky="e", padx=(24, 0)
            )

    def _build_results(self, parent: ttk.Frame) -> None:
        results = ttk.LabelFrame(parent, text="Captured draws", padding=8)
        results.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        columns = ("position", "draw_id", "result", "range", "color")
        self._draws = ttk.Treeview(results, columns=columns, show="headings", height=12)
        headings = {
            "position": ("Pos", 55),
            "draw_id": ("Draw ID", 240),
            "result": ("Result", 90),
            "range": ("Range", 100),
            "color": ("Color", 100),
        }
        for column, (text, width) in headings.items():
            self._draws.heading(column, text=text)
            self._draws.column(column, width=width, anchor="center")
        self._draws.tag_configure("black", background="#202124", foreground="#ffffff")
        self._draws.tag_configure("gray", background="#d1d5db", foreground="#111827")
        self._draws.tag_configure("red", background="#fee2e2", foreground="#991b1b")
        self._draws.tag_configure("zero", background="#f3f4f6", foreground="#4b5563")
        self._draws.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(results, orient="vertical", command=self._draws.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._draws.configure(yscrollcommand=scrollbar.set)

    def _build_activity(self, parent: ttk.Frame) -> None:
        activity = ttk.LabelFrame(parent, text="Activity", padding=8)
        activity.grid(row=4, column=0, sticky="nsew", pady=(16, 0))
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(0, weight=1)
        self._activity = tk.Text(activity, height=8, state="disabled", wrap="word")
        self._activity.grid(row=0, column=0, sticky="nsew")

    def _poll_events(self) -> None:
        if self._closing:
            return
        for event in self.events.drain():
            self._handle(event)
        self.root.after(self._POLL_INTERVAL_MS, self._poll_events)

    def _handle(self, event: DashboardEvent) -> None:
        payload = event.payload
        if event.kind == "log":
            self._append_activity(
                f"[{payload['timestamp']}] [{payload['level']}] {payload['message']}"
            )
        elif event.kind == "browser_ready":
            self._connection_var.set("Browser ready")
            self._status_var.set("Open Wheel Of Fortune in the browser, then click Start tracking.")
            self._start_button.configure(state="normal")
        elif event.kind == "tracking_started":
            self._connection_var.set("Connecting")
            self._status_var.set("Searching for Wheel Of Fortune…")
        elif event.kind == "connected":
            self._connection_var.set("Connected")
        elif event.kind == "status":
            self._status_var.set(payload["message"])
        elif event.kind == "waiting":
            self._status_var.set(
                f"Waiting for session boundary • draw {payload['draw_id']} "
                f"(position {payload['position']})"
            )
        elif event.kind == "session_started":
            self._session_var.set(payload["session_name"])
            self._progress_var.set(f"0 / {payload['draw_count']}")
            self._latest_draw_var.set("-")
            self._latest_result_var.set("-")
            self._clear_draws()
            self._alerts.delete(0, tk.END)
            self._status_var.set(
                f"Session runs from {payload['start_draw_id']} to {payload['end_draw_id']}."
            )
        elif event.kind == "session_update":
            self._update_session(payload)
        elif event.kind == "alert":
            self._alerts.insert(0, payload["message"])
            self._status_var.set(payload["message"])
        elif event.kind == "session_finished":
            self._status_var.set(f"Session saved to {payload['filename']}")
            self._append_activity("Session complete and saved.")
        elif event.kind == "session_incomplete":
            self._status_var.set("Session incomplete; saved for review.")
            self._append_activity(payload["message"])
        elif event.kind == "tracker_stopped":
            self._connection_var.set("Stopped")
            self._status_var.set("Tracking stopped.")
            self._start_button.configure(state="disabled")
        elif event.kind == "worker_error":
            self._connection_var.set("Error")
            self._status_var.set("Tracker stopped because of an error. See Activity.")
            self._append_activity(payload["message"])
            self._start_button.configure(state="disabled")
        elif event.kind == "worker_stopped":
            if self._connection_var.get() != "Error":
                self._connection_var.set("Stopped")

    def _update_session(self, payload: dict[str, object]) -> None:
        results = tuple(payload["results"])
        self._session_var.set(str(payload["session_name"]))
        self._progress_var.set(f"{len(results)} / {payload['draw_count']}")
        self._clear_draws()
        for position, (draw_id, result) in enumerate(results, start=1):
            color = number_color(result)
            self._draws.insert(
                "",
                "end",
                values=(
                    position,
                    draw_id,
                    result,
                    number_band(result) or "-",
                    color or "-",
                ),
                tags=((color or "zero").lower(),),
            )

        if results:
            draw_id, result = results[-1]
            self._latest_draw_var.set(draw_id)
            self._latest_result_var.set(
                f"{result}  •  {number_band(result) or 'Zero'}  •  "
                f"{number_color(result) or 'Uncolored'}"
            )

        range_counts = payload["range_counts"]
        for label, variable in self._range_vars.items():
            variable.set(str(range_counts[label]))
        color_counts = payload["color_counts"]
        for label, variable in self._color_vars.items():
            variable.set(str(color_counts[label]))

    def _clear_draws(self) -> None:
        self._draws.delete(*self._draws.get_children())

    def _append_activity(self, message: str) -> None:
        self._activity.configure(state="normal")
        self._activity.insert(tk.END, message + "\n")
        line_count = int(self._activity.index("end-1c").split(".")[0])
        if line_count > self._MAX_LOG_LINES:
            self._activity.delete("1.0", f"{line_count - self._MAX_LOG_LINES + 1}.0")
        self._activity.see(tk.END)
        self._activity.configure(state="disabled")

    def _start_tracking(self) -> None:
        if self.start_event.is_set() or self._closing:
            return
        self.start_event.set()
        self._start_button.configure(state="disabled")
        self._status_var.set("Starting tracker…")

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.stop_event.set()
        self.start_event.set()
        self.root.destroy()
