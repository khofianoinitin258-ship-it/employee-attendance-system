# Employee Attendance Management System

A web-based Employee Attendance Management System built with **Python (Flask)**, **MySQL/MariaDB**, **HTML/CSS/JavaScript**, and **Bootstrap 5**.

It supports admin and employee roles, employee/department management, clock in/out with late detection, attendance monitoring, configurable working hours, and attendance reports with CSV export.

## Features

### Administrator
- Secure login/logout
- Register, edit, deactivate/reactivate employees
- Create employee login accounts (hashed passwords)
- Manage departments
- View today's attendance overview (present/late/not clocked in)
- Configure working hours and timezone
- Generate daily, weekly, monthly, late, absence, and individual reports
- Export reports to CSV

### Employee
- Secure login/logout
- Clock in and clock out
- View today's attendance status and hours worked
- View personal attendance history
- View personal profile

## Attendance rules
- Default working hours: **08:00–17:00** (Africa/Accra), configurable by admin
- Clock in after start time is marked **late**
- Duplicate clock-ins are blocked (app check + DB unique constraint)
- Employee must clock in before clocking out
- Working hours are calculated automatically on clock out

## Tech stack
- Python 3.12, Flask
- PyMySQL
- MySQL/MariaDB (XAMPP MariaDB used in development)
- Bootstrap 5
- Git/GitHub

## Project structure

```text
app/            Flask blueprints, DB helpers, decorators
templates/      Jinja HTML templates
static/         CSS/JS
sql/            Database schema
scripts/        Setup scripts
tests/          unittest test suite
run.py          Development entry point
```

## Local setup (Windows)

1. **Install prerequisites**
   - Python 3.12+
   - Git
   - XAMPP (MySQL/MariaDB) or MySQL Server

2. **Start database**
   - Start MySQL/MariaDB in XAMPP Control Panel (port 3306)

3. **Clone and enter project**
   ```powershell
   git clone https://github.com/khofianoinitin258-ship-it/employee-attendance-system.git
   cd employee-attendance-system
   ```

4. **Create virtual environment and install deps**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

5. **Configure environment**
   ```powershell
   copy .env.example .env
   ```
   Edit `.env` if your DB credentials differ.

6. **Create database and seed admin**
   ```powershell
   .\.venv\Scripts\python.exe scripts\setup_database.py
   ```

7. **Run the app**
   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```
   Open http://127.0.0.1:5000

## Default admin account (development)
- Username: `admin`
- Password: `admin123`

**Change this before any real deployment.**

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

> Tests require the MariaDB/MySQL server to be running.

## Notes
- `.env` is ignored by Git; do not commit secrets.
- The project uses `Africa/Accra` by default and stores datetimes as local naive datetimes for consistency with MySQL `DATETIME`.
- For production, use a production WSGI server, strong secrets, HTTPS, and proper database user permissions.
