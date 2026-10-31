"""Hevy Insights: verified workout transformation, strength trends, and forecast evaluation.

Run from the project virtual environment:
    python transform.py

Required packages: pandas, matplotlib, scikit-learn
The script reads workouts_raw.json from the same folder as this script.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Save charts without pausing execution for a chart window.
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LinearRegression
from cli import select_exercise
from forecast_features import run_feature_forecast
from forecast_insights import forecast_insights

DATA_FILE = Path(__file__).resolve().parent / "workouts_raw.json"
CHART_FILE = Path(__file__).resolve().parent / "bench_press_trend.png"
EXERCISE_NAME = "Bench Press (Barbell)"
KG_TO_LB = 2.2046226218


def load_workouts(path):
    with path.open("r", encoding="utf-8") as handle:
        workouts = json.load(handle)
    if not isinstance(workouts, list):
        raise ValueError("Expected workouts_raw.json to contain a list of workouts.")
    ids = [workout["id"] for workout in workouts]
    duplicates = len(ids) - len(set(ids))
    print(f"Workouts: {len(workouts)} | Duplicate workout IDs: {duplicates}")
    if duplicates:
        raise ValueError("Duplicate workout IDs found. Fix API pagination and re-extract data.")
    return workouts


def flatten_sets(workouts):
    rows = []
    for workout in workouts:
        for exercise in workout.get("exercises", []):
            for set_data in exercise.get("sets", []):
                rows.append({
                    "workout_id": workout["id"],
                    "workout_title": workout.get("title"),
                    "start_time": workout["start_time"],
                    "exercise_id": exercise["exercise_template_id"],
                    "exercise_title": exercise.get("title"),
                    "set_index": set_data.get("index"),
                    "set_type": set_data.get("type"),
                    "weight_kg": set_data.get("weight_kg"),
                    "reps": set_data.get("reps"),
                    "rpe": set_data.get("rpe"),
                })
    if not rows:
        raise ValueError("No sets found in the workout data.")
    df = pd.DataFrame(rows)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce")
    df["weight_lb"] = df["weight_kg"] * KG_TO_LB
    print(f"Total sets: {len(df)} | Missing weights: {df['weight_kg'].isna().sum()}")
    return df


def calculate_best_sets(df):
    # Initial e1RM model: positive external loads, normal sets, 1–10 reps.
    # Weighted pull-ups/dips and machines need special interpretation.
    eligible = df.loc[
        (df["set_type"] == "normal")
        & (df["weight_kg"] > 0)
        & (df["reps"].between(1, 10))
    ].copy()
    eligible["estimated_1rm_lb"] = eligible["weight_lb"] * (1 + eligible["reps"] / 30)
    best = (
        eligible.groupby(
            ["workout_id", "start_time", "exercise_id", "exercise_title"],
            as_index=False,
        )
        .agg(best_e1rm_lb=("estimated_1rm_lb", "max"))
        .sort_values(["exercise_id", "start_time", "workout_id"])
        .reset_index(drop=True)
    )
    best["previous_e1rm_lb"] = best.groupby("exercise_id")["best_e1rm_lb"].shift(1)
    best["progress_pct"] = (
        (best["best_e1rm_lb"] / best["previous_e1rm_lb"] - 1) * 100
    )
    print(f"Eligible sets: {len(eligible)} | Exercise/workout records: {len(best)}")
    return best

    history = history.sort_values("start_time").reset_index(drop=True)
    if history.empty:
        raise ValueError(f"No eligible records for {exercise_name!r}.")
    # Causal smoothing: each median uses the current and previous two sessions only.
    history["rolling_e1rm"] = history["best_e1rm_lb"].rolling(3, min_periods=3).median()
    return history

def summarize_progress(best):
    latest = best["start_time"].max()
    recent = best.loc[best["start_time"] >= latest - pd.Timedelta(weeks=12)].copy()
    summary = (
        recent.sort_values(["exercise_id", "start_time"])
        .groupby(["exercise_id", "exercise_title"], as_index=False)
        .agg(
            sessions=("workout_id", "nunique"),
            first_e1rm=("best_e1rm_lb", "first"),
            latest_e1rm=("best_e1rm_lb", "last"),
            best_e1rm=("best_e1rm_lb", "max"),
        )
    )
    summary = summary.loc[summary["sessions"] >= 3].copy()
    summary["progress_pct"] = (
        (summary["latest_e1rm"] / summary["first_e1rm"] - 1) * 100
    )
    print("\nTop 10 exercise changes over the latest 12 weeks:")
    print(
        summary.sort_values("progress_pct", ascending=False)
        [["exercise_title", "sessions", "first_e1rm", "latest_e1rm", "best_e1rm", "progress_pct"]]
        .head(10).round(2).to_string(index=False)
    )

    # Quarterly summary is the maximum session-level estimate in each calendar quarter.
    # Quarterly strength analysis
    quarterly = best.copy()

    # Extract the quarter from workout date
    quarterly["quarter"] = (
        quarterly["start_time"]
        .dt.tz_localize(None)
        .dt.to_period("Q")
        .astype(str)
    )

    # Calculate quarterly strength metrics
    quarterly = (
        quarterly
        .groupby(
            ["exercise_id", "exercise_title", "quarter"],
            as_index=False
        )
        .agg(
            median_e1rm_lb=("best_e1rm_lb", "median"),
            peak_e1rm_lb=("best_e1rm_lb", "max"),
            sessions=("workout_id", "nunique")
        )
        .sort_values(["exercise_id", "quarter"])
    )
    return summary, quarterly


def get_exercise_history(best, exercise_id):

    history = best.loc[
        best["exercise_id"] == exercise_id,
        ["start_time", "best_e1rm_lb"]
    ].copy()

    history = history.sort_values(
        "start_time"
    ).reset_index(drop=True)

    if history.empty:
        return history

    history["rolling_e1rm"] = (
        history["best_e1rm_lb"]
        .rolling(3, min_periods=3)
        .median()
    )

    return history

def save_trend_chart(history):
    recent_cutoff = history["start_time"].max() - pd.Timedelta(weeks=12)
    recent = history.loc[history["start_time"] >= recent_cutoff]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(recent["start_time"], recent["best_e1rm_lb"], marker="o",
            alpha=0.5, label="Session best e1RM")
    ax.plot(recent["start_time"], recent["rolling_e1rm"], linewidth=2,
            label="3-session rolling median")
    ax.set(title=f"{EXERCISE_NAME}: last 12 weeks", xlabel="Workout date",
           ylabel="Estimated 1RM (lb)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150)
    plt.close(fig)
    print(f"Trend chart saved: {CHART_FILE.name}")


def four_week_backtest(history):
    observed = history.dropna(subset=["rolling_e1rm"]).copy()
    results = []
    for i in range(len(observed)):
        cutoff = observed.iloc[i]["start_time"]
        train = observed.loc[
            (observed["start_time"] <= cutoff)
            & (observed["start_time"] >= cutoff - pd.Timedelta(weeks=6))
        ].copy()
        if len(train) < 4:
            continue

        target_date = cutoff + pd.Timedelta(weeks=4)
        # Compare against an actual session within ±7 days of the 4-week target.
        candidates = observed.loc[
            (observed["start_time"] >= target_date - pd.Timedelta(days=7))
            & (observed["start_time"] <= target_date + pd.Timedelta(days=7))
        ].copy()
        if candidates.empty:
            continue
        candidates["distance"] = (candidates["start_time"] - target_date).abs()
        test = candidates.sort_values("distance").iloc[0]

        origin = train["start_time"].min()
        X_train = pd.DataFrame({
            "days": (train["start_time"] - origin).dt.total_seconds() / 86400
        })
        X_target = pd.DataFrame({
            "days": [(target_date - origin).total_seconds() / 86400]
        })
        model = LinearRegression().fit(X_train, train["rolling_e1rm"])
        lr_prediction = model.predict(X_target)[0]
        baseline_prediction = train["rolling_e1rm"].iloc[-1]
        actual = test["rolling_e1rm"]
        
        # Damped trend: project 50% of the estimated daily trend
        damping_factor = 0.5

        days_ahead = (
            target_date - cutoff
        ).total_seconds() / 86400

        trend_per_day = model.coef_[0]

        damped_prediction = (
            baseline_prediction
            + damping_factor * trend_per_day * days_ahead
        )

        results.append({
            "forecast_date": cutoff,
            "target_date": target_date,
            "actual_date": test["start_time"],  # Fixed: included in saved records
            "days_from_target": (test["start_time"] - target_date).total_seconds() / 86400,
            "actual": actual,
            "lr_prediction": lr_prediction,
            "baseline_prediction": baseline_prediction,
            "lr_error": abs(actual - lr_prediction),
            "baseline_error": abs(actual - baseline_prediction),
            "damped_prediction": damped_prediction,
            "damped_error": abs(actual - damped_prediction),
        })
        
    return pd.DataFrame(results)




def forecast_next_four_weeks(history):

    observed = history.dropna(
        subset=["rolling_e1rm"]
    ).copy()

    if len(observed) < 4:
        print("\nForecast unavailable: insufficient workout history.")
        return

    # Backtest all three models
    results = four_week_backtest(history)

    if len(results) < 5:
        print(
            f"\nForecast unavailable: only {len(results)} "
            "valid historical backtests (minimum 5)."
        )
        return

    # Historical forecasting errors
    model_errors = {
        "No-change baseline": results["baseline_error"].mean(),
        "Linear Regression": results["lr_error"].mean(),
        "Damped Trend": results["damped_error"].mean()
    }

    # Use most recent six weeks of workouts
    cutoff = observed["start_time"].max()

    train = observed.loc[
        observed["start_time"] >= cutoff - pd.Timedelta(weeks=6)
    ].copy()

    current_strength = observed["rolling_e1rm"].iloc[-1]
    target_date = cutoff + pd.Timedelta(weeks=4)
    
    # Check whether the forecast date is already in the past
    today = pd.Timestamp.now(tz="UTC")

    if target_date <= today:
        print("\nForecast unavailable: workout history is outdated.")
        print(f"Last eligible workout: {cutoff.date()}")
        print(f"Forecast target date: {target_date.date()}")
        print("Log a new workout before generating a future forecast.")
        return

    # Baseline always available
    predictions = {
        "No-change baseline": current_strength
    }

    if len(train) >= 4:

        origin = train["start_time"].min()

        X_train = pd.DataFrame({
            "days": (
                train["start_time"] - origin
            ).dt.total_seconds() / 86400
        })

        X_target = pd.DataFrame({
            "days": [
                (target_date - origin).total_seconds() / 86400
            ]
        })

        model = LinearRegression()
        model.fit(X_train, train["rolling_e1rm"])

        # Full linear regression
        lr_prediction = model.predict(X_target)[0]

        # Damped trend
        days_ahead = (
            target_date - cutoff
        ).total_seconds() / 86400

        damped_prediction = (
            current_strength
            + 0.5 * model.coef_[0] * days_ahead
        )

        predictions["Linear Regression"] = lr_prediction
        predictions["Damped Trend"] = damped_prediction

    # Select lowest historical MAE among available models
    selected_model = min(
        predictions,
        key=lambda name: model_errors[name]
    )

    selected_prediction = predictions[selected_model]

    progress_lb = selected_prediction - current_strength

    progress_pct = (
        progress_lb / current_strength * 100
        if current_strength > 0 else float("nan")
    )

    print("\n===== FOUR-WEEK STRENGTH FORECAST =====")

    print(f"Historical backtests: {len(results)}")

    print("\nModel comparison:")

    for name, mae in model_errors.items():
        print(f"{name}: MAE = {mae:.2f} lb")

    print("\nCandidate predictions:")

    for name, prediction in predictions.items():
        print(f"{name}: {prediction:.2f} lb")

    print(f"\nSelected model: {selected_model}")
    print(f"Current smoothed e1RM: {current_strength:.2f} lb")
    print(f"Forecast date: {target_date.date()}")
    print(f"Four-week forecast: {selected_prediction:.2f} lb")

    print(f"Predicted change: {progress_lb:+.2f} lb")
    print(f"Predicted progress: {progress_pct:+.2f}%")

    print(
        "\nExperimental model selection based on overlapping "
        "historical backtests; accuracy is not independently validated."
    )

    
def plot_quarterly_progress(quarterly, exercise_id):
    exercise_data = quarterly[
        quarterly["exercise_id"] == exercise_id
    ].sort_values("quarter")

    if exercise_data.empty:
        print("No quarterly data found.")
        return
    
    # Convert quarter labels to quarterly periods
    exercise_data = exercise_data.copy()

    exercise_data["quarter_period"] = pd.PeriodIndex(
        exercise_data["quarter"],
        freq="Q"
    )

    # Generate all quarters between the first and last record
    all_quarters = pd.period_range(
        start=exercise_data["quarter_period"].min(),
        end=exercise_data["quarter_period"].max(),
        freq="Q"
    )

    # Insert missing quarters with NaN values
    exercise_data = (
        exercise_data
        .set_index("quarter_period")
        .reindex(all_quarters)
    )

    # Convert periods back to chart labels
    exercise_data["quarter"] = exercise_data.index.astype(str)

    exercise_title = exercise_data["exercise_title"].iloc[0]

    plt.figure(figsize=(12, 6))

    plt.plot(
        exercise_data["quarter"],
        exercise_data["median_e1rm_lb"],
        marker="o",
        label="Median e1RM"
    )

    plt.plot(
        exercise_data["quarter"],
        exercise_data["peak_e1rm_lb"],
        marker="s",
        linestyle="--",
        label="Peak e1RM"
    )
    
    # Annotate each quarter with its session count
    for quarter, median, sessions in zip(
        exercise_data["quarter"],
        exercise_data["median_e1rm_lb"],
        exercise_data["sessions"]
    ):
        if pd.notna(median):
            plt.annotate(
                f"n={int(sessions)}",
                (quarter, median),
                textcoords="offset points",
                xytext=(0, -16),
                ha="center",
                fontsize=9
            )

    plt.title(f"{exercise_title} - Quarterly Strength Progression")
    plt.xlabel("Quarter")
    plt.ylabel("Estimated 1RM (lb)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True)
    plt.margins(y=0.15)
    plt.tight_layout()

    plt.savefig("quarterly_progress.png", dpi=150)
    plt.close()


def main():
    workouts = load_workouts(DATA_FILE)
    df = flatten_sets(workouts)
    best = calculate_best_sets(df)

    # Calculate quarterly statistics
    _, quarterly = summarize_progress(best)

    # Select exercise from CLI
    selected_exercise_id = select_exercise(quarterly)

    # Filter selected exercise
    selected_quarters = quarterly[
        quarterly["exercise_id"] == selected_exercise_id
    ].sort_values("quarter")

    # Retrieve exercise name
    selected_exercise_name = selected_quarters["exercise_title"].iloc[0]

    # Print quarterly analysis
    print(f"\nQuarterly Analysis: {selected_exercise_name}")

    print(
        selected_quarters[
            [
                "quarter",
                "sessions",
                "median_e1rm_lb",
                "peak_e1rm_lb"
            ]
        ].round(2).to_string(index=False)
    )

    # Generate quarterly chart
    plot_quarterly_progress(quarterly, selected_exercise_id)
    
    run_feature_forecast(
    df,
    best,
    selected_exercise_id
    )
    
    forecast_insights(df, best, selected_exercise_id)
    
    history = get_exercise_history(best, selected_exercise_id)

    # forecast_next_four_weeks(history)

    print(f"\nChart generated for {selected_exercise_name}!")
    

if __name__ == "__main__":
    main()
