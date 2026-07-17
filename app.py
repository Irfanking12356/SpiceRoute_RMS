"""
Restaurant Management System (RMS) - Flask prototype
Modules: Table Management, Order Management, Kitchen Display, Billing, Menu & Inventory
"""
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rms.db"
app.config["SECRET_KEY"] = "dev-secret-key-change-me"
db = SQLAlchemy(app)

TAX_RATE = 0.05  # 5% tax

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, default=4)
    status = db.Column(db.String(20), default="available")
    # available -> ordering -> kitchen -> ready -> billing -> available

    orders = db.relationship("Order", backref="table", lazy=True)


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default="Main")
    price = db.Column(db.Float, nullable=False)
    stock_qty = db.Column(db.Integer, default=100)
    available = db.Column(db.Boolean, default=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("table.id"), nullable=False)
    status = db.Column(db.String(20), default="open")
    # open -> sent_to_kitchen -> ready -> billed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")

    @property
    def subtotal(self):
        return sum(i.price_at_order * i.quantity for i in self.items)

    @property
    def tax(self):
        return round(self.subtotal * TAX_RATE, 2)

    @property
    def total(self):
        return round(self.subtotal + self.tax, 2)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price_at_order = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="pending")
    # pending -> preparing -> ready

    menu_item = db.relationship("MenuItem")


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_data():
    if Table.query.count() == 0:
        for n in range(1, 9):
            db.session.add(Table(number=n, capacity=4 if n % 2 else 2))
    if MenuItem.query.count() == 0:
        items = [
            ("Paneer Tikka", "Starter", 220, 40),
            ("Veg Spring Roll", "Starter", 180, 40),
            ("Butter Chicken", "Main", 320, 30),
            ("Dal Makhani", "Main", 240, 40),
            ("Veg Biryani", "Main", 260, 30),
            ("Garlic Naan", "Bread", 60, 100),
            ("Butter Roti", "Bread", 30, 100),
            ("Gulab Jamun", "Dessert", 90, 50),
            ("Cold Coffee", "Beverage", 120, 60),
            ("Masala Papad", "Starter", 70, 50),
        ]
        for name, cat, price, stock in items:
            db.session.add(MenuItem(name=name, category=cat, price=price, stock_qty=stock))
    db.session.commit()


# ---------------------------------------------------------------------------
# Table Management
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    tables = Table.query.order_by(Table.number).all()
    return render_template("tables.html", tables=tables)


@app.route("/table/<int:table_id>/seat", methods=["POST"])
def seat_table(table_id):
    table = Table.query.get_or_404(table_id)
    if table.status != "available":
        flash(f"Table {table.number} is not available.", "error")
        return redirect(url_for("dashboard"))
    order = Order(table_id=table.id, status="open")
    table.status = "ordering"
    db.session.add(order)
    db.session.commit()
    return redirect(url_for("build_order", order_id=order.id))


@app.route("/table/<int:table_id>/free", methods=["POST"])
def free_table(table_id):
    table = Table.query.get_or_404(table_id)
    table.status = "available"
    db.session.commit()
    flash(f"Table {table.number} is now available.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Order Management
# ---------------------------------------------------------------------------

@app.route("/order/<int:order_id>")
def build_order(order_id):
    order = Order.query.get_or_404(order_id)
    menu_by_category = {}
    for item in MenuItem.query.filter_by(available=True).order_by(MenuItem.category, MenuItem.name):
        menu_by_category.setdefault(item.category, []).append(item)
    return render_template("order.html", order=order, menu_by_category=menu_by_category)


@app.route("/order/<int:order_id>/add", methods=["POST"])
def add_item(order_id):
    order = Order.query.get_or_404(order_id)
    menu_item_id = int(request.form["menu_item_id"])
    qty = int(request.form.get("qty", 1))
    menu_item = MenuItem.query.get_or_404(menu_item_id)

    existing = OrderItem.query.filter_by(order_id=order.id, menu_item_id=menu_item_id, status="pending").first()
    if existing:
        existing.quantity += qty
    else:
        db.session.add(OrderItem(
            order_id=order.id,
            menu_item_id=menu_item_id,
            quantity=qty,
            price_at_order=menu_item.price,
        ))
    db.session.commit()
    return redirect(url_for("build_order", order_id=order.id))


@app.route("/order/<int:order_id>/item/<int:item_id>/remove", methods=["POST"])
def remove_item(order_id, item_id):
    item = OrderItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("build_order", order_id=order_id))


@app.route("/order/<int:order_id>/submit", methods=["POST"])
def submit_order(order_id):
    order = Order.query.get_or_404(order_id)
    if not order.items:
        flash("Add at least one item before sending to kitchen.", "error")
        return redirect(url_for("build_order", order_id=order.id))
    order.status = "sent_to_kitchen"
    order.table.status = "kitchen"
    for item in order.items:
        if item.status == "pending":
            item.status = "queued"
    db.session.commit()
    flash("Order sent to kitchen!", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Kitchen Display
# ---------------------------------------------------------------------------

@app.route("/kitchen")
def kitchen():
    orders = Order.query.filter(Order.status.in_(["sent_to_kitchen"])).order_by(Order.created_at).all()
    return render_template("kitchen.html", orders=orders)


@app.route("/kitchen/item/<int:item_id>/status", methods=["POST"])
def update_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    new_status = request.form["status"]
    item.status = new_status
    db.session.commit()

    order = item.order
    if order.items and all(i.status == "ready" for i in order.items):
        order.status = "ready"
        order.table.status = "ready"
        db.session.commit()

    return redirect(url_for("kitchen"))


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@app.route("/billing")
def billing_list():
    orders = Order.query.filter(Order.status.in_(["ready", "sent_to_kitchen"])).order_by(Order.created_at).all()
    return render_template("billing_list.html", orders=orders)


@app.route("/billing/<int:order_id>")
def bill(order_id):
    order = Order.query.get_or_404(order_id)
    order.table.status = "billing"
    db.session.commit()
    return render_template("bill.html", order=order, tax_rate=TAX_RATE)


@app.route("/billing/<int:order_id>/pay", methods=["POST"])
def pay(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = "billed"
    order.table.status = "available"
    db.session.commit()
    flash(f"Payment received for Table {order.table.number}. Total: Rs.{order.total}", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Menu & Inventory Management
# ---------------------------------------------------------------------------

@app.route("/menu")
def menu_list():
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.name).all()
    return render_template("menu.html", items=items)


@app.route("/menu/add", methods=["POST"])
def menu_add():
    name = request.form["name"].strip()
    category = request.form["category"].strip() or "Main"
    price = float(request.form["price"])
    stock_qty = int(request.form.get("stock_qty", 0) or 0)
    if name:
        db.session.add(MenuItem(name=name, category=category, price=price, stock_qty=stock_qty))
        db.session.commit()
        flash(f"Added '{name}' to menu.", "success")
    return redirect(url_for("menu_list"))


@app.route("/menu/<int:item_id>/edit", methods=["POST"])
def menu_edit(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.name = request.form["name"].strip()
    item.category = request.form["category"].strip() or "Main"
    item.price = float(request.form["price"])
    item.stock_qty = int(request.form.get("stock_qty", 0) or 0)
    item.available = "available" in request.form
    db.session.commit()
    flash(f"Updated '{item.name}'.", "success")
    return redirect(url_for("menu_list"))


@app.route("/menu/<int:item_id>/delete", methods=["POST"])
def menu_delete(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from menu.", "success")
    return redirect(url_for("menu_list"))


# ---------------------------------------------------------------------------
# Reports (daily sales history)
# ---------------------------------------------------------------------------

@app.route("/reports")
def reports():
    billed_orders = Order.query.filter_by(status="billed").order_by(Order.created_at.desc()).all()
    total_sales = sum(o.total for o in billed_orders)
    return render_template("reports.html", orders=billed_orders, total_sales=round(total_sales, 2))


# ---------------------------------------------------------------------------
# Bootstrap DB
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
