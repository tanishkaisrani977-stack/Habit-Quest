# Habit-Quest

Habit Quest is a full-stack gamified habit tracker built with Flask, SQLite, HTML, CSS, and JavaScript. It helps users build daily habits with XP, streaks, levels, a leaderboard, and progress tracking.

## Run locally

The Flask server serves both the frontend and API. From this folder, install the dependencies and start the server:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Then open [http://localhost:5000](http://localhost:5000). Do not open `index.html` directly or use a separate static server unless you configure `window.HABIT_QUEST_API_BASE`; those methods can send `/api/...` requests to the frontend server, which responds with HTML instead of JSON.
