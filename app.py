from flask import Flask, render_template, request, redirect, send_from_directory
from datetime import date
import os

from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set in .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = Flask(__name__)
@app.route("/sw.js")
def service_worker():
    return send_from_directory(
        "static",
        "sw.js",
        mimetype="application/javascript"
    )


def get_active_expenses():
    response = (
        supabase
        .table("expenses")
        .select("id, person, description, amount, expense_date")
        .eq("settled", False)
        .order("expense_date", desc=True)
        .order("id", desc=True)
        .execute()
    )

    return [
        (
            expense["id"],
            expense["person"],
            expense["description"],
            float(expense["amount"]),
            expense["expense_date"]
        )
        for expense in response.data
    ]


def get_settlements():
    response = (
        supabase
        .table("settlements")
        .select(
            "id, settlement_date, total, "
            "mehrshad_paid, shaghayegh_paid, "
            "share_per_person, debt_text"
        )
        .order("settlement_date", desc=True)
        .order("id", desc=True)
        .execute()
    )

    return [
        (
            settlement["id"],
            settlement["settlement_date"],
            float(settlement["total"]),
            float(settlement["mehrshad_paid"]),
            float(settlement["shaghayegh_paid"]),
            float(settlement["share_per_person"]),
            settlement["debt_text"]
        )
        for settlement in response.data
    ]


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

        supabase.table("expenses").insert({
            "person": person,
            "description": description,
            "amount": amount,
            "expense_date": expense_date,
            "settled": False
        }).execute()

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

    if request.method == "POST":
        person = request.form["person"]
        description = request.form["description"]
        amount = float(request.form["amount"])
        expense_date = request.form["expense_date"]

        supabase.table("expenses").update({
            "person": person,
            "description": description,
            "amount": amount,
            "expense_date": expense_date
        }).eq("id", expense_id).eq("settled", False).execute()

        return redirect("/")

    response = (
        supabase
        .table("expenses")
        .select("id, person, description, amount, expense_date")
        .eq("id", expense_id)
        .eq("settled", False)
        .maybe_single()
        .execute()
    )

    if not response.data:
        return redirect("/")

    expense = (
        response.data["id"],
        response.data["person"],
        response.data["description"],
        float(response.data["amount"]),
        response.data["expense_date"]
    )

    return render_template(
        "edit.html",
        expense=expense
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):

    supabase.table("expenses").delete() \
        .eq("id", expense_id) \
        .eq("settled", False) \
        .execute()

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

    supabase.table("settlements").insert({
        "settlement_date": date.today().isoformat(),
        "total": total,
        "mehrshad_paid": mehrshad_total,
        "shaghayegh_paid": shaghayegh_total,
        "share_per_person": share_per_person,
        "debt_text": debt_text
    }).execute()

    supabase.table("expenses").update({
        "settled": True
    }).eq("settled", False).execute()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)