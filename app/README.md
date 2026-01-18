# VPEMaster - Toastmasters Club Management System

VPEMaster is a comprehensive web application designed to help Toastmasters clubs, particularly the Vice President Education (VPE), manage meeting agendas, book roles, track member speeches, and handle club settings efficiently.

## Features

- **Dynamic Agenda Management**: Create, update, and reorder meeting agendas with real-time start time calculations.
- **Role Booking System**: Members can book roles for upcoming meetings, and officers can manage assignments.
- **Speech & Pathway Tracking**: Log member speeches, track progress through Pathways, and manage project history.
- **Contact Management**: Maintain a directory of members and guests.
- **Customizable Exports**: Export formatted agendas and raw data dumps for PowerBI analysis.
- **Role-Based Permissions**: Granular access control for different user roles (Admin, VPE, Member, etc.).
- **Configurable Settings**: Customize session types, role requirements, and club-specific details through a settings UI and configuration files.

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy ORM (compatible with SQLite, PostgreSQL, MySQL) with Flask-Migrate for database migrations.
    - *Architectural Note*: Both `user_clubs` and `contact_clubs` associate contacts with clubs. `user_clubs` specifically links contacts to actual user accounts, while `contact_clubs` tracks all potential members (both registered users and guest contacts) within a club context.
- **Frontend**: Jinja2 templates, JavaScript, HTML, CSS.

---

## Installation

Follow these steps to set up the VPEMaster application on your local machine.

### 1. Prerequisites

- **Python 3.8+** and `pip`.
- **Git** for cloning the repository.
- **Database Server**: A database server like **MySQL** or PostgreSQL is required for production. For simple local development, SQLite can be used without a separate server.
- A **virtual environment manager** like `venv` or `conda` (recommended).

### 2. Clone the Repository

Open your terminal and clone the project repository:

```bash
git clone <your-repository-url>
cd vpemaster
```

### 3. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

**Using `venv`:**

```bash
# Create the environment
python3 -m venv venv

# Activate the environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 4. Install Dependencies

Install all the required Python packages using the `requirements.txt` file.

```bash
# Ensure you have a requirements.txt file
pip install -r requirements.txt
```

> **Note**: If a `requirements.txt` file is not present, you will need to create one based on the project's imports. Key libraries include `Flask`, `Flask-SQLAlchemy`, `Flask-Migrate`, `Flask-Bcrypt`, `python-dotenv`, `openpyxl`, and `markdown`.

---

## Configuration

The application requires a few configuration files to be set up before its first run.

### 1. Environment Variables (`.env` file)

Create a file named `.env` in the root directory of the project. This file will store sensitive configuration details.

```ini
# .env

# A strong, random string for session security.
# You can generate one in a Python shell with:
# >>> import secrets
# >>> secrets.token_hex(16)
SECRET_KEY='your_generated_secret_key'

# The connection string for your database.
# Examples below:

# For SQLite (simplest for local development):
DATABASE_URL='sqlite:///vpemaster.db'

# For PostgreSQL:
# DATABASE_URL='postgresql://user:password@localhost/vpemaster_db'

# For MySQL:
# DATABASE_URL='mysql+pymysql://user:password@localhost/vpemaster_db'
```

### 3. Database Initialization

With the `DATABASE_URL` configured in your `.env` file, you can now create and initialize the database using Flask-Migrate.

Run the following commands in your terminal (with the virtual environment activated):

```bash
# Initializes the migration environment (run only once)
flask db init

# Creates the initial migration script based on your models
flask db migrate -m "Initial database schema"

# Applies the migration to the database, creating the tables
flask db upgrade
```

---

## Running the Application

### 1. Development Server

To run the application in a local development environment, use the following command:

```bash
flask run
```

The application will be available at `http://127.0.0.1:5000`.

### 2. First-Time Setup: Creating an Admin User

The application does not have a default admin user. Follow these steps to create one:

1.  Run the application and navigate to the registration page.
2.  Create a new user account.
3.  By default, this user will have the 'Member' role. You need to manually update their role to 'Admin' in the database.
4.  Use a database management tool (like DB Browser for SQLite) to open your database (`vpemaster.db` if using SQLite).
5.  Find the `Users` table and change the `Role` column for your newly created user from `Member` to `Admin`.
6.  Log in with your user, who will now have administrative privileges.

### 3. Production

For a production deployment, do not use the built-in Flask development server. Instead, use a production-ready WSGI server like Gunicorn or uWSGI.

Example using Gunicorn:

```bash
gunicorn --workers 4 --bind 0.0.0.0:8000 run:app
```
