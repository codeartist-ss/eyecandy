from flask import Flask, jsonify, request, render_template, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
import sys

app = Flask(__name__)
CORS(app)

SECRET_KEY = os.environ.get('SECRET_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not SECRET_KEY:
    sys.exit('SECRET_KEY environment variable is not set. Refusing to start.')
if not DATABASE_URL:
    sys.exit('DATABASE_URL environment variable is not set. Refusing to start.')

app.secret_key = SECRET_KEY

DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'


def get_db():
    return psycopg2.connect(DATABASE_URL)


def query(sql, params=(), one=False):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    result = cur.fetchone() if one else cur.fetchall()
    conn.close()
    return result


def execute(sql, params=(), returning=None):
    """Run an INSERT/UPDATE/DELETE. If `returning` is truthy, sql must include
    a RETURNING clause; the first column of the first row is returned."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = None
    if returning:
        row = cur.fetchone()
        result = row[0] if row else None
    conn.commit()
    conn.close()
    return result

# ── Frontend ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

# ── Items ─────────────────────────────────────────────────────────────────────

@app.route('/api/items', methods=['GET'])
def get_items():
    search = request.args.get('search', '')
    gender = request.args.get('gender', '')
    category = request.args.get('category', '')

    sql = """
        SELECT ci.item_id, ci.title, ci.price, ci.brand, ci.gender, ci.buy_link,
               c.name AS category, s.store_name AS seller,
               img.image_url AS primary_image
        FROM clothing_item ci
        JOIN seller s ON ci.seller_id = s.seller_id
        JOIN category c ON ci.category_id = c.category_id
        LEFT JOIN item_image img ON img.item_id = ci.item_id AND img.is_primary = true
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (ci.title ILIKE %s OR ci.brand ILIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if gender:
        sql += " AND ci.gender = %s"
        params.append(gender)
    if category:
        sql += " AND c.name = %s"
        params.append(category)
    sql += " ORDER BY ci.uploaded_at DESC"
    return jsonify(query(sql, params))

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    item = query("""
        SELECT ci.*, c.name AS category, s.store_name AS seller
        FROM clothing_item ci
        JOIN seller s ON ci.seller_id = s.seller_id
        JOIN category c ON ci.category_id = c.category_id
        WHERE ci.item_id = %s
    """, (item_id,), one=True)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    item['images'] = query("SELECT image_url, is_primary FROM item_image WHERE item_id = %s", (item_id,))
    item['likes'] = query("SELECT COUNT(*) AS total FROM likes WHERE item_id = %s", (item_id,), one=True)['total']
    item['comments'] = query("""
        SELECT u.name, c.content, c.posted_at
        FROM comment c JOIN app_user u ON u.user_id = c.user_id
        WHERE c.item_id = %s ORDER BY c.posted_at ASC
    """, (item_id,))
    return jsonify(item)

@app.route('/api/items', methods=['POST'])
def create_item():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO clothing_item (seller_id, category_id, title, description, price, brand, gender, buy_link)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING item_id
        """, (d['seller_id'], d['category_id'], d['title'], d.get('description'),
              d['price'], d.get('brand'), d.get('gender', 'women'), d['buy_link']))
        item_id = cur.fetchone()[0]
        if d.get('image_url'):
            cur.execute("INSERT INTO item_image (item_id, image_url, is_primary) VALUES (%s,%s,true)",
                        (item_id, d['image_url']))
        conn.commit()
        return jsonify({'item_id': item_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

# ── Categories ────────────────────────────────────────────────────────────────

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify(query("SELECT * FROM category ORDER BY name"))

# ── Users ─────────────────────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(query("SELECT user_id, name, email, role, bio, joined_at FROM app_user"))

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    profile = query("""
        SELECT name, email, role, bio, joined_at FROM app_user WHERE user_id = %s
    """, (user_id,), one=True)
    if not profile:
        return jsonify({'error': 'Not found'}), 404

    closet = query("""
        SELECT COUNT(cl.closet_item_id) AS total_items_in_closet
        FROM board b
        JOIN closet_item cl ON cl.board_id = b.board_id
        WHERE b.user_id = %s AND b.board_type = 'closet'
    """, (user_id,), one=True)

    boards = query("""
        SELECT b.name AS board_name, COUNT(bi.item_id) AS items_saved
        FROM board b
        LEFT JOIN board_item bi ON bi.board_id = b.board_id
        WHERE b.user_id = %s AND b.board_type = 'wishlist' AND b.is_private = false
        GROUP BY b.board_id, b.name
    """, (user_id,))

    return jsonify({
        'profile': profile,
        'closet_count': closet['total_items_in_closet'] if closet else 0,
        'boards': boards
    })

# ── Authentication ────────────────────────────────────────────────────────────

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    d = request.json or {}
    name = d.get('name')
    email = d.get('email')
    password = d.get('password')
    role = d.get('role', 'buyer')

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400
    if role not in ('buyer', 'seller', 'both'):
        return jsonify({'error': 'Invalid role'}), 400

    existing = query("SELECT user_id FROM app_user WHERE email = %s", (email,), one=True)
    if existing:
        return jsonify({'error': 'An account with that email already exists'}), 409

    password_hash = generate_password_hash(password)

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO app_user (name, email, password_hash, role)
            VALUES (%s,%s,%s,%s)
            RETURNING user_id
        """, (name, email, password_hash, role))
        user_id = cur.fetchone()[0]

        if role in ('buyer', 'both'):
            cur.execute("INSERT INTO buyer (user_id) VALUES (%s)", (user_id,))
            cur.execute("""
                INSERT INTO board (user_id, name, board_type, is_private)
                VALUES (%s, 'my closet', 'closet', false)
            """, (user_id,))
        if role in ('seller', 'both'):
            cur.execute("INSERT INTO seller (user_id, store_name) VALUES (%s,%s)", (user_id, f"{name}'s store"))

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

    session['user_id'] = user_id
    session['user_name'] = name
    session['user_role'] = role

    return jsonify({'user_id': user_id, 'name': name, 'email': email, 'role': role}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.json or {}
    email = d.get('email')
    password = d.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    user = query("""
        SELECT user_id, name, email, role, password_hash FROM app_user WHERE email = %s
    """, (email,), one=True)

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_role'] = user['role']

    return jsonify({
        'user_id': user['user_id'],
        'name': user['name'],
        'email': user['email'],
        'role': user['role']
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'logged_out': True}), 200

@app.route('/api/auth/current-user', methods=['GET'])
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'user': None}), 200

    user = query("""
        SELECT user_id, name, email, role FROM app_user WHERE user_id = %s
    """, (session['user_id'],), one=True)

    return jsonify({'user': user}), 200

# ── Boards ────────────────────────────────────────────────────────────────────

@app.route('/api/boards', methods=['GET'])
def get_boards():
    user_id = request.args.get('user_id')
    sql = """
        SELECT b.board_id, b.name, b.board_type, b.is_private,
               u.name AS owner, COUNT(bi.item_id) AS item_count
        FROM board b
        JOIN app_user u ON b.user_id = u.user_id
        LEFT JOIN board_item bi ON bi.board_id = b.board_id
        WHERE b.is_private = false
    """
    params = []
    if user_id:
        sql = sql.replace("WHERE b.is_private = false", "WHERE b.user_id = %s")
        params.append(user_id)
    sql += " GROUP BY b.board_id, b.name, b.board_type, b.is_private, u.name ORDER BY b.created_at DESC"
    return jsonify(query(sql, params))

@app.route('/api/boards', methods=['POST'])
def create_board():
    d = request.json
    bid = execute("""
        INSERT INTO board (user_id, name, board_type, is_private)
        VALUES (%s,%s,%s,%s)
        RETURNING board_id
    """, (d['user_id'], d['name'], d.get('board_type', 'wishlist'), d.get('is_private', False)), returning=True)
    return jsonify({'board_id': bid}), 201

@app.route('/api/boards/<int:board_id>', methods=['DELETE'])
def delete_board(board_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM board WHERE board_id = %s AND board_type = 'wishlist'", (board_id,))
        conn.commit()
        return jsonify({'deleted': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/boards/<int:board_id>/items', methods=['GET'])
def get_board_items(board_id):
    return jsonify(query("""
        SELECT ci.item_id, ci.title, ci.price, ci.brand,
               img.image_url AS primary_image
        FROM board_item bi
        JOIN clothing_item ci ON ci.item_id = bi.item_id
        LEFT JOIN item_image img ON img.item_id = ci.item_id AND img.is_primary = true
        WHERE bi.board_id = %s
    """, (board_id,)))

@app.route('/api/boards/<int:board_id>/items', methods=['POST'])
def add_to_board(board_id):
    item_id = request.json.get('item_id')
    try:
        execute("INSERT INTO board_item (board_id, item_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (board_id, item_id))
        return jsonify({'added': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Orders ────────────────────────────────────────────────────────────────────

@app.route('/api/orders', methods=['GET'])
def get_orders():
    buyer_id = request.args.get('buyer_id')
    sql = """
        SELECT o.order_id, o.size, o.quantity, o.status, o.ordered_at,
               ci.title AS item_title, ci.price,
               u.name AS buyer_name
        FROM orders o
        JOIN clothing_item ci ON ci.item_id = o.item_id
        JOIN buyer b ON b.buyer_id = o.buyer_id
        JOIN app_user u ON u.user_id = b.user_id
    """
    params = []
    if buyer_id:
        sql += " WHERE o.buyer_id = %s"
        params.append(buyer_id)
    sql += " ORDER BY o.ordered_at DESC"
    return jsonify(query(sql, params))

@app.route('/api/orders', methods=['POST'])
def place_order():
    d = request.json
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO orders (buyer_id, item_id, size, quantity, status)
            VALUES (%s,%s,%s,%s,'pending')
            RETURNING order_id
        """, (d['buyer_id'], d['item_id'], d.get('size'), d.get('quantity', 1)))
        order_id = cur.fetchone()['order_id']

        cur.execute("""
            SELECT board_id FROM board
            WHERE user_id = (SELECT user_id FROM buyer WHERE buyer_id = %s)
              AND board_type = 'closet' LIMIT 1
        """, (d['buyer_id'],))
        board = cur.fetchone()
        if board:
            cur.execute("SELECT buy_link FROM clothing_item WHERE item_id=%s", (d['item_id'],))
            item = cur.fetchone()
            cur.execute("""
                INSERT INTO closet_item (board_id, item_id, store_link, purchased_at, notes)
                VALUES (%s,%s,%s,CURRENT_DATE,'purchased via eyecandy')
            """, (board['board_id'], d['item_id'], item['buy_link']))
        conn.commit()
        return jsonify({'order_id': order_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    status = request.json.get('status')
    valid = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
    if status not in valid:
        return jsonify({'error': 'Invalid status'}), 400
    execute("UPDATE orders SET status=%s WHERE order_id=%s", (status, order_id))
    return jsonify({'updated': True})

# ── Likes & Comments ──────────────────────────────────────────────────────────

@app.route('/api/items/<int:item_id>/like', methods=['POST'])
def like_item(item_id):
    user_id = request.json.get('user_id')
    try:
        execute("INSERT INTO likes (user_id, item_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user_id, item_id))
        return jsonify({'liked': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/items/<int:item_id>/comment', methods=['POST'])
def post_comment(item_id):
    d = request.json
    execute("INSERT INTO comment (user_id, item_id, content) VALUES (%s,%s,%s)",
            (d['user_id'], item_id, d['content']))
    return jsonify({'posted': True}), 201

# ── Analytics ─────────────────────────────────────────────────────────────────

@app.route('/api/analytics/top-items', methods=['GET'])
def top_items():
    return jsonify(query("""
        SELECT ci.title, ci.brand, COUNT(l.like_id) AS total_likes
        FROM clothing_item ci
        JOIN likes l ON l.item_id = ci.item_id
        GROUP BY ci.item_id, ci.title, ci.brand
        ORDER BY total_likes DESC LIMIT 5
    """))

@app.route('/api/analytics/seller-performance', methods=['GET'])
def seller_performance():
    return jsonify(query("""
        SELECT s.store_name,
               COUNT(DISTINCT ci.item_id) AS items_listed,
               COUNT(o.order_id) AS total_orders,
               COALESCE(SUM(ci.price * o.quantity), 0) AS total_revenue
        FROM seller s
        JOIN clothing_item ci ON ci.seller_id = s.seller_id
        LEFT JOIN orders o ON o.item_id = ci.item_id AND o.status != 'cancelled'
        GROUP BY s.seller_id, s.store_name
        ORDER BY total_revenue DESC
    """))

@app.route('/api/analytics/wishlist-never-ordered', methods=['GET'])
def wishlist_never_ordered():
    return jsonify(query("""
        SELECT ci.title, ci.brand, COUNT(bi.board_id) AS times_wishlisted
        FROM clothing_item ci
        JOIN board_item bi ON bi.item_id = ci.item_id
        LEFT JOIN orders o ON o.item_id = ci.item_id
        WHERE o.order_id IS NULL
        GROUP BY ci.item_id, ci.title, ci.brand
        HAVING COUNT(bi.board_id) > 0
        ORDER BY times_wishlisted DESC
    """))

if __name__ == '__main__':
    app.run(debug=DEBUG, port=5000)
