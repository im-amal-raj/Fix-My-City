# FixMyCity 🏙️

**Live Demo:** [Insert PythonAnywhere Live Link Here]
**GitHub Repository:** [Insert GitHub Repository Link Here]

FixMyCity is a role-based civic issue tracking platform built with Django. It bridges the gap between citizens and local government by allowing residents to report infrastructure issues (like potholes, broken streetlights, or water leaks), and providing a streamlined dashboard for city officials to triage and assign those tasks to field workers.

## 👥 User Roles & Access Control

The platform implements strict Role-Based Access Control (RBAC) with three distinct user types:

1. **Citizen (`CITIZEN`)**
   * **Abilities:** Submit new issues with photos and GPS coordinates, track their own reports, view the community map, and follow other public issues.
   * **Economy:** Operates on a "Civic Points" system to prevent spam.

2. **Officer (`OFFICER` / Staff)**
   * **Abilities:** Triage incoming tickets. They can review photos and data, validate genuine issues, reject junk, and assign validated tickets to specific Field Workers.

3. **Field Worker (`FIELD_WORKER` / Staff)**
   * **Abilities:** Receive assigned tasks, view the exact map location of the issue, and mark tickets as "Resolved" by uploading a proof-of-resolution photo.

## ✨ Core Features

* **Civic Economy (Anti-Spam Gamification):** 
  Citizens start with 15 points. Submitting a ticket costs 5 points. If an officer validates the ticket, the citizen is rewarded with +10 points (net gain). If rejected, the citizen is penalized. Points refill slightly every 24 hours to prevent permanent lockouts.
* **Algorithmic Auto-Triage:** 
  Submitted tickets are automatically parsed for keywords (e.g., "urgent", "danger", "pothole") to assign an initial Priority Score (1-10) and automatically route the ticket to the correct city department (e.g., PWD_Roads, KWA_Water).
* **Spatial Deduplication:** 
  When a new ticket is submitted, the backend calculates the Haversine distance against existing active tickets. If a similar issue is found within 50 meters, it is flagged as a potential duplicate to reduce worker redundancy.
* **Interactive Mapping:** 
  Integrated Leaflet.js mapping with free CartoDB dark tiles for selecting issue locations and viewing community feeds without requiring paid API keys.
* **Automated Email Notifications:** 
  Integrated Django SMTP backend to automatically email users when their tickets are validated, rejected, or resolved.

## 🛠️ Technology Stack

* **Backend:** Python, Django 6.x
* **Database:** SQLite3 (Perfect for portability and intermediate-level deployments)
* **Frontend:** HTML5, Vanilla JavaScript, Tailwind CSS (via CDN)
* **Maps:** Leaflet.js

## 🚀 Local Setup & Installation

Follow these steps to run the project locally:

1. **Clone the repository**
   ```bash
   git clone [Insert GitHub Repository Link Here]
   cd fix-my-street
   ```

2. **Set up a Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install django pillow
   ```

4. **Apply Database Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create a Superuser (Admin)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Configure Email (Optional)**
   * Open `fixmycity/settings.py`
   * Add your Gmail address to `EMAIL_HOST_USER`
   * Add your 16-character Google App Password (without spaces) to `EMAIL_HOST_PASSWORD`

7. **Run the Development Server**
   ```bash
   python manage.py runserver
   ```
   * Access the app at `http://127.0.0.1:8000/`
   * Access the admin panel at `http://127.0.0.1:8000/admin/` to create Officer and Worker accounts.

## 📚 Mentorship & Project Guidelines

This project was built to satisfy standard academic project guidelines:
* **Minimum Modules:** User Management, Issue Management (CRUD), Dashboard/Reporting.
* **Database Operations:** Full CRUD implemented natively via Django ORM.
* **Code Quality:** Backend logic cleanly separated into `utils.py` (algorithms), `views.py` (controllers), and `models.py` (data structures). No over-reliance on third-party APIs.
