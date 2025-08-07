import sqlite3
import os

# from backend.models import OrderItem
print("Connected DB path:", os.path.abspath("users.db"))
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required, verify_jwt_in_request, get_jwt, unset_jwt_cookies
from flask_migrate import Migrate
from datetime import timedelta
from sqlalchemy import asc, desc
from extensions import db
from models import Product, Customer, Order, User
import random
import string
from models import Product  # ensure this imports your Product model
# from backend import db  

bcrypt = Bcrypt()
jwt = JWTManager()
migrate = Migrate()
cors = CORS()

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), '../templates'),
            static_folder=os.path.join(os.path.dirname(__file__), '../static'))

basedir = os.path.abspath(os.path.dirname(__file__))

# Configuration
app.config['SECRET_KEY'] = 'super-secret'
app.config['JWT_SECRET_KEY'] = 'super-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_COOKIE_SECURE'] = False  # Change to True in prod
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

# Initialize extensions with app
db.init_app(app)
bcrypt.init_app(app)
jwt.init_app(app)
migrate.init_app(app, db)
cors.init_app(app)

if not os.path.exists('users.db'):
    with app.app_context():
        db.create_all()

with app.app_context():
    db.create_all()  # Create tables if not exist
    print(Customer.query.all())
    # Check if admin exists
    admin_email = 'admin123@example.com'
    admin_password = 'admin123'
    existing_admin = User.query.filter_by(email=admin_email, role='admin').first()
    if not existing_admin:
        hashed_pw = bcrypt.generate_password_hash(admin_password).decode('utf-8')
        admin = User(name='Admin', email=admin_email, password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
@app.route('/')
def index():
    user_name = None
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        user_name = claims.get('name')
    except Exception as e:
        featured_products = Product.query.limit(4).all()
        return render_template('index.html', products=featured_products)

    # ✅ Now also return the same for authenticated users
    featured_products = Product.query.limit(4).all()
    return render_template('index.html', products=featured_products, user_name=user_name)


# @app.route('/')
# def index():

#     user_name = None
#     try:
#         print("Verifying JWT in request...")
#         verify_jwt_in_request(optional=True)
#         print("JWT verified!")
        
#         claims = get_jwt()
#         print("Claims:", claims)
        
#         user_name = claims.get('name')
#         print("User name extracted:", user_name)
#     except Exception as e:
#         print("Exception caught:", e)
#         featured_products = Product.query.limit(4).all()
#         return render_template('index.html', products=featured_products)
    # return render_template('index.html', user_name=user_name)

# @app.route('/')
# def home():
#     return render_template('index.html', user_name=session.get('user_name'))


DATABASE = os.path.join(os.path.dirname(__file__), 'users.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# def seed_admin():
#     conn = get_db()
#     cur = conn.cursor()

#     # Debug: list all tables
#     cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
#     tables = [row["name"] for row in cur.fetchall()]
#     print("📦 Tables in DB:", tables)

#     # Fix table name to "user" (not "users")
#     cur.execute("SELECT * FROM user WHERE email = ?", ('admin@example.com',))
#     if not cur.fetchone():
#         password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
#         cur.execute(
#             "INSERT INTO user (email, password,name,  role) VALUES (?, ?, ?, ?)",
#             ('admin@example.com', password, 'Admin', 'admin')
#         )

# seed_admin()



from models import User  # ✅ Ensure this import matches your folder structure

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if not email or not password or not role:
        return render_template('login.html', error="All fields are required.")

    if role == 'admin':
        user = User.query.filter_by(email=email, role='admin').first()
        if user and bcrypt.check_password_hash(user.password, password):
            token = create_access_token(
                identity=user.email,  # must be a string
                additional_claims={
                    'role': user.role,
                    'name': user.name  # Send only first name here
                }
            )
            resp = make_response(redirect(url_for('admin_dashboard')))
            resp.set_cookie('access_token_cookie', token, httponly=True)
            return resp
        return render_template('login.html', error="Invalid admin credentials")

    user = User.query.filter_by(email=email, role='customer').first()
    if user and bcrypt.check_password_hash(user.password, password):
        token = create_access_token(
            identity=user.email,  # must be a string
            additional_claims={
                'role': user.role,
                'name': user.name  # Send only first name here
            }
        )
        resp = make_response(redirect(url_for('customer_dashboard')))
        resp.set_cookie('access_token_cookie', token, httponly=True)
        return resp

    return render_template('login.html', error="Invalid customer credentials")

# routes/admin.py or your main app file

@app.route('/register', methods=['GET'])
def register_form():
    return render_template('register.html')



@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')
    role = 'customer'  # Default to customer

    if not email or not name or not password:
        return jsonify({'msg': 'All fields are required'}), 400

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        # Add to 'user' table
        user = User(name=name, email=email, password=hashed_pw, role=role)
        db.session.add(user)

        # Also add to 'customer' table
        customer = Customer(name=name, email=email, password=hashed_pw)
        db.session.add(customer)

        db.session.commit()
        return jsonify({'msg': 'Customer registered successfully'}), 201

    except Exception as e:
        db.session.rollback()
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'msg': 'Email already exists'}), 409
        return jsonify({'msg': 'Registration failed'}), 500


def debug_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print("🛠 Available tables:", [t[0] for t in tables])

# Call this after get_db()
debug_tables()

@app.route('/customer/dashboard')
@jwt_required()
def customer_dashboard():
    claims = get_jwt()
    if claims['role'] != 'customer':
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM user WHERE email = ?", (claims['sub'],)).fetchone()
    products = Product.query.filter(Product.stock_quantity > 0).all()
    return render_template('customer_dashboard.html', user=user,products=products)



@app.route('/update_profile', methods=['POST'])
@jwt_required()
def update_profile():
    db = get_db()
    claims = get_jwt()
    name = request.form['name']
    email = claims['sub']
    db.execute("UPDATE user SET name = ? WHERE email = ?", (name, email))
    db.commit()
    flash("Profile updated successfully.")
    return redirect(url_for('customer_dashboard'))


@app.route('/change_password', methods=['POST'])
@jwt_required()
def change_password():
    db = get_db()
    claims = get_jwt()
    email = claims['sub']

    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    user = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()

    if not bcrypt.check_password_hash(user['password'], current_password):
        flash("Incorrect current password.")
        return redirect(url_for('customer_dashboard'))

    if new_password != confirm_password:
        flash("New passwords do not match.")
        return redirect(url_for('customer_dashboard'))

    hashed = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.execute("UPDATE user SET password = ? WHERE email = ?", (hashed, email))
    db.commit()
    flash("Password changed successfully.")
    return redirect(url_for('customer_dashboard'))

# @app.route('/update_profile', methods=['POST'])
# @jwt_required()
# def update_profile():
#     claims = get_jwt()
#     if claims['role'] != 'customer':
#         return redirect('/login')

#     name = request.form['name']
#     db = get_db()
#     db.execute("UPDATE user SET name = ? WHERE email = ?", (name, claims['sub']))
#     db.commit()
#     flash("Profile updated.")
#     return redirect(url_for('customer_dashboard'))

# @app.route('/change_password', methods=['POST'])
# @jwt_required()
# def change_password():
#     claims = get_jwt()
#     if claims['role'] != 'customer':
#         return redirect('/login')

#     current = request.form['current_password']
#     new = request.form['new_password']
#     confirm = request.form['confirm_password']

#     if new != confirm:
#         flash("Passwords do not match.")
#         return redirect(url_for('customer_dashboard'))

#     db = get_db()
#     user = db.execute("SELECT * FROM user WHERE email = ?", (claims['sub'],)).fetchone()

#     if not bcrypt.check_password_hash(user['password'], current):
#         flash("Current password is incorrect.")
#         return redirect(url_for('customer_dashboard'))

#     hashed = bcrypt.generate_password_hash(new).decode('utf-8')
#     db.execute("UPDATE user SET password = ? WHERE email = ?", (hashed, claims['sub']))
#     db.commit()
#     flash("Password changed.")
#     return redirect(url_for('customer_dashboard'))

# from models import Product  # Ensure your Product model includes a 'category' and 'image_url' field

# @app.route('/explore')
# def explore():
#     products = Product.query.order_by(Product.name.asc()).all()
#     return render_template('explore.html', products=products)

# @app.route('/explore')
# def explore():
#     conn = sqlite3.connect('users.db')
#     c = conn.cursor()
#     c.execute("SELECT id, name, description, price, image, category FROM product")
#     products = [
#         {
#             "id": row[0],
#             "name": row[1],
#             "description": row[2],
#             "price": row[3],
#             "image": row[4],
#             "category": row[5]
#         } for row in c.fetchall()
#     ]
#     conn.close()
#     return render_template("explore.html", products=products)
from models import Product
import os  # ✅ Add at the top of the file (if not already there)

@app.route("/explore")
def explore():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # current file's folder
    db_path = os.path.join(BASE_DIR, "users.db")  # path to DB inside backend/
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product")
    rows = cursor.fetchall()
    
    products = []
    for row in rows:
        products.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "price": row["price"],
            "image_url": row["image_url"]
        })
        
    print("Fetched products:", products)


    return render_template("explore.html", products=products)


# @app.route("/explore")
# def explore():
#     products = Product.query.all()
#     formatted_products = [
#         {
#             "id": p.id,
#             "title": p.name,
#             "price": p.price,
#             "img": p.image_url,
#             "category": p.category,
#             "dateAdded": "2024-08-01",  # example static date
#             "bestSellingRank": i  # or whatever logic you want
#         }
#         for i, p in enumerate(products)
#     ]
#     return render_template("explor.html", products=formatted_products)
@app.route('/create-view_product-table')
def create_view_product_table():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS view_product (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER,
            image TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return "Products table created!"


@app.route('/insert-test-view_product')
def insert_test_view_product():
    # conn = sqlite3.connect('backend/users.db')
    conn = sqlite3.connect('users.db')

    cursor = conn.cursor()
    products = [
        (2, 'Dark Chocolate Brownie', 'Rich and fudgy brownie with dark chocolate.', 350, 'static/Fudgy_Dark_Chocolate.jpg'),
        (3, 'Fudge Brownie', 'Brownie with crunchy walnut pieces.', 400, 'static/featured_brownie.jpg'),
        (4, 'Nutty Delight', 'Fudgy brownie with caramel swirls.', 420, 'static/Almond_Flour_Chocolate_Brownies.jpg'),
        (5, 'Boozy Brownie Box', 'Brownie with a hint of rum.', 350, 'static/boozy_brownie.webp'),
        (6, 'Roasted Nuts Brownie', 'Brownie with roasted nuts.', 400, 'static/RoastedNutsBrownie.webp'),
        (7, 'Red Velvet Brownie', 'Brownie with red velvet.', 420, 'static/RedVelvetBrownie.webp'),
        (8, 'Choco Hazelnut Spread Brownie', 'Brownie with choco hazelnut spread.', 350, 'static/choco.jpg'),
        (8,'Eggless Choco Hazelnut Spread Brownie', 'Eggless brownie with choco hazelnut spread.', 400, 'static/EgglessChoco.webp'),
        (1,'Brownie Slab', 'Rich and fudgy brownie with dark chocolate.', 700, 'static/BrownieSlab.webp'),
        (9,'Brownie Slab', 'Rich and fudgy brownie with dark chocolate.', 700, 'static/BrownieSlab.webp'),
        (11,'Choco Hazelnut Crunch', 'Rich and fudgy brownie with dark chocolate.', 1150, 'static/crunchhazelnut_600x.jpg'),
        (12,'Heart Unlock Brownie Cake', 'Rich and fudgy brownie with dark chocolate.',400, 'static/heartunlock_600x.jpg'),
        (13,'Nutty Professor Brownie', 'Rich and fudgy brownie with dark chocolate.', 420, 'static/nutty_600x.jpg'),
        (14,'Oreo Brownie', 'Rich and fudgy brownie with dark chocolate.', 350, 'static/OreoBrownie_600x.webp'),
        (15,'Salted Caramel Fudge Brownie', 'Rich and fudgy brownie with dark chocolate.', 400, 'static/SaltedCaramelBrownie_600x.webp'),
        (16,'Triple Chocolate Brownie', 'Rich and fudgy brownie with dark chocolate.', 420, 'static/TripleChocolateBrownie_600x.webp'),
    ]
    for p in products:
        try:
            cursor.execute("INSERT INTO view_product (id, name, description, price, image) VALUES (?, ?, ?, ?, ?)", p)
        except sqlite3.IntegrityError:
            continue  # skip if already inserted
    conn.commit()
    conn.close()
    return "Test products inserted!"

@app.route('/admin/products/test-insert')
def insert_test_products():
    import sqlite3
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    product = [
        (1, 'Dark Chocolate Brownie', 'Rich and fudgy brownie with dark chocolate.', 350, 'static/Fudgy_Dark_Chocolate.jpg','Brownies'),
        (2, 'Fudge Brownie', 'Brownie with crunchy walnut pieces.', 400, 'static/featured_brownie.jpg','Brownies'),
        (3, 'Nutty Delight', 'Fudgy brownie with caramel swirls.', 420, 'static/Almond_Flour_Chocolate_Brownies.jpg','Cakes'),
        (4, 'Boozy Brownie Box', 'Brownie with a hint of rum.', 350, 'static/boozy_brownie.webp','Cakes'),
        (5, 'Roasted Nuts Brownie', 'Brownie with roasted nuts.', 400, 'static/RoastedNutsBrownie.webp','Cakes'),
        (6, 'Red Velvet Brownie', 'Brownie with red velvet.', 420, 'static/RedVelvetBrownie.webp','Brownies'),
        (7, 'Choco Hazelnut Spread Brownie', 'Brownie with choco hazelnut spread.', 350, 'static/choco.jpg','Cakes'),
        (8,'Eggless Choco Hazelnut Spread Brownie', 'Eggless brownie with choco hazelnut spread.', 400, 'static/EgglessChoco.webp','Brownies'),
        (9,'Brownie Slab', 'Rich and fudgy brownie with dark chocolate.', 700, 'static/BrownieSlab.webp','Cakes'),
        (10,'Choco Hazelnut Crunch', 'Rich and fudgy brownie with dark chocolate.', 1150, 'static/crunchhazelnut_600x.jpg','Cakes'),
        (11,'Heart Unlock Brownie Cake', 'Rich and fudgy brownie with dark chocolate.',400, 'static/heartunlock_600x.jpg','Cakes'),
        (12,'Nutty Professor Brownie', 'Rich and fudgy brownie with dark chocolate.', 420, 'static/nutty_600x.jpg','Brownies'),
        (13,'Oreo Brownie', 'Rich and fudgy brownie with dark chocolate.', 350, 'static/OreoBrownie_600x.webp','Brownies'),
        (14,'Salted Caramel Fudge Brownie', 'Rich and fudgy brownie with dark chocolate.', 400, 'static/SaltedCaramelBrownie_600x.webp','Brownies'),
        (15,'Triple Chocolate Brownie', 'Rich and fudgy brownie with dark chocolate.', 420, 'static/TripleChocolateBrownie_600x.webp','Brownies'),
    ]

    for p in product:
        try:
            cursor.execute("""
                INSERT INTO product (id, name, description, price, stock_quantity, image_url, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, p)
        except sqlite3.IntegrityError:
            continue  # skip duplicates

    conn.commit()
    conn.close()
    return "Test products inserted!"


@app.route('/create-product-table')
def create_products_table():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER,
            image TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return "Products table created!"
create_products_table()
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, image FROM view_product WHERE id=?", (product_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        product = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3],
            'image_url': row[4]
        }
        return render_template('product_details.html', product=product)
    else:
        return "Product not found", 404



@app.route('/debug-product')
def debug_products():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product")
    rows = cursor.fetchall()
    conn.close()
    return {"product": rows}

from flask import request
# from flask_sqlalchemy import Pagination
from sqlalchemy import text, asc, desc


# @app.route('/admin/dashboard')
# def admin_dashboard():
#     conn = sqlite3.connect('users.db')
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, name, description, price, stock_quantity, image_url, category FROM product")
#     products = cursor.fetchall()
#     conn.close()
#     return render_template('admin_dashboard.html', products=products)

# Add Product Route
@app.route('/admin/product/add', methods=['POST'])
def add_product():
    data = request.form
    name = data.get("name")
    description = data.get("description")
    price = data.get("price")
    stock_quantity = data.get("stock_quantity")
    image_url = data.get("image_url")
    category = data.get("category")

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO product (name, description, price, stock_quantity, image_url, category)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, description, price, stock_quantity, image_url, category))
    conn.commit()
    conn.close()

    flash('Product added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))
@app.route('/admin/dashboard')
def admin_dashboard():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    direction = request.args.get('direction', 'asc')

    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    column = getattr(Product, sort_by, Product.name)
    query = query.order_by(column.desc() if direction == 'desc' else column.asc())

    pagination = query.paginate(page=page, per_page=10, error_out=False)

    def serialize_product(product):
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock": product.stock_quantity,
            "image_url": product.image_url,
            "category": product.category
        }

    products = [serialize_product(p) for p in pagination.items]
    total_products = Product.query.count()
    total_customers = Customer.query.count()

    customers = Customer.query.all()  # or however you're loading customers

    return render_template(
        'admin_dashboard.html',
        products=products,
        pagination=pagination,
        search=search,
        customers=customers,
        total_products=total_products,
        total_customers=total_customers

    )


@app.route('/admin/products/data')
def get_products_data():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    direction = request.args.get('direction', 'asc')

    query = Product.query

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    if direction == 'asc':
        query = query.order_by(asc(getattr(Product, sort_by)))
    else:
        query = query.order_by(desc(getattr(Product, sort_by)))

    pagination = query.paginate(page=page, per_page=20)
    
    return jsonify({
        'products': [{
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'stock_quantity': p.stock_quantity,
            'description': p.description
        } for p in pagination.items],
        'total_pages': pagination.pages,
        'current_page': pagination.page
    })

# Product List with Pagination, Search, and Sort
@app.route('/admin/product')
def admin_products():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    direction = request.args.get('direction', 'asc')

    customers = db.execute("SELECT * FROM user WHERE role = 'customer'").fetchall()

    query = Product.query

    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    if direction == 'asc':
        query = query.order_by(asc(getattr(Product, sort_by)))
    else:
        query = query.order_by(desc(getattr(Product, sort_by)))

    pagination = query.paginate(page=page, per_page=20)
    return render_template('admin_dashboard.html',customers=customers, products=pagination.items, pagination=pagination, search=search, sort_by=sort_by, direction=direction)


# @app.route('/admin/products/add', methods=['POST'])
# def add_product():
#     name = request.form['name']
#     description = request.form['description']
#     price = float(request.form['price'])
#     stock_quantity = int(request.form['stock_quantity'])
#     category = request.form.get('category', '')
#     image_url = request.form.get('image_url', '')

#     new_product = Product(
#         name=name,
#         description=description,
#         price=price,
#         stock_quantity=stock_quantity,
#         category=category,
#         image_url=image_url
#     )
#     db.session.add(new_product)
#     db.session.commit()

#     flash("Brownie added successfully!", "success")
#     return redirect(url_for('admin_dashboard'))


# @app.route('/admin/products/edit/<int:product_id>', methods=['POST'])
# def edit_product(product_id):
#     product = Product.query.get_or_404(product_id)
#     product.name = request.form['name']
#     product.description = request.form['description']
#     product.price = float(request.form['price'])
#     product.stock_quantity = int(request.form['stock_quantity'])
#     product.category = request.form.get('category', '')
#     product.image_url = request.form.get('image_url', '')
#     db.session.commit()
#     return redirect('/admin')
@app.route('/admin/products/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.stock_quantity = int(request.form['stock_quantity'])
        product.category = request.form.get('category', '')
        product.image_url = request.form.get('image_url', '')

        db.session.commit()
        return redirect('/admin')
    except Exception as e:
        db.session.rollback()
        return f"An error occurred: {str(e)}", 500



# Delete Product
@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted!", "info")
    return redirect(url_for('admin_products'))



@app.route('/admin/customers')
def admin_customers():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')

    query = Customer.query

    if search:
        query = query.filter(
            (Customer.name.ilike(f'%{search}%')) |
            (Customer.email.ilike(f'%{search}%'))
        )

    if status_filter != 'all':
        active_status = True if status_filter == 'active' else False
        query = query.filter(Customer.active == active_status)

    customers = query.all()
    return render_template('customers.html', customers=customers)

@app.route('/admin/customer/<int:customer_id>')
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = Order.query.filter_by(customer_id=customer.id).all()
    return render_template('customer_profile.html', customer=customer, orders=orders)

@app.route('/admin/customer/toggle/<int:customer_id>')
def toggle_customer_status(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.active = not customer.active
    db.session.commit()
    return redirect(url_for('admin_customers'))

@app.route('/admin/customer/delete/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted successfully.')
    return redirect(url_for('admin_customers'))

@app.route('/admin/customer/reset_password/<int:customer_id>', methods=['POST'])
def reset_password(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    customer.password = hashed
    db.session.commit()
    flash(f"Temporary password: {temp_password}")
    return redirect(url_for('view_customer', customer_id=customer_id))

@app.route('/admin/customer/impersonate/<int:customer_id>')
def impersonate_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    session['impersonated_customer_id'] = customer.id
    session['original_admin'] = True
    return redirect('/customer/dashboard')  # Assume you have customer dashboard

@app.route('/admin/stop_impersonation')
def stop_impersonation():
    session.pop('impersonated_customer_id', None)
    session.pop('original_admin', None)
    return redirect('/admin/dashboard')


@app.route('/admin/orders')
def admin_orders():
    orders = Order.query.all()  # Assuming you have an Order model
    return render_template('orders.html')

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))  # Redirect to homepage or wherever you want
    unset_jwt_cookies(response)  # Clear the JWT cookies
    return response


@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if request.method == 'POST':
        html_content = request.form.get('editor_html')
        print("Received HTML content from Quill Editor:\n", html_content)
        # TODO: Save to DB if needed
        return redirect(url_for('admin_settings'))

    return render_template('settings.html')



@app.route('/place-order', methods=['POST'])
def place_order():
    email = request.form['email']
    first_name = request.form['first_name']
    last_name = request.form['last_name']

    # Calculate totals again from cart
    total = 0
    order_items = []
    for product_id, data in cart.items():
        product = Product.query.get(product_id)
        quantity = data['quantity']
        subtotal = product.price * quantity
        total += subtotal

        order_items.append((product.id, quantity, subtotal))

    # Save customer (if not exists)
    customer = Customer.query.filter_by(email=email).first()
    if not customer:
        customer = Customer(email=email, first_name=first_name, last_name=last_name)
        db.session.add(customer)
        db.session.commit()

    # Save order
    order = Order(customer_email=email, total=total)
    db.session.add(order)
    db.session.commit()

    # Save order items
    for pid, qty, sub in order_items:
        item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, subtotal=sub)
        db.session.add(item)

        # Decrement stock
        product = Product.query.get(pid)
        product.stock -= qty

    db.session.commit()

    flash("Order placed successfully!", "success")
    return redirect(url_for('checkout'))

@app.route('/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', {})

    if str(product_id) in cart:
        cart[str(product_id)] += 1
    else:
        cart[str(product_id)] = 1

    session['cart'] = cart
    return redirect(url_for('checkout'))
@app.route('/checkout')
def checkout():
    cart = session.get('cart', {})
    items = []
    total = 0

    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        subtotal = product.price * qty
        items.append({'product': product, 'quantity': qty, 'subtotal': subtotal})
        total += subtotal

    discount = 0
    tax = round(0.05 * total, 2)
    grand_total = total - discount + tax

    return render_template('card.html', items=items, total=total, discount=discount, tax=tax, grand_total=grand_total)




# TEMP: Drop and recreate all tables (only for development)
# with app.app_context():
#     from models import db
#     db.drop_all()
#     db.create_all()
#     print("✅ Dropped and recreated all tables.")


if __name__ == '__main__':
    
    app.run(debug=True)