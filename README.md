# StudentHub

StudentHub is a Flask web application for organizing student assignments, study
notes, and tasks in one workspace.

## Features

- Account signup, login, and logout
- Password hashing with Werkzeug
- Dashboard statistics and recent assignments/tasks
- Assignment, note, and task CRUD operations
- Assignment search and status filtering
- Task completion toggling
- Session-based authentication and ownership checks
- JSON REST APIs used by the JavaScript interface
- CSRF protection, input validation, and security headers

## Technology stack

- Python
- Flask
- Flask-SQLAlchemy
- SQLite for local development
- Jinja templates
- HTML and CSS
- Vanilla JavaScript with `fetch()`

## Project structure

```text
studenthub/
├── app.py                 # Flask application, models, routes, and APIs
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable names and placeholders
├── templates/             # Jinja HTML templates
├── static/
│   ├── style.css          # Application styles
│   └── script.js          # Browser-side API and UI behavior
├── studenthub.db          # Local database (ignored by Git)
└── myenv/                # Local virtual environment (ignored by Git)
```

The project also contains `.vscode/settings.json`, which points this local
workspace at the existing Windows virtual environment. It is machine-specific
and is ignored by Git.

## Setup on Windows

Open PowerShell in the project directory.

### 1. Create a virtual environment

The project already uses `myenv`. For a fresh checkout, create a new local
environment with:

```powershell
py -m venv myenv
```

Do not commit the environment directory.

### 2. Activate the environment

```powershell
.\myenv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the interpreter directly instead:

```powershell
.\myenv\Scripts\python.exe --version
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` for local reference and configure the variables
in the shell or your local environment. Never commit `.env`.

```text
STUDENTHUB_ENV=development
STUDENTHUB_SECRET_KEY=replace_with_a_secure_random_secret
```

For production, set `STUDENTHUB_ENV=production` and provide a strong,
random `STUDENTHUB_SECRET_KEY`. The application refuses to start in production
when that secret is missing. The current application does not load `.env`
automatically, so PowerShell environment variables can be set like this:

```powershell
$env:STUDENTHUB_ENV = "development"
$env:STUDENTHUB_SECRET_KEY = "use-a-local-secret"
```

## Run locally

With the virtual environment active:

```powershell
python app.py
```

Open <http://127.0.0.1:5000> in a browser.

The built-in Flask server is for local development only. Use a production WSGI
server and HTTPS when deploying.

## Database

StudentHub uses Flask-SQLAlchemy with a local SQLite database at
`studenthub.db`. The application creates missing tables and preserves existing
local data. The database is intentionally ignored by Git because it contains
local user and application data. A future deployment should use a managed
database and a separate migration process.

## Authentication

Users sign up with an email address and password. Passwords are stored as
Werkzeug hashes rather than plain text. A successful login stores the
authenticated user's ID in a signed Flask session cookie. Protected routes use
that session and apply ownership checks so users can access only their own
assignments, notes, and tasks.

## REST APIs and JavaScript

The assignment, note, task, and dashboard API routes return JSON. The browser
code in `static/script.js` calls these routes with `fetch()` to load records,
create and update data, delete records, toggle task completion, and refresh
dashboard statistics.

State-changing API requests include the CSRF token supplied by the page. The
server validates the token, authenticates the session, validates the JSON
payload, and applies the current user's ownership scope before changing data.

## Git preparation

The repository should include application source, templates, static assets,
`requirements.txt`, `.env.example`, and this README. It should not include
`myenv`, `.env`, cache files, `.vscode`, or local SQLite database files.
