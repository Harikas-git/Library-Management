"""
cli.py - Terminal-based Interactive Simulation & Library Management Console.
Provides a full-featured CLI interface for running the simulation, inspecting database records,
and performing library operations directly from the terminal.
"""

import sys
import os
from datetime import datetime

import models
from database import init_db, get_system_config
from simulator import simulator
from seed_data import seed_database

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title=""):
    print("\n" + "=" * 70)
    print("  [ATHENAEUM] LIBRARY MANAGEMENT & SIMULATION ENGINE")
    if title:
        print(f"  >> {title}")
    config = get_system_config()
    print(f"  [Date: {config.get('current_sim_date', 'N/A')}]  |  [Fine Rate: ${config.get('fine_rate_per_day', '0.50')}/day]")
    print("=" * 70)

def show_dashboard():
    print_header("SYSTEM DASHBOARD & ANALYTICS")
    stats = models.get_dashboard_stats()
    print(f"\n  📚 Total Titles:         {stats['total_titles']}")
    print(f"  📦 Total Copies:         {stats['total_copies']} ({stats['available_copies']} available on shelf)")
    print(f"  👥 Registered Patrons:   {stats['total_patrons']}")
    print(f"  🔄 Active Loans:         {stats['active_loans']}")
    print(f"  ⚠️ Overdue Loans:        {stats['overdue_loans']}")
    print(f"  ⏳ Pending Holds:        {stats['pending_holds']}")
    print(f"  💵 Outstanding Fines:    ${stats['outstanding_fines']:.2f}")
    print(f"  💰 Collected Fines:      ${stats['collected_fines']:.2f}")
    print("-" * 70)

def list_books():
    print_header("BOOK CATALOG")
    search = input("Enter search keyword (or press Enter for all): ").strip()
    books = models.get_all_books(search=search if search else None)
    
    print(f"\n{'ID':<4} {'Title':<35} {'Category':<16} {'Avail/Total':<12} {'Shelf':<8}")
    print("-" * 80)
    for b in books:
        stock = f"{b['available_copies']}/{b['total_copies']}"
        title = (b['title'][:32] + '...') if len(b['title']) > 32 else b['title']
        print(f"{b['id']:<4} {title:<35} {b['category']:<16} {stock:<12} {b['shelf_location']:<8}")
    print(f"\nTotal: {len(books)} books listed.")

def list_patrons():
    print_header("REGISTERED PATRONS")
    search = input("Enter search keyword (or press Enter for all): ").strip()
    patrons = models.get_all_patrons(search=search if search else None)
    
    print(f"\n{'ID':<4} {'Card #':<10} {'Name':<22} {'Role':<11} {'Persona':<15} {'Fines':<9}")
    print("-" * 80)
    for p in patrons:
        fine = f"${p['balance_fines']:.2f}"
        print(f"{p['id']:<4} {p['card_number']:<10} {p['name'][:20]:<22} {p['patron_type']:<11} {p['behavior_profile']:<15} {fine:<9}")
    print(f"\nTotal: {len(patrons)} patrons listed.")

def list_loans():
    print_header("CIRCULATION & LOANS")
    filter_choice = input("Filter (A: Active, O: Overdue, R: Returned, Enter: All): ").strip().upper()
    status_map = {"A": "Active", "O": "Overdue", "R": "Returned"}
    status = status_map.get(filter_choice, None)

    loans = models.get_loans(status_filter=status)
    print(f"\n{'ID':<5} {'Title':<28} {'Borrower':<18} {'Due Date':<11} {'Status':<10} {'Fine':<7}")
    print("-" * 85)
    for l in loans:
        title = (l['book_title'][:25] + '...') if len(l['book_title']) > 25 else l['book_title']
        borrower = (l['patron_name'][:16] + '..') if len(l['patron_name']) > 16 else l['patron_name']
        fine = f"${l['fine_accrued']:.2f}" if l['fine_accrued'] > 0 else "-"
        print(f"#{l['id']:<4} {title:<28} {borrower:<18} {l['due_date']:<11} {l['status']:<10} {fine:<7}")
    print(f"\nTotal: {len(loans)} loan records.")

def advance_time_cli():
    print_header("ADVANCE SIMULATION CLOCK")
    print("Choose step duration:")
    print("  1) +1 Day")
    print("  2) +7 Days (1 Week)")
    print("  3) +30 Days (1 Month)")
    print("  4) Custom Days")
    choice = input("Select option (1-4): ").strip()
    
    days = 1
    if choice == "2":
        days = 7
    elif choice == "3":
        days = 30
    elif choice == "4":
        try:
            days = int(input("Enter number of days: ").strip())
        except ValueError:
            print("Invalid number. Stepping 1 day.")
            days = 1

    print(f"\nSimulating {days} day(s) of library activities...")
    res = simulator.advance_time(days)
    print("\n[OK] Simulation Complete!")
    print(f"  - Date Range:         {res['start_date']} -> {res['end_date']}")
    print(f"  - Returns Processed:  {res['returns_processed']}")
    print(f"  - Borrows Processed:  {res['borrows_processed']}")
    print(f"  - Fines Paid Count:   {res['fines_paid_count']}")
    print(f"  - Accrued Overdue $:  ${res['fines_accrued_total']:.2f}")

def checkout_book_cli():
    print_header("ISSUE / CHECK OUT BOOK")
    try:
        book_id = int(input("Enter Book ID: ").strip())
        patron_id = int(input("Enter Patron ID: ").strip())
        result = models.issue_book(book_id, patron_id)
        print(f"\n[OK] Successfully issued '{result['book_title']}' to {result['patron_name']}!")
        print(f"   Loan ID: #{result['loan_id']} | Due Date: {result['due_date']}")
    except Exception as e:
        print(f"\n[FAIL] Checkout failed: {e}")

def return_book_cli():
    print_header("RETURN BOOK (CHECK IN)")
    try:
        loan_id = int(input("Enter Loan ID to return: ").strip())
        result = models.return_book(loan_id)
        print(f"\n[OK] Returned '{result['book_title']}' from {result['patron_name']} on {result['return_date']}.")
        if result['fine_accrued'] > 0:
            print(f"   [NOTICE] Book was {result['days_overdue']} days overdue. Fine assessed: ${result['fine_accrued']:.2f}.")
        if result['hold_notification']:
            print(f"   [HOLD READY] {result['hold_notification']}")
    except Exception as e:
        print(f"\n[FAIL] Return failed: {e}")

def pay_fine_cli():
    print_header("SETTLE PATRON FINE")
    try:
        patron_id = int(input("Enter Patron ID: ").strip())
        patron = models.get_patron_by_id(patron_id)
        if not patron:
            print("Patron not found.")
            return
        print(f"Patron: {patron['name']} | Current Unpaid Fines: ${patron['balance_fines']:.2f}")
        if patron['balance_fines'] <= 0:
            print("No fines pending.")
            return
        amount = float(input(f"Enter payment amount (max ${patron['balance_fines']:.2f}): ").strip())
        method = input("Payment method (Cash/Card/Online) [Cash]: ").strip() or "Cash"
        res = models.record_fine_payment(patron_id, amount, payment_method=method)
        print(f"\n[OK] Recorded ${res['amount_paid']:.2f} payment. Remaining balance: ${res['remaining_balance']:.2f}")
    except Exception as e:
        print(f"\n[FAIL] Payment failed: {e}")

def view_events_cli():
    print_header("SIMULATION EVENT AUDIT STREAM")
    events = models.get_recent_events(limit=25)
    print(f"\n{'Date':<11} {'Type':<14} {'Actor':<18} {'Summary':<35}")
    print("-" * 80)
    for e in events:
        actor = (e['actor_name'] or 'System')[:16]
        summary = (e['summary'][:32] + '...') if len(e['summary']) > 32 else e['summary']
        print(f"{e['sim_date']:<11} {e['event_type']:<14} {actor:<18} {summary:<35}")

def main_menu():
    while True:
        print_header("MAIN MENU")
        print("  1) System Dashboard & Statistics")
        print("  2) Advance Simulation Clock (+1, +7, +30 Days)")
        print("  3) Catalog Books (Search & Stock)")
        print("  4) Patrons & Behavior Personas")
        print("  5) Circulation Loans & Overdue Status")
        print("  6) Check Out / Issue Book")
        print("  7) Check In / Return Book")
        print("  8) Settle Patron Fine Payment")
        print("  9) View Recent Simulation Events")
        print(" 10) Reset to Initial Seed Scenario")
        print("  0) Exit Console")
        print("-" * 70)
        
        choice = input("Enter choice (0-10): ").strip()
        if choice == "1":
            show_dashboard()
        elif choice == "2":
            advance_time_cli()
        elif choice == "3":
            list_books()
        elif choice == "4":
            list_patrons()
        elif choice == "5":
            list_loans()
        elif choice == "6":
            checkout_book_cli()
        elif choice == "7":
            return_book_cli()
        elif choice == "8":
            pay_fine_cli()
        elif choice == "9":
            view_events_cli()
        elif choice == "10":
            if input("Confirm reset database to seed scenario? (y/n): ").lower() == 'y':
                seed_database(reset=True)
                print("Database reset successfully.")
        elif choice == "0":
            print("\nExiting Athenaeum CLI. Goodbye!\n")
            break
        else:
            print("Invalid option. Please choose 0-10.")
        
        input("\nPress Enter to return to menu...")

if __name__ == "__main__":
    main_menu()
