"""
seed_data.py - Populates the library database with curated books, patrons,
historical loans, reservations, and initial simulation events.
"""

from database import init_db, update_system_config
from models import add_book, add_patron, issue_book, return_book, place_reservation, log_event

BOOKS_DATA = [
    # Computer Science & Technology
    ("978-0132350884", "Clean Code: A Handbook of Agile Software Craftsmanship", "Robert C. Martin", "Computer Science", 2008, "CS-A10", 4, 38.99, 95),
    ("978-0262033848", "Introduction to Algorithms (CLRS)", "Thomas H. Cormen", "Computer Science", 2009, "CS-A11", 5, 89.50, 92),
    ("978-0201633610", "Design Patterns: Elements of Reusable Object-Oriented Software", "Erich Gamma, Richard Helm", "Computer Science", 1994, "CS-A12", 3, 44.99, 88),
    ("978-0134685991", "Effective Java", "Joshua Bloch", "Computer Science", 2018, "CS-A14", 3, 42.00, 85),
    ("978-0136042594", "Artificial Intelligence: A Modern Approach", "Stuart Russell, Peter Norvig", "Computer Science", 2020, "CS-B01", 4, 99.00, 94),
    ("978-0135957059", "The Pragmatic Programmer: 20th Anniversary Edition", "David Thomas, Andrew Hunt", "Computer Science", 2019, "CS-B02", 4, 45.00, 90),
    ("978-1449373320", "Designing Data-Intensive Applications", "Martin Kleppmann", "Computer Science", 2017, "CS-B04", 4, 49.99, 96),
    ("978-0262510875", "Structure and Interpretation of Computer Programs", "Harold Abelson, Gerald Jay Sussman", "Computer Science", 1996, "CS-B05", 2, 60.00, 80),

    # Science & Mathematics
    ("978-0553380163", "A Brief History of Time", "Stephen Hawking", "Science", 1998, "SCI-C01", 3, 18.00, 89),
    ("978-0345539434", "Cosmos", "Carl Sagan", "Science", 2013, "SCI-C02", 3, 21.00, 87),
    ("978-0143114949", "The Selfish Gene", "Richard Dawkins", "Science", 2006, "SCI-C03", 2, 17.50, 78),
    ("978-0143110569", "The Elegant Universe", "Brian Greene", "Science", 2003, "SCI-C04", 2, 19.99, 75),

    # Literature & Fiction
    ("978-0451524935", "1984", "George Orwell", "Fiction", 1949, "LIT-D01", 5, 14.99, 93),
    ("978-0060935467", "To Kill a Mockingbird", "Harper Lee", "Fiction", 1960, "LIT-D02", 4, 15.99, 91),
    ("978-0743273565", "The Great Gatsby", "F. Scott Fitzgerald", "Fiction", 1925, "LIT-D03", 3, 13.50, 84),
    ("978-0140449136", "Crime and Punishment", "Fyodor Dostoevsky", "Fiction", 1866, "LIT-D04", 3, 16.00, 82),
    ("978-0547928227", "The Hobbit", "J.R.R. Tolkien", "Fiction", 1937, "LIT-D05", 4, 18.00, 90),

    # Philosophy & History
    ("978-0062316097", "Sapiens: A Brief History of Humankind", "Yuval Noah Harari", "History", 2015, "HIS-E01", 5, 24.99, 95),
    ("978-0140449334", "Meditations", "Marcus Aurelius", "Philosophy", 2006, "PHI-E02", 3, 12.00, 86),
    ("978-0140455113", "The Republic", "Plato", "Philosophy", 2007, "PHI-E03", 2, 14.00, 79),
    ("978-0393317558", "Guns, Germs, and Steel", "Jared Diamond", "History", 1997, "HIS-E04", 3, 19.50, 83),

    # Business, Psychology & Self-Improvement
    ("978-0374533557", "Thinking, Fast and Slow", "Daniel Kahneman", "Psychology", 2011, "PSY-F01", 4, 20.00, 92),
    ("978-0735211292", "Atomic Habits", "James Clear", "Self-Help", 2018, "SLF-F02", 5, 27.00, 97),
    ("978-0804139298", "Zero to One: Notes on Startups", "Peter Thiel, Blake Masters", "Business", 2014, "BUS-F03", 3, 22.00, 88),
    ("978-0307887894", "The Lean Startup", "Eric Ries", "Business", 2011, "BUS-F04", 3, 23.50, 85)
]

PATRONS_DATA = [
    ("LIB-1001", "Dr. Alan Turing", "a.turing@cambridge.edu", "Faculty", "Meticulous", 7),
    ("LIB-1002", "Ada Lovelace", "ada.lovelace@oxford.ac.uk", "Faculty", "Meticulous", 7),
    ("LIB-1003", "Bob Vance", "bob.vance@vancerefrigeration.com", "Community", "Typical", 2),
    ("LIB-1004", "Charlie Brown", "cbrown@student.state.edu", "Student", "Procrastinator", 3),
    ("LIB-1005", "Diana Prince", "diana.prince@themyscira.gov", "Student", "Meticulous", 4),
    ("LIB-1006", "Edward Cullen", "edward@forkshigh.edu", "Student", "Typical", 3),
    ("LIB-1007", "Fiona Apple", "fiona@soundarts.edu", "Student", "Forgetful", 3),
    ("LIB-1008", "George Costanza", "george@vandelayindustries.net", "Community", "Procrastinator", 2),
    ("LIB-1009", "Hannah Abbott", "h.abbott@hogwarts.edu", "Student", "Typical", 3),
    ("LIB-1010", "Ian Malcolm", "ian.malcolm@chaos-inst.org", "Faculty", "Typical", 7),
    ("LIB-1011", "Julia Roberts", "julia@cinema-arts.org", "Community", "Typical", 2),
    ("LIB-1012", "Kevin Mitnick", "kevin@defcon-security.io", "Student", "Meticulous", 4),
    ("LIB-1013", "Laura Croft", "laura@archaeology-oxford.edu", "Student", "Typical", 3),
    ("LIB-1014", "Michael Scott", "m.scott@dundermifflin.com", "Community", "Forgetful", 2),
    ("LIB-1015", "Nora Fatehi", "nora@danceacademy.edu", "Student", "Procrastinator", 3)
]

def seed_database(reset=True):
    """Initializes the database and populates comprehensive starter data."""
    print("=" * 60)
    print("Initializing Database & Populating Seed Data...")
    print("=" * 60)

    init_db(reset=reset)

    # Base simulation date
    start_sim_date = "2026-10-01"
    update_system_config("current_sim_date", start_sim_date)

    # 1. Insert Books
    book_ids = []
    for book in BOOKS_DATA:
        b_id = add_book(*book)
        book_ids.append(b_id)
    print(f"[+] Loaded {len(book_ids)} curated books into catalog.")

    # 2. Insert Patrons
    patron_ids = []
    for patron in PATRONS_DATA:
        p_id = add_patron(*patron)
        patron_ids.append(p_id)
    print(f"[+] Registered {len(patron_ids)} patrons with behavioral personas.")

    # 3. Simulate initial checkout history (10 days prior: Sept 20 to Sept 30)
    print("[*] Generating realistic circulation history...")

    # Past returned loans
    loan1 = issue_book(book_id=book_ids[0], patron_id=patron_ids[0], loan_date="2026-09-15")  # Clean Code -> Alan Turing
    return_book(loan1["loan_id"], return_date="2026-09-24")

    loan2 = issue_book(book_id=book_ids[17], patron_id=patron_ids[1], loan_date="2026-09-18")  # Sapiens -> Ada Lovelace
    return_book(loan2["loan_id"], return_date="2026-09-28")

    # Currently Active Loans (due in early/mid October)
    issue_book(book_id=book_ids[6], patron_id=patron_ids[0], loan_date="2026-09-26")  # DDIA -> Alan Turing
    issue_book(book_id=book_ids[4], patron_id=patron_ids[1], loan_date="2026-09-27")  # AI: Modern Approach -> Ada Lovelace
    issue_book(book_id=book_ids[12], patron_id=patron_ids[4], loan_date="2026-09-28") # 1984 -> Diana Prince
    issue_book(book_id=book_ids[22], patron_id=patron_ids[11], loan_date="2026-09-29") # Atomic Habits -> Kevin Mitnick
    issue_book(book_id=book_ids[1], patron_id=patron_ids[5], loan_date="2026-09-30")  # CLRS -> Edward Cullen

    # An Overdue loan created intentionally (borrowed on Sept 12 by Charlie Brown - Procrastinator, due Sept 26)
    loan_overdue = issue_book(book_id=book_ids[2], patron_id=patron_ids[3], loan_date="2026-09-12") # Design Patterns -> Charlie Brown

    # A Forgetful patron with overdue book
    loan_overdue2 = issue_book(book_id=book_ids[13], patron_id=patron_ids[6], loan_date="2026-09-10") # Mockingbird -> Fiona Gallagher

    # Place a pending hold / reservation
    place_reservation(book_id=book_ids[6], patron_id=patron_ids[3], current_date="2026-09-29")  # Charlie Brown placed hold on DDIA
    place_reservation(book_id=book_ids[22], patron_id=patron_ids[8], current_date="2026-09-30") # Hannah Abbott placed hold on Atomic Habits

    log_event(
        sim_date=start_sim_date,
        event_type="SYSTEM_INIT",
        actor_name="System",
        summary="Library system initialized with seed catalog and patrons",
        details="Full relational database initialized. Ready for simulation ticks."
    )

    print(f"[+] Seed data setup complete! Simulated date set to: {start_sim_date}")

if __name__ == "__main__":
    seed_database()
