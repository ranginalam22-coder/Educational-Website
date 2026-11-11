# Evergreen University

A university website with four faculty pages, 14 undergraduate programs, student registration and login, online applications, a student dashboard, and a role-protected admissions administration page with CSV export.

## Run locally

Requires Python 3.10 or later. The server uses only Python's standard library and SQLite; there are no packages to install.

On Windows, open PowerShell in this folder:

```powershell
py -3 server.py
```

Then open <http://127.0.0.1:8000/>.

Do not open the HTML files directly. The website and its API must be served by `server.py`.

## Create an administrator

In another PowerShell window, from this folder:

```powershell
py -3 server.py --create-admin admissions-admin@example.edu
```

Enter and confirm a password of at least 12 characters when prompted. Sign in at `/login.html`; administrator accounts are sent to `/admin.html`. Student accounts can be created through `/create-account.html`.

## Data and deployment

- The SQLite database is created as `university.sqlite3` in this folder on first start. It stores faculty/program catalog data, account records, sessions, and admission applications.
- Set `EVERGREEN_DB` to move the database to a protected persistent-data location. `EVERGREEN_HOST` and `EVERGREEN_PORT` configure the bind address and port.
- Back up the database file regularly and restrict access to it and to administrator accounts. CSV exports contain personal applicant information.
- For a public deployment, use a production-grade HTTPS reverse proxy, firewall, backups, and monitored host. Configure forwarded HTTPS headers correctly so session cookies are marked `Secure`. The built-in Python HTTP server is intended for local development and a small demonstration, not as a hardened public production server.
- Passwords are stored with salted PBKDF2-HMAC-SHA256 hashes; sessions use HttpOnly, SameSite cookies and state-changing API requests require a CSRF token. Use HTTPS for all real accounts and applicant data.
- The admissions administrator can review records, change an application status, and export separate Excel-compatible UTF-8 CSV files for applications and registered student accounts.

## Pages

- `index.html` — University homepage
- `faculty-engineering.html`
- `faculty-computer-science.html`
- `faculty-business.html`
- `faculty-law.html`
- `create-account.html` and `login.html`
- `admission.html` — Online admission application
- `dashboard.html` — Student profile and application status
- `admin.html` — Administrator application review and export

## Languages

The website interface is available in English, Spanish, French, Persian, Arabic, Hindi, Chinese, Portuguese, Russian, and Japanese. Language preference is saved in the browser; Persian and Arabic use right-to-left layout.
