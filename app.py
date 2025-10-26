from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
import config

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

    return render_template('index.html',
                           dates=available_dates,
                           selected_date=selected_date,
                           plan=plan_records,
                           message=None,
                           workout_type=workout_type)


@app.route('/exercises')
def show_exercises():
    # Group exercises by Day Type
    grouped = exercise_df.groupby('Day Type')

    exercise_groups = []
    for day_type, group in grouped:
        exercises = group[['Exercise', 'Primary Muscle Group']].to_dict(orient='records')
        exercise_groups.append({'day_type': day_type, 'exercises': exercises})

    return render_template('exercises.html', exercise_groups=exercise_groups)

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)