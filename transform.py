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
    quarterly = best.copy()
    quarterly["quarter"] = quarterly["start_time"].dt.tz_localize(None).dt.to_period("Q").astype(str)
    quarterly = (
        quarterly.groupby(["exercise_id", "exercise_title", "quarter"], as_index=False)
        .agg(best_e1rm_lb=("best_e1rm_lb", "max"), sessions=("workout_id", "nunique"))
    )
    return summary, quarterly


def get_exercise_history(best, exercise_name):
    history = best.loc[best["exercise_title"] == exercise_name,
                       ["start_time", "best_e1rm_lb"]].copy()
    history = history.sort_values("start_time").reset_index(drop=True)
    if history.empty:
        raise ValueError(f"No eligible records for {exercise_name!r}.")
    # Causal smoothing: each median uses the current and previous two sessions only.
    history["rolling_e1rm"] = history["best_e1rm_lb"].rolling(3, min_periods=3).median()
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
        })
    return pd.DataFrame(results)


def forecast_next_four_weeks(history):
    cutoff = history["start_time"].max()
    train = history.loc[
        (history["start_time"] >= cutoff - pd.Timedelta(weeks=6))
    ].dropna(subset=["rolling_e1rm"])
    if len(train) < 4:
        print("Not enough recent sessions for a regression projection.")
        return
    origin = train["start_time"].min()
    X = pd.DataFrame({"days": (train["start_time"] - origin).dt.total_seconds() / 86400})
    target_date = cutoff + pd.Timedelta(weeks=4)
    X_target = pd.DataFrame({"days": [(target_date - origin).total_seconds() / 86400]})
    model = LinearRegression().fit(X, train["rolling_e1rm"])
    print(f"\nLatest raw e1RM: {history['best_e1rm_lb'].iloc[-1]:.2f} lb")
    print(f"Latest smoothed e1RM: {history['rolling_e1rm'].iloc[-1]:.2f} lb")
    print(f"Experimental regression 4-week projection: {model.predict(X_target)[0]:.2f} lb")
    print(f"No-change 4-week projection: {train['rolling_e1rm'].iloc[-1]:.2f} lb")
    print("These are experimental projections, not validated strength targets.")


def main():
    # Everything called here is defined above, including summarize_progress().
    workouts = load_workouts(DATA_FILE)
    df = flatten_sets(workouts)
    best = calculate_best_sets(df)
    _, quarterly = summarize_progress(best)

    print(f"\nQuarterly {EXERCISE_NAME} best e1RM:")
    bench_quarters = quarterly.loc[quarterly["exercise_title"] == EXERCISE_NAME]
    print(bench_quarters[["quarter", "sessions", "best_e1rm_lb"]].round(2).to_string(index=False))

    history = get_exercise_history(best, EXERCISE_NAME)
    print(f"\nBench sessions: {len(history)} | {history['start_time'].min()} to {history['start_time'].max()}")
    save_trend_chart(history)

    results = four_week_backtest(history)
    print(f"\nFour-week backtests: {len(results)}")
    if not results.empty:
        print(results[["target_date", "actual_date", "days_from_target", "actual", "lr_error", "baseline_error"]]
              .tail(10).round(2).to_string(index=False))
        print(f"Linear regression MAE: {results['lr_error'].mean():.2f} lb")
        print(f"No-change baseline MAE: {results['baseline_error'].mean():.2f} lb")
        print(f"Average absolute days from target: {results['days_from_target'].abs().mean():.2f}")
    forecast_next_four_weeks(history)


if __name__ == "__main__":
    main()
