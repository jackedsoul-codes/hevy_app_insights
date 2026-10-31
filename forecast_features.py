
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = [
    "current_e1rm",
    "trend_lb_per_week",
    "volume_lb_per_week",
    "sessions_per_week",
    "sets_per_week",
    "avg_working_weight_lb",
    "days_since_last_session",
]


def make_snapshot(history, sets, cutoff):
    """Create features using data available at cutoff."""

    past = history[
        history["start_time"] <= cutoff
    ]

    if len(past) < 3:
        return None

    last = past.iloc[-1]

    days_since = (
        cutoff - last["start_time"]
    ).total_seconds() / 86400

    # Avoid very stale historical strength observations.
    if days_since > 21:
        return None

    # Recent strength trend: last 6 weeks
    recent_history = past[
        past["start_time"] >
        cutoff - pd.Timedelta(weeks=6)
    ].dropna(subset=["rolling_e1rm"])

    trend = 0.0

    if len(recent_history) >= 3:

        weeks = (
            recent_history["start_time"]
            - recent_history["start_time"].min()
        ).dt.total_seconds().to_numpy() / (86400 * 7)

        if weeks.max() > 0:
            trend = float(
                np.polyfit(
                    weeks,
                    recent_history["rolling_e1rm"],
                    1
                )[0]
            )

    # Training activity during the last 4 weeks
    recent_sets = sets.loc[
        (sets["start_time"] <= cutoff)
        & (
            sets["start_time"] >
            cutoff - pd.Timedelta(weeks=4)
        )
    ]

    return {
        "current_e1rm": float(last["rolling_e1rm"]),

        "trend_lb_per_week": trend,

        "volume_lb_per_week": float(
            (
                recent_sets["weight_lb"]
                * recent_sets["reps"]
            ).sum() / 4
        ),

        "sessions_per_week":
            recent_sets["workout_id"].nunique() / 4,

        "sets_per_week": len(recent_sets) / 4,

        "avg_working_weight_lb": (
            float(recent_sets["weight_lb"].mean())
            if len(recent_sets) else 0.0
        ),

        "days_since_last_session": float(days_since),
    }


def run_feature_forecast(df, best, exercise_id):

    # Exercise-level strength history
    history = best.loc[
        best["exercise_id"] == exercise_id,
        ["start_time", "best_e1rm_lb"]
    ].sort_values("start_time").copy()

    if len(history) < 8:
        print("Not enough exercise sessions.")
        return

    history["rolling_e1rm"] = (
        history["best_e1rm_lb"]
        .rolling(3, min_periods=3)
        .median()
    )

    # Eligible working sets for this exercise
    sets = df.loc[
        (df["exercise_id"] == exercise_id)
        & (df["set_type"] == "normal")
        & (df["weight_lb"] > 0)
        & (df["reps"].between(1, 10))
    ].copy()

    # Create historical snapshots every 7 days
    snapshots = pd.date_range(
        start=(
            history["start_time"].min()
            + pd.Timedelta(weeks=6)
        ),
        end=history["start_time"].max(),
        freq="7D"
    )

    examples = []

    for cutoff in snapshots:

        features = make_snapshot(
            history, sets, cutoff
        )

        if features is None:
            continue

        target_date = (
            cutoff + pd.Timedelta(weeks=4)
        )

        # Find actual strength around the 4-week target
        future = history.loc[
            (
                history["start_time"] >=
                target_date - pd.Timedelta(days=7)
            )
            & (
                history["start_time"] <=
                target_date + pd.Timedelta(days=7)
            )
            & history["rolling_e1rm"].notna()
        ].copy()

        if future.empty:
            continue

        future["distance"] = (
            future["start_time"] - target_date
        ).abs()

        actual = (
            future.sort_values("distance").iloc[0]
        )

        examples.append({
            **features,
            "cutoff": cutoff,
            "actual_date": actual["start_time"],
            "actual_e1rm": float(actual["rolling_e1rm"]),
            "change_lb": float(
                actual["rolling_e1rm"]
                - features["current_e1rm"]
            )
        })

    if not examples:
        print("No historical four-week outcomes found.")
        return

    examples = (
        pd.DataFrame(examples)
        .sort_values("cutoff")
        .reset_index(drop=True)
    )

    if len(examples) < 20:
        print(
            f"Only {len(examples)} labeled snapshots. "
            "Need at least 20 for this experiment."
        )
        return

    # Chronological train/test split
    split = int(len(examples) * 0.75)

    test = (
    examples.iloc[split:]
    .drop_duplicates(subset=["actual_date"], keep="first")
    .copy()
    )

    first_test_date = test["cutoff"].min()

    # Exclude training examples whose targets
    # were observed after the test period began.
    earlier = examples.iloc[:split]

    train = earlier.loc[
        earlier["actual_date"] < first_test_date
    ].copy()

    if len(train) < 12 or len(test) < 5:
        print(
            f"Insufficient split: "
            f"{len(train)} train / {len(test)} test."
        )
        return

    # Standardize features and train Ridge regression
    model = make_pipeline(
        StandardScaler(),
        Ridge(alpha=10.0)
    )

    model.fit(
        train[FEATURES],
        train["change_lb"]
    )

    # Predict future strength changes in the test set
    predicted = (
        test["current_e1rm"].to_numpy()
        + model.predict(test[FEATURES])
    )

    baseline = test["current_e1rm"].to_numpy()
    truth = test["actual_e1rm"].to_numpy()

    model_mae = float(
        np.mean(np.abs(truth - predicted))
    )

    baseline_mae = float(
        np.mean(np.abs(truth - baseline))
    )
    
    comparison = test[
    ["cutoff", "actual_date"]
    ].copy()

    comparison["actual_e1rm"] = truth
    comparison["ridge_prediction"] = predicted
    comparison["baseline_prediction"] = baseline

    comparison["ridge_error"] = np.abs(
        truth - predicted
    )

    comparison["baseline_error"] = np.abs(
        truth - baseline
    )

    print("\n===== INDIVIDUAL HOLDOUT PREDICTIONS =====")

    print(
        comparison.round(2).to_string(index=False)
    )

    print("\n===== FOUR-WEEK FEATURE-BASED FORECAST TEST =====")

    print(f"Weekly labeled snapshots: {len(examples)}")
    print(
        f"Chronological train/test: "
        f"{len(train)} / {len(test)}"
    )

    print(f"No-change holdout MAE: {baseline_mae:.2f} lb")
    print(f"Feature model holdout MAE: {model_mae:.2f} lb")

    winner = (
        "Feature Ridge"
        if model_mae < baseline_mae
        else "No-change baseline"
    )

    print(f"Better holdout model: {winner}")

    # Generate a forecast from the latest eligible session
    cutoff = history["start_time"].max()
    target_date = cutoff + pd.Timedelta(weeks=4)

    now = pd.Timestamp.now(tz="UTC")

    if target_date <= now:
        print(
            f"No current forecast: latest eligible workout "
            f"is {cutoff.date()} (target already passed)."
        )
        return

    current = make_snapshot(
        history, sets, cutoff
    )

    if current is None:
        print("Insufficient recent session history.")
        return

    # Refit using all completed historical examples
    model.fit(
        examples[FEATURES],
        examples["change_lb"]
    )

    feature_prediction = (
        current["current_e1rm"]
        + model.predict(
            pd.DataFrame([current])[FEATURES]
        )[0]
    )

    # Choose model based on holdout evaluation
    if model_mae < baseline_mae:
        selected_model = "Feature Ridge"
        selected_prediction = feature_prediction
    else:
        selected_model = "No-change baseline"
        selected_prediction = current["current_e1rm"]

    predicted_change = (
        selected_prediction - current["current_e1rm"]
    )

    print("\n===== SELECTED FORECAST =====")
    print(f"Selected model: {selected_model}")
    print(f"Current e1RM: {current['current_e1rm']:.2f} lb")
    print(f"Forecast: {selected_prediction:.2f} lb")
    print(f"Predicted change: {predicted_change:+.2f} lb")

    print(
        "Provisional model selection based on a small, "
        "overlapping historical test set."
    )
        
    print("\nCurrent feature values:")

    for key in FEATURES:
        print(f"  {key}: {current[key]:.2f}")

    print(
        f"\nCurrent smoothed e1RM: "
        f"{current['current_e1rm']:.2f} lb"
    )

    print(f"Forecast target: {target_date.date()}")

    print("\n===== FINAL FORECAST =====")

    print(f"Selected model: {selected_model}")

    print(
        f"Selected 4-week forecast: "
        f"{selected_prediction:.2f} lb"
    )

    print(
        f"Expected change: "
        f"{selected_prediction - current['current_e1rm']:+.2f} lb"
    )

    print(
        f"\nExperimental Ridge candidate: "
        f"{feature_prediction:.2f} lb"
    )

    print(
        "\nExperimental forecast. Holdout examples "
        "may overlap and are not fully independent."
    )
