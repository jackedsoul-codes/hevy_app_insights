"""Compare an exercise's latest 4 weeks with the preceding 4 weeks.

Uses the same eligible working sets as Hevy Insights' e1RM/forecasting
pipeline: normal sets, positive weight, and 1–10 repetitions.
"""

import pandas as pd


def forecast_insights(df, best, exercise_id):
    """Print recent training context for a chosen exercise.

    Both windows are anchored to that exercise's latest eligible session,
    rather than the current date, so the comparison remains reproducible.
    """
    history = best.loc[best["exercise_id"] == exercise_id].copy()
    if history.empty:
        print("\nTraining insights unavailable: no eligible exercise sessions.")
        return

    history = history.sort_values("start_time")
    cutoff = history["start_time"].max()
    recent_start = cutoff - pd.Timedelta(weeks=4)
    previous_start = cutoff - pd.Timedelta(weeks=8)

    sets = df.loc[
        (df["exercise_id"] == exercise_id)
        & (df["set_type"] == "normal")
        & (df["weight_lb"] > 0)
        & (df["reps"].between(1, 10))
    ].copy()

    def summarize_window(start, end):
        # Left-open, right-closed windows prevent counting a boundary twice.
        window_sets = sets.loc[
            (sets["start_time"] > start)
            & (sets["start_time"] <= end)
        ]
        window_history = history.loc[
            (history["start_time"] > start)
            & (history["start_time"] <= end)
        ]

        return {
            "sessions_per_week": window_sets["workout_id"].nunique() / 4,
            "sets_per_week": len(window_sets) / 4,
            "volume_lb_per_week": float(
                (window_sets["weight_lb"] * window_sets["reps"]).sum() / 4
            ),
            "avg_working_weight_lb": (
                float(window_sets["weight_lb"].mean())
                if not window_sets.empty else None
            ),
            # Median of session-best e1RM, not the three-session rolling median.
            "median_session_e1rm_lb": (
                float(window_history["best_e1rm_lb"].median())
                if not window_history.empty else None
            ),
            "session_count": window_history["workout_id"].nunique(),
        }

    previous = summarize_window(previous_start, recent_start)
    recent = summarize_window(recent_start, cutoff)

    def show(value, decimals=2):
        return "N/A" if value is None or pd.isna(value) else f"{value:,.{decimals}f}"

    def change(old, new):
        if old is None or new is None or pd.isna(old) or pd.isna(new):
            return "N/A"
        if old == 0:
            return "N/A (no prior value)"
        return f"{(new / old - 1) * 100:+.1f}%"

    title = history["exercise_title"].iloc[-1]
    print(f"\n===== TRAINING INSIGHTS: {title} =====")
    print(f"Previous window: {previous_start.date()} to {recent_start.date()}")
    print(f"Recent window:   {recent_start.date()} to {cutoff.date()}")
    print("Windows are 28 days each, ending on the latest eligible session.")
    print(f"{'Metric':<28} {'Previous':>12} {'Recent':>12} {'Change':>24}")
    print("-" * 80)

    labels = [
        ("Sessions / week", "sessions_per_week"),
        ("Working sets / week", "sets_per_week"),
        ("Volume load (lb / week)", "volume_lb_per_week"),
        ("Avg working weight (lb)", "avg_working_weight_lb"),
        ("Median session e1RM (lb)", "median_session_e1rm_lb"),
    ]

    for label, metric in labels:
        old, new = previous[metric], recent[metric]
        print(f"{label:<28} {show(old):>12} {show(new):>12} {change(old, new):>24}")

    print(
        f"Eligible sessions: {previous['session_count']} previous, "
        f"{recent['session_count']} recent."
    )
    if min(previous["session_count"], recent["session_count"]) < 3:
        print("Limited data: fewer than three sessions in at least one window.")
    print(
        "These are descriptive training changes, not proven reasons "
        "for a forecast or evidence of causation."
    )
