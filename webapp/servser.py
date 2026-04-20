# webapp/server.py
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from parser_schedule import parse_schedule, get_week_start
from database import get_user
from config import WEBAPP_PORT, DAYS_OF_WEEK

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/schedule/<group_id>")
def schedule_page(group_id):
    """Главная страница WebApp расписания"""
    return render_template("schedule.html", group_id=group_id)


@app.route("/api/schedule/<group_id>")
def api_schedule(group_id):
    """API для получения расписания"""
    date_str = request.args.get("date")

    if date_str:
        try:
            week_start = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            week_start = get_week_start()
    else:
        week_start = get_week_start()

    # Убедимся, что это понедельник
    week_start = get_week_start(week_start)

    schedule = parse_schedule(group_id, week_start)

    # Преобразуем для JSON
    result = {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": (week_start + timedelta(days=5)).strftime("%Y-%m-%d"),
        "week_start_display": week_start.strftime("%d.%m.%Y"),
        "week_end_display": (week_start + timedelta(days=5)).strftime("%d.%m.%Y"),
        "prev_week": (week_start - timedelta(days=7)).strftime("%Y-%m-%d"),
        "next_week": (week_start + timedelta(days=7)).strftime("%Y-%m-%d"),
        "days": [],
        "error": schedule.get("error", ""),
    }

    for i, day_name in enumerate(DAYS_OF_WEEK):
        day_date = week_start + timedelta(days=i)
        lessons = schedule.get("days", {}).get(day_name, [])
        date_str = schedule.get("dates", {}).get(day_name, day_date.strftime("%d.%m.%Y"))

        is_today = day_date.date() == datetime.now().date()

        result["days"].append({
            "name": day_name,
            "date": date_str,
            "is_today": is_today,
            "lessons": lessons,
        })

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=WEBAPP_PORT, debug=True)