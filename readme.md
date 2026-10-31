Hevy Insights

Personalized strength analytics and experimental four-week forecasting from your Hevy workout history.

Hevy Insights is a Python command-line application that extracts workouts from the Hevy API, turns nested exercise/set records into structured data, analyzes estimated strength over time, and forecasts an exercise's estimated one-rep max (e1RM) four weeks ahead. It also compares recent training behavior against the preceding four weeks to give each prediction context.

The project is an independent portfolio and learning project, not an official Hevy product. Forecasts are experimental and are not guaranteed strength outcomes or training prescriptions.

Features
- Hevy API ingestion: Authenticate with a personal API key and download paginated workout history to a local JSON file.
- Set-level data pipeline: Flatten workouts → exercises → sets with Pandas; clean timestamps, set types, reps, and weights; convert kilograms to pounds.
- Estimated strength: Calculate e1RM using the Epley equation for eligible working sets and retain the best value per exercise/session.
- Interactive exercise analysis: Select an exercise from a terminal menu, with Bench Press, Squat, and Deadlift prioritized when present.
- Quarterly progression: Display session counts, median session-best e1RM, and peak session-best e1RM, with a saved chart.
- Four-week forecasting: Use recent strength and training features with a regularized Ridge regression model; compare it against a no-change baseline and select the model with the lower historical holdout mean absolute error (MAE).
- Training context: Compare two consecutive 28-day windows for weekly sessions, working sets, volume load, average working weight, and median session e1RM.
- Data sufficiency checks: Avoid generating certain predictions when there is too little or stale exercise history.

How it works

Hevy REST API
    |
    v
api_call.py  -->  workouts_raw.json (local / private)
                         |
                         v
                    transform.py
                         |
            +------------+-------------+
            |            |             |
            v            v             v
      Session e1RM   Quarterly     Exercise sets
      + smoothing    summaries     and history
            |            |             |
            +------------+------+------+
                                |
                     Exercise selection (cli.py)
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
       forecast_features.py          forecast_insights.py
       4-week Ridge vs baseline       Recent vs prior 28 days
                  |                           |
                  +-------------+-------------+
                                |
                    Terminal results + chart
      

Strength calculation

For eligible sets, the Epley estimate is:

e1RM (lb) = weight_lb * (1 + reps / 30)

The current analysis includes normal sets with positive recorded load and 1–10 repetitions. The highest eligible estimate from an exercise within a workout becomes its session-best e1RM.

Quarterly metrics use session-best values:
- Median e1RM: The median of session-best estimates recorded in that quarter; reflects a typical observed strength level.
- Peak e1RM: The highest session-best estimate in that quarter; reflects the strongest estimated performance.
- Sessions: Number of eligible exercise sessions in the quarter.

Forecasting uses a three-session rolling median of session-best e1RM to smooth fluctuations. That rolling estimate is different from the quarterly median or peak.
Four-week strength forecasting
forecast_features.py constructs historical, time-indexed training snapshots and predicts the change in smoothed e1RM over approximately four weeks, rather than directly predicting an absolute max.

The Ridge model uses the following features:
Feature	Meaning
Current e1RM	Most recent three-session rolling median
Recent strength trend	Estimated e1RM slope (lb/week)
Weekly volume load	Sets × reps × load over the past four weeks, divided by four
Sessions per week	Distinct exercise workouts per week
Sets per week	Eligible working sets per week
Average working weight	Mean eligible set weight
Days since last session	Recency of the latest eligible exercise session


The pipeline tests predictions chronologically against a no-change baseline (current smoothed e1RM carried forward). It prints both holdout errors and uses the lower-MAE approach for the selected forecast. The Ridge pipeline uses feature standardization and Ridge(alpha=10.0).

Important: This model-selection procedure is provisional. Historical samples are small and some forecast/label windows overlap; deduplicating repeated holdout outcome dates does not make every test independent. The reported holdout MAE is an exploratory result, not a production-grade accuracy guarantee.

Four-week training insights
forecast_insights.py compares the latest 28 days of eligible workouts for the selected exercise with the 28 days immediately before them. The output includes:
- Sessions per week
- Working sets per week
- Volume load (lb per week)
- Average working weight (lb)
- Median session e1RM (lb)
- Relative changes between the two windows, plus sample counts

Windows are anchored to the latest eligible session in the dataset, not necessarily the current calendar date. These metrics describe training changes; they do not prove that a metric caused the model's forecast.
Example output

The following is an illustrative run from a development workout history (October 2026); results vary by person, exercise, and available data.

Quarterly Analysis: Bench Press (Barbell)
quarter  sessions  median_e1rm_lb  peak_e1rm_lb
 2026Q2        20          191.83        198.33
 2026Q3        21          197.33        232.50
 2026Q4         5          192.00        198.33

===== FOUR-WEEK FEATURE-BASED FORECAST TEST =====
Weekly labeled snapshots: 31
Chronological train/test: 20 / 7
No-change holdout MAE: 14.98 lb
Feature model holdout MAE: 11.92 lb
Better holdout model: Feature Ridge

===== FINAL FORECAST =====
Selected model: Feature Ridge
Current smoothed e1RM: 192.50 lb
Forecast target: 2026-11-28
Selected 4-week forecast: 197.22 lb
Expected change: +4.72 lb

===== TRAINING INSIGHTS: Bench Press (Barbell) =====
Metric                           Previous       Recent       Change
Sessions / week                      0.75         1.25       +66.7%
Working sets / week                  2.75         4.75       +72.7%
Volume load (lb / week)          2,597.50     3,888.75       +49.7%
Avg working weight (lb)            141.36       159.21       +12.6%
Median session e1RM (lb)           180.83       192.00        +6.2%

In this seven-observation Bench Press holdout, Ridge reduced MAE relative to the no-change baseline by approximately 20.4%. This is a preliminary exercise-specific result, not evidence that Ridge is best for all exercises. In other tested lifts, the baseline performed better.

Repository layout
hevy_app_insights/
├── api_call.py              # Hevy API extraction and pagination
├── transform.py            # Set-level transforms, e1RM, summaries, charts, main entry point
├── cli.py                  # Interactive exercise selection
├── forecast_features.py    # Historical snapshots, Ridge model, baseline comparison
├── forecast_insights.py    # Previous vs recent 28-day training comparisons
├── requirements.txt        # Python dependencies
├── .gitignore              # Ignore credentials, private data, generated files
└── README.md

# Generated locally (not for Git):
# .env, .venv/, workouts_raw.json, quarterly_progress.png

How to run Hevy Insights

Hevy Insights runs locally in a terminal. You do not need to deploy a website or set up a database. The first run has two separate stages: download workouts with api_call.py, then analyze them with transform.py.
Quick start
Once Python, dependencies, and your Hevy API key are configured, run these two commands from the project folder:
python api_call.py
python transform.py
The first command refreshes workouts_raw.json; the second launches the interactive exercise selection and analysis. See the full setup below if this is your first run.

Prerequisites
- Python 3.9 or newer (python3 --version on macOS/Linux, or python --version on Windows)
- A Hevy account with API access and a personal API key (Hevy API documentation)
- The project files, including api_call.py, transform.py, cli.py, forecast_features.py, forecast_insights.py, and requirements.txt
1. Download the code and open a terminal in the project folder
Clone the repository using its GitHub Code → HTTPS URL, or download the ZIP and extract it. Then open a terminal inside the hevy_app_insights folder (the folder containing requirements.txt). For example, if you downloaded it into your current directory:
cd hevy_app_insights
2. Create a virtual environment and install dependencies
macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
If PowerShell blocks activation, use Command Prompt with .venv\Scripts\activate.bat, or use your system's approved virtual-environment activation settings.
3. Set up your Hevy API key
Create a file called .env in the project folder, containing:
HEVY_API_KEY=your_personal_hevy_api_key
Replace the placeholder with your own key. You can also provide HEVY_API_KEY as an environment variable; follow any API-key prompt shown by the script. Never upload .env or share your API key.
4. Download your workout history (api_call.py)
With your virtual environment active, run:
python api_call.py
This makes paginated requests to the Hevy API and writes your workout history to a local file named workouts_raw.json. The file is personal data and should not be committed to Git.
5. Analyze your workouts (transform.py)
python transform.py
The program displays an interactive numbered list of exercises. Enter the number of the exercise you want (for example, Bench Press) and press Enter.
Depending on the available workout history, the terminal will show:
1. Quarterly median e1RM, peak e1RM, and session counts.
2. A four-week forecast and a Ridge-versus-baseline historical MAE comparison, when sufficient recent training data are available.
3. Training insights comparing the most recent 28 days with the preceding 28 days: sessions, working sets, volume load, average working weight, and session e1RM.
4. A generated quarterly strength chart, saved locally (for example, quarterly_progress.png).
The forecasts are experimental; some exercises may use the no-change baseline or have insufficient data for a current forecast.
6. Run it again after logging more workouts
Whenever you want updated results, reopen your terminal in the project directory, activate the virtual environment, and run:
python api_call.py     # Refresh local workouts from Hevy
python transform.py   # Choose an exercise and view updated insights
You do not need to reinstall dependencies each time. The extraction step is separate from the analysis step: running only transform.py uses the last downloaded workouts_raw.json.

Common issues
Problem	What to check
ModuleNotFoundError	Activate .venv and rerun python -m pip install -r requirements.txt.
API authentication error	Verify your Hevy API access and that HEVY_API_KEY is correct.
Missing workouts_raw.json	Run python api_call.py before python transform.py.
Not enough sessions for a forecast	Choose an exercise with more eligible recent workouts. Quarterly analysis may still work.
Chart not found	Look in the directory from which you ran python transform.py.


Privacy and Git hygiene
Hevy workout exports can include personal history and timestamps. Keep private workout data, credentials, and local environments out of the repository.
Suggested .gitignore contents:
.env
.env.*
!.env.example
.venv/
__pycache__/
*.py[cod]
workouts_raw.json
*.png
.DS_Store
Before publishing, inspect staged files:
git status --short
git diff --cached --name-only
If a secret or private JSON file was already committed, adding it to .gitignore will not erase it from Git history; remove it from tracking/history as appropriate and rotate any exposed API key.

Limitations
- Estimated 1RM is not a tested max. The Epley estimate depends on effort, accurate logging, exercise selection, and rep range.
- Strength forecasts are experimental. Training outcomes are affected by factors outside this dataset, and a point forecast is not a guarantee or confidence interval.
- Evaluation is limited. Training snapshots and forecast outcomes can overlap; the limited test set is used to choose between Ridge and the baseline. More independent, forward-in-time evaluation is needed before claiming general accuracy.
- Some exercises may fall back to baseline or have no forecast. This is intentional when observed performance favors the baseline or data are insufficient/outdated.
- Weighted pull-ups and dips: Recorded load may represent added weight only; the current calculation does not incorporate bodyweight.
- Dumbbells, machines, and cables: Loads may be recorded differently across exercises and equipment, so estimates should generally be interpreted within the same exercise/template.
- Sparse training periods: A quarter with one or two sessions is less representative. Missing quarters indicate no eligible recorded data, not zero strength.
- Training insights are descriptive: Changes in frequency, sets, and volume cannot by themselves explain why the forecasting model made a prediction.
- Local CLI: This version uses terminal interaction and local chart files, not a hosted dashboard or mobile app.

Why I built it
This project explores how to turn an existing workout log into a small end-to-end data product: REST API integration → data ingestion → nested JSON transformation → feature engineering → time-aware model evaluation → interpretable exercise-level insights.
It also demonstrates practical Python, Pandas, NumPy, Matplotlib, and scikit-learn work without claiming that a prototype model is more accurate than the evidence supports.

Status
v1 — feature-complete MVP. Current functionality includes exercise selection, historical strength reporting, quarterly visualizations, provisional four-week forecasts, and recent-versus-previous training insights. Independent forecast validation and a graphical interface are potential future improvements.
