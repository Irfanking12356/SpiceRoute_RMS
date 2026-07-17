# SpiceRoute RMS — Restaurant Management System (Prototype)

A Flask + SQLite prototype covering the modules from your lab manual:

- **Table Management** — live status per table (Available → Ordering → Kitchen → Ready → Billing)
- **Order Management** — waitstaff build an order against a table, sent instantly to the kitchen
- **Kitchen Display** — live ticket queue; kitchen staff mark items Preparing / Ready
- **Billing** — auto-computed subtotal, 5% tax, total; mark bills paid
- **Menu & Inventory** — add/edit/delete menu items, categories, prices, stock quantity
- **Reports** — daily sales history of settled bills

## Setup

```bash
cd rms
pip install flask flask_sqlalchemy
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The database (`instance/rms.db`) is created automatically on first run, pre-seeded with 8 tables and a sample menu (Indian restaurant items — feel free to edit via the Menu page or in `seed_data()` in `app.py`).

## Typical flow to try

1. **Tables** page → click *Seat Guests* on any available table.
2. You're taken to the **Order** screen → add menu items, adjust quantity, then *Send to Kitchen*.
3. **Kitchen** page → click *Start* then *Ready* on each ticket item.
4. Back on **Tables**, the table turns "Ready" → click *Generate Bill*.
5. **Billing** page shows subtotal/tax/total → click *Mark as Paid*. Table frees up automatically.
6. **Reports** page shows the settled sale.

## Project structure

```
rms/
├── app.py                # Flask app: models, routes, business logic
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── tables.html
│   ├── order.html
│   ├── kitchen.html
│   ├── billing_list.html
│   ├── bill.html
│   ├── menu.html
│   └── reports.html
└── static/
    └── style.css
```

## Notes / extending it

- Tax rate is a constant (`TAX_RATE = 0.05`) in `app.py` — change it there.
- This is a single-process prototype (matches the "Activity 5: Implementation" deliverable in PR2) — for production you'd add authentication/roles per stakeholder (waiter, kitchen, manager), a real database (MySQL/Postgres), and payment gateway integration as called out in the Secondary Objectives.
- To reset all data, stop the server and delete `instance/rms.db`.
