# All business rules here, change in ONE place
# Other modules import from here (no hardcoding)

# Pricing
BASE_PRICE = 40.00 # full adult price
DISCOUNT_RATE = 0.20 # 20% off for children and seniors
SURCHARGE = 5.00 # flat per PAYING ticket on weekends / PH

# Age cut-offs
TODDLER_MAX_AGE = 4 # age 0-4 free
CHILD_MAX_AGE = 11 # age 5-11 discount
SENIOR_MIN_AGE = 60 # age 60+ discount

# ---------- Ticket categories ----------
# Order here = order on screen
# "discounted" = DISCOUNT_RATE applies; "free" = no charge
CATEGORIES = {
    "toddler": {"label": "Toddler", "ages": "0–4", "free": True, "discounted": False},
    "child":   {"label": "Child", "ages": "5–11", "free": False, "discounted": True},
    "adult":   {"label": "Adult", "ages": "12–59", "free": False, "discounted": False},
    "senior":  {"label": "Senior", "ages": "60+", "free": False, "discounted": True},
}

# ---------- Booking limits ----------
MAX_PER_CATEGORY = 10         # max tickets per category per booking

# ---------- Contact / ticket ID rules ----------
PHONE_LENGTH = 8              # Singapore numbers
TICKET_ID_PREFIX = "TP-"
TICKET_ID_LENGTH = 6          # characters after the prefix

# ---------- Public holidays ----------
# PH dates read from this CSV (columns: date, day, holiday), from MOM list
# New year = replace file, no code change
PUBLIC_HOLIDAYS_FILE = "PublicHolidaysfor2026-2027.csv"
