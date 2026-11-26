import os
from datetime import date, datetime

import streamlit as st

from config import CATEGORIES, DISCOUNT_RATE, MAX_PER_CATEGORY
from logic import (
    calculate_order,
    calculate_ticket_price,
    format_date_with_holiday,
    format_money,
    format_phone,
    format_tickets,
    generate_ticket_id,
    normalize_phone,
    validate_contact,
)
from storage import find_booking, load_bookings, save_booking

# Widget keys we copy in/out of st.session_state
# (Streamlit forgets widget value when widget not drawn,
#  so keep own copy + re-seed widget from it)
COUNT_KEYS = {category: f"count_{category}" for category in CATEGORIES}
DATE_KEY = "visit_date_input"
CONTACT_KEYS = ["name", "email", "phone"]

# Logo
LOGO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

# Session state helpers
def default_counts():
    """One adult ticket to start with, nothing else."""
    counts = {category: 0 for category in CATEGORIES}
    counts["adult"] = 1
    return counts

def init_state():
    """Set defaults the first time the app runs."""
    # Streamlit reruns whole script every interaction, so set only once
    if "step" not in st.session_state:
        st.session_state.step = "select"
        st.session_state.counts = default_counts()
        st.session_state.visit_date = date.today()
        st.session_state.contact = {"name": "", "email": "", "phone": ""}
        st.session_state.ticket_id = None
        st.session_state.booking = None

def seed(key, value):
    """Give a widget its starting value only if it has none yet."""
    if key not in st.session_state:
        st.session_state[key] = value

def go_to(step):
    """Change screen and redraw."""
    st.session_state.step = step
    st.rerun()

def reset_booking():
    """Clear everything so the visitor can start a new booking."""
    st.session_state.counts = default_counts()
    st.session_state.visit_date = date.today()
    st.session_state.contact = {"name": "", "email": "", "phone": ""}
    st.session_state.ticket_id = None
    st.session_state.booking = None
    # Remove old widget values too, so widgets re-seed from defaults
    for key in list(COUNT_KEYS.values()) + [DATE_KEY] + [f"contact_{k}" for k in CONTACT_KEYS]:
        st.session_state.pop(key, None)

# Small display helpers (shared by screens)
def price_label(category):
    """Text for the price table: 'Free', '$32.00 (20% off)' or '$40.00'."""
    details = CATEGORIES[category]
    if details["free"]:
        return "Free"
    price = format_money(calculate_ticket_price(category, False))
    if details["discounted"]:
        return f"{price} ({round(DISCOUNT_RATE * 100)}% off)"
    return price

def money_row(label, amount_text, big=False, red=False):
    """One row: label on the left, amount right-aligned on the right."""
    # No built-in right-align in Streamlit, so use bit of HTML
    left, right = st.columns([4, 1])
    size = "1.4rem" if big else "1rem"
    weight = "700" if big else "400"
    colour = "#FF4B4B" if red else "inherit"
    left.markdown(
        f"<div style='font-size:{size};font-weight:{weight}'>{label}</div>",
        unsafe_allow_html=True,
    )
    right.markdown(
        f"<div style='text-align:right;font-size:{size};font-weight:{weight};"
        f"color:{colour}'>{amount_text}</div>",
        unsafe_allow_html=True,
    )

def detail_row(label, value):
    """Grey label + value, used on the confirmation and retrieve cards."""
    left, right = st.columns([1, 3])
    left.markdown(f":gray[{label}]")
    right.write(value)

def show_order_lines(order):
    """Line items, surcharge and total. Used on screens 1 and 2."""
    for line in order["lines"]:
        text = f"{line['quantity']} × {line['label']}"
        if line["discounted"]:
            text += f" ({round(DISCOUNT_RATE * 100)}% off)"
        amount = "Free" if line["unit_price"] == 0 else format_money(line["subtotal"])
        money_row(text, amount)

    if order["surcharge_day"]:
        unit = order["surcharge_total"] / order["surcharge_qty"] if order["surcharge_qty"] else 0
        # Show PH name on surcharge line (why extra charge)
        if order["holiday_name"]:
            reason = f"Public holiday surcharge – {order['holiday_name']}"
        else:
            reason = "Weekend surcharge"
        money_row(
            f"{reason} ({order['surcharge_qty']} × {format_money(unit)})",
            format_money(order["surcharge_total"]),
        )

    st.divider()
    money_row("Total", format_money(order["total"]), big=True, red=True)

def show_ticket_card(ticket_id):
    """Big red ticket ID header shared by screens 3 and 4."""
    st.caption("Ticket ID")
    st.markdown(f"## :red[{ticket_id}]")
    st.divider()

def page_header(title, caption):
    """Title + caption on the left, park logo top-right. Used by every screen."""
    title_col, logo_col = st.columns([3, 1], vertical_alignment="center")
    title_col.title(title)
    title_col.caption(caption)
    # Skip logo if file missing (crash prevention)
    if os.path.exists(LOGO_FILE):
        logo_col.image(LOGO_FILE, width="stretch")

# Screen 1: select tickets
def show_select_screen():
    page_header("Theme Park Tickets", "Step 1 of 3: Choose your tickets")

    # Price table built from config (price change = no edit here)
    table = "| Category | Age | Price |\n|---|---|---|\n"
    for category, details in CATEGORIES.items():
        table += f"| {details['label']} | {details['ages']} | {price_label(category)} |\n"
    st.markdown(table)

    # --- Visit date + surcharge notice ---
    # max() so old saved date doesn't break min_value
    seed(DATE_KEY, max(st.session_state.visit_date, date.today()))
    date_col, notice_col = st.columns(2)
    visit_date = date_col.date_input(
        "Visit date", min_value=date.today(), format="YYYY/MM/DD", key=DATE_KEY
    )
    st.session_state.visit_date = visit_date

    # --- One counter per category ---
    count_cols = st.columns(len(CATEGORIES))
    counts = {}
    for column, (category, details) in zip(count_cols, CATEGORIES.items()):
        seed(COUNT_KEYS[category], st.session_state.counts[category])
        counts[category] = column.number_input(
            f"{details['label']} ({details['ages']})",
            min_value=0,
            max_value=MAX_PER_CATEGORY,
            step=1,
            key=COUNT_KEYS[category],
        )
    st.session_state.counts = counts

    order = calculate_order(counts, visit_date)

    # Notice goes in column made earlier, now order known
    # PH checked first (e.g. Vesak Day on Sunday still shows PH name)
    if order["holiday_name"]:
        notice_col.info(f"🎉 Public holiday: **{order['holiday_name']}**  \nSurcharge applies")
    elif order["surcharge_day"]:
        notice_col.info("Weekend surcharge applies")
    else:
        notice_col.success("Standard pricing applies")

    # --- Order summary ---
    with st.container(border=True):
        st.subheader("Order summary")
        if order["total_tickets"] == 0:
            st.write("No tickets selected yet.")
        else:
            show_order_lines(order)

    _, button_col = st.columns([3, 1])
    if button_col.button(
        "Proceed to checkout",
        type="primary",
        use_container_width=True,
        disabled=order["total_tickets"] == 0,  # need min 1 ticket
    ):
        go_to("checkout")

# Screen 2: checkout
def show_checkout_screen():
    page_header("Theme Park Tickets", "Step 2 of 3: Checkout")

    counts = st.session_state.counts
    visit_date = st.session_state.visit_date
    order = calculate_order(counts, visit_date)

    # Collapsed order summary (date shows PH name if any)
    summary = (
        f"{format_date_with_holiday(visit_date)} · {order['total_tickets']} tickets · "
        f"Total {format_money(order['total'])}"
    )
    with st.expander(f"Review order: {summary}"):
        show_order_lines(order)

    # --- Contact details ---
    st.subheader("Your details")
    contact = st.session_state.contact
    for field in CONTACT_KEYS:
        seed(f"contact_{field}", contact[field])

    name = st.text_input("Full name", key="contact_name")
    email_col, phone_col = st.columns(2)
    email = email_col.text_input(
        "Email", placeholder="name@example.com", help="Used to retrieve your ticket later.",
        key="contact_email",
    )
    phone = phone_col.text_input("Phone number", placeholder="8123 4567", key="contact_phone")
    st.session_state.contact = {"name": name, "email": email, "phone": phone}

    # Errors drawn here (above buttons)
    error_box = st.container()

    back_col, _, confirm_col = st.columns([1, 3, 1])
    if back_col.button("Back", use_container_width=True):
        go_to("select")

    if confirm_col.button("Confirm & pay", type="primary", use_container_width=True):
        errors = validate_contact(name, email, phone)
        if errors:
            with error_box:
                for message in errors:
                    st.error(message)
        else:
            # No real payment (prototype)
            ticket_id = generate_ticket_id(load_bookings())
            booking = {
                "name": name.strip(),
                "email": email.strip(),
                "phone": normalize_phone(phone.strip()),
                "visit_date": visit_date.isoformat(),
                "counts": counts,
                "total": order["total"],
                "booked_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_booking(ticket_id, booking)
            st.session_state.ticket_id = ticket_id
            st.session_state.booking = booking
            go_to("confirmation")

# Screen 3: confirmation
def show_confirmation_screen():
    booking = st.session_state.booking
    if booking is None:
        # Nothing to confirm (e.g. page reloaded), send visitor back
        go_to("select")
        return

    page_header("Theme Park Tickets", "Step 3 of 3: Confirmation")
    st.success("Booking confirmed!")

    with st.container(border=True):
        show_ticket_card(st.session_state.ticket_id)
        detail_row("Visitor", booking["name"])
        detail_row("Visit date", format_date_with_holiday(date.fromisoformat(booking["visit_date"])))
        detail_row("Tickets", format_tickets(booking["counts"]))
        detail_row("Contact", f"{booking['email']} · {format_phone(booking['phone'])}")
        st.divider()
        money_row("Total paid", format_money(booking["total"]), big=True)
        st.caption("Keep your ticket ID to retrieve this booking later.")

    if st.button("Book another", type="primary"):
        reset_booking()
        go_to("select")

# Screen 4: retrieve ticket
def show_retrieve_screen():
    page_header("Retrieve your ticket", "Find an existing booking")

    contact_col, id_col = st.columns(2)
    contact = contact_col.text_input("Email or phone number", placeholder="name@example.com")
    ticket_id = id_col.text_input("Ticket ID", placeholder="TP-XXXXXX")

    if st.button("Find ticket", type="primary"):
        booking = find_booking(ticket_id, contact)
        if booking is None:
            # Same msg for wrong ID or contact (IDs can't be guessed)
            st.error("No booking found. Check your details and try again.")
        else:
            with st.container(border=True):
                show_ticket_card(ticket_id.strip().upper())
                detail_row("Visit date", format_date_with_holiday(date.fromisoformat(booking["visit_date"])))
                detail_row("Tickets", format_tickets(booking["counts"]))
                detail_row("Total paid", format_money(booking["total"]))

# Main: sidebar nav + pick screen to draw
# Step -> screen function (no long if/elif chain)
BOOKING_SCREENS = {
    "select": show_select_screen,
    "checkout": show_checkout_screen,
    "confirmation": show_confirmation_screen,
}

def main():
    st.set_page_config(page_title="Theme Park Tickets", page_icon="🎢")
    init_state()

    st.sidebar.caption("Navigation")
    page = st.sidebar.radio(
        "Navigation", ["Book Tickets", "Retrieve Ticket"], label_visibility="collapsed"
    )

    if page == "Book Tickets":
        BOOKING_SCREENS[st.session_state.step]()
    else:
        show_retrieve_screen()

main()
