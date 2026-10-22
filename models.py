"""
models.py - Business Logic and Data Access Layer for Library Management System.
Contains comprehensive CRUD, circulation management, fine calculation, and analytics queries.
"""

from datetime import datetime, timedelta
import json
from database import get_db_connection, get_system_config, update_system_config

# ==========================================
# BOOKS SERVICE
# ==========================================

def get_all_books(search=None, category=None, available_only=False):
    """Retrieve books with optional filtering by title/author/ISBN, category, or stock availability."""
    query = """
        SELECT b.*, 
               (b.total_copies - b.available_copies) AS borrowed_copies,
               (SELECT COUNT(*) FROM reservations r WHERE r.book_id = b.id AND r.status = 'Pending') AS pending_holds
        FROM books b
        WHERE 1=1
    """
    params = []

    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    if category and category != "All":
        query += " AND b.category = ?"
        params.append(category)

    if available_only:
        query += " AND b.available_copies > 0"

    query += " ORDER BY b.title ASC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_book_by_id(book_id):
    """Fetch single book by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.*, 
                   (b.total_copies - b.available_copies) AS borrowed_copies,
                   (SELECT COUNT(*) FROM reservations r WHERE r.book_id = b.id AND r.status = 'Pending') AS pending_holds
            FROM books b 
            WHERE b.id = ?
        """, (book_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_book(isbn, title, author, category, publication_year, shelf_location, total_copies=1, price=19.99, popularity_score=50):
    """Add a new book to the catalog."""
    total_copies = int(total_copies)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO books (isbn, title, author, category, publication_year, shelf_location, total_copies, available_copies, price, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (isbn.strip(), title.strip(), author.strip(), category.strip(), int(publication_year), shelf_location.strip(), total_copies, total_copies, float(price), int(popularity_score)))
        book_id = cursor.lastrowid
        return book_id

def update_book(book_id, data):
    """Update book information, ensuring available copies stay consistent."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT total_copies, available_copies FROM books WHERE id = ?", (book_id,))
        current = cursor.fetchone()
        if not current:
            raise ValueError(f"Book #{book_id} not found.")

        current_total = current["total_copies"]
        current_avail = current["available_copies"]
        new_total = int(data.get("total_copies", current_total))

        # Adjust available copies based on change in total copies
        delta_copies = new_total - current_total
        new_avail = max(0, current_avail + delta_copies)

        cursor.execute("""
            UPDATE books 
            SET title = ?, author = ?, category = ?, publication_year = ?, 
                shelf_location = ?, total_copies = ?, available_copies = ?, 
                price = ?, popularity_score = ?
            WHERE id = ?
        """, (
            data.get("title").strip(),
            data.get("author").strip(),
            data.get("category").strip(),
            int(data.get("publication_year")),
            data.get("shelf_location").strip(),
            new_total,
            new_avail,
            float(data.get("price", 19.99)),
            int(data.get("popularity_score", 50)),
            book_id
        ))
        return True

def delete_book(book_id):
    """Deletes a book if it has no active loans."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as active_cnt FROM loans WHERE book_id = ? AND status IN ('Active', 'Overdue')", (book_id,))
        row = cursor.fetchone()
        if row["active_cnt"] > 0:
            raise ValueError("Cannot delete book while copies are actively checked out.")
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        return True

def get_categories():
    """Return distinct categories present in catalog."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM books ORDER BY category")
        return [row["category"] for row in cursor.fetchall()]

# ==========================================
# PATRONS SERVICE
# ==========================================

def get_all_patrons(search=None, patron_type=None, status=None):
    """List patrons with filtering and active borrow counts."""
    query = """
        SELECT p.*,
               (SELECT COUNT(*) FROM loans l WHERE l.patron_id = p.id AND l.status IN ('Active', 'Overdue')) AS active_loans_count
        FROM patrons p
        WHERE 1=1
    """
    params = []

    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (p.name LIKE ? OR p.email LIKE ? OR p.card_number LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    if patron_type and patron_type != "All":
        query += " AND p.patron_type = ?"
        params.append(patron_type)

    if status and status != "All":
        query += " AND p.status = ?"
        params.append(status)

    query += " ORDER BY p.name ASC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_patron_by_id(patron_id):
    """Fetch single patron details with loan counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM loans l WHERE l.patron_id = p.id AND l.status IN ('Active', 'Overdue')) AS active_loans_count
            FROM patrons p
            WHERE p.id = ?
        """, (patron_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_patron(card_number, name, email, patron_type="Student", behavior_profile="Typical", borrow_limit=None):
    """Register a new patron."""
    if not borrow_limit:
        borrow_limit = 7 if patron_type == "Faculty" else (2 if patron_type == "Community" else 3)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patrons (card_number, name, email, patron_type, borrow_limit, status, balance_fines, behavior_profile)
            VALUES (?, ?, ?, ?, ?, 'Active', 0.0, ?)
        """, (card_number.strip().upper(), name.strip(), email.strip().lower(), patron_type, int(borrow_limit), behavior_profile))
        return cursor.lastrowid

def update_patron(patron_id, data):
    """Update patron information."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE patrons
            SET name = ?, email = ?, patron_type = ?, borrow_limit = ?, status = ?, behavior_profile = ?
            WHERE id = ?
        """, (
            data.get("name").strip(),
            data.get("email").strip().lower(),
            data.get("patron_type"),
            int(data.get("borrow_limit", 3)),
            data.get("status", "Active"),
            data.get("behavior_profile", "Typical"),
            patron_id
        ))
        return True

def delete_patron(patron_id):
    """Delete patron if no active loans or pending fines exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as active_cnt FROM loans WHERE patron_id = ? AND status IN ('Active', 'Overdue')", (patron_id,))
        if cursor.fetchone()["active_cnt"] > 0:
            raise ValueError("Cannot delete patron with active loans.")

        cursor.execute("SELECT balance_fines FROM patrons WHERE id = ?", (patron_id,))
        patron = cursor.fetchone()
        if patron and patron["balance_fines"] > 0:
            raise ValueError(f"Cannot delete patron with outstanding unpaid fine balance of ${patron['balance_fines']:.2f}.")

        cursor.execute("DELETE FROM patrons WHERE id = ?", (patron_id,))
        return True

# ==========================================
# CIRCULATION & LOANS SERVICE
# ==========================================

def calculate_due_date(loan_date_str, patron_type):
    """Compute due date based on patron classification."""
    config = get_system_config()
    days_key = f"loan_duration_{patron_type.lower()}"
    days = int(config.get(days_key, 14))
    
    loan_dt = datetime.strptime(loan_date_str, "%Y-%m-%d")
    due_dt = loan_dt + timedelta(days=days)
    return due_dt.strftime("%Y-%m-%d")

def issue_book(book_id, patron_id, loan_date=None):
    """
    Issues a book to a patron with validation:
    - Availability check
    - Patron active check & limit check
    - Fine threshold check ($10 limit for new loans)
    """
    config = get_system_config()
    current_date = loan_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check patron
        cursor.execute("SELECT * FROM patrons WHERE id = ?", (patron_id,))
        patron = cursor.fetchone()
        if not patron:
            raise ValueError(f"Patron ID #{patron_id} not found.")
        if patron["status"] != "Active":
            raise ValueError(f"Patron '{patron['name']}' account is {patron['status']}. Checkout denied.")
        if patron["balance_fines"] >= 10.0:
            raise ValueError(f"Patron has excessive unpaid fines (${patron['balance_fines']:.2f}). Must settle fines before borrowing.")

        cursor.execute("SELECT COUNT(*) AS current_loans FROM loans WHERE patron_id = ? AND status IN ('Active', 'Overdue')", (patron_id,))
        if cursor.fetchone()["current_loans"] >= patron["borrow_limit"]:
            raise ValueError(f"Patron reached maximum checkout quota ({patron['borrow_limit']} books).")

        # Check book
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        book = cursor.fetchone()
        if not book:
            raise ValueError(f"Book ID #{book_id} not found.")
        if book["available_copies"] <= 0:
            raise ValueError(f"'{book['title']}' has no available copies in stock. Please place a reservation instead.")

        # Calculate due date
        due_date = calculate_due_date(current_date, patron["patron_type"])

        # Insert loan
        cursor.execute("""
            INSERT INTO loans (book_id, patron_id, loan_date, due_date, status, fine_accrued, fine_paid)
            VALUES (?, ?, ?, ?, 'Active', 0.0, 0.0)
        """, (book_id, patron_id, current_date, due_date))
        loan_id = cursor.lastrowid

        # Decrement available copies
        cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))

        # Check if patron had a pending reservation for this book; mark it fulfilled
        cursor.execute("""
            UPDATE reservations
            SET status = 'Fulfilled'
            WHERE book_id = ? AND patron_id = ? AND status IN ('Pending', 'Ready')
        """, (book_id, patron_id))

        # Log simulation event
        log_event(
            sim_date=current_date,
            event_type="BORROW",
            actor_name=patron["name"],
            summary=f"Borrowed '{book['title']}'",
            details=f"Loan #{loan_id} created. Due date: {due_date}.",
            cursor=cursor
        )

        return {"loan_id": loan_id, "due_date": due_date, "book_title": book["title"], "patron_name": patron["name"]}

def return_book(loan_id, return_date=None):
    """
    Returns a book:
    - Calculates overdue fine if returned past due date
    - Increments book available_copies
    - Updates patron fine balance if fine incurred
    - Checks reservation queue to notify/hold for next patron
    """
    config = get_system_config()
    current_date = return_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))
    fine_rate = float(config.get("fine_rate_per_day", 0.50))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT l.*, b.title AS book_title, b.id AS book_id, p.name AS patron_name, p.id AS patron_id
            FROM loans l
            JOIN books b ON l.book_id = b.id
            JOIN patrons p ON l.patron_id = p.id
            WHERE l.id = ?
        """, (loan_id,))
        loan = cursor.fetchone()

        if not loan:
            raise ValueError(f"Loan #{loan_id} not found.")
        if loan["status"] == "Returned":
            raise ValueError("This loan has already been marked as returned.")

        due_dt = datetime.strptime(loan["due_date"], "%Y-%m-%d")
        return_dt = datetime.strptime(current_date, "%Y-%m-%d")

        days_overdue = max(0, (return_dt - due_dt).days)
        fine = round(days_overdue * fine_rate, 2)

        # Update loan record
        cursor.execute("""
            UPDATE loans
            SET return_date = ?, status = 'Returned', fine_accrued = ?
            WHERE id = ?
        """, (current_date, fine, loan_id))

        # Restock available copies
        cursor.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (loan["book_id"],))

        # Update patron fine balance if overdue
        if fine > 0:
            cursor.execute("UPDATE patrons SET balance_fines = balance_fines + ? WHERE id = ?", (fine, loan["patron_id"]))

        # Check for pending holds/reservations
        cursor.execute("""
            SELECT r.*, p.name as hold_patron_name 
            FROM reservations r
            JOIN patrons p ON r.patron_id = p.id
            WHERE r.book_id = ? AND r.status = 'Pending'
            ORDER BY r.reservation_date ASC, r.id ASC
            LIMIT 1
        """, (loan["book_id"],))
        next_hold = cursor.fetchone()

        hold_notification = None
        if next_hold:
            cursor.execute("UPDATE reservations SET status = 'Ready', notified_date = ? WHERE id = ?", (current_date, next_hold["id"]))
            hold_notification = f"Hold #{next_hold['id']} for {next_hold['hold_patron_name']} marked READY for pickup!"
            log_event(
                sim_date=current_date,
                event_type="HOLD_READY",
                actor_name=next_hold["hold_patron_name"],
                summary=f"Reserved copy of '{loan['book_title']}' is ready for pickup",
                details=f"Reserved since {next_hold['reservation_date']}.",
                cursor=cursor
            )

        log_event(
            sim_date=current_date,
            event_type="RETURN",
            actor_name=loan["patron_name"],
            summary=f"Returned '{loan['book_title']}'" + (f" ({days_overdue} days late, fine: ${fine:.2f})" if fine > 0 else " on time!"),
            details=f"Loan #{loan_id}. Returned on {current_date}.",
            cursor=cursor
        )

        return {
            "loan_id": loan_id,
            "book_title": loan["book_title"],
            "patron_name": loan["patron_name"],
            "return_date": current_date,
            "days_overdue": days_overdue,
            "fine_accrued": fine,
            "hold_notification": hold_notification
        }

def renew_loan(loan_id, current_date=None, extension_days=14):
    """Renews loan if no hold exists on the book."""
    config = get_system_config()
    current_date = current_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.*, b.title AS book_title, p.name AS patron_name
            FROM loans l
            JOIN books b ON l.book_id = b.id
            JOIN patrons p ON l.patron_id = p.id
            WHERE l.id = ?
        """, (loan_id,))
        loan = cursor.fetchone()

        if not loan:
            raise ValueError(f"Loan #{loan_id} not found.")
        if loan["status"] == "Returned":
            raise ValueError("Cannot renew a returned loan.")

        # Check if reservations exist for this book
        cursor.execute("SELECT COUNT(*) AS hold_cnt FROM reservations WHERE book_id = ? AND status = 'Pending'", (loan["book_id"],))
        if cursor.fetchone()["hold_cnt"] > 0:
            raise ValueError(f"Renewal denied: another patron has placed a hold on '{loan['book_title']}'.")

        # Calculate new due date
        cur_due = datetime.strptime(loan["due_date"], "%Y-%m-%d")
        new_due = (cur_due + timedelta(days=extension_days)).strftime("%Y-%m-%d")

        cursor.execute("UPDATE loans SET due_date = ?, status = 'Active' WHERE id = ?", (new_due, loan_id))

        log_event(
            sim_date=current_date,
            event_type="RENEWAL",
            actor_name=loan["patron_name"],
            summary=f"Renewed '{loan['book_title']}' until {new_due}",
            details=f"Loan #{loan_id} extended by {extension_days} days.",
            cursor=cursor
        )

        return {"loan_id": loan_id, "new_due_date": new_due}

def get_loans(status_filter=None, patron_id=None, book_id=None):
    """Fetch loans with rich relational details."""
    query = """
        SELECT l.*,
               b.title AS book_title, b.author AS book_author, b.isbn,
               p.name AS patron_name, p.card_number, p.patron_type
        FROM loans l
        JOIN books b ON l.book_id = b.id
        JOIN patrons p ON l.patron_id = p.id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != "All":
        query += " AND l.status = ?"
        params.append(status_filter)

    if patron_id:
        query += " AND l.patron_id = ?"
        params.append(patron_id)

    if book_id:
        query += " AND l.book_id = ?"
        params.append(book_id)

    query += " ORDER BY l.id DESC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# ==========================================
# RESERVATIONS & HOLDS SERVICE
# ==========================================

def place_reservation(book_id, patron_id, current_date=None):
    """Place a hold on a book."""
    config = get_system_config()
    current_date = current_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT name, status FROM patrons WHERE id = ?", (patron_id,))
        patron = cursor.fetchone()
        if not patron or patron["status"] != "Active":
            raise ValueError("Active patron required to place hold.")

        cursor.execute("SELECT title, available_copies FROM books WHERE id = ?", (book_id,))
        book = cursor.fetchone()
        if not book:
            raise ValueError("Book not found.")

        # Check existing hold
        cursor.execute("SELECT id FROM reservations WHERE book_id = ? AND patron_id = ? AND status IN ('Pending', 'Ready')", (book_id, patron_id))
        if cursor.fetchone():
            raise ValueError("Patron already has an active reservation for this book.")

        initial_status = "Ready" if book["available_copies"] > 0 else "Pending"
        cursor.execute("""
            INSERT INTO reservations (book_id, patron_id, reservation_date, status)
            VALUES (?, ?, ?, ?)
        """, (book_id, patron_id, current_date, initial_status))
        res_id = cursor.lastrowid

        log_event(
            sim_date=current_date,
            event_type="HOLD_PLACED",
            actor_name=patron["name"],
            summary=f"Placed hold on '{book['title']}' (Status: {initial_status})",
            details=f"Reservation #{res_id} registered.",
            cursor=cursor
        )

        return {"reservation_id": res_id, "status": initial_status}

def cancel_reservation(reservation_id, current_date=None):
    """Cancel a hold."""
    config = get_system_config()
    current_date = current_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, b.title as book_title, p.name as patron_name
            FROM reservations r
            JOIN books b ON r.book_id = b.id
            JOIN patrons p ON r.patron_id = p.id
            WHERE r.id = ?
        """, (reservation_id,))
        res = cursor.fetchone()
        if not res:
            raise ValueError("Reservation not found.")

        cursor.execute("UPDATE reservations SET status = 'Cancelled' WHERE id = ?", (reservation_id,))

        log_event(
            sim_date=current_date,
            event_type="HOLD_CANCELLED",
            actor_name=res["patron_name"],
            summary=f"Cancelled hold on '{res['book_title']}'",
            details=f"Reservation #{reservation_id} cancelled.",
            cursor=cursor
        )
        return True

def get_reservations(status_filter=None):
    """Fetch reservations with relations."""
    query = """
        SELECT r.*,
               b.title AS book_title, b.author AS book_author, b.available_copies,
               p.name AS patron_name, p.card_number
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        JOIN patrons p ON r.patron_id = p.id
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter != "All":
        query += " AND r.status = ?"
        params.append(status_filter)

    query += " ORDER BY r.reservation_date DESC, r.id DESC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# ==========================================
# FINES & PAYMENTS
# ==========================================

def record_fine_payment(patron_id, amount, payment_date=None, payment_method="Cash", loan_id=None):
    """Records payment for fines, reducing the patron's balance."""
    config = get_system_config()
    current_date = payment_date or config.get("current_sim_date", datetime.today().strftime("%Y-%m-%d"))
    amount = float(amount)

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, balance_fines FROM patrons WHERE id = ?", (patron_id,))
        patron = cursor.fetchone()
        if not patron:
            raise ValueError(f"Patron #{patron_id} not found.")

        # Cap payment to actual balance
        effective_payment = min(amount, patron["balance_fines"])
        new_balance = max(0.0, round(patron["balance_fines"] - effective_payment, 2))

        cursor.execute("UPDATE patrons SET balance_fines = ? WHERE id = ?", (new_balance, patron_id))

        cursor.execute("""
            INSERT INTO fine_payments (patron_id, loan_id, amount, payment_date, payment_method)
            VALUES (?, ?, ?, ?, ?)
        """, (patron_id, loan_id, effective_payment, current_date, payment_method))
        payment_id = cursor.lastrowid

        if loan_id:
            cursor.execute("UPDATE loans SET fine_paid = fine_paid + ? WHERE id = ?", (effective_payment, loan_id))

        log_event(
            sim_date=current_date,
            event_type="FINE_PAID",
            actor_name=patron["name"],
            summary=f"Paid fine of ${effective_payment:.2f} via {payment_method}",
            details=f"Payment #{payment_id}. Remaining patron balance: ${new_balance:.2f}.",
            cursor=cursor
        )

        return {"payment_id": payment_id, "amount_paid": effective_payment, "remaining_balance": new_balance}

def get_fine_payments(patron_id=None):
    """Retrieve fine payments list."""
    query = """
        SELECT fp.*, p.name AS patron_name, p.card_number
        FROM fine_payments fp
        JOIN patrons p ON fp.patron_id = p.id
        WHERE 1=1
    """
    params = []
    if patron_id:
        query += " AND fp.patron_id = ?"
        params.append(patron_id)
    query += " ORDER BY fp.payment_date DESC, fp.id DESC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# ==========================================
# SIMULATION EVENTS & AUDIT LOG
# ==========================================

def log_event(sim_date, event_type, actor_name, summary, details="", cursor=None):
    """Inserts a simulation event record."""
    if cursor is not None:
        cursor.execute("""
            INSERT INTO simulation_events (sim_date, event_type, actor_name, summary, details)
            VALUES (?, ?, ?, ?, ?)
        """, (sim_date, event_type, actor_name, summary, details))
        return cursor.lastrowid

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO simulation_events (sim_date, event_type, actor_name, summary, details)
            VALUES (?, ?, ?, ?, ?)
        """, (sim_date, event_type, actor_name, summary, details))
        return c.lastrowid

def get_recent_events(limit=50):
    """Get most recent events for live ticker or feed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM simulation_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

# ==========================================
# ANALYTICS & DASHBOARD METRICS
# ==========================================

def get_dashboard_stats():
    """Calculates real-time KPIs for the dashboard."""
    config = get_system_config()
    current_sim_date = config.get("current_sim_date", "2026-10-01")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS total_books, SUM(total_copies) AS total_copies, SUM(available_copies) AS available_copies FROM books")
        books_stats = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS total_patrons FROM patrons")
        patrons_stats = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS active_loans FROM loans WHERE status IN ('Active', 'Overdue')")
        active_loans = cursor.fetchone()["active_loans"]

        cursor.execute("SELECT COUNT(*) AS overdue_loans FROM loans WHERE status = 'Overdue'")
        overdue_loans = cursor.fetchone()["overdue_loans"]

        cursor.execute("SELECT SUM(balance_fines) AS outstanding_fines FROM patrons")
        outstanding_row = cursor.fetchone()
        outstanding_fines = outstanding_row["outstanding_fines"] if outstanding_row["outstanding_fines"] else 0.0

        cursor.execute("SELECT SUM(amount) AS collected_fines FROM fine_payments")
        collected_row = cursor.fetchone()
        collected_fines = collected_row["collected_fines"] if collected_row["collected_fines"] else 0.0

        cursor.execute("SELECT COUNT(*) AS pending_holds FROM reservations WHERE status IN ('Pending', 'Ready')")
        pending_holds = cursor.fetchone()["pending_holds"]

        return {
            "current_sim_date": current_sim_date,
            "total_titles": books_stats["total_books"] or 0,
            "total_copies": books_stats["total_copies"] or 0,
            "available_copies": books_stats["available_copies"] or 0,
            "total_patrons": patrons_stats["total_patrons"] or 0,
            "active_loans": active_loans,
            "overdue_loans": overdue_loans,
            "outstanding_fines": round(outstanding_fines, 2),
            "collected_fines": round(collected_fines, 2),
            "pending_holds": pending_holds,
            "library_name": config.get("library_name", "Athenaeum Central Simulation Library")
        }

def get_chart_analytics():
    """Generates data for Chart.js interactive visualizations."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Loans by Category
        cursor.execute("""
            SELECT b.category, COUNT(l.id) AS count
            FROM books b
            LEFT JOIN loans l ON b.id = l.book_id
            GROUP BY b.category
            ORDER BY count DESC
        """)
        genre_distribution = [dict(row) for row in cursor.fetchall()]

        # 2. Top 5 Most Borrowed Books
        cursor.execute("""
            SELECT b.title, b.author, COUNT(l.id) as borrow_count
            FROM books b
            JOIN loans l ON b.id = l.book_id
            GROUP BY b.id
            ORDER BY borrow_count DESC
            LIMIT 5
        """)
        top_books = [dict(row) for row in cursor.fetchall()]

        # 3. Patron Personas distribution
        cursor.execute("""
            SELECT behavior_profile, COUNT(*) as count
            FROM patrons
            GROUP BY behavior_profile
        """)
        patron_personas = [dict(row) for row in cursor.fetchall()]

        # 4. Recent Daily Activity Trend (Borrows vs Returns by date)
        cursor.execute("""
            SELECT sim_date,
                   SUM(CASE WHEN event_type = 'BORROW' THEN 1 ELSE 0 END) AS borrows,
                   SUM(CASE WHEN event_type = 'RETURN' THEN 1 ELSE 0 END) AS returns,
                   SUM(CASE WHEN event_type = 'FINE_PAID' THEN 1 ELSE 0 END) AS payments
            FROM simulation_events
            GROUP BY sim_date
            ORDER BY sim_date DESC
            LIMIT 14
        """)
        activity_trend = [dict(row) for row in cursor.fetchall()]
        activity_trend.reverse()

        return {
            "genre_distribution": genre_distribution,
            "top_books": top_books,
            "patron_personas": patron_personas,
            "activity_trend": activity_trend
        }
