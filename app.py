from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
import config
from flask import jsonify
import os

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
    # match exercise names with their primary muscle groups
    exercise_muscle_map = dict(zip(exercise_df['Exercise'], exercise_df['Primary Muscle Group']))
    for record in plan_records:
        exercise_name = record['Exercise']
        record['Primary Muscle Group'] = exercise_muscle_map.get(exercise_name, 'N/A')

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
                'Primary Muscle Group': row['Primary Muscle Group'],
                'Day Type': day
            })

    expanded_df = pd.DataFrame(expanded_rows)

    # Group exercises by the cleaned day types
    exercise_groups = []
    for day_type, group in expanded_df.groupby('Day Type'):
        exercises = group[['Exercise', 'Primary Muscle Group']].to_dict(orient='records')
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
            'Primary Muscle Group': item['PrimaryMuscleGroup'],
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

    # --- Filter only selected exercises ---
    filtered_df = workout_df[workout_df["Exercise"].isin(selected_exercises)]
    filtered_df = filtered_df.sort_values(by=["Exercise", "Date"], ascending=[True, True])

    # --- Handle no matches ---
    if filtered_df.empty:
        return jsonify([])

    # --- Convert all values to strings (for JSON safety) ---
    filtered_df = filtered_df.fillna("-").astype(str)

    return jsonify(filtered_df.to_dict(orient="records"))

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
