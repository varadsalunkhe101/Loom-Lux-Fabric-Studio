import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, session, flash, redirect, url_for
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "rightfabricssecret"


# ==============================================================================
# 01. PUBLIC USER ROUTES (Home, Products, Categories, & Contact)
# ==============================================================================

@app.route("/")
def home():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Categories
    cursor.execute("""
        SELECT *
        FROM categories
        WHERE status='Active'
        ORDER BY category_name
    """)
    categories = cursor.fetchall()

    # New Arrivals (Latest 4)
    cursor.execute("""
        SELECT
            p.*,
            c.category_name
        FROM products p
        INNER JOIN categories c
            ON p.category_id=c.category_id
        WHERE p.is_new_arrival=1
          AND p.status='Available'
        ORDER BY p.product_id DESC
        LIMIT 4
    """)
    new_arrivals = cursor.fetchall()

    # Latest Products
    cursor.execute("""
        SELECT
            p.*,
            c.category_name
        FROM products p
        INNER JOIN categories c
            ON p.category_id=c.category_id
        WHERE p.status='Available'
        ORDER BY p.product_id DESC
        LIMIT 8
    """)
    latest_products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "index.html",
        categories=categories,
        new_arrivals=new_arrivals,
        latest_products=latest_products,
    )


@app.route("/new-arrivals")
def new_arrivals():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        p.*,
        c.category_name
    FROM products p
    INNER JOIN categories c
        ON p.category_id = c.category_id
    WHERE p.is_new_arrival = 1
      AND p.status = 'Available'
    ORDER BY p.product_id DESC
    """

    cursor.execute(query)
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "new-arrivals.html",
        products=products
    )


@app.route("/category/<int:category_id>")
def category(category_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get Category Details
    cursor.execute("""
        SELECT *
        FROM categories
        WHERE category_id=%s
        AND status='Active'
    """, (category_id,))

    category = cursor.fetchone()

    if not category:
        cursor.close()
        connection.close()

        flash("Category Not Found!", "danger")
        return redirect(url_for("home"))

    # Get Products
    cursor.execute("""
        SELECT
            p.*,
            c.category_name
        FROM products p
        INNER JOIN categories c
            ON p.category_id = c.category_id
        WHERE p.category_id=%s
        AND p.status='Available'
        ORDER BY p.product_id DESC
    """, (category_id,))

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "category.html",
        category=category,
        products=products
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        subject = request.form["subject"]
        message = request.form["message"]

        query = """
        INSERT INTO contact_messages
        (
            full_name,
            email,
            phone,
            subject,
            message
        )
        VALUES
        (%s,%s,%s,%s,%s)
        """

        cursor.execute(
            query,
            (
                full_name,
                email,
                phone,
                subject,
                message
            )
        )

        connection.commit()

        flash(
            "Message sent successfully! We will contact you soon.",
            "success"
        )

        cursor.close()
        connection.close()

        return redirect(url_for("contact"))

    cursor.close()
    connection.close()

    return render_template("contact.html")


# ==============================================================================
# 02. AUTHENTICATION ROUTES (Login, Logout, & Session Management)
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        email = request.form["username"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT * FROM admins
            WHERE email=%s AND password=%s
        """

        cursor.execute(query, (email, password))
        admin = cursor.fetchone()

        cursor.close()
        connection.close()

        if admin:
            session["admin"] = admin["full_name"]
            return redirect(url_for("admin_dashboard"))

        flash("Invalid Email or Password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("account"))


# ==============================================================================
# 03. CUSTOMER ORDER FLOW (Checkout / Order Placement)
# ==============================================================================

@app.route("/order", methods=["GET", "POST"])
def order():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        category_id = request.form["category_id"]
        product_id = request.form["product_id"]
        quantity = request.form["quantity"]
        address = request.form["address"]
        utr_number = request.form["utr_number"]
        message = request.form["message"]

        insert_query = """
        INSERT INTO orders
        (
            customer_name,
            customer_phone,
            customer_email,
            category_id,
            product_id,
            quantity,
            delivery_address,
            utr_number,
            additional_requirements
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """
        cursor.execute(
            insert_query,
            (
                name,
                phone,
                email,
                category_id,
                product_id,
                quantity,
                address,
                utr_number,
                message
            )
        )
        connection.commit()
        flash("Order Submitted Successfully!", "success")

        cursor.close()
        connection.close()

        return redirect(url_for("order"))

    # Load Categories for the form dropdown
    cursor.execute("""
        SELECT
            category_id,
            category_name
        FROM categories
        WHERE status='Active'
        ORDER BY category_name
    """)
    categories = cursor.fetchall()

    # Load Products for the form dropdown
    cursor.execute("""
        SELECT
            product_id,
            product_name,
            category_id
        FROM products
        WHERE status='Available'
        ORDER BY product_name
    """)
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "order.html",
        categories=categories,
        products=products
    )


@app.route("/view_order/<int:order_id>")
def view_order(order_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            o.*,
            p.product_name,
            c.category_name
        FROM orders o
        INNER JOIN products p
            ON o.product_id = p.product_id
        INNER JOIN categories c
            ON o.category_id = c.category_id
        WHERE o.order_id=%s
    """, (order_id,))

    order = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        "view_order.html",
        order=order
    )


# ==============================================================================
# 04. ADMIN DASHBOARD & METRICS OVERVIEW
# ==============================================================================

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Dashboard Analytical Counts
    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()["total_products"]

    cursor.execute("SELECT COUNT(*) AS total_categories FROM categories")
    total_categories = cursor.fetchone()["total_categories"]

    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()["total_orders"]

    cursor.execute("""
        SELECT COUNT(DISTINCT customer_phone) AS total_customers
        FROM orders
    """)
    total_customers = cursor.fetchone()["total_customers"]

    cursor.execute("SELECT COUNT(*) AS total_messages FROM contact_messages")
    total_messages = cursor.fetchone()["total_messages"]

    # Dashboard Recent Activity Feeds
    cursor.execute("""
        SELECT
            order_id,
            customer_name,
            order_status
        FROM orders
        ORDER BY order_id DESC
        LIMIT 5
    """)
    recent_orders = cursor.fetchall()

    cursor.execute("""
        SELECT
            full_name,
            subject
        FROM contact_messages
        ORDER BY message_id DESC
        LIMIT 5
    """)
    recent_messages = cursor.fetchall()

    cursor.execute("""
        SELECT
            p.product_id,
            p.product_name,
            p.status,
            c.category_name
        FROM products p
        INNER JOIN categories c
            ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
        LIMIT 5
    """)
    latest_products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        total_products=total_products,
        total_categories=total_categories,
        total_orders=total_orders,
        total_customers=total_customers,
        total_messages=total_messages,
        recent_orders=recent_orders,
        recent_messages=recent_messages,
        latest_products=latest_products
    )


# ==============================================================================
# 05. ADMIN MANAGEMENT: PRODUCT CRUD
# ==============================================================================

@app.route("/all_products")
def all_products():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        p.*,
        c.category_name
    FROM products p
    INNER JOIN categories c
    ON p.category_id = c.category_id
    ORDER BY p.product_id DESC
    """

    cursor.execute(query)
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "all_products.html",
        products=products
    )


@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load Active Categories for selection
    cursor.execute("SELECT * FROM categories WHERE status='Active'")
    categories = cursor.fetchall()

    if request.method == "POST":
        product_name = request.form["product_name"]
        category_id = request.form["category_id"]
        price = request.form["price"]
        description = request.form["description"]
        stock = request.form["stock"]
        status = request.form["status"]
        is_new_arrival = request.form["is_new_arrival"]

        # Handle file secure uploading
        image = request.files["product_image"]
        filename = secure_filename(image.filename)
        upload_folder = os.path.join(
            app.root_path,
            "static",
            "uploads",
            "products"
        )
        os.makedirs(upload_folder, exist_ok=True)
        image.save(os.path.join(upload_folder, filename))
        image_path = "uploads/products/" + filename

        query = """
        INSERT INTO products
        (
            category_id,
            product_name,
            price,
            stock,
            description,
            main_image,
            is_new_arrival,
            status
        )
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s)
        """

        cursor.execute(
            query,
            (
                category_id,
                product_name,
                price,
                stock,
                description,
                image_path,
                is_new_arrival,
                status
            )
        )

        connection.commit()
        flash("Product Added Successfully!", "success")
        return redirect(url_for("add_product"))

    cursor.close()
    connection.close()

    return render_template(
        "add_product.html",
        categories=categories
    )


@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        product_name = request.form["product_name"]
        category_id = request.form["category_id"]
        price = request.form["price"]
        description = request.form["description"]
        stock = request.form["stock"]
        status = request.form["status"]
        is_new_arrival = request.form["is_new_arrival"]

        # Check if new image file was selected
        image = request.files.get("product_image")
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            upload_folder = os.path.join(app.root_path, "static", "uploads", "products")
            os.makedirs(upload_folder, exist_ok=True)
            image.save(os.path.join(upload_folder, filename))
            image_path = "uploads/products/" + filename

            cursor.execute("""
                UPDATE products 
                SET category_id=%s, product_name=%s, price=%s, stock=%s, description=%s, main_image=%s, is_new_arrival=%s, status=%s
                WHERE product_id=%s
            """, (category_id, product_name, price, stock, description, image_path, is_new_arrival, status, product_id))
        else:
            cursor.execute("""
                UPDATE products 
                SET category_id=%s, product_name=%s, price=%s, stock=%s, description=%s, is_new_arrival=%s, status=%s
                WHERE product_id=%s
            """, (category_id, product_name, price, stock, description, is_new_arrival, status, product_id))

        connection.commit()
        flash("Product Updated Successfully!", "success")
        cursor.close()
        connection.close()
        return redirect(url_for("all_products"))

    cursor.execute("SELECT * FROM categories WHERE status='Active'")
    categories = cursor.fetchall()

    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    connection.close()
    return render_template("edit_product.html", product=product, categories=categories)


@app.route("/delete_product/<int:product_id>")
def delete_product(product_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM products WHERE product_id=%s",
        (product_id,)
    )

    connection.commit()
    cursor.close()
    connection.close()

    flash("Product Deleted Successfully!", "success")
    return redirect(url_for("all_products"))


# ==============================================================================
# 06. ADMIN MANAGEMENT: CATEGORY CRUD / UNIFIED LIST
# ==============================================================================

@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        category_name = request.form["category_name"]
        description = request.form["description"]
        status = request.form["status"]

        # Handle Image File Uploading
        image = request.files.get("category_image")
        image_path = None

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            upload_folder = os.path.join(app.root_path, "static", "uploads", "categories")
            os.makedirs(upload_folder, exist_ok=True)
            image.save(os.path.join(upload_folder, filename))
            image_path = "uploads/categories/" + filename

        query = """
        INSERT INTO categories
        (category_name, description, category_image, status)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (category_name, description, image_path, status))
        connection.commit()

        flash("Category Added Successfully!", "success")
        return redirect(url_for("add_category"))

    # GET: Fetch all categories for the master management list below
    cursor.execute("""
        SELECT *
        FROM categories
        ORDER BY category_id DESC
    """)
    categories = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "add_category.html",
        categories=categories
    )


@app.route("/edit_category/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        category_name = request.form["category_name"]
        description = request.form["description"]
        status = request.form["status"]

        cursor.execute("""
            UPDATE categories
            SET
                category_name=%s,
                description=%s,
                status=%s
            WHERE category_id=%s
        """, (
            category_name,
            description,
            status,
            category_id
        ))

        connection.commit()
        flash("Category Updated Successfully!", "success")

        cursor.close()
        connection.close()

        return redirect(url_for("add_category"))

    cursor.execute("""
        SELECT *
        FROM categories
        WHERE category_id=%s
    """, (category_id,))

    category = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        "edit_category.html",
        category=category
    )


@app.route("/delete_category/<int:category_id>")
def delete_category(category_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM categories
        WHERE category_id=%s
    """, (category_id,))

    connection.commit()
    cursor.close()
    connection.close()

    flash("Category Deleted Successfully!", "success")
    return redirect(url_for("add_category"))


# ==============================================================================
# 07. ADMIN MANAGEMENT: CAMPAIGNS & SHOWCASES (New Arrivals Feature)
# ==============================================================================

@app.route("/admin_new_arrivals")
def admin_new_arrivals():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        p.*,
        c.category_name
    FROM products p
    INNER JOIN categories c
        ON p.category_id = c.category_id
    WHERE p.is_new_arrival = 1
    ORDER BY p.product_id DESC
    """

    cursor.execute(query)
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_new_arrivals.html",
        products=products
    )


@app.route("/remove_new_arrival/<int:product_id>")
def remove_new_arrival(product_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE products
        SET is_new_arrival = 0
        WHERE product_id = %s
        """,
        (product_id,)
    )

    connection.commit()
    cursor.close()
    connection.close()

    flash("Product removed from New Arrivals!", "success")
    return redirect(url_for("admin_new_arrivals"))


# ==============================================================================
# 08. ADMIN MANAGEMENT: DATA VIEWS (Orders & Customers)
# ==============================================================================

@app.route("/orders")
def orders():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        o.*,
        p.product_name
    FROM orders o
    INNER JOIN products p
        ON o.product_id = p.product_id
    ORDER BY o.order_id DESC
    """

    cursor.execute(query)
    orders = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "orders.html",
        orders=orders
    )


@app.route("/update_order_status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    status = request.form["order_status"]

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE orders
        SET order_status=%s
        WHERE order_id=%s
    """, (status, order_id))

    connection.commit()

    cursor.close()
    connection.close()

    flash("Order status updated successfully!", "success")

    return redirect(url_for("orders"))


@app.route("/customers")
def customers():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        customer_name,
        customer_email,
        customer_phone,
        COUNT(order_id) AS total_orders
    FROM orders
    GROUP BY
        customer_name,
        customer_email,
        customer_phone
    ORDER BY customer_name
    """

    cursor.execute(query)
    customers = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "customers.html",
        customers=customers
    )


# ==============================================================================
# 09. ADMIN MANAGEMENT: INBOUND COMMUNICATIONS & REVIEWS (Messages/Testimonials)
# ==============================================================================
@app.route("/messages")
def messages():
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # All Messages
    cursor.execute("""
        SELECT *
        FROM contact_messages
        ORDER BY message_id DESC
    """)
    messages = cursor.fetchall()

    # Total
    cursor.execute("SELECT COUNT(*) AS total FROM contact_messages")
    total_messages = cursor.fetchone()["total"]

    # Read
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM contact_messages
        WHERE status='Read'
    """)
    read_messages = cursor.fetchone()["total"]

    # Unread
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM contact_messages
        WHERE status='Unread'
    """)
    unread_messages = cursor.fetchone()["total"]

    # Today's Messages
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM contact_messages
        WHERE DATE(created_at)=CURDATE()
    """)
    today_messages = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "messages.html",
        messages=messages,
        total_messages=total_messages,
        read_messages=read_messages,
        unread_messages=unread_messages,
        today_messages=today_messages
    )


@app.route("/view_message/<int:message_id>")
def view_message(message_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Mark as Read
    cursor.execute("""
        UPDATE contact_messages
        SET status='Read'
        WHERE message_id=%s
    """, (message_id,))
    connection.commit()

    # Fetch message
    cursor.execute("""
        SELECT *
        FROM contact_messages
        WHERE message_id=%s
    """, (message_id,))

    message = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        "view_message.html",
        message=message
    )


@app.route("/delete_message/<int:message_id>")
def delete_message(message_id):
    if "admin" not in session:
        return redirect(url_for("account"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM contact_messages WHERE message_id=%s",
        (message_id,)
    )

    connection.commit()
    cursor.close()
    connection.close()

    flash("Message Deleted Successfully!", "success")
    return redirect(url_for("messages"))


# ==============================================================================
# 10. SYSTEM CONFIGURATION & ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    app.run(debug=True)
