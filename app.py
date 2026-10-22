"""
app.py - Flask Web Application and REST API for Athenaeum Library Management System.
Features:
- Full RESTful API for Catalog, Patrons, Circulation, Holds, and Fines
- Real-time autonomous simulation runner with background thread
- Dynamic CSV reporting and receipts
- Premium web dashboard serving interactive UI
"""

import os
import csv
import io
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response

import models
from database import init_db, get_system_config, update_system_config
from simulator import simulator
from seed_data import seed_database

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Auto-simulation thread management
auto_sim_lock = threading.Lock()
auto_sim_running = False
auto_sim_interval_seconds = 3

def background_sim_worker():
    """Background thread that advances simulation when auto_sim is activated."""
    global auto_sim_running
    while True:
        with auto_sim_lock:
            active = auto_sim_running
        if active:
            try:
                simulator.advance_time(1)
            except Exception as e:
                print(f"[Sim Worker Error] {e}")
        time.sleep(auto_sim_interval_seconds)

sim_thread = threading.Thread(target=background_sim_worker, daemon=True)
sim_thread.start()

# ==========================================
# WEB VIEW ROUTES
# ==========================================

@app.route("/")
def index():
    """Serves the main single-page application dashboard."""
    return render_template("index.html")

# ==========================================
# ANALYTICS & DASHBOARD APIS
# ==========================================

@app.route("/api/analytics/dashboard", methods=["GET"])
def api_dashboard_stats():
    """Returns top-level KPIs and library status."""
    try:
        stats = models.get_dashboard_stats()
        stats["auto_sim_running"] = auto_sim_running
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/analytics/charts", methods=["GET"])
def api_chart_data():
    """Returns aggregated datasets for Chart.js visualizations."""
    try:
        data = models.get_chart_analytics()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# SIMULATION CONTROL APIS
# ==========================================

@app.route("/api/simulation/state", methods=["GET"])
def api_sim_state():
    """Returns simulation engine state and recent events."""
    try:
        config = get_system_config()
        events = models.get_recent_events(limit=30)
        return jsonify({
            "success": True,
            "current_sim_date": config.get("current_sim_date", "2026-10-01"),
            "fine_rate": float(config.get("fine_rate_per_day", 0.50)),
            "auto_sim_running": auto_sim_running,
            "recent_events": events
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/simulation/step", methods=["POST"])
def api_sim_step():
    """Advance simulation by N days (default: 1)."""
    try:
        payload = request.get_json(silent=True) or {}
        days = int(payload.get("days", 1))
        result = simulator.advance_time(days=days)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/simulation/toggle_auto", methods=["POST"])
def api_toggle_auto():
    """Toggle continuous simulation background loop."""
    global auto_sim_running
    payload = request.get_json(silent=True) or {}
    desired_state = payload.get("active")
    with auto_sim_lock:
        if desired_state is None:
            auto_sim_running = not auto_sim_running
        else:
            auto_sim_running = bool(desired_state)
        current = auto_sim_running
    return jsonify({"success": True, "auto_sim_running": current})

@app.route("/api/simulation/reset", methods=["POST"])
def api_sim_reset():
    """Resets database and re-initializes rich seed scenario."""
    global auto_sim_running
    with auto_sim_lock:
        auto_sim_running = False
    try:
        seed_database(reset=True)
        return jsonify({"success": True, "message": "Library database reset to initial seed state."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/simulation/events", methods=["GET"])
def api_sim_events():
    """Retrieve recent simulation event stream."""
    try:
        limit = min(100, int(request.args.get("limit", 50)))
        events = models.get_recent_events(limit=limit)
        return jsonify({"success": True, "events": events})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# BOOKS / CATALOG APIS
# ==========================================

@app.route("/api/books", methods=["GET"])
def api_get_books():
    """Catalog lookup with search, category and availability filters."""
    try:
        search = request.args.get("search", None)
        category = request.args.get("category", None)
        available_only = request.args.get("available_only", "false").lower() == "true"
        books = models.get_all_books(search=search, category=category, available_only=available_only)
        return jsonify({"success": True, "books": books})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/books/<int:book_id>", methods=["GET"])
def api_get_book(book_id):
    """Retrieve single book."""
    try:
        book = models.get_book_by_id(book_id)
        if not book:
            return jsonify({"success": False, "error": "Book not found"}), 404
        return jsonify({"success": True, "book": book})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/books", methods=["POST"])
def api_add_book():
    """Add a new title."""
    try:
        data = request.get_json() or {}
        required = ["isbn", "title", "author", "category", "publication_year", "shelf_location"]
        for field in required:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Field '{field}' is required"}), 400

        book_id = models.add_book(
            isbn=data["isbn"],
            title=data["title"],
            author=data["author"],
            category=data["category"],
            publication_year=int(data["publication_year"]),
            shelf_location=data["shelf_location"],
            total_copies=int(data.get("total_copies", 1)),
            price=float(data.get("price", 19.99)),
            popularity_score=int(data.get("popularity_score", 50))
        )
        return jsonify({"success": True, "book_id": book_id, "message": "Book added successfully!"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/books/<int:book_id>", methods=["PUT"])
def api_update_book(book_id):
    """Update title details."""
    try:
        data = request.get_json() or {}
        models.update_book(book_id, data)
        return jsonify({"success": True, "message": "Book updated successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/books/<int:book_id>", methods=["DELETE"])
def api_delete_book(book_id):
    """Delete title if no active loans."""
    try:
        models.delete_book(book_id)
        return jsonify({"success": True, "message": "Book deleted successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/categories", methods=["GET"])
def api_categories():
    """Distinct book categories."""
    try:
        categories = models.get_categories()
        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# PATRONS APIS
# ==========================================

@app.route("/api/patrons", methods=["GET"])
def api_get_patrons():
    """List patrons with filtering."""
    try:
        search = request.args.get("search", None)
        patron_type = request.args.get("patron_type", None)
        status = request.args.get("status", None)
        patrons = models.get_all_patrons(search=search, patron_type=patron_type, status=status)
        return jsonify({"success": True, "patrons": patrons})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/patrons/<int:patron_id>", methods=["GET"])
def api_get_patron(patron_id):
    """Get single patron and their active loans."""
    try:
        patron = models.get_patron_by_id(patron_id)
        if not patron:
            return jsonify({"success": False, "error": "Patron not found"}), 404
        loans = models.get_loans(patron_id=patron_id)
        return jsonify({"success": True, "patron": patron, "loans": loans})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/patrons", methods=["POST"])
def api_add_patron():
    """Register patron."""
    try:
        data = request.get_json() or {}
        required = ["card_number", "name", "email"]
        for field in required:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Field '{field}' is required"}), 400

        patron_id = models.add_patron(
            card_number=data["card_number"],
            name=data["name"],
            email=data["email"],
            patron_type=data.get("patron_type", "Student"),
            behavior_profile=data.get("behavior_profile", "Typical"),
            borrow_limit=data.get("borrow_limit")
        )
        return jsonify({"success": True, "patron_id": patron_id, "message": "Patron registered successfully!"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/patrons/<int:patron_id>", methods=["PUT"])
def api_update_patron(patron_id):
    """Update patron."""
    try:
        data = request.get_json() or {}
        models.update_patron(patron_id, data)
        return jsonify({"success": True, "message": "Patron updated successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/patrons/<int:patron_id>", methods=["DELETE"])
def api_delete_patron(patron_id):
    """Delete patron."""
    try:
        models.delete_patron(patron_id)
        return jsonify({"success": True, "message": "Patron deleted successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ==========================================
# CIRCULATION (LOANS & RETURNS) APIS
# ==========================================

@app.route("/api/loans", methods=["GET"])
def api_get_loans():
    """Retrieve loan records."""
    try:
        status = request.args.get("status", None)
        patron_id = request.args.get("patron_id", None)
        book_id = request.args.get("book_id", None)
        loans = models.get_loans(status_filter=status, patron_id=patron_id, book_id=book_id)
        return jsonify({"success": True, "loans": loans})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/loans/issue", methods=["POST"])
def api_issue_loan():
    """Check out a book."""
    try:
        data = request.get_json() or {}
        book_id = data.get("book_id")
        patron_id = data.get("patron_id")
        if not book_id or not patron_id:
            return jsonify({"success": False, "error": "Both book_id and patron_id are required"}), 400

        result = models.issue_book(book_id=int(book_id), patron_id=int(patron_id))
        return jsonify({"success": True, "result": result, "message": f"Successfully issued to {result['patron_name']}! Due: {result['due_date']}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/loans/return", methods=["POST"])
def api_return_loan():
    """Check in a book."""
    try:
        data = request.get_json() or {}
        loan_id = data.get("loan_id")
        if not loan_id:
            return jsonify({"success": False, "error": "loan_id is required"}), 400

        result = models.return_book(loan_id=int(loan_id))
        msg = f"Returned '{result['book_title']}'."
        if result["fine_accrued"] > 0:
            msg += f" Late by {result['days_overdue']} days (Fine: ${result['fine_accrued']:.2f})."
        if result["hold_notification"]:
            msg += f" [{result['hold_notification']}]"

        return jsonify({"success": True, "result": result, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/loans/renew", methods=["POST"])
def api_renew_loan():
    """Renew an active loan."""
    try:
        data = request.get_json() or {}
        loan_id = data.get("loan_id")
        if not loan_id:
            return jsonify({"success": False, "error": "loan_id is required"}), 400

        result = models.renew_loan(loan_id=int(loan_id))
        return jsonify({"success": True, "result": result, "message": f"Loan renewed! New due date: {result['new_due_date']}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ==========================================
# RESERVATIONS / HOLDS APIS
# ==========================================

@app.route("/api/reservations", methods=["GET"])
def api_get_reservations():
    """List holds."""
    try:
        status = request.args.get("status", None)
        reservations = models.get_reservations(status_filter=status)
        return jsonify({"success": True, "reservations": reservations})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reservations", methods=["POST"])
def api_place_reservation():
    """Place hold."""
    try:
        data = request.get_json() or {}
        book_id = data.get("book_id")
        patron_id = data.get("patron_id")
        if not book_id or not patron_id:
            return jsonify({"success": False, "error": "Both book_id and patron_id are required"}), 400

        result = models.place_reservation(int(book_id), int(patron_id))
        return jsonify({"success": True, "result": result, "message": f"Hold placed successfully (Status: {result['status']})"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reservations/<int:res_id>/cancel", methods=["POST"])
def api_cancel_reservation(res_id):
    """Cancel hold."""
    try:
        models.cancel_reservation(res_id)
        return jsonify({"success": True, "message": "Reservation cancelled successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ==========================================
# FINES & PAYMENTS APIS
# ==========================================

@app.route("/api/fines", methods=["GET"])
def api_get_fines():
    """List fine payments history."""
    try:
        patron_id = request.args.get("patron_id", None)
        payments = models.get_fine_payments(patron_id=patron_id)
        return jsonify({"success": True, "payments": payments})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/fines/pay", methods=["POST"])
def api_pay_fine():
    """Record payment of patron fine balance."""
    try:
        data = request.get_json() or {}
        patron_id = data.get("patron_id")
        amount = data.get("amount")
        method = data.get("payment_method", "Cash")
        loan_id = data.get("loan_id", None)

        if not patron_id or amount is None:
            return jsonify({"success": False, "error": "patron_id and amount are required"}), 400

        result = models.record_fine_payment(int(patron_id), float(amount), payment_method=method, loan_id=loan_id)
        return jsonify({
            "success": True,
            "result": result,
            "message": f"Payment of ${result['amount_paid']:.2f} recorded. Remaining balance: ${result['remaining_balance']:.2f}."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ==========================================
# CSV EXPORT REPORTS
# ==========================================

@app.route("/export/csv/<report_type>")
def export_csv(report_type):
    """Generate and download live CSV reports."""
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "books":
        writer.writerow(["ID", "ISBN", "Title", "Author", "Category", "Year", "Shelf", "Total Copies", "Available Copies", "Price", "Popularity Score"])
        books = models.get_all_books()
        for b in books:
            writer.writerow([b["id"], b["isbn"], b["title"], b["author"], b["category"], b["publication_year"], b["shelf_location"], b["total_copies"], b["available_copies"], f"${b['price']:.2f}", b["popularity_score"]])
        filename = f"library_books_{datetime.now().strftime('%Y%m%d')}.csv"

    elif report_type == "patrons":
        writer.writerow(["ID", "Card Number", "Name", "Email", "Type", "Status", "Borrow Limit", "Fine Balance", "Persona"])
        patrons = models.get_all_patrons()
        for p in patrons:
            writer.writerow([p["id"], p["card_number"], p["name"], p["email"], p["patron_type"], p["status"], p["borrow_limit"], f"${p['balance_fines']:.2f}", p["behavior_profile"]])
        filename = f"library_patrons_{datetime.now().strftime('%Y%m%d')}.csv"

    elif report_type == "overdue":
        writer.writerow(["Loan ID", "Book Title", "ISBN", "Patron Name", "Card Number", "Loan Date", "Due Date", "Days Overdue", "Fine Accrued ($)"])
        loans = models.get_loans(status_filter="Overdue")
        config = get_system_config()
        cur_dt = datetime.strptime(config.get("current_sim_date", "2026-10-01"), "%Y-%m-%d")
        for l in loans:
            due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d")
            days_late = max(0, (cur_dt - due_dt).days)
            writer.writerow([l["id"], l["book_title"], l["isbn"], l["patron_name"], l["card_number"], l["loan_date"], l["due_date"], days_late, f"${l['fine_accrued']:.2f}"])
        filename = f"overdue_report_{datetime.now().strftime('%Y%m%d')}.csv"

    else:
        return "Unknown report type", 400

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  ATHENAEUM LIBRARY MANAGEMENT & SIMULATION PLATFORM")
    print("  Server launching at http://127.0.0.1:5000")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
