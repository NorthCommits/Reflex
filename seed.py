"""Deterministic, idempotent seed data for the Reflex sample database.

Uses a fixed random seed and a fixed reference date so the generated
numbers never drift between runs.
"""

import datetime
import logging
import random

from reflex.db import get_writer_session
from reflex.logging_config import configure_logging
from reflex.models import Customer, Order, OrderItem, Payment, Product

logger = logging.getLogger("reflex.seed")

SEED = 42
REFERENCE_DATE = datetime.date(2026, 1, 1)

COUNTRIES = ["USA", "UK", "Germany", "France", "Canada", "India", "Australia", "Brazil"]
FIRST_NAMES = [
    "Olivia", "Liam", "Emma", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "Lucas", "Mia", "Elijah", "Amelia", "James", "Harper", "Ben",
    "Evelyn", "Henry", "Luna", "Alex", "Grace", "Leo", "Chloe", "Owen",
    "Zoe", "Jack", "Nora", "Sam", "Ella", "Max",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor",
    "Thomas", "Moore", "Jackson", "Martin", "Lee", "Perez", "White",
]

PRODUCTS = [
    # Electronics
    ("Wireless Mouse", "Electronics", 24.99),
    ("Mechanical Keyboard", "Electronics", 89.99),
    ("USB-C Hub", "Electronics", 39.50),
    ("Noise Cancelling Headphones", "Electronics", 199.00),
    ("27-inch Monitor", "Electronics", 249.99),
    ("Wireless Charger", "Electronics", 29.99),
    ("Bluetooth Speaker", "Electronics", 59.99),
    ("4K Webcam", "Electronics", 79.50),
    ("Portable SSD 1TB", "Electronics", 109.99),
    ("Smart Watch", "Electronics", 229.00),
    ("Fitness Tracker", "Electronics", 89.00),
    ("Wireless Earbuds", "Electronics", 129.99),
    ("Laptop Stand", "Electronics", 34.50),
    ("HDMI Cable 2m", "Electronics", 9.99),
    ("Power Bank 10000mAh", "Electronics", 34.99),
    ("Smart Plug", "Electronics", 19.99),
    ("Action Camera", "Electronics", 179.00),
    ("Drone Mini", "Electronics", 299.00),
    ("Tablet Stylus", "Electronics", 44.99),
    ("Gaming Mouse Pad", "Electronics", 14.99),
    ("Ring Light", "Electronics", 39.99),
    ("Wifi 6 Router", "Electronics", 129.00),
    ("External Hard Drive 2TB", "Electronics", 74.99),
    ("Graphics Tablet", "Electronics", 89.00),
    ("Webcam Privacy Cover", "Electronics", 6.99),
    # Furniture
    ("Standing Desk", "Furniture", 349.00),
    ("Ergonomic Chair", "Furniture", 279.50),
    ("Desk Lamp", "Furniture", 34.99),
    ("Bookshelf", "Furniture", 129.00),
    ("Filing Cabinet", "Furniture", 159.00),
    ("Monitor Arm", "Furniture", 49.99),
    ("Bean Bag Chair", "Furniture", 89.00),
    ("Coffee Table", "Furniture", 179.00),
    ("TV Stand", "Furniture", 199.00),
    ("Wardrobe", "Furniture", 399.00),
    ("Bar Stool", "Furniture", 69.99),
    ("Recliner Sofa", "Furniture", 599.00),
    ("Nightstand", "Furniture", 89.99),
    ("Bunk Bed", "Furniture", 449.00),
    ("Office Desk", "Furniture", 249.00),
    ("Storage Ottoman", "Furniture", 59.99),
    ("Shoe Rack", "Furniture", 44.99),
    ("Room Divider", "Furniture", 99.00),
    ("Accent Chair", "Furniture", 189.00),
    ("Dining Table", "Furniture", 429.00),
    # Books
    ("The Pragmatic Programmer", "Books", 42.00),
    ("Designing Data-Intensive Applications", "Books", 49.99),
    ("Clean Code", "Books", 37.50),
    ("Atomic Habits", "Books", 18.99),
    ("Sapiens", "Books", 22.50),
    ("The Lean Startup", "Books", 19.99),
    ("Deep Work", "Books", 17.99),
    ("Thinking, Fast and Slow", "Books", 21.00),
    ("The Alchemist", "Books", 14.99),
    ("1984", "Books", 12.99),
    ("To Kill a Mockingbird", "Books", 13.99),
    ("The Great Gatsby", "Books", 11.99),
    ("Educated", "Books", 19.50),
    ("Where the Crawdads Sing", "Books", 16.99),
    ("The Silent Patient", "Books", 15.99),
    ("Project Hail Mary", "Books", 20.99),
    ("Dune", "Books", 18.50),
    ("The Hobbit", "Books", 16.50),
    ("Becoming", "Books", 21.99),
    ("Man's Search for Meaning", "Books", 13.50),
    # Sports
    ("Running Shoes", "Sports", 79.99),
    ("Yoga Mat", "Sports", 29.99),
    ("Dumbbell Set", "Sports", 119.00),
    ("Water Bottle", "Sports", 14.99),
    ("Resistance Bands Set", "Sports", 24.99),
    ("Jump Rope", "Sports", 12.99),
    ("Foam Roller", "Sports", 27.99),
    ("Cycling Helmet", "Sports", 54.99),
    ("Tennis Racket", "Sports", 89.99),
    ("Basketball", "Sports", 29.99),
    ("Soccer Ball", "Sports", 24.99),
    ("Swim Goggles", "Sports", 16.99),
    ("Hiking Backpack", "Sports", 99.00),
    ("Camping Tent 2-Person", "Sports", 149.00),
    ("Sleeping Bag", "Sports", 69.99),
    ("Trekking Poles", "Sports", 44.99),
    ("Golf Balls Dozen", "Sports", 27.99),
    ("Boxing Gloves", "Sports", 39.99),
    ("Yoga Block Set", "Sports", 17.99),
    ("Gym Gloves", "Sports", 19.99),
    # Home
    ("Coffee Maker", "Home", 64.99),
    ("Blender", "Home", 54.50),
    ("Air Purifier", "Home", 149.99),
    ("Vacuum Cleaner", "Home", 189.00),
    ("Electric Kettle", "Home", 34.99),
    ("Toaster", "Home", 29.99),
    ("Air Fryer", "Home", 99.99),
    ("Robot Vacuum", "Home", 279.00),
    ("Humidifier", "Home", 44.99),
    ("Space Heater", "Home", 59.99),
    ("Cast Iron Skillet", "Home", 39.99),
    ("Knife Set", "Home", 79.99),
    ("Cutting Board", "Home", 19.99),
    ("Dish Rack", "Home", 24.99),
    ("Storage Bins Set", "Home", 34.99),
    ("Throw Blanket", "Home", 29.99),
    ("Scented Candle Set", "Home", 22.99),
    ("Wall Clock", "Home", 27.99),
    ("Blackout Curtains", "Home", 44.99),
    ("Bath Towel Set", "Home", 32.99),
]

ORDER_STATUSES = ["completed", "shipped", "pending", "cancelled"]
ORDER_STATUS_WEIGHTS = [0.55, 0.2, 0.15, 0.1]

NUM_CUSTOMERS = 120
NUM_ORDERS = 300


def _already_seeded(session) -> bool:
    return session.query(Customer).count() > 0


def _build_customers(rng: random.Random) -> list[Customer]:
    customers = []
    for i in range(NUM_CUSTOMERS):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        signup_offset_days = rng.randint(30, 900)
        customers.append(
            Customer(
                name=name,
                country=rng.choice(COUNTRIES),
                signup_date=REFERENCE_DATE - datetime.timedelta(days=signup_offset_days),
            )
        )
    return customers


def _build_products() -> list[Product]:
    return [
        Product(name=name, category=category, price=price)
        for name, category, price in PRODUCTS
    ]


def _build_orders_with_items_and_payments(
    rng: random.Random, customers: list[Customer], products: list[Product]
) -> tuple[list[Order], list[OrderItem], list[Payment]]:
    orders = []
    order_items = []
    payments = []

    for i in range(NUM_ORDERS):
        customer = rng.choice(customers)
        order_offset_days = rng.randint(0, 365)
        order_date = REFERENCE_DATE - datetime.timedelta(days=order_offset_days)
        status = rng.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS, k=1)[0]

        order = Order(customer=customer, order_date=order_date, status=status)
        orders.append(order)

        num_items = rng.randint(1, 4)
        chosen_products = rng.sample(products, k=min(num_items, len(products)))
        order_total = 0.0

        for product in chosen_products:
            quantity = rng.randint(1, 3)
            item = OrderItem(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )
            order_items.append(item)
            order_total += float(product.price) * quantity

        if status in ("completed", "shipped"):
            paid_offset_days = rng.randint(0, 5)
            payments.append(
                Payment(
                    order=order,
                    amount=round(order_total, 2),
                    paid_date=order_date + datetime.timedelta(days=paid_offset_days),
                )
            )

    return orders, order_items, payments


def seed() -> None:
    session = get_writer_session()
    try:
        if _already_seeded(session):
            logger.info("database already seeded, skipping")
            return

        rng = random.Random(SEED)

        customers = _build_customers(rng)
        products = _build_products()
        session.add_all(customers)
        session.add_all(products)
        session.flush()

        orders, order_items, payments = _build_orders_with_items_and_payments(
            rng, customers, products
        )
        session.add_all(orders)
        session.add_all(order_items)
        session.add_all(payments)

        session.commit()
        logger.info(
            "seeded %d customers, %d products, %d orders, %d order_items, %d payments",
            len(customers),
            len(products),
            len(orders),
            len(order_items),
            len(payments),
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    from reflex.config import settings

    configure_logging(settings.log_level)
    seed()
