"""
simulator.py - Dynamic Simulation Engine for Athenaeum Library Management System.
Simulates patron behavior, automated returns, fine accruals, holds queue processing,
and daily library operational cycles.
"""

from datetime import datetime, timedelta
import random
from database import get_db_connection, get_system_config, update_system_config
from models import (
    issue_book, return_book, record_fine_payment, place_reservation,
    log_event, get_all_books, get_all_patrons, get_loans
)

class LibrarySimulator:
    """Core simulation engine driving autonomous patron and library mechanics."""

    def __init__(self):
        pass

    @property
    def current_date_str(self):
        config = get_system_config()
        return config.get("current_sim_date", "2026-10-01")

    def advance_time(self, days=1):
        """
        Advances the simulation clock by the specified number of days,
        processing daily lifecycle events for each step.
        """
        days = max(1, int(days))
        summary_results = {
            "days_advanced": days,
            "start_date": self.current_date_str,
            "end_date": None,
            "events_logged": 0,
            "returns_processed": 0,
            "borrows_processed": 0,
            "fines_paid_count": 0,
            "fines_accrued_total": 0.0,
            "holds_fulfilled": 0
        }

        current_dt = datetime.strptime(self.current_date_str, "%Y-%m-%d")

        for _ in range(days):
            current_dt += timedelta(days=1)
            date_str = current_dt.strftime("%Y-%m-%d")
            update_system_config("current_sim_date", date_str)

            # Daily simulation tick
            day_stats = self._simulate_day(date_str)

            summary_results["events_logged"] += day_stats["events"]
            summary_results["returns_processed"] += day_stats["returns"]
            summary_results["borrows_processed"] += day_stats["borrows"]
            summary_results["fines_paid_count"] += day_stats["payments"]
            summary_results["fines_accrued_total"] += day_stats["fines_accrued"]

        summary_results["end_date"] = current_dt.strftime("%Y-%m-%d")
        return summary_results

    def _simulate_day(self, date_str):
        """Executes all operations for one single simulated day."""
        stats = {
            "events": 0,
            "returns": 0,
            "borrows": 0,
            "payments": 0,
            "fines_accrued": 0.0
        }

        # 1. Check for overdue transitions and fine accumulation
        fines_accrued = self._process_overdue_loans(date_str)
        stats["fines_accrued"] += fines_accrued

        # 2. Process hold expirations
        self._process_hold_expirations(date_str)

        # 3. Process automated patron returns based on personas
        returns_count = self._process_patron_returns(date_str)
        stats["returns"] += returns_count

        # 4. Process automated fine payments
        payments_count = self._process_patron_payments(date_str)
        stats["payments"] += payments_count

        # 5. Process automated borrows and new holds
        borrows_count = self._process_patron_borrows(date_str)
        stats["borrows"] += borrows_count

        # 6. Occasional Library acquisitions (every 14-20 days probability)
        self._process_occasional_restock(date_str)

        return stats

    def _process_overdue_loans(self, date_str):
        """Updates active loans that crossed due date to Overdue status."""
        config = get_system_config()
        fine_rate = float(config.get("fine_rate_per_day", 0.50))
        total_fines_today = 0.0

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Active loans that just became overdue today
            cursor.execute("""
                SELECT l.id, l.book_id, l.patron_id, l.due_date, b.title, p.name as patron_name
                FROM loans l
                JOIN books b ON l.book_id = b.id
                JOIN patrons p ON l.patron_id = p.id
                WHERE l.status = 'Active' AND l.due_date < ?
            """, (date_str,))
            newly_overdue = cursor.fetchall()

            for loan in newly_overdue:
                cursor.execute("""
                    UPDATE loans 
                    SET status = 'Overdue', fine_accrued = fine_accrued + ?
                    WHERE id = ?
                """, (fine_rate, loan["id"]))

                total_fines_today += fine_rate

                log_event(
                    sim_date=date_str,
                    event_type="OVERDUE_ALERT",
                    actor_name=loan["patron_name"],
                    summary=f"Loan for '{loan['title']}' is now OVERDUE!",
                    details=f"Due date was {loan['due_date']}. Daily fine rate: ${fine_rate:.2f}.",
                    cursor=cursor
                )

            # Ongoing overdue loans: accumulate fine
            cursor.execute("""
                SELECT l.id, l.patron_id
                FROM loans l
                WHERE l.status = 'Overdue' AND l.due_date < ?
            """, (date_str,))
            ongoing_overdue = cursor.fetchall()
            for loan in ongoing_overdue:
                # Add daily fine rate
                cursor.execute("UPDATE loans SET fine_accrued = fine_accrued + ? WHERE id = ?", (fine_rate, loan["id"]))
                total_fines_today += fine_rate

        return total_fines_today

    def _process_hold_expirations(self, date_str):
        """If a reserved copy was marked 'Ready' for more than 3 days and unclaimed, expire it."""
        current_dt = datetime.strptime(date_str, "%Y-%m-%d")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.book_id, r.patron_id, r.notified_date, b.title, p.name as patron_name
                FROM reservations r
                JOIN books b ON r.book_id = b.id
                JOIN patrons p ON r.patron_id = p.id
                WHERE r.status = 'Ready' AND r.notified_date IS NOT NULL
            """)
            ready_holds = cursor.fetchall()

            for hold in ready_holds:
                notified_dt = datetime.strptime(hold["notified_date"], "%Y-%m-%d")
                if (current_dt - notified_dt).days >= 3:
                    # Expire hold
                    cursor.execute("UPDATE reservations SET status = 'Expired' WHERE id = ?", (hold["id"],))

                    log_event(
                        sim_date=date_str,
                        event_type="HOLD_EXPIRED",
                        actor_name=hold["patron_name"],
                        summary=f"Hold on '{hold['title']}' expired (unclaimed for 3 days)",
                        details=f"Reservation #{hold['id']} expired on {date_str}.",
                        cursor=cursor
                    )

                    # Check if next patron in line
                    cursor.execute("""
                        SELECT r.id, p.name as next_patron_name
                        FROM reservations r
                        JOIN patrons p ON r.patron_id = p.id
                        WHERE r.book_id = ? AND r.status = 'Pending'
                        ORDER BY r.reservation_date ASC, r.id ASC
                        LIMIT 1
                    """, (hold["book_id"],))
                    next_in_queue = cursor.fetchone()
                    if next_in_queue:
                        cursor.execute("UPDATE reservations SET status = 'Ready', notified_date = ? WHERE id = ?", (date_str, next_in_queue["id"]))
                        log_event(
                            sim_date=date_str,
                            event_type="HOLD_READY",
                            actor_name=next_in_queue["next_patron_name"],
                            summary=f"Reserved copy of '{hold['title']}' allocated to next patron in queue",
                            details=f"Reservation #{next_in_queue['id']} now ready.",
                            cursor=cursor
                        )

    def _process_patron_returns(self, date_str):
        """Simulate patrons returning books according to persona and due date closeness."""
        returns_count = 0
        current_dt = datetime.strptime(date_str, "%Y-%m-%d")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.id, l.book_id, l.patron_id, l.loan_date, l.due_date, l.status,
                       p.behavior_profile, p.name as patron_name, b.title as book_title
                FROM loans l
                JOIN patrons p ON l.patron_id = p.id
                JOIN books b ON l.book_id = b.id
                WHERE l.status IN ('Active', 'Overdue')
            """)
            active_loans = cursor.fetchall()

        for loan in active_loans:
            due_dt = datetime.strptime(loan["due_date"], "%Y-%m-%d")
            loan_dt = datetime.strptime(loan["loan_date"], "%Y-%m-%d")
            total_duration = max(1, (due_dt - loan_dt).days)
            elapsed_days = (current_dt - loan_dt).days
            days_until_due = (due_dt - current_dt).days

            profile = loan["behavior_profile"]
            should_return = False

            if profile == "Meticulous":
                # Returns either early (halfway through) or on exact due date
                if days_until_due <= 0:
                    should_return = True
                elif elapsed_days >= (total_duration * 0.6) and random.random() < 0.25:
                    should_return = True

            elif profile == "Typical":
                # Returns right around due date, occasionally 1-2 days late
                if days_until_due < -2:
                    should_return = True
                elif days_until_due <= 0 and random.random() < 0.65:
                    should_return = True
                elif days_until_due == 1 and random.random() < 0.30:
                    should_return = True

            elif profile == "Procrastinator":
                # Often returns 3 to 7 days late
                if days_until_due < -7:
                    should_return = True
                elif days_until_due < -3 and random.random() < 0.40:
                    should_return = True
                elif days_until_due <= 0 and random.random() < 0.20:
                    should_return = True

            elif profile == "Forgetful":
                # Stays overdue until fine grows or random recall
                if days_until_due < -12:
                    should_return = True
                elif days_until_due < -5 and random.random() < 0.25:
                    should_return = True

            if should_return:
                try:
                    return_book(loan["id"], return_date=date_str)
                    returns_count += 1
                except Exception as e:
                    # Ignore if concurrent issue
                    pass

        return returns_count

    def _process_patron_payments(self, date_str):
        """Simulate patrons settling fines when they have an outstanding balance."""
        payments_count = 0

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, balance_fines, behavior_profile FROM patrons WHERE balance_fines > 0")
            patrons_with_fines = cursor.fetchall()

        for patron in patrons_with_fines:
            balance = patron["balance_fines"]
            profile = patron["behavior_profile"]

            # Probability of paying
            pay_chance = 0.50
            if balance >= 10.0:  # Urgent: blocked from borrowing
                pay_chance = 0.85
            elif profile == "Meticulous":
                pay_chance = 0.80
            elif profile == "Forgetful":
                pay_chance = 0.20

            if random.random() < pay_chance:
                # Decide payment amount (either full or partial)
                if random.random() < 0.70 or balance < 5.0:
                    amount = balance
                else:
                    amount = round(random.uniform(2.0, balance), 2)

                method = random.choice(["Cash", "Card", "Online"])
                try:
                    record_fine_payment(patron["id"], amount, payment_date=date_str, payment_method=method)
                    payments_count += 1
                except Exception:
                    pass

        return payments_count

    def _process_patron_borrows(self, date_str):
        """Simulate patrons browsing catalog and borrowing or reserving books."""
        borrows_count = 0

        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Select active patrons who have quota available and low fines
            cursor.execute("""
                SELECT p.id, p.name, p.patron_type, p.borrow_limit, p.balance_fines, p.behavior_profile,
                       (SELECT COUNT(*) FROM loans l WHERE l.patron_id = p.id AND l.status IN ('Active', 'Overdue')) as current_loans
                FROM patrons p
                WHERE p.status = 'Active' AND p.balance_fines < 10.0
            """)
            eligible_patrons = cursor.fetchall()

            # Select available books & total books
            cursor.execute("SELECT id, title, available_copies, popularity_score, category FROM books")
            all_books = cursor.fetchall()

        if not all_books or not eligible_patrons:
            return 0

        # Shuffle patrons
        shuffled_patrons = list(eligible_patrons)
        random.shuffle(shuffled_patrons)

        for patron in shuffled_patrons:
            if patron["current_loans"] >= patron["borrow_limit"]:
                continue

            # Check if patron visits today
            visit_chance = 0.30 if patron["patron_type"] == "Student" else (0.35 if patron["patron_type"] == "Faculty" else 0.20)
            if random.random() > visit_chance:
                continue

            # Pick a book weighted by popularity
            # 80% pick from top popular, 20% random discovery
            if random.random() < 0.80:
                weighted_pool = sorted(all_books, key=lambda b: b["popularity_score"] + random.randint(0, 30), reverse=True)
                chosen_book = weighted_pool[random.randint(0, min(6, len(weighted_pool) - 1))]
            else:
                chosen_book = random.choice(all_books)

            # Check if patron already has an active loan of this book
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM loans 
                    WHERE patron_id = ? AND book_id = ? AND status IN ('Active', 'Overdue')
                """, (patron["id"], chosen_book["id"]))
                already_has = cursor.fetchone()

            if already_has:
                continue

            # If book has available copies, borrow it!
            if chosen_book["available_copies"] > 0:
                try:
                    issue_book(chosen_book["id"], patron["id"], loan_date=date_str)
                    borrows_count += 1
                except Exception:
                    pass
            else:
                # Copies out of stock: place hold if interest is high
                if random.random() < 0.60:
                    try:
                        place_reservation(chosen_book["id"], patron["id"], current_date=date_str)
                    except Exception:
                        pass

        return borrows_count

    def _process_occasional_restock(self, date_str):
        """Simulates periodic library acquisition / restocking high demand titles."""
        if random.random() < 0.08:  # Approx once every 12-15 days
            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Find high demand books (many loans or reservations with low availability)
                cursor.execute("""
                    SELECT id, title, popularity_score, available_copies, total_copies
                    FROM books
                    WHERE available_copies <= 1
                    ORDER BY popularity_score DESC
                    LIMIT 1
                """)
                high_demand = cursor.fetchone()

                if high_demand:
                    extra_copies = random.randint(1, 3)
                    cursor.execute("""
                        UPDATE books
                        SET total_copies = total_copies + ?, available_copies = available_copies + ?
                        WHERE id = ?
                    """, (extra_copies, extra_copies, high_demand["id"]))

                    log_event(
                        sim_date=date_str,
                        event_type="RESTOCK",
                        actor_name="Library Procurement",
                        summary=f"Acquired {extra_copies} new copies of '{high_demand['title']}'",
                        details=f"Stock increased due to sustained high reader demand. Total copies now: {high_demand['total_copies'] + extra_copies}.",
                        cursor=cursor
                    )

# Singleton instance
simulator = LibrarySimulator()
