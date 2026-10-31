from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from flask_mail import Mail, Message
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
load_dotenv()
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USERNAME")
mail = Mail(app)
app.secret_key = "labgear_book_demo_secret_key_change_later"


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Muthu@2008",
        database="labgear_book"
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "student")

    if not name or not email or len(password) < 6:
        return "Please enter a name, valid email, and password with at least 6 characters."

    if role not in ("student", "faculty"):
        role = "student"

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, generate_password_hash(password), role)
        )
        connection.commit()

        return """
        <h2>Registration successful!</h2>
        <p>Your account has been created.</p>
        <a href="/">Go to Login</a>
        """

    except mysql.connector.IntegrityError:
        return 'This email is already registered. <a href="/">Go back</a>'

    except mysql.connector.Error as error:
        app.logger.error("Registration database error: %s", error)
        return "Database error while registering. Please check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, name, email, password, role FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard | LabGear Book</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f1f5f9;
            color: #172554;
            text-align: center;
        }}
        header {{
            background: #123b75;
            color: white;
            padding: 25px;
        }}
        header span {{ color: #93c5fd; }}
        .card {{
            max-width: 550px;
            margin: 50px auto;
            padding: 35px 20px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 20px #0f172a12;
        }}
        .btn {{
            display: block;
            margin: 15px auto;
            max-width: 280px;
            padding: 14px;
            border-radius: 8px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            font-weight: bold;
        }}
        .logout {{ background: #dc2626; }}
    </style>
</head>
<body>
    <header>
        <h1>LabGear <span>Book</span></h1>
        <p>Campus Lab & Resource Scheduler</p>
    </header>
    <main class="card">
        <h2>Welcome, {user['name']}!</h2>
        <p>Login successful 🎉</p>
        <p>Account Type: <strong>{user['role'].title()}</strong></p>
        <a class="btn" href="/resources">Browse Lab Resources</a>
        <a class="btn" href="/my-bookings">My Bookings</a>
        {"<a class='btn' href='/faculty-bookings'>Faculty Approvals</a>" if user['role'] == 'faculty' else ""}
        <a class="btn logout" href="/logout">Logout</a>
    </main>
</body>
</html>
"""

        return 'Incorrect email or password. <a href="/">Try again</a>'

    except mysql.connector.Error as error:
        app.logger.error("Login database error: %s", error)
        return "Database error while logging in. Please check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route("/resources")
def resources():
    if "user_id" not in session:
        return redirect("/")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, name, description, location, status FROM resources"
        )
        all_resources = cursor.fetchall()

        return render_template(
            "resources.html",
            resources=all_resources,
            name=session.get("name")
        )

    except mysql.connector.Error as error:
        app.logger.error("Resources database error: %s", error)
        return "Could not load resources. Please check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route("/book/<int:resource_id>", methods=["GET", "POST"])
def book_resource(resource_id):
    if "user_id" not in session:
        return redirect("/")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, name, status FROM resources WHERE id = %s",
            (resource_id,)
        )
        resource = cursor.fetchone()

        if not resource:
            return "Resource not found.", 404

        if request.method == "POST":
            booking_date = request.form.get("booking_date")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")

            if not booking_date or not start_time or not end_time:
                return "Please fill in all fields. <a href='/resources'>Back</a>"

            if start_time >= end_time:
                return "End time must be after start time. <a href='/resources'>Back</a>"

            cursor.execute(
                """
                SELECT id FROM bookings
                WHERE resource_id = %s
                AND booking_date = %s
                AND status IN ('pending', 'approved')
                AND start_time < %s
                AND end_time > %s
                """,
                (resource_id, booking_date, end_time, start_time)
            )

            if cursor.fetchone():
                return "Already booked for this time. <a href='/resources'>Back</a>"

            cursor.execute(
                """
                INSERT INTO bookings
                (user_id, resource_id, booking_date, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                """,
                (
                    session["user_id"],
                    resource_id,
                    booking_date,
                    start_time,
                    end_time
                )
            )
            connection.commit()

            return """
            <h2>Booking Request Submitted!</h2>
            <p>Your booking is pending approval.</p>
            <a href="/resources">Back to Resources</a>
            """

        return render_template(
            "book.html",
            resource=resource,
            today=__import__("datetime").date.today().isoformat()
        )

    except mysql.connector.Error as error:
        app.logger.error("Booking database error: %s", error)
        return "Could not process booking. Check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route("/faculty-bookings")
def faculty_bookings():
    if "user_id" not in session:
        return redirect("/")

    if session.get("role") != "faculty":
        return "Access denied. Faculty only."

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                bookings.id,
                users.name AS student_name,
                resources.name AS resource_name,
                bookings.booking_date,
                bookings.start_time,
                bookings.end_time,
                bookings.status
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            JOIN resources ON bookings.resource_id = resources.id
            ORDER BY bookings.booking_date DESC
            """
        )

        all_bookings = cursor.fetchall()

        return render_template(
            "faculty_bookings.html",
            bookings=all_bookings
        )

    except mysql.connector.Error as error:
        app.logger.error("Faculty bookings error: %s", error)
        return "Could not load bookings. Check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/booking-status/<int:booking_id>/<action>", methods=["POST"])
def update_booking_status(booking_id, action):
    if "user_id" not in session:
        return redirect("/")

    if session.get("role") != "faculty":
        return "Access denied. Faculty only."

    if action not in ("approve", "reject"):
        return "Invalid action.", 400

    new_status = "approved" if action == "approve" else "rejected"

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT users.email, users.name, resources.name AS resource_name,
                   bookings.booking_date, bookings.start_time, bookings.end_time
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            JOIN resources ON bookings.resource_id = resources.id
            WHERE bookings.id = %s AND bookings.status = 'pending'
            """,
            (booking_id,)
        )

        booking_info = cursor.fetchone()

        if not booking_info:
            return "Booking not found or already processed.", 404

        cursor.execute(
            """
            UPDATE bookings
            SET status = %s
            WHERE id = %s AND status = 'pending'
            """,
            (new_status, booking_id)
        )

        connection.commit()

        try:
            msg = Message(
                subject=f"LabGear Book: Booking {new_status.title()}",
                recipients=[booking_info["email"]]
            )

            msg.body = (
                f"Hi {booking_info['name']},\n\n"
                f"Your lab resource booking has been {new_status}.\n\n"
                f"Resource: {booking_info['resource_name']}\n"
                f"Date: {booking_info['booking_date']}\n"
                f"Start time: {booking_info['start_time']}\n"
                f"End time: {booking_info['end_time']}\n\n"
                "Thank you for using LabGear Book!"
            )
             
            mail.send(msg)

        except Exception as email_error:
            app.logger.error("Email notification failed: %s", email_error)

        return redirect("/faculty-bookings")

    except mysql.connector.Error as error:
        app.logger.error("Booking status update error: %s", error)
        return "Could not update booking. Check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route("/my-bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect("/")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                bookings.id,
                resources.name AS resource_name,
                bookings.booking_date,
                bookings.start_time,
                bookings.end_time,
                bookings.status
            FROM bookings
            JOIN resources
                ON bookings.resource_id = resources.id
            WHERE bookings.user_id = %s
            ORDER BY bookings.booking_date DESC
            """,
            (session["user_id"],)
        )

        bookings_list = cursor.fetchall()

        return render_template(
            "my_bookings.html",
            bookings=bookings_list,
            name=session.get("name")
        )

    except mysql.connector.Error as error:
        app.logger.error("My bookings database error: %s", error)
        return "Could not load your bookings. Check the server terminal."

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)