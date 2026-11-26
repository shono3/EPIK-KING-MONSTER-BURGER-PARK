import csv
import os
import random
import string

from config import *

# ---------- Public holidays (from CSV) ----------
def load_public_holidays():
    """Read the PH CSV and return {'2026-12-25': 'Christmas Day', ...}."""
    # Path built from this file's folder, so still works when
    # Streamlit run from different folder
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), PUBLIC_HOLIDAYS_FILE)

    holidays = {}
    try:
        # utf-8-sig: names have curly apostrophes (New Year’s Day)
        # + Excel-saved files may start with BOM
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                date_text = row["date"].strip()
                if date_text == "":
                    continue  # skip blank lines at end of teh file
                holidays[date_text] = row["holiday"].strip()
    except FileNotFoundError:
        # No CSV = no holidays (weekend surcharge still applies)
        return {}
    return holidays

# Load once at startup (not every rerun)
PUBLIC_HOLIDAYS = load_public_holidays()

def get_holiday_name(visit_date):
    """Return the PH name for a datetime.date, or None if it's a normal day."""
    # CSV dates are ISO strings, convert before lookup
    return PUBLIC_HOLIDAYS.get(visit_date.isoformat())

def get_ticket_category(age):
    """Return 'toddler', 'child', 'adult' or 'senior' for an age."""
    # Check youngest group first, then go up
    if age <= TODDLER_MAX_AGE:
        return "toddler"
    elif age <= CHILD_MAX_AGE:
        return "child"
    elif age < SENIOR_MIN_AGE:
        return "adult"
    else:
        return "senior"

def counts_from_ages(ages):
    """Turn a list of ages into {category: how many}. (Counting algorithm.)"""
    counts = {category: 0 for category in CATEGORIES}
    for age in ages:
        counts[get_ticket_category(age)] += 1
    return counts

def is_surcharge_day(visit_date):
    """Return True if visit_date (a datetime.date) is a weekend or public holiday."""
    # weekday(): Monday = 0 ... Saturday = 5, Sunday = 6
    if visit_date.weekday() >= 5:
        return True
    return get_holiday_name(visit_date) is not None

def calculate_ticket_price(category, surcharge_day):
    """Price of ONE ticket, surcharge included.

    The discount applies to the base price only. The surcharge is a flat
    amount added AFTER the discount, so a child pays $32 + $5 = $37.
    """
    details = CATEGORIES[category]

    # Toddlers free, no surcharge either
    if details["free"]:
        return 0.00

    price = BASE_PRICE
    if details["discounted"]:
        price = price * (1 - DISCOUNT_RATE)
    if surcharge_day:
        price = price + SURCHARGE
    # Round to avoid float errors (e.g. 37.000000000004)
    return round(price, 2)


def calculate_order(counts, visit_date):
    """Build the line-item breakdown and total for an order.

    counts: {category: number of tickets}, e.g. {"adult": 2, "child": 1, ...}
    Returns a dict with: lines, surcharge_day, holiday_name, surcharge_qty,
    surcharge_total, total_tickets and total.
    """
    surcharge_day = is_surcharge_day(visit_date)

    lines = []
    total = 0.0
    total_tickets = 0
    paying_tickets = 0

    # One line per category with min 1 ticket
    for category, details in CATEGORIES.items():
        quantity = counts.get(category, 0)
        if quantity == 0:
            continue

        # Price WITHOUT surcharge (surcharge has own line)
        unit_price = calculate_ticket_price(category, False)
        subtotal = round(unit_price * quantity, 2)

        lines.append({
            "category": category,
            "label": details["label"],
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "discounted": details["discounted"],
        })

        total += subtotal
        total_tickets += quantity
        if not details["free"]:
            paying_tickets += quantity

    # Surcharge only for paying tickets
    surcharge_total = 0.0
    if surcharge_day:
        surcharge_total = round(paying_tickets * SURCHARGE, 2)
    total = round(total + surcharge_total, 2)

    return {
        "lines": lines,
        "surcharge_day": surcharge_day,
        # None on normal days (page knows whether to show PH name)
        "holiday_name": get_holiday_name(visit_date),
        "surcharge_qty": paying_tickets if surcharge_day else 0,
        "surcharge_total": surcharge_total,
        "total_tickets": total_tickets,
        "total": total,
    }

def generate_ticket_id(existing_ids):
    """Random ID like 'TP-7K3QX9' that is not already in existing_ids."""
    characters = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(characters, k=TICKET_ID_LENGTH))
        ticket_id = TICKET_ID_PREFIX + code
        # Loop until unused ID found
        # (clash unlikely, but guarantees unique)
        if ticket_id not in existing_ids:
            return ticket_id

def normalize_phone(phone):
    """Remove spaces and dashes so '8123 4567' and '81234567' are the same."""
    return phone.replace(" ", "").replace("-", "")

def validate_contact(name, email, phone):
    """Return a list of error messages (empty list means valid)."""
    errors = []

    if name.strip() == "":
        errors.append("Please enter your full name")

    email = email.strip()
    # Simple check: something before @, dot somewhere after
    # Basic check only, not full email validation
    local_part, at_sign, domain = email.partition("@")
    if at_sign == "" or local_part == "" or "." not in domain:
        errors.append("Please enter a valid email address")

    phone = normalize_phone(phone.strip())
    if not (phone.isdigit() and len(phone) == PHONE_LENGTH):
        errors.append(f"Phone must be {PHONE_LENGTH} digits")

    return errors

def format_money(amount):
    """12.5 -> '$12.50'"""
    return f"${amount:,.2f}"

def format_date(visit_date):
    """datetime.date -> 'Sat 28 Nov 2026'"""
    return visit_date.strftime("%a %d %b %Y")

def format_date_with_holiday(visit_date):
    """'Fri 25 Dec 2026 (Christmas Day)', or just the date if it's not a PH."""
    text = format_date(visit_date)
    holiday = get_holiday_name(visit_date)
    if holiday:
        text += f" ({holiday})"
    return text

def format_tickets(counts):
    """{'toddler': 1, 'child': 1, 'adult': 2, 'senior': 0} -> '1 Toddler · 1 Child · 2 Adult'"""
    parts = []
    for category, details in CATEGORIES.items():
        if counts.get(category, 0) > 0:
            parts.append(f"{counts[category]} {details['label']}")
    return " · ".join(parts)

def format_phone(phone):
    """'81234567' -> '8123 4567' (for display only)"""
    return phone[:4] + " " + phone[4:]
