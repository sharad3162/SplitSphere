from decimal import Decimal, ROUND_HALF_UP

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------- DATABASE CONNECTION ----------

def get_db():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        port=app.config["MYSQL_PORT"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"],
        ssl_ca=app.config["MYSQL_SSL_CA"],
        ssl_verify_cert=True,
        ssl_verify_identity=True
    )


# ---------- USER MODEL ----------
class User(UserMixin):
    def __init__(self, user_id, name, email):
        self.id = str(user_id)
        self.name = name
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, name, email FROM users WHERE id = %s",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return User(row["id"], row["name"], row["email"])
        return None
    finally:
        cursor.close()
        conn.close()


# ---------- HOME ----------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html", title="Home")


# ---------- REGISTRATION ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Enter your name, email, and a password of at least 8 characters.")
            return redirect(url_for("register"))

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
            flash("Registration successful! Please log in.")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            conn.rollback()
            flash("This email is already registered.")
        except mysql.connector.Error:
            conn.rollback()
            app.logger.exception("Registration failed")
            flash("Registration failed. Check your database setup.")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html", title="Register")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, name, email, password_hash FROM users WHERE email = %s",
                (email,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row["id"], row["name"], row["email"]))
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.")

    return render_template("login.html", title="Login")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", title="Dashboard")


# ---------- CREATE AND VIEW GROUPS ----------
@app.route("/groups", methods=["GET", "POST"])
@login_required
def groups():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == "POST":
            group_name = request.form.get("group_name", "").strip()
            description = request.form.get("description", "").strip()

            if not group_name:
                flash("Please enter a group name.")
                return redirect(url_for("groups"))

            try:
                cursor.execute(
                    "INSERT INTO expense_groups (group_name, description, created_by) VALUES (%s, %s, %s)",
                    (group_name, description, int(current_user.id)),
                )
                group_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)",
                    (group_id, int(current_user.id)),
                )
                conn.commit()
                flash("Group created successfully!")
            except mysql.connector.Error:
                conn.rollback()
                app.logger.exception("Group creation failed")
                flash("Could not create the group. Please check the database.")
            return redirect(url_for("groups"))

        cursor.execute("""
            SELECT eg.id, eg.group_name, eg.description, eg.created_at
            FROM expense_groups eg
            JOIN group_members gm ON gm.group_id = eg.id
            WHERE gm.user_id = %s
            ORDER BY eg.created_at DESC
        """, (int(current_user.id),))
        my_groups = cursor.fetchall()
        return render_template("groups.html", title="My Groups", groups=my_groups)
    finally:
        cursor.close()
        conn.close()


# ---------- GROUP EXPENSES ----------
@app.route("/groups/<int:group_id>/expenses", methods=["GET", "POST"])
@login_required
def expenses(group_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT eg.id, eg.group_name
            FROM expense_groups eg
            JOIN group_members gm ON gm.group_id = eg.id
            WHERE eg.id = %s AND gm.user_id = %s
        """, (group_id, int(current_user.id)))
        group = cursor.fetchone()

        if not group:
            flash("Group not found or you are not a member.")
            return redirect(url_for("groups"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            notes = request.form.get("notes", "").strip()
            try:
                amount = Decimal(request.form.get("amount", "0"))
            except Exception:
                amount = Decimal("0")

            if not title or not amount.is_finite() or amount <= 0:
                flash("Enter a valid expense title and amount.")
                return redirect(url_for("expenses", group_id=group_id))

            try:
                cursor.execute("""
                    INSERT INTO expenses (group_id, paid_by, title, amount, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (group_id, int(current_user.id), title, str(amount), notes))
                conn.commit()
                flash("Expense added successfully!")
            except mysql.connector.Error:
                conn.rollback()
                app.logger.exception("Expense creation failed")
                flash("Could not save the expense.")
            return redirect(url_for("expenses", group_id=group_id))

        cursor.execute("""
            SELECT e.id, e.title, e.amount, e.notes, e.created_at,
                   u.name AS payer_name
            FROM expenses e
            JOIN users u ON u.id = e.paid_by
            WHERE e.group_id = %s
            ORDER BY e.created_at DESC, e.id DESC
        """, (group_id,))
        expense_list = cursor.fetchall()
        total = sum((Decimal(str(item["amount"])) for item in expense_list), Decimal("0"))
        return render_template(
            "expenses.html", title="Group Expenses", group=group,
            expense_list=expense_list, total=total,
        )
    finally:
        cursor.close()
        conn.close()


# ---------- SETTLEMENT ----------
@app.route("/groups/<int:group_id>/settlement")
@login_required
def settlement(group_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT eg.id, eg.group_name
            FROM expense_groups eg
            JOIN group_members gm ON gm.group_id = eg.id
            WHERE eg.id = %s AND gm.user_id = %s
        """, (group_id, int(current_user.id)))
        group = cursor.fetchone()

        if not group:
            flash("Group not found or you are not a member.")
            return redirect(url_for("groups"))

        cursor.execute("""
            SELECT u.id, u.name, COALESCE(SUM(e.amount), 0) AS paid_total
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN expenses e
                ON e.group_id = gm.group_id AND e.paid_by = gm.user_id
            WHERE gm.group_id = %s
            GROUP BY u.id, u.name
            ORDER BY u.name, u.id
        """, (group_id,))
        members = cursor.fetchall()

        if not members:
            flash("Add members to this group first.")
            return redirect(url_for("groups"))

        for member in members:
            amount = Decimal(str(member["paid_total"] or 0))
            member["paid_cents"] = int(
                (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )

        total_cents = sum(member["paid_cents"] for member in members)
        member_count = len(members)
        base_share, remainder = divmod(total_cents, member_count)

        for index, member in enumerate(members):
            member["share_cents"] = base_share + (1 if index < remainder else 0)
            member["balance_cents"] = member["paid_cents"] - member["share_cents"]

        creditors = [
            {"name": m["name"], "balance": m["balance_cents"]}
            for m in members if m["balance_cents"] > 0
        ]
        debtors = [
            {"name": m["name"], "balance": -m["balance_cents"]}
            for m in members if m["balance_cents"] < 0
        ]

        settlements = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            amount_cents = min(debtors[i]["balance"], creditors[j]["balance"])
            settlements.append({
                "from_name": debtors[i]["name"],
                "to_name": creditors[j]["name"],
                "amount": amount_cents / 100,
            })
            debtors[i]["balance"] -= amount_cents
            creditors[j]["balance"] -= amount_cents
            if debtors[i]["balance"] == 0:
                i += 1
            if creditors[j]["balance"] == 0:
                j += 1

        for member in members:
            member["paid_display"] = member["paid_cents"] / 100
            member["share_display"] = member["share_cents"] / 100
            member["balance_display"] = member["balance_cents"] / 100

        return render_template(
            "settlement.html", title="Settlement", group=group,
            members=members, settlements=settlements, total_cents=total_cents,
        )
    finally:
        cursor.close()
        conn.close()


# ---------- MANAGE GROUP MEMBERS ----------
@app.route("/groups/<int:group_id>/members", methods=["GET", "POST"])
@login_required
def manage_members(group_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT eg.id, eg.group_name
            FROM expense_groups eg
            JOIN group_members gm ON gm.group_id = eg.id
            WHERE eg.id = %s AND gm.user_id = %s
        """, (group_id, int(current_user.id)))
        group = cursor.fetchone()

        if not group:
            flash("Group not found or you are not a member.")
            return redirect(url_for("groups"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
            friend = cursor.fetchone()

            if not friend:
                flash("No account found with that email. Ask your friend to register first.")
                return redirect(url_for("manage_members", group_id=group_id))

            try:
                cursor.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)",
                    (group_id, friend["id"]),
                )
                conn.commit()
                flash(friend["name"] + " added to the group!")
            except mysql.connector.IntegrityError:
                conn.rollback()
                flash("This person is already a group member.")
            except mysql.connector.Error:
                conn.rollback()
                app.logger.exception("Could not add group member")
                flash("Could not add this member. Please try again.")
            return redirect(url_for("manage_members", group_id=group_id))

        cursor.execute("""
            SELECT u.id, u.name, u.email
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = %s
            ORDER BY u.name
        """, (group_id,))
        members = cursor.fetchall()
        return render_template(
            "members.html", title="Manage Members", group=group, members=members
        )
    finally:
        cursor.close()
        conn.close()


# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
