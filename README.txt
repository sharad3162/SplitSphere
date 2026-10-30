BILLSPLIT CAMPUS - PROJECT SETUP
================================

Project files:
- app.py: Flask routes and backend logic
- config.py: application/database configuration
- templates/: HTML pages
- static/css/style.css: CSS styling
- .env.example: example environment settings (not your actual credentials)
- requirements.txt: Python dependencies

IMPORTANT:
1. Keep your existing MySQL database and tables. This code expects the same table names:
   users, expense_groups, group_members, expenses.
2. Do not overwrite your real .env file with a public example or share it.
3. Copy the existing working .env file into the project root if it is not already there.
   It should contain SECRET_KEY, MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD and MYSQL_DATABASE.
4. If your existing project has a working venv, you can keep using it.
5. Install any missing requirements in your activated virtual environment:
   pip install -r requirements.txt
6. Run from the project root:
   python app.py
7. Open:
   http://127.0.0.1:5000

If you are replacing an existing project, make a backup first. This version keeps
the current feature set but changes HTML rendering from inline strings to templates.
