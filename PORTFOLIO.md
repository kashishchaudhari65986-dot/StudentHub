# StudentHub Portfolio Notes

StudentHub is a Flask-based student productivity platform for managing assignments, study notes, and tasks in one authenticated workspace.

## Resume-Ready Bullets

- Built a student productivity platform with assignment, note, and task CRUD, task completion toggling, dashboard statistics, and client-side search and filtering.
- Implemented a Flask and Jinja backend with Flask-SQLAlchemy, JavaScript `fetch()` interactions, JSON REST APIs, SQLite local development, and PostgreSQL production support.
- Applied password hashing, session-based authentication, CSRF protection, server-side validation, ownership checks, security headers, Gunicorn, and Render deployment with a health endpoint.

## Technical Interview Talking Points

1. **Database portability:** The application uses SQLite for local development and selects PostgreSQL through `DATABASE_URL` in production, keeping local setup simple while supporting a managed deployment database.
2. **Ownership and authorization:** Each assignment, note, and task is associated with a user, and protected queries scope records to the authenticated user's ID before reads or changes.
3. **Browser/API boundary:** Jinja renders the initial pages, while `static/script.js` uses `fetch()` against JSON endpoints for interactive CRUD operations and dashboard updates.
4. **Request protection:** State-changing requests require a session CSRF token, and server-side validation checks payload shape, required fields, lengths, dates, and allowed assignment statuses.
5. **Production readiness:** Render runs the Flask application with Gunicorn, uses PostgreSQL for persistent production data, and checks `/health` to verify service availability.

## 30-Second Explanation

StudentHub is a student productivity app I built with Flask. It lets authenticated users manage assignments, notes, and tasks from a dashboard, with CRUD operations and task completion tracking. The pages use Jinja and JavaScript `fetch()` calls to communicate with REST APIs. Locally it uses SQLite, while the deployed Render service uses PostgreSQL, with session security, CSRF protection, validation, and ownership checks built into the backend.

## 1-Minute Explanation

StudentHub solves a focused organization problem: keeping assignments, study notes, and tasks together in one account-based workspace. The backend is written in Flask with Jinja templates and Flask-SQLAlchemy models for users, assignments, notes, and tasks. The browser loads server-rendered pages and then uses JavaScript `fetch()` to call JSON APIs for listing, creating, updating, deleting, and toggling records. The backend validates input, requires CSRF tokens for state-changing requests, hashes passwords, manages sessions, and scopes records to the authenticated user so one user cannot operate on another user's data. SQLite keeps local development lightweight, while `DATABASE_URL` enables PostgreSQL in production. The application is deployed on Render with Gunicorn and a `/health` endpoint for service monitoring.

## Name

Kashish Chaudhari