Hevy Insights

A Python and Pandas project that turns workout history from the Hevy API into exercise-level strength insights and quarterly progression charts.
The current interface is a command-line menu: choose an exercise from your workout history and the program prints its quarterly statistics and saves a chart. This is a personal analytics/learning project, not an official Hevy product.

What it does

1. Extract (separate step): Retrieve paginated workouts from Hevy using your own API key and save them as workouts_raw.json. The extractor and interactive key entry are being finalized; transform.py currently expects this JSON file to exist already.
2. Transform: Flatten nested workouts → exercises → sets into a Pandas DataFrame, parse timestamps, and convert loads from kilograms to pounds.
3. Calculate strength estimates: Keep normal sets with a positive recorded external load and 1–10 repetitions. Estimate one-rep max (e1RM) using the Epley formula: weight_lb * (1 + reps / 30).
4. Aggregate by session: Retain the highest eligible e1RM for each exercise in each workout.
5. Summarize quarterly: For every exercise and calendar quarter, calculate the median session-best e1RM, peak session-best e1RM, and number of sessions.
6. Choose an exercise: A terminal menu in cli.py lists exercises from the actual data, with Bench Press, Squat, and Deadlift placed first if available.
7. Visualize: Plot quarterly median and peak e1RM, leave gaps for quarters with no recorded eligible sessions, and annotate each recorded quarter with its number of sessions.

The analysis code also includes exploratory 12-week trends and four-week forecasting/backtesting functions. Forecasting is not part of the current exercise-selection workflow and is not validated for user-facing predictions. In the initial bench-press backtest, a simple no-change baseline outperformed the tested linear-regression model.

Project layout

hevy_app_insights/
├── cli.py                 # Terminal menu and exercise selection
├── transform.py           # Workout transformations, summaries, charts
├── workouts_raw.json      # Private extracted workout data (do not commit)
├── .env                   # Optional local API key (do not commit)
├── .gitignore
├── README.md
└── quarterly_progress.png # Generated chart (do not commit)

You may also have a separate Hevy API extraction script in your local project. Its exact filename and final interactive API-key workflow are not yet specified here.

Requirements
- Python 3.9 or newer
- pandas
- matplotlib
- scikit-learn (used by the existing experimental forecasting functions)
- requests and python-dotenv for the separate API extraction workflow
- A Hevy API key and access to the corresponding workout history for extracting fresh data

Install

From the project directory, set up a virtual environment if you do not already have one:
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas matplotlib scikit-learn requests python-dotenv
If you use uv, install the same packages with uv pip install ... while your virtual environment is active.
Running the current analysis
Prerequisite: workouts_raw.json must already contain a JSON list of workout objects produced by the Hevy extraction step. A fresh clone of this repository will not contain your private data.
python transform.py

The program will:
1. Report the number of workouts, sets, and eligible exercise/workout records.
2. Print the largest first-to-last changes over the most recent 12 weeks of the available workout history (for exercises with at least three sessions in that window).
3. Display an exercise selection menu.
4. Print quarterly statistics for the selected exercise.
5. Save the corresponding chart as quarterly_progress.png in the working directory.

Select an exercise by entering its menu number. Running again with a different selection overwrites the previous quarterly_progress.png.

Example output (illustrative)

===== HEVY STRENGTH INSIGHTS =====
Select an exercise:
1. Bench Press (Barbell)
2. Squat (Barbell)
3. Deadlift (Barbell)
...
Enter exercise number: 2

Quarterly Analysis: Squat (Barbell)
quarter  sessions  median_e1rm_lb  peak_e1rm_lb
...
Actual exercises and numbers depend on the user's workout history.
API key handling — next implementation step
Do not hardcode an API key or commit it to Git. The recommended approach for the extraction script is to:
- Check for a locally supplied HEVY_API_KEY environment variable (optionally loaded from .env).
- If missing, prompt using Python's getpass.getpass() so typed characters do not appear in the terminal.
- Send the key in the API's api-key header and paginate through workouts.
- Save the returned workouts locally to workouts_raw.json, then run the analysis script.

The CLI currently selects exercises; it does not yet request the API key or invoke extraction. This section describes the intended next feature, not a completed one.
Privacy and Git

Workout history can contain personal information. Keep API keys and raw workout records private. Suggested .gitignore entries:
.env
.venv/
__pycache__/
workouts_raw.json
*.png

If these files were already committed, adding entries to .gitignore does not remove them from Git history. Revoke/rotate any key that was committed or shared publicly.

Data interpretation and limitations
- e1RM is an estimate, not a measured one-rep maximum. It depends on the rep range, effort, and accurate logging.
- The current filter excludes warm-up, drop, failure-type, zero-load, missing-load, and >10-rep sets from the e1RM analysis. These workouts may still exist in the raw data.
- For weighted pull-ups and dips, Hevy may record only added load; the current formula does not add bodyweight.
- Cable and machine loads are not necessarily comparable across equipment, and dumbbell loads may be recorded per hand.
- Low-volume quarters (e.g., only 1–2 sessions) are less informative. The chart shows session counts so readers can judge coverage.
- A missing quarter means no eligible exercise records for that period, not zero strength. Charts leave a visible gap.
- Exercise selection uses template IDs because titles can repeat or vary; different IDs should not be combined blindly.
- The most recent 12-week report is based on the latest workout timestamp in the dataset, not necessarily today's date.

Remaining work before sharing with other users
1. Finish the extraction entry point so each user can enter their own API key and refresh workouts_raw.json before analysis.
2. Verify a clean setup in a new virtual environment, using only the README and the files committed to Git.
3. Remove old hardcoded Bench Press output from the default workflow (if any remains) and ensure no credentials or private workouts are tracked.

Optional future features include exercise-name search instead of a 100+ item menu, unique filenames for exported charts, a web UI, bodyweight-aware strength metrics, and forecasting only after a model beats a simple historical baseline in meaningful backtests.

Educational purpose
This project practices REST API extraction, pagination, nested JSON processing, Pandas transformations and grouping, time-series aggregation, visualization, input validation, modular Python design, and model evaluation.