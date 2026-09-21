from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date

app = Flask(__name__)

DB = "expenses.db"


def init_db():
    conn = sqlite3.connect(DB)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            settled INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            settlement_date TEXT NOT NULL,
            total REAL NOT NULL,
            mehrshad_paid REAL NOT NULL,
            shaghayegh_paid REAL NOT NULL,
            share_per_person REAL NOT NULL,
            debt_text TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_active_expenses():
    conn = sqlite3.connect(DB)

    expenses = conn.execute("""
        SELECT id, person, description, amount, expense_date
        FROM expenses
        WHERE settled = 0
        ORDER BY expense_date DESC, id DESC
    """).fetchall()

    conn.close()
    return expenses


def get_settlements():
    conn = sqlite3.connect(DB)

    settlements = conn.execute("""
        SELECT id, settlement_date, total,
               mehrshad_paid, shaghayegh_paid,
               share_per_person, debt_text
        FROM settlements
        ORDER BY settlement_date DESC, id DESC
    """).fetchall()

    conn.close()
    return settlements


def calculate_summary(expenses):
    total = sum(expense[3] for expense in expenses)

    mehrshad_total = sum(
        expense[3]
        for expense in expenses
        if expense[1] == "Mehrshad"
    )

    shaghayegh_total = sum(
        expense[3]
        for expense in expenses
        if expense[1] == "Shaghayegh"
    )

    share_per_person = total / 2 if total else 0

    mehrshad_balance = mehrshad_total - share_per_person
    shaghayegh_balance = shaghayegh_total - share_per_person

    if mehrshad_balance > 0:
        debt_text = (
            f"Shaghayegh owes Mehrshad "
            f"{mehrshad_balance:.2f} SEK"
        )
    elif shaghayegh_balance > 0:
        debt_text = (
            f"Mehrshad owes Shaghayegh "
            f"{shaghayegh_balance:.2f} SEK"
        )
    else:
        debt_text = "You are even!"

    return (
        total,
        mehrshad_total,
        shaghayegh_total,
        share_per_person,
        debt_text
    )


@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":
        person = request.form["person"]
        description = request.form["description"]
        amount = float(request.form["amount"])
        expense_date = request.form["expense_date"]

        conn = sqlite3.connect(DB)

        conn.execute("""
            INSERT INTO expenses
            (person, description, amount, expense_date, settled)
            VALUES (?, ?, ?, ?, 0)
        """, (
            person,
            description,
            amount,
            expense_date
        ))

        conn.commit()
        conn.close()

        return redirect("/")

    expenses = get_active_expenses()

    (
        total,
        mehrshad_total,
        shaghayegh_total,
        share_per_person,
        debt_text
    ) = calculate_summary(expenses)

    settlements = get_settlements()

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        mehrshad_total=mehrshad_total,
        shaghayegh_total=shaghayegh_total,
        share_per_person=share_per_person,
        debt_text=debt_text,
        settlements=settlements,
        today=date.today().isoformat()
    )


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):

    conn = sqlite3.connect(DB)

    if request.method == "POST":
        person = request.form["person"]
        description = request.form["description"]
        amount = float(request.form["amount"])
        expense_date = request.form["expense_date"]

        conn.execute("""
            UPDATE expenses
            SET person = ?,
                description = ?,
                amount = ?,
                expense_date = ?
            WHERE id = ?
            AND settled = 0
        """, (
            person,
            description,
            amount,
            expense_date,
            expense_id
        ))

        conn.commit()
        conn.close()

        return redirect("/")

    expense = conn.execute("""
        SELECT id, person, description, amount, expense_date
        FROM expenses
        WHERE id = ?
        AND settled = 0
    """, (expense_id,)).fetchone()

    conn.close()

    if expense is None:
        return redirect("/")

    return render_template(
        "edit.html",
        expense=expense
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):

    conn = sqlite3.connect(DB)

    conn.execute("""
        DELETE FROM expenses
        WHERE id = ?
        AND settled = 0
    """, (expense_id,))

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/settle", methods=["POST"])
def settle():

    expenses = get_active_expenses()

    if not expenses:
        return redirect("/")

    (
        total,
        mehrshad_total,
        shaghayegh_total,
        share_per_person,
        debt_text
    ) = calculate_summary(expenses)

    conn = sqlite3.connect(DB)

    conn.execute("""
        INSERT INTO settlements
        (
            settlement_date,
            total,
            mehrshad_paid,
            shaghayegh_paid,
            share_per_person,
            debt_text
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        date.today().isoformat(),
        total,
        mehrshad_total,
        shaghayegh_total,
        share_per_person,
        debt_text
    ))

    conn.execute("""
        UPDATE expenses
        SET settled = 1
        WHERE settled = 0
    """)

    conn.commit()
    conn.close()

    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)