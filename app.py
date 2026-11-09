import os
import smtplib
import logging
from email.message import EmailMessage
from sqlalchemy import URL
from datetime import date, datetime, timedelta
from functools import wraps

import click
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, UserMixin, current_user, login_required,
    login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash


# --------------------------------------------------
# LOGGING: show email diagnostics in the terminal
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------


app = Flask(__name__)

# Require production credentials from environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

required_settings = {
    "SECRET_KEY": SECRET_KEY,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_HOST": DB_HOST,
    "DB_NAME": DB_NAME,
}

missing_settings = [
    name for name, value in required_settings.items()
    if not value
]

if missing_settings:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(missing_settings)
    )

app.config["SECRET_KEY"] = SECRET_KEY
csrf = CSRFProtect(app)

app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    database=DB_NAME,
    query={"charset": "utf8mb4"},
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
DB_SSL_CA = os.getenv("DB_SSL_CA")

if DB_SSL_CA:
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "ssl": {"ca": DB_SSL_CA},
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }
    }

db = SQLAlchemy(app)
app.jinja_env.globals["timedelta"] = timedelta

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# --------------------------------------------------
# EMAIL NOTIFICATION SERVICE
# --------------------------------------------------

def send_email(to_email, subject, message_text):

    """Send an email using Gmail SMTP and log diagnostic results."""

    sender = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_APP_PASSWORD")

    # Temporary diagnostic messages. Never print the password.


    if not sender or not password or not to_email:
        logger.warning(
            "Email skipped: sender, app password, or recipient missing."
        )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message.set_content(message_text)

    try:
        logger.info("Connecting to Gmail SMTP server...")

        with smtplib.SMTP(
            "smtp.gmail.com", 587, timeout=20
        ) as server:
            server.starttls()
            logger.info("Gmail TLS connection established.")

            server.login(sender, password)
            logger.info("Gmail authentication successful.")

            server.send_message(message)

        logger.info("Email sent successfully to %s", to_email)
        return True

    except Exception:
        logger.exception("Email notification failed.")
        return False


def notify_status_change(appt, status):
    """Send an email for selected appointment status changes."""

    farmer = appt.farmer

    create_notification(
        farmer.id,
        "Appointment Status Updated",
        f"Your appointment status has been updated to: {status}. "
        f"Sample ID: {appt.sample_id}."
    )

    notifications = {
        "Confirmed": (
            "Soil Testing Appointment Confirmed",
            f"""Hello {farmer.full_name},

Your soil testing appointment has been confirmed.

Sample ID: {appt.sample_id}
Laboratory: {appt.lab_name}
Date: {appt.appointment_date}
Time: {appt.time_slot}
Farm location: {appt.farm_location}

Please keep your sample ID for reference.

Soil Testing Portal"""
        ),
        "Sample received": (
            "Soil Sample Received",
            f"""Hello {farmer.full_name},

Your soil sample has been received by the laboratory.

Sample ID: {appt.sample_id}

We will notify you when your soil test report is ready.

Soil Testing Portal"""
        ),
        "Testing in progress": (
            "Soil Testing in Progress",
            f"""Hello {farmer.full_name},

Testing of your soil sample is now in progress.

Sample ID: {appt.sample_id}

We will notify you when your report is ready.

Soil Testing Portal"""
        ),
        "Cancelled": (
            "Soil Testing Appointment Cancelled",
            f"""Hello {farmer.full_name},

Your soil testing appointment has been cancelled.

Sample ID: {appt.sample_id}
Date: {appt.appointment_date}
Time: {appt.time_slot}

Please contact the laboratory if you need assistance.

Soil Testing Portal"""
        ),
    }

    if status in notifications:
        subject, body = notifications[status]
        send_email(farmer.email, subject, body)


# --------------------------------------------------
# DATABASE MODELS
# --------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(
        db.String(180), unique=True, nullable=True, index=True
    )
    phone = db.Column(db.String(30), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="farmer")
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    appointments = db.relationship(
        "Appointment",
        back_populates="farmer",
        foreign_keys="Appointment.farmer_id",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    farm_location = db.Column(db.String(255), nullable=False)
    land_area_acres = db.Column(db.Float, nullable=True)
    crop_name = db.Column(db.String(120), nullable=False)
    lab_name = db.Column(
        db.String(160), nullable=False,
        default="Central Soil Testing Laboratory"
    )
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(30), nullable=False)
    sample_id = db.Column(
        db.String(40), unique=True, nullable=False
    )
    status = db.Column(
        db.String(30), nullable=False, default="Booked"
    )
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    farmer = db.relationship(
        "User",
        back_populates="appointments",
        foreign_keys=[farmer_id],
    )
    report = db.relationship(
        "SoilReport",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SoilReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointment.id"),
        unique=True, nullable=False
    )
    ph = db.Column(db.Float, nullable=True)
    ec = db.Column(db.Float, nullable=True)
    organic_carbon = db.Column(db.Float, nullable=True)
    nitrogen = db.Column(db.Float, nullable=True)
    phosphorus = db.Column(db.Float, nullable=True)
    potassium = db.Column(db.Float, nullable=True)
    other_parameters = db.Column(db.Text, nullable=True)
    interpretation = db.Column(db.Text, nullable=True)
    recommendations = db.Column(db.Text, nullable=True)
    prepared_by = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    approved = db.Column(
        db.Boolean, nullable=False, default=False
    )
    published_at = db.Column(db.DateTime, nullable=True)

    appointment = db.relationship(
        "Appointment", back_populates="report"
    )
    preparer = db.relationship(
        "User", foreign_keys=[prepared_by]
    )
# --------------------------------------------------
# FARMER NOTIFICATIONS
# --------------------------------------------------

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

# --------------------------------------------------
# LOGIN AND ACCESS CONTROL
# --------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def next_sample_id():
    return (
        "ST-"
        + datetime.utcnow().strftime("%y%m%d")
        + "-"
        + os.urandom(3).hex().upper()
    )
# --------------------------------------------------
# CREATE FARMER NOTIFICATION
# --------------------------------------------------

def create_notification(user_id, title, message):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message
    )

    db.session.add(notification)
    db.session.commit()

# --------------------------------------------------
# VIEW NOTIFICATIONS
# --------------------------------------------------

@app.route("/notifications")
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    for notification in user_notifications:
        notification.is_read = True

    db.session.commit()

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()

    return render_template(
        "notifications.html",
        notifications=user_notifications,
        unread_count=unread_count
    )
# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def index():

    return render_template("index.html")


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower() or None
        phone = request.form.get("phone", "").strip() or None
        password = request.form.get("password", "")

        if not name or (not email and not phone):
            flash(
                "Enter your name and either email or mobile number.",
                "danger",
            )
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("register.html")

        if email and User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("register.html")

        if phone and User.query.filter_by(phone=phone).first():
            flash("This mobile number is already registered.", "danger")
            return render_template("register.html")

        user = User(
            full_name=name,
            email=email,
            phone=phone,
            role="farmer",
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        login_user(user)

        flash("Account created. Welcome!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")

# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            (User.email == identifier.lower()) |
            (User.phone == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email/mobile number or password.", "danger")

    return render_template("login.html")

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------
# FARMER DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role in ("admin", "lab_staff"):
        return redirect(url_for("admin_dashboard"))

    appointments = Appointment.query.filter_by(
        farmer_id=current_user.id
    ).order_by(
        Appointment.appointment_date.desc(),
        Appointment.id.desc(),
    ).all()
    unread_count = Notification.query.filter_by(
    user_id=current_user.id,
    is_read=False
).count()
    return render_template(
    "dashboard.html",
    appointments=appointments,
    unread_count=unread_count
)


# --------------------------------------------------
# BOOK APPOINTMENT
# --------------------------------------------------

@app.route("/appointments/new", methods=["GET", "POST"])
@role_required("farmer")
def new_appointment():
    if request.method == "POST":
        location = request.form.get(
            "farm_location", ""
        ).strip()
        crop = request.form.get("crop_name", "").strip()
        lab = request.form.get(
            "lab_name", ""
        ).strip() or "Central Soil Testing Laboratory"
        date_text = request.form.get("appointment_date", "")
        slot = request.form.get("time_slot", "")
        notes = request.form.get("notes", "").strip()
        area_text = request.form.get(
            "land_area_acres", ""
        ).strip()

        try:
            appointment_date = date.fromisoformat(date_text)
            area = float(area_text) if area_text else None

            if area is not None and area <= 0:
                raise ValueError()

        except ValueError:
            flash(
                "Enter a valid future date and a positive land area.",
                "danger",
            )
            return render_template(
                "appointment_form.html",
                min_date=date.today().isoformat(),
            )

        valid_slots = {
            "09:00–10:00",
            "10:00–11:00",
            "11:00–12:00",
            "14:00–15:00",
            "15:00–16:00",
        }
        if (
            appointment_date < date.today()
            or not location
            or not crop
            or slot not in valid_slots
        ):
            flash(
                "Check the farm location, crop, date and time slot.",
                "danger",
            )
            return render_template(
                "appointment_form.html",
                min_date=date.today().isoformat(),
            )

        exists = Appointment.query.filter_by(
            lab_name=lab,
            appointment_date=appointment_date,
            time_slot=slot,
        ).filter(
            Appointment.status != "Cancelled"
        ).first()

        if exists:
            flash(
                "That laboratory slot is already booked. "
                "Please select another date or time.",
                "warning",
            )
            return render_template(
                "appointment_form.html",
                min_date=date.today().isoformat(),
            )

        appt = Appointment(
            farmer_id=current_user.id,
            farm_location=location,
            crop_name=crop,
            lab_name=lab,
            appointment_date=appointment_date,
            time_slot=slot,
            land_area_acres=area,
            sample_id=next_sample_id(),
            notes=notes,
        )

        db.session.add(appt)
        db.session.commit()
        create_notification(
    current_user.id,
    "Appointment Booked",
    f"Your appointment has been booked successfully. "
    f"Your Sample ID is {appt.sample_id}. "
    f"Your appointment is awaiting confirmation."
)

        # Booking notification
        send_email(
            current_user.email,
            "Soil Testing Appointment Booked",
            f"""Hello {current_user.full_name},

Your soil testing appointment has been booked successfully.

Sample ID: {appt.sample_id}
Laboratory: {appt.lab_name}
Date: {appt.appointment_date}
Time: {appt.time_slot}
Farm location: {appt.farm_location}

Your appointment is awaiting confirmation.

Soil Testing Portal""",
        )

        flash(
            f"Appointment booked. Your sample reference is "
            f"{appt.sample_id}.",
            "success",
        )
        return redirect(url_for("dashboard"))

    return render_template(
        "appointment_form.html",
        min_date=date.today().isoformat(),
    )


# --------------------------------------------------
# FARMER CANCELS APPOINTMENT
# --------------------------------------------------

@app.route(
    "/appointments/<int:appointment_id>/cancel",
    methods=["POST"],
)
@role_required("farmer")
def cancel_appointment(appointment_id):
    appt = db.get_or_404(Appointment, appointment_id)

    if appt.farmer_id != current_user.id:
        abort(403)

    if appt.status not in ("Booked", "Confirmed"):
        flash(
            "This appointment can no longer be cancelled online.",
            "warning",
        )
    else:
        appt.status = "Cancelled"
        db.session.commit()

        send_email(
            current_user.email,
            "Soil Testing Appointment Cancelled",
            f"""Hello {current_user.full_name},

Your soil testing appointment has been cancelled.

Sample ID: {appt.sample_id}
Date: {appt.appointment_date}
Time: {appt.time_slot}

Soil Testing Portal""",
        )

        flash("Appointment cancelled.", "info")

    return redirect(url_for("dashboard"))


# --------------------------------------------------
# VIEW REPORT
# --------------------------------------------------

@app.route("/reports/<int:report_id>")
@login_required
def view_report(report_id):
    report = db.get_or_404(SoilReport, report_id)
    appt = report.appointment

    if (
        current_user.role == "farmer"
        and appt.farmer_id != current_user.id
    ):
        abort(403)

    if current_user.role == "farmer" and not report.approved:
        abort(404)

    return render_template("report.html", report=report)


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

@app.route("/admin")
@role_required("admin", "lab_staff")
def admin_dashboard():
    appointments = Appointment.query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.id.desc(),
    ).all()

    users_count = User.query.filter_by(role="farmer").count()

    pending_count = Appointment.query.filter(
        Appointment.status.in_([
            "Booked",
            "Confirmed",
            "Sample received",
            "Testing in progress",
        ])
    ).count()

    reports_count = SoilReport.query.filter_by(
        approved=True
    ).count()

    return render_template(
        "admin_dashboard.html",
        appointments=appointments,
        users_count=users_count,
        pending_count=pending_count,
        reports_count=reports_count,
    )


# --------------------------------------------------
# UPDATE APPOINTMENT STATUS
# --------------------------------------------------

@app.route(
    "/admin/appointments/<int:appointment_id>/status",
    methods=["POST"],
)
@role_required("admin", "lab_staff")
def update_status(appointment_id):
    appt = db.get_or_404(Appointment, appointment_id)
    if appt.status == "Cancelled":
        flash("Cancelled appointments cannot be modified.", "warning")
        return redirect(url_for("admin_dashboard"))
    old_status = appt.status
    status = request.form.get("status", "")

    allowed = {
        "Booked",
        "Confirmed",
        "Sample received",
        "Testing in progress",
        "Report ready",
        "Cancelled",
    }

    if status not in allowed:
        abort(400)

    if status == "Report ready" and (
        not appt.report or not appt.report.approved
    ):
        flash(
            "Publish an approved report before setting this "
            "status to Report ready.",
            "warning",
        )
    else:
        appt.status = status
        db.session.commit()

        if status != old_status:
            notify_status_change(appt, status)

        flash("Appointment status updated.", "success")

    return redirect(url_for("admin_dashboard"))


# --------------------------------------------------
# CREATE OR PUBLISH SOIL REPORT
# --------------------------------------------------

@app.route(
    "/admin/appointments/<int:appointment_id>/report",
    methods=["GET", "POST"],
)
@role_required("admin", "lab_staff")
def edit_report(appointment_id):
    appt = db.get_or_404(Appointment, appointment_id)

    if appt.status == "Cancelled":
        flash("Reports cannot be created or edited for cancelled appointments.", "warning")
        return redirect(url_for("admin_dashboard"))

    report = appt.report

    if request.method == "POST":

        def optional_float(field):
            value = request.form.get(field, "").strip()

            if not value:
                return None

            number = float(value)

            if number < 0:
                raise ValueError()

            return number

        try:
            values = {
                "ph": optional_float("ph"),
                "ec": optional_float("ec"),
                "organic_carbon": optional_float("organic_carbon"),
                "nitrogen": optional_float("nitrogen"),
                "phosphorus": optional_float("phosphorus"),
                "potassium": optional_float("potassium"),
            }
        except ValueError:
            flash(
                "Numeric test values must be valid and non-negative.",
                "danger",
            )
            return render_template(
                "report_form.html",
                appointment=appt,
                report=report,
            )

        was_approved = bool(report and report.approved)

        if not report:
            report = SoilReport(
                appointment_id=appt.id,
                prepared_by=current_user.id,
            )
            db.session.add(report)

        for key, value in values.items():
            setattr(report, key, value)

        report.other_parameters = request.form.get(
            "other_parameters", ""
        ).strip()
        report.interpretation = request.form.get(
            "interpretation", ""
        ).strip()
        report.recommendations = request.form.get(
            "recommendations", ""
        ).strip()

        publish = request.form.get("publish") == "yes"
        report.approved = publish
        report.published_at = datetime.utcnow() if publish else None

        if publish:
            appt.status = "Report ready"

        db.session.commit()

        # Send report-ready email only on first publication
        if publish and not was_approved:
            farmer = appt.farmer

            create_notification(
        farmer.id,
        "Soil Report Ready",
        f"Your soil test report is ready! "
        f"Sample ID: {appt.sample_id}. "
        f"Please log in to view your report."
    )

            send_email(
                farmer.email,
                "Your Soil Test Report Is Ready",
                f"""Hello {farmer.full_name},

Your soil test report has been published and is ready to view.

Sample ID: {appt.sample_id}

Log in to your Soil Testing Portal account to view your report.

Soil Testing Portal""",
            )

        flash(
            "Report saved and published."
            if publish
            else "Draft report saved.",
            "success",
        )

        return redirect(url_for("admin_dashboard"))

    return render_template(
        "report_form.html",
        appointment=appt,
        report=report,
    )


# --------------------------------------------------
# CREATE DATABASE TABLES
# --------------------------------------------------

@app.cli.command("create-db")
def create_db():
    """Create database tables. Create the MySQL database first."""
    db.create_all()
    click.echo("Database tables created.")


# --------------------------------------------------
# CREATE ADMIN ACCOUNT
# --------------------------------------------------

@app.cli.command("create-admin")
@click.option("--name", prompt="Administrator name")
@click.option("--email", prompt="Administrator email")
@click.password_option()
def create_admin(name, email, password):
    """Create an administrator account."""
    email = email.strip().lower()

    if User.query.filter_by(email=email).first():
        click.echo("That email already exists.")
        return

    user = User(
        full_name=name.strip(),
        email=email,
        role="admin",
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    click.echo(f"Administrator account created for {email}.")


# --------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------

@app.errorhandler(403)
def forbidden(_error):
    return render_template(
        "error.html",
        code=403,
        message="You do not have permission to view this page.",
    ), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template(
        "error.html",
        code=404,
        message="The requested page or report was not found.",
    ), 404


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", 5000)),
        debug=False,
    )
