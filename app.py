from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
import config
from flask import jsonify
from difflib import get_close_matches
import os
import re

# 🧹 Helper function to normalize exercise names
def normalize_exercise(name):
    if not isinstance(name, str):
        return ""
    # Remove parentheses and text inside them, lowercase, trim spaces
    name = re.sub(r'\(.*?\)', '', name)
    return name.strip().lower()

app = Flask(__name__)

# Load main workout CSV (for the daily view)
workout_df = pd.read_csv('gym_routines_with_muscles.csv')
workout_df['Date'] = workout_df['Date'].astype(str).str.strip()
available_dates = sorted(workout_df['Date'].unique(), key=lambda x: datetime.strptime(x, "%d %b"))

# Load exercise–muscle–day mapping CSV
exercise_df = pd.read_csv('exercise_muscle_daytype.csv')

@app.route('/', methods=['GET', 'POST'])
def show_plan():
    today_str = datetime.now().strftime("%d %b")
    selected_date = request.form.get('date') or today_str

    # 🔁 RELOAD CSV fresh each time
    workout_df = pd.read_csv('gym_routines_with_muscles.csv')
    workout_df['Date'] = workout_df['Date'].astype(str).str.strip()
    available_dates = sorted(workout_df['Date'].unique(), key=lambda x: datetime.strptime(x, "%d %b"))

    # Filter for selected date
    plan = workout_df[workout_df['Date'].str.startswith(selected_date)]

    if plan.empty:
        message = f"No workout planned for {selected_date} 💆‍♀️"
        return render_template('index.html',
                               dates=available_dates,
                               selected_date=selected_date,
                               plan=None,
                               message=message,
                               workout_type=None)

    workout_type = plan.iloc[0]['Workout Type']
    plan_records = plan.to_dict(orient='records')
    # match exercise names with their Muscle Groups
# 🧠 Build the normalized lookup map
    exercise_muscle_map = {
        normalize_exercise(ex): muscle
        for ex, muscle in zip(exercise_df['Exercise'], exercise_df['Muscle Group'])
    }

    # 🔍 Apply matching using normalized names
    for record in plan_records:
        normalized_name = normalize_exercise(record['Exercise'])
        print(normalized_name)
        record['Muscle Group'] = exercise_muscle_map.get(normalized_name, 'N/A')

    return render_template('index.html',
                           dates=available_dates,
                           selected_date=selected_date,
                           plan=plan_records,
                           message=None,
                           workout_type=workout_type)


@app.route('/exercises')
def show_exercises():
    # --- 🧠 Split multi-day entries (e.g. "Arms/Push Day" -> ["Arms", "Push Day"]) ---
    expanded_rows = []

    for _, row in exercise_df.iterrows():
        # Split by "/" and clean whitespace
        day_types = [d.strip() for d in str(row['Day Type']).split('/') if d.strip()]
        for day in day_types:
            expanded_rows.append({
                'Exercise': row['Exercise'],
                'Muscle Group': row['Muscle Group'],
                'Day Type': day
            })

    expanded_df = pd.DataFrame(expanded_rows)

    # Group exercises by the cleaned day types
    exercise_groups = []
    for day_type, group in expanded_df.groupby('Day Type'):
        exercises = group[['Exercise', 'Muscle Group']].to_dict(orient='records')
        exercise_groups.append({'day_type': day_type, 'exercises': exercises})

    # Sort alphabetically for nicer dropdown display
    exercise_groups = sorted(exercise_groups, key=lambda x: x['day_type'].lower())

    return render_template('exercises.html', exercise_groups=exercise_groups)

@app.route('/save_plan', methods=['POST'])
def save_plan():
    data = request.get_json()
    date = data.get('date')
    plan = data.get('plan', [])
    workout_type = data.get('workout_type', 'N/A')

    if not plan:
        return jsonify({'status': 'error', 'message': 'No data received'})

    csv_path = 'gym_routines_with_muscles.csv'
    df = pd.read_csv(csv_path)

    # Remove existing rows for that date (replace plan)
    df = df[df['Date'] != date]

    # Add the updated plan
    for item in plan:
        new_row = {
            'Date': date,
            'Workout Type': workout_type,
            'Exercise': item['Exercise'],
            'Sets': item['Sets'],
            'Reps': item['Reps'],
            'Weight': item['Weight'],
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(csv_path, index=False)

    return jsonify({'status': 'success', 'message': f'✅ Plan for {date} saved successfully!'})

@app.route("/history")
def history():
    # Render page (JS will fetch filtered data)
    return render_template("history.html")

@app.route("/api/history_data", methods=["POST"])
def history_data():
    data = request.get_json()
    selected_exercises = data.get("exercises", [])

    # --- Load the dataset safely ---
    csv_path = "gym_routines_with_muscles.csv"
    if not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 404

    workout_df = pd.read_csv(csv_path)

    # --- Normalize all exercise names ---
    workout_df["normalized_exercise"] = workout_df["Exercise"].apply(normalize_exercise)
    normalized_selected = [normalize_exercise(e) for e in selected_exercises]

    # --- Try to find close matches (to handle typos, plural forms, etc.) ---
    matched_rows = []
    for sel in normalized_selected:
        # Exact normalized match first
        matches = workout_df[workout_df["normalized_exercise"] == sel]
        if matches.empty:
            # Try fuzzy matching (e.g., "bicep curls" vs "biceps curl")
            possible_keys = get_close_matches(sel, workout_df["normalized_exercise"].unique(), n=1, cutoff=0.8)
            if possible_keys:
                matches = workout_df[workout_df["normalized_exercise"] == possible_keys[0]]
        if not matches.empty:
            matched_rows.append(matches)

    if not matched_rows:
        return jsonify([])

    # --- Combine and clean ---
    filtered_df = pd.concat(matched_rows)
    filtered_df = filtered_df.sort_values(by=["Exercise", "Date"], ascending=[True, True])
    filtered_df = filtered_df.fillna("-").astype(str)

    return jsonify(filtered_df.to_dict(orient="records"))

@app.route("/newplan")
def new_plan():
    return render_template("newplan.html")

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
