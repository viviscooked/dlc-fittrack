import gradio as gr
import sqlite3
import jwt
import datetime
import pandas as pd
import os
import google.generativeai as genai

genai.configure(api_key="AIzaSyDydi2hsZV8yh_nv8hqIccQk_1Eqq0GFF0")
model = genai.GenerativeModel('gemini-1.5-pro')

def init_db():
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY, username TEXT, workout_type TEXT, duration INTEGER, calories INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS goals (username TEXT PRIMARY KEY, daily_calories INTEGER, weekly_workouts INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (id INTEGER PRIMARY KEY, username TEXT, rating INTEGER, feedback TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS food_tracker (id INTEGER PRIMARY KEY, username TEXT, food_name TEXT, calories INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS workout_types (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')

    default_workouts = [('Running',), ('Cycling',), ('Swimming',), ('Weight Training',), ('Yoga',), ('HIIT',)]
    c.executemany('INSERT OR IGNORE INTO workout_types (name) VALUES (?)', default_workouts)
    conn.commit()
    conn.close()

init_db()

SECRET_KEY = "super-secret-123" 

def signup_user(username, password):
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        return "Username already exists", False, None
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()
    return validate_user(username, password)

def validate_user(username, password):
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    user = c.execute("SELECT username FROM users WHERE username=? AND password=?", (username, password)).fetchone()
    conn.close()
    if user:
        token = jwt.encode({ 'user': username, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1) }, SECRET_KEY, algorithm='HS256')
        return f"✅ Login successful! Welcome {username}", True, token
    return "❌ Invalid credentials", False, None

def logout():
    return "👋 Logged out successfully", False, None

def get_workout_types():
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    types = c.execute("SELECT name FROM workout_types").fetchall()
    conn.close()
    return [t[0] for t in types]

def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])['user']

def add_workout(token, workout_type, duration, date):
    try:
        username = decode_token(token)
        calories = int(duration) * 5
        conn = sqlite3.connect('fitness.db')
        c = conn.cursor()
        c.execute("INSERT INTO workouts (username, workout_type, duration, calories, date) VALUES (?, ?, ?, ?, ?)",
                  (username, workout_type, duration, calories, date))
        conn.commit()
        conn.close()
        return f"💪 Workout added: {workout_type} for {duration} minutes on {date}"
    except:
        return "⚠️ Session expired or invalid. Please login again."

def add_food(token, food_name, calories, date):
    try:
        username = decode_token(token)
        conn = sqlite3.connect('fitness.db')
        c = conn.cursor()
        c.execute("INSERT INTO food_tracker (username, food_name, calories, date) VALUES (?, ?, ?, ?)",
                  (username, food_name, calories, date))
        conn.commit()
        conn.close()
        return f"🍎 Food logged: {food_name} ({calories} calories) on {date}"
    except:
        return "⚠️ Session expired or invalid. Please login again."

def view_progress(token):
    try:
        username = decode_token(token)
        conn = sqlite3.connect('fitness.db')
        workouts_df = pd.read_sql_query(f"SELECT date, SUM(calories) as calories_burned FROM workouts WHERE username='{username}' GROUP BY date", conn)
        food_df = pd.read_sql_query(f"SELECT date, SUM(calories) as calories_consumed FROM food_tracker WHERE username='{username}' GROUP BY date", conn)
        conn.close()
        if workouts_df.empty and food_df.empty:
            return "📉 No activity recorded yet."

        workouts_df['date'] = pd.to_datetime(workouts_df['date'])
        food_df['date'] = pd.to_datetime(food_df['date'])
        all_dates = pd.concat([workouts_df['date'], food_df['date']]).unique()
        summary_lines = []
        for date in sorted(all_dates):
            date_str = date.strftime('%Y-%m-%d')
            burned = workouts_df[workouts_df['date'] == date]['calories_burned'].sum()
            consumed = food_df[food_df['date'] == date]['calories_consumed'].sum()
            net = burned - consumed
            summary_lines.append(f"📆 {date_str}:\n🔥 Burned: {burned} cal\n🍽️ Consumed: {consumed} cal\n📊 Net: {net:+d} {'(Deficit)' if net > 0 else '(Surplus)'}\n")
        return "\n".join(summary_lines)
    except Exception as e:
        return f"Error: {str(e)}"

def clear_user_data(token):
    try:
        username = decode_token(token)
        conn = sqlite3.connect('fitness.db')
        c = conn.cursor()
        c.execute("DELETE FROM workouts WHERE username=?", (username,))
        c.execute("DELETE FROM food_tracker WHERE username=?", (username,))
        conn.commit()
        conn.close()
        return "🗑️ All workout and food tracking data cleared."
    except:
        return "⚠️ Session expired or invalid. Please login again."

def submit_rating(token, rating, feedback):
    try:
        username = decode_token(token)
        conn = sqlite3.connect('fitness.db')
        c = conn.cursor()
        c.execute("INSERT INTO ratings (username, rating, feedback, date) VALUES (?, ?, ?, ?)",
                  (username, rating, feedback, datetime.date.today().isoformat()))
        conn.commit()
        conn.close()
        return "✅ Thank you for your feedback!"
    except:
        return "⚠️ Session expired or invalid. Please login again."

def view_ratings():
    try:
        conn = sqlite3.connect('fitness.db')
        df = pd.read_sql_query("SELECT username, rating, feedback, date FROM ratings ORDER BY date DESC", conn)
        conn.close()
        if df.empty:
            return "No ratings yet."
        ratings_summary = []
        for _, row in df.iterrows():
            rating = int(row['rating']) if isinstance(row['rating'], (int, float)) else 0
            rating = max(1, min(rating, 5))
            ratings_summary.append(f"{row['date']} - {row['username']}:\n⭐ {'★' * rating} (Rating: {rating})\n💬 {row['feedback']}\n")
        return "\n".join(ratings_summary)
    except Exception as e:
        return f"Error: {str(e)}"

def chat_with_bot(user_input):
    try:
        response = model.generate_content(user_input)
        return response.text
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def fitness_plan(age, weight, height, goal_weight, gender, activity_level):
    try:
        weight = float(weight)
        height = float(height)
        age = int(age)
        goal_weight = float(goal_weight)

        if gender.lower() == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        activity_multiplier = {
            "Sedentary": 1.2,
            "Lightly active": 1.375,
            "Moderately active": 1.55,
            "Very active": 1.725,
            "Super active": 1.9
        }.get(activity_level, 1.2)

        tdee = bmr * activity_multiplier
        weight_diff = goal_weight - weight
        calories_needed = 7700 * abs(weight_diff)

        if weight_diff < 0:
            daily_deficit = 500
            days_needed = calories_needed / daily_deficit
            return (f"Your BMR is ~{int(bmr)} kcal/day, and your TDEE is ~{int(tdee)} kcal/day.\n\n"
                    f"To lose {abs(weight_diff):.1f} kg, aim for ~{int(tdee - daily_deficit)} kcal/day.\n"
                    f"Estimated time to reach goal: {int(days_needed)} days (~{int(days_needed // 7)} weeks).")
        elif weight_diff > 0:
            daily_surplus = 300
            days_needed = calories_needed / daily_surplus
            return (f"Your BMR is ~{int(bmr)} kcal/day, and your TDEE is ~{int(tdee)} kcal/day.\n\n"
                    f"To gain {abs(weight_diff):.1f} kg, aim for ~{int(tdee + daily_surplus)} kcal/day.\n"
                    f"Estimated time to reach goal: {int(days_needed)} days (~{int(days_needed // 7)} weeks).")
        else:
            return "🎯 You're already at your goal weight!"
    except Exception as e:
        return f"⚠️ Error calculating plan: {str(e)}"

with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue")) as app:
    gr.Markdown("# 🏋️‍♂️ **FitTrack** - Your Personal Fitness Dashboard")

    is_logged = gr.State(False)
    token_state = gr.State()

    with gr.Column(visible=True) as login_page:
        gr.Markdown("### 🔐 Login or Create Account")
        username = gr.Textbox(label="Username")
        password = gr.Textbox(label="Password", type="password")
        with gr.Row():
            login_btn = gr.Button("Login", variant="primary")
            signup_btn = gr.Button("Sign Up", variant="secondary")
        login_output = gr.Textbox(label="Status", interactive=False)

    with gr.Column(visible=False) as app_page:
        logout_btn = gr.Button("Logout", variant="secondary")

        with gr.Tab("🏋️ Add Workout"):
            workout_type = gr.Dropdown(choices=get_workout_types(), label="Workout Type")
            duration = gr.Number(label="Duration (minutes)")
            workout_date = gr.Textbox(label="Date (YYYY-MM-DD)")
            workout_btn = gr.Button("Add Workout")
            workout_output = gr.Textbox(interactive=False)

        with gr.Tab("🍎 Log Food"):
            food_name = gr.Textbox(label="Food Name")
            calories = gr.Number(label="Calories")
            food_date = gr.Textbox(label="Date (YYYY-MM-DD)")
            food_btn = gr.Button("Log Food")
            food_output = gr.Textbox(interactive=False)

        with gr.Tab("📈 Progress"):
            progress_btn = gr.Button("View Progress")
            clear_btn = gr.Button("Clear All Progress", variant="secondary")
            progress_output = gr.Textbox(lines=10, interactive=False)

        with gr.Tab("💬 Chat with Bot"):
            chat_input = gr.Textbox(label="Ask anything about fitness!")
            chat_btn = gr.Button("Get Response")
            chat_output = gr.Textbox(label="Bot Response", interactive=False)

        with gr.Tab("🌟 Submit Rating"):
            rating = gr.Slider(1, 5, step=1, label="Your Rating")
            feedback = gr.Textbox(label="Your Feedback")
            submit_btn = gr.Button("Submit Feedback")
            rating_output = gr.Textbox(interactive=False)

        with gr.Tab("📋 View Ratings"):
            view_ratings_btn = gr.Button("View All Ratings")
            ratings_output = gr.Textbox(lines=10, interactive=False)

        with gr.Tab("🎯 Set Fitness Goal"):
            age_input = gr.Number(label="Age (years)")
            weight_input = gr.Number(label="Current Weight (kg)")
            height_input = gr.Number(label="Height (cm)")
            gender_input = gr.Dropdown(choices=["Male", "Female"], label="Gender")
            goal_weight_input = gr.Number(label="Goal Weight (kg)")
            activity_level_input = gr.Dropdown(
                choices=["Sedentary", "Lightly active", "Moderately active", "Very active", "Super active"],
                label="Activity Level"
            )
            get_plan_btn = gr.Button("Generate Plan")
            plan_output = gr.Textbox(label="Personalized Plan", lines=6, interactive=False)

        workout_btn.click(add_workout, [token_state, workout_type, duration, workout_date], [workout_output])
        food_btn.click(add_food, [token_state, food_name, calories, food_date], [food_output])
        progress_btn.click(view_progress, [token_state], [progress_output])
        clear_btn.click(clear_user_data, [token_state], [progress_output])
        chat_btn.click(chat_with_bot, [chat_input], [chat_output])
        submit_btn.click(submit_rating, [token_state, rating, feedback], [rating_output])
        view_ratings_btn.click(view_ratings, [], [ratings_output])
        get_plan_btn.click(fitness_plan, [age_input, weight_input, height_input, goal_weight_input, gender_input, activity_level_input], [plan_output])

    def switch_ui(is_logged_in):
        return gr.update(visible=not is_logged_in), gr.update(visible=is_logged_in)

    login_btn.click(validate_user, [username, password], [login_output, is_logged, token_state]).then(switch_ui, [is_logged], [login_page, app_page])
    signup_btn.click(signup_user, [username, password], [login_output, is_logged, token_state]).then(switch_ui, [is_logged], [login_page, app_page])
    logout_btn.click(logout, outputs=[login_output, is_logged, token_state]).then(switch_ui, [is_logged], [login_page, app_page])

app.launch(server_name="0.0.0.0", server_port=5000)
