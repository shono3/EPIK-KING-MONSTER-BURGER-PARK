import json

from logic import normalize_phone

# Bookings stored in local JSON file (enough for prototype)
BOOKINGS_FILE = "bookings.json"

def load_bookings():
    """Return a dict {ticket_id: booking_dict}. Return {} if the file doesn't exist yet."""
    try:
        with open(BOOKINGS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # File empty or damaged: start fresh, no crash
        return {}

def save_booking(ticket_id, booking):
    """Add one booking and write the whole dict back to the file."""
    # Read all, add new one, rewrite file (fine at this scale)
    bookings = load_bookings()
    bookings[ticket_id] = booking
    with open(BOOKINGS_FILE, "w") as file:
        json.dump(bookings, file, indent=2)

def find_booking(ticket_id, contact):
    """Return the booking if the ID exists AND contact matches email or phone, else None."""
    bookings = load_bookings()
    booking = bookings.get(ticket_id.strip().upper())
    if booking is None:
        return None

    # Email match case-insensitive ("Name@Gmail.com" still matches)
    contact = contact.strip().lower()
    email_matches = contact == booking["email"].lower()
    phone_matches = normalize_phone(contact) == booking["phone"]

    if email_matches or phone_matches:
        return booking
    return None

