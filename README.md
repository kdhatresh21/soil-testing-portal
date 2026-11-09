# Soil Testing Appointment & Report Access Portal

A beginner-friendly Flask + MySQL web application for farmers to book soil-testing appointments and view approved digital reports. Laboratory staff and administrators can manage appointment status and enter/publish test results.

Features in this starter version

* Farmer registration and login with hashed passwords
* Role-based access: farmer, lab staff, administrator
* Appointment booking with date, time slot and duplicate-slot protection
* Unique soil sample reference
* Farmer dashboard and appointment cancellation
* Laboratory/admin dashboard and appointment status updates
* Soil report drafts, approval/publication and farmer report access
* Report screen that can be printed or saved as PDF from the browser

1. Requirements

* Python 3.10 or newer
* MySQL Server 8.x (or a compatible MySQL server)
* A terminal/command prompt
* A web browser

2. Create the MySQL database

Start MySQL and run:

```sql
CREATE DATABASE soil_testing_portal_public
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

You can also run the included `schema.sql` in MySQL Workbench.

3. Install the project

Extract the ZIP, open a terminal in the `soil_testing_portal_public` folder, then run:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='replace-with-a-long-random-secret'
export DB_USER='root'
export DB_PASSWORD='your_mysql_password'
export DB_HOST='localhost'
export DB_NAME='soil_testing_portal_public'
flask --app app create-db
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:DB_USER="root"
$env:DB_PASSWORD="your_mysql_password"
$env:DB_HOST="localhost"
$env:DB_NAME="soil_testing_portal_public"
flask --app app create-db
```

If your MySQL root account has no password, set `DB_PASSWORD` to an empty string. If you use another database user, grant it privileges on `soil_testing_portal_public` and use that account.

4. Create an administrator

With the virtual environment active and environment variables set:

```bash
flask --app app create-admin
```

Enter the administrator's name, email and password when prompted. Do not share this account with farmers.

5. Run the app

```bash
flask --app app run --debug
```

Open http://127.0.0.1:5000 in your browser.

6. Basic usage / demo flow

1. Open the site and register a farmer account.
2. Log in as the farmer and choose **Book appointment**.
3. Enter farm location, crop, lab, date and time slot.
4. Check the farmer dashboard for the generated `ST-...` sample reference.
5. Log out and log in using the administrator account.
6. Open the admin dashboard and update the appointment status to **Sample received** or **Testing in progress**.
7. Choose **Enter report**, enter the available lab values and interpretation.
8. Save as draft to keep the report private, or tick **Publish approved report** to make it visible to the farmer.
9. Log out and log in as the farmer. Open the report from the dashboard.

The app currently supports one booking per laboratory/date/time slot. Change the capacity logic in `new_appointment()` if a laboratory can accept multiple samples per slot.

7. Testing checklist

* [ ] Register a farmer with a valid email and password of at least 8 characters.
* [ ] Try registering the same email again; it should be rejected.
* [ ] Log in with the wrong password; access should be rejected.
* [ ] Book a future appointment; a sample reference should be generated.
* [ ] Try booking the same lab/date/slot; the second booking should be rejected.
* [ ] Try booking a past date; it should be rejected.
* [ ] Confirm a farmer cannot open another farmer's report URL.
* [ ] Confirm a farmer cannot access `/admin`.
* [ ] As admin, update appointment status.
* [ ] Save a draft report; it should not be visible to the farmer.
* [ ] Publish a report; the farmer should be able to view it.
* [ ] Use the report page's **Print / Save PDF** button and choose Save as PDF.

## 8. Project structure

```text
soil_testing_portal_public/
|-- app.py
|-- check_login.py
|-- email_service.py
|-- requirements.txt
|-- schema.sql
|-- .env.example
|-- .gitignore
|-- README.md
|-- static/
|   `-- style.css
`-- templates/
    |-- admin_dashboard.html
    |-- appointment_form.html
    |-- base.html
    |-- dashboard.html
    |-- error.html
    |-- index.html
    |-- login.html
    |-- notifications.html
    |-- register.html
    |-- report.html
    `-- report_form.html
```

## 9. Security and deployment notes



This project includes CSRF protection using Flask-WTF, password hashing, role-based access control and environment-based configuration.



Before public deployment:



* Use a strong, unique production SECRET_KEY.
* Use a separate online MySQL database. Never expose your local database.
* Configure Gmail SMTP credentials using environment variables.
* Use HTTPS in production.
* Keep database backups.
* Test access permissions for farmers, laboratory staff and administrators.
* Run without Flask debug mode in production.
* Use approved laboratory standards when interpreting soil results and preparing recommendations.



The PDF option uses the browser's print-to-PDF feature. It does not create or store a server-side PDF file.
