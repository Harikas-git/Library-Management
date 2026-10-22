"""
test_system.py - Comprehensive Unit & Integration Test Suite for Library System & Simulation Engine.
Verifies relational database operations, circulation business rules, fine calculations,
holds queue fulfillment, simulation ticks, and REST API endpoints.
"""

import unittest
import os
import json
from datetime import datetime, timedelta

from database import init_db, get_db_connection, get_system_config, update_system_config
import models
from simulator import simulator
from app import app

class TestLibrarySystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize clean test database with test data."""
        init_db(reset=True)

    def setUp(self):
        """Prepare fresh state for each test if necessary."""
        pass

    def test_01_book_crud_and_stock(self):
        """Test adding, fetching, and updating book records."""
        book_id = models.add_book(
            isbn="TEST-999-001",
            title="Automated Test-Driven Development",
            author="Kent Beck",
            category="Software Engineering",
            publication_year=2003,
            shelf_location="SE-T01",
            total_copies=3,
            price=29.99,
            popularity_score=80
        )
        self.assertIsNotNone(book_id)

        book = models.get_book_by_id(book_id)
        self.assertEqual(book["title"], "Automated Test-Driven Development")
        self.assertEqual(book["available_copies"], 3)
        self.assertEqual(book["total_copies"], 3)

        # Update book
        models.update_book(book_id, {
            "title": "Test-Driven Development by Example",
            "author": "Kent Beck",
            "category": "Software Engineering",
            "publication_year": 2003,
            "shelf_location": "SE-T02",
            "total_copies": 5,
            "price": 32.50,
            "popularity_score": 85
        })
        updated = models.get_book_by_id(book_id)
        self.assertEqual(updated["title"], "Test-Driven Development by Example")
        self.assertEqual(updated["total_copies"], 5)
        self.assertEqual(updated["available_copies"], 5)

    def test_02_patron_registration_and_limits(self):
        """Test patron creation and default borrow limits."""
        patron_id = models.add_patron(
            card_number="TEST-P100",
            name="Grace Hopper",
            email="hopper@navy.mil",
            patron_type="Faculty",
            behavior_profile="Meticulous"
        )
        self.assertIsNotNone(patron_id)

        patron = models.get_patron_by_id(patron_id)
        self.assertEqual(patron["name"], "Grace Hopper")
        self.assertEqual(patron["patron_type"], "Faculty")
        self.assertEqual(patron["borrow_limit"], 7)  # Faculty gets 7 by default
        self.assertEqual(patron["balance_fines"], 0.0)

    def test_03_issue_and_return_book(self):
        """Test borrowing decrements stock and returning restores stock."""
        # Setup book and patron
        b_id = models.add_book(
            isbn="TEST-CIRC-001",
            title="Refactoring",
            author="Martin Fowler",
            category="Software Engineering",
            publication_year=2018,
            shelf_location="SE-F01",
            total_copies=2
        )
        p_id = models.add_patron(
            card_number="TEST-P101",
            name="Linus Torvalds",
            email="linus@linuxfoundation.org",
            patron_type="Student",
            behavior_profile="Typical"
        )

        initial_book = models.get_book_by_id(b_id)
        self.assertEqual(initial_book["available_copies"], 2)

        # 1. Issue Book
        issue_res = models.issue_book(b_id, p_id, loan_date="2026-10-01")
        self.assertIn("loan_id", issue_res)
        self.assertEqual(issue_res["book_title"], "Refactoring")

        book_after_issue = models.get_book_by_id(b_id)
        self.assertEqual(book_after_issue["available_copies"], 1)

        # 2. Return Book (on time)
        return_res = models.return_book(issue_res["loan_id"], return_date="2026-10-10")
        self.assertEqual(return_res["days_overdue"], 0)
        self.assertEqual(return_res["fine_accrued"], 0.0)

        book_after_return = models.get_book_by_id(b_id)
        self.assertEqual(book_after_return["available_copies"], 2)

    def test_04_overdue_and_fine_calculation(self):
        """Test overdue returns accurately calculate fines and update patron balance."""
        b_id = models.add_book(
            isbn="TEST-OVERDUE-001",
            title="Compilers: Principles, Techniques, and Tools",
            author="Alfred Aho et al.",
            category="Computer Science",
            publication_year=2006,
            shelf_location="CS-AHO",
            total_copies=1
        )
        p_id = models.add_patron(
            card_number="TEST-P102",
            name="Dennis Ritchie",
            email="dennis@bell-labs.com",
            patron_type="Student"
        )

        # Issue book on Sept 1 (Due Sept 15 for 14-day student loan)
        issue_res = models.issue_book(b_id, p_id, loan_date="2026-09-01")
        loan_id = issue_res["loan_id"]

        # Return on Sept 20 (5 days overdue at $0.50/day = $2.50)
        return_res = models.return_book(loan_id, return_date="2026-09-20")
        self.assertEqual(return_res["days_overdue"], 5)
        self.assertEqual(return_res["fine_accrued"], 2.50)

        patron = models.get_patron_by_id(p_id)
        self.assertEqual(patron["balance_fines"], 2.50)

        # Test fine payment
        pay_res = models.record_fine_payment(p_id, amount=2.50, payment_date="2026-09-21", payment_method="Card")
        self.assertEqual(pay_res["amount_paid"], 2.50)
        self.assertEqual(pay_res["remaining_balance"], 0.0)

        patron_paid = models.get_patron_by_id(p_id)
        self.assertEqual(patron_paid["balance_fines"], 0.0)

    def test_05_hold_queue_fulfillment(self):
        """Test that holds placed on zero-stock books are triggered when returned."""
        b_id = models.add_book(
            isbn="TEST-HOLD-001",
            title="Mythical Man-Month",
            author="Fred Brooks",
            category="Management",
            publication_year=1975,
            shelf_location="MGT-01",
            total_copies=1
        )
        p1_id = models.add_patron(card_number="TEST-P103", name="Patron One", email="p1@test.com")
        p2_id = models.add_patron(card_number="TEST-P104", name="Patron Two", email="p2@test.com")

        # P1 borrows the only copy
        loan = models.issue_book(b_id, p1_id, loan_date="2026-10-01")
        self.assertEqual(models.get_book_by_id(b_id)["available_copies"], 0)

        # P2 places hold
        hold = models.place_reservation(b_id, p2_id, current_date="2026-10-02")
        self.assertEqual(hold["status"], "Pending")

        # P1 returns book
        ret = models.return_book(loan["loan_id"], return_date="2026-10-05")
        self.assertIsNotNone(ret["hold_notification"])
        self.assertIn("READY", ret["hold_notification"])

        # Verify hold is now Ready
        holds = models.get_reservations()
        target_hold = next((h for h in holds if h["id"] == hold["reservation_id"]), None)
        self.assertEqual(target_hold["status"], "Ready")

    def test_06_simulation_stepping(self):
        """Test simulation clock advancement and event logging."""
        update_system_config("current_sim_date", "2026-10-01")
        result = simulator.advance_time(days=3)
        self.assertEqual(result["days_advanced"], 3)
        self.assertEqual(result["start_date"], "2026-10-01")
        self.assertEqual(result["end_date"], "2026-10-04")

        config = get_system_config()
        self.assertEqual(config["current_sim_date"], "2026-10-04")

        # Verify simulation events were logged
        events = models.get_recent_events(limit=10)
        self.assertTrue(len(events) > 0)

    def test_07_rest_api_endpoints(self):
        """Test Flask REST API routes."""
        client = app.test_client()

        # 1. Dashboard stats
        res = client.get("/api/analytics/dashboard")
        self.assertEqual(res.status_code, 200)
        json_data = json.loads(res.data)
        self.assertTrue(json_data["success"])
        self.assertIn("total_titles", json_data["data"])

        # 2. Books API
        res_books = client.get("/api/books")
        self.assertEqual(res_books.status_code, 200)
        books_json = json.loads(res_books.data)
        self.assertTrue(books_json["success"])
        self.assertTrue(len(books_json["books"]) > 0)

        # 3. Simulation state API
        res_sim = client.get("/api/simulation/state")
        self.assertEqual(res_sim.status_code, 200)
        sim_json = json.loads(res_sim.data)
        self.assertTrue(sim_json["success"])
        self.assertIn("current_sim_date", sim_json)

if __name__ == "__main__":
    unittest.main()
