import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required

products_bp = Blueprint('products', __name__)

# 卖家添加产品
@products_bp.route('/products', methods=['POST'])
@jwt_required()
@role_required('seller')
def add_product():
    """添加新产品"""
    conn = None  # 初始化 conn 为 None
    try:
        data = request.get_json()
        name = data['name']
        price = data['price']
        stock = data['stock']

        # 解析当前用户身份信息
        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO products (name, price, stock, seller_id) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, price, stock, seller_id))
            conn.commit()
        return jsonify({'message': '产品添加成功'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:  # 确保 conn 已初始化
            conn.close()

# 获取所有产品
@products_bp.route('/products', methods=['GET'])
@jwt_required()
def get_products():
    """获取所有产品，包括平均评分和评价数量"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    p.product_id,
                    p.name,
                    p.price,
                    p.stock,
                    u.username AS seller_name,
                    IFNULL(ar.average_stars, 0.00) AS average_rating,
                    IFNULL(ar.review_count, 0) AS rating_count
                FROM 
                    products p
                LEFT JOIN 
                    average_ratings ar
                ON 
                    p.product_id = ar.product_id
                LEFT JOIN
                    users u
                ON
                    p.seller_id = u.user_id
            """
            cursor.execute(sql)
            products = cursor.fetchall()
        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 卖家更新产品信息
@products_bp.route('/products/<int:product_id>', methods=['PUT'])
@jwt_required()
@role_required('seller')
def update_product(product_id):
    """更新产品信息"""
    conn = None
    try:
        data = request.get_json()
        name = data.get('name')
        price = float(data.get('price'))  # 确保接受和存储小数
        stock = int(data.get('stock'))

        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                UPDATE products 
                SET name=%s, price=%s, stock=%s 
                WHERE product_id=%s AND seller_id=%s
            """
            cursor.execute(sql, (name, price, stock, product_id, seller_id))
            if cursor.rowcount == 0:
                return jsonify({'error': '无权更新此产品或产品不存在'}), 403
            conn.commit()
        return jsonify({'message': '产品信息更新成功'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 卖家删除产品
@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
@jwt_required()
@role_required('seller')
def delete_product(product_id):
    """删除产品"""
    conn = None
    try:
        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "DELETE FROM products WHERE product_id=%s AND seller_id=%s"
            cursor.execute(sql, (product_id, seller_id))
            if cursor.rowcount == 0:
                return jsonify({'error': '无权删除此产品或产品不存在'}), 403
            conn.commit()
        return jsonify({'message': '产品删除成功'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 搜索产品
@products_bp.route('/products/search', methods=['GET'])
@jwt_required()
def search_products():
    """根据条件搜索产品，返回平均评分、评分数量和商家名"""
    conn = None
    try:
        # 获取查询参数
        product_id = request.args.get('product_id', type=int)
        seller_id = request.args.get('seller_id', type=int)
        product_name = request.args.get('name', type=str)
        seller_name = request.args.get('seller_name', type=str)

        conn = get_connection()
        with conn.cursor() as cursor:
            # 动态 SQL 查询构建
            sql = """
                SELECT 
                    p.product_id, 
                    p.name AS product_name, 
                    p.price, 
                    p.stock, 
                    u.username AS seller_name, 
                    IFNULL(ar.average_stars, 0.00) AS average_rating, 
                    IFNULL(ar.review_count, 0) AS rating_count
                FROM products p
                JOIN users u ON p.seller_id = u.user_id
                LEFT JOIN average_ratings ar ON p.product_id = ar.product_id
                WHERE 1=1
            """
            params = []

            # 动态条件拼接
            if product_id:
                sql += " AND p.product_id = %s"
                params.append(product_id)
            if seller_id:
                sql += " AND p.seller_id = %s"
                params.append(seller_id)
            if product_name:
                sql += " AND p.name LIKE %s"
                params.append(f"%{product_name}%")
            if seller_name:
                sql += " AND u.username LIKE %s"
                params.append(f"%{seller_name}%")

            # 按评分数从大到小，再按平均评分从大到小排序
            sql += " ORDER BY rating_count DESC, average_rating DESC"

            # 执行 SQL
            cursor.execute(sql, params)
            products = cursor.fetchall()

        # 返回结果
        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 查看卖家自己的商品
@products_bp.route('/products/seller', methods=['GET'])
@jwt_required()
@role_required('seller')
def get_seller_products():
    """获取卖家自己的商品，包括评价数目和平均评分"""
    conn = None
    try:
        # 获取当前登录卖家信息
        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询商品信息并关联平均评分和评价数
            sql = """
                SELECT 
                    p.product_id, 
                    p.name, 
                    p.price, 
                    p.stock, 
                    IFNULL(ar.average_stars, 0.00) AS average_rating, 
                    IFNULL(ar.review_count, 0) AS rating_count
                FROM products p
                LEFT JOIN average_ratings ar ON p.product_id = ar.product_id
                WHERE p.seller_id = %s
            """
            cursor.execute(sql, (seller_id,))
            products = cursor.fetchall()

        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 获取单个商品信息
@products_bp.route('/products/<int:product_id>', methods=['GET'])
@jwt_required()
@role_required('seller')
def get_product(product_id):
    """获取单个商品信息，包括评分数和平均评分"""
    conn = None
    try:
        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询商品信息并关联评分数和平均评分
            sql = """
                SELECT 
                    p.product_id, 
                    p.name, 
                    p.price, 
                    p.stock, 
                    IFNULL(ar.average_stars, 0.00) AS average_rating, 
                    IFNULL(ar.review_count, 0) AS rating_count
                FROM products p
                LEFT JOIN average_ratings ar ON p.product_id = ar.product_id
                WHERE p.product_id = %s AND p.seller_id = %s
            """
            cursor.execute(sql, (product_id, seller_id))
            product = cursor.fetchone()
            if not product:
                return jsonify({'error': '商品不存在或无权限访问'}), 404
        return jsonify(product), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 推荐产品
@products_bp.route('/products/recommend', methods=['GET'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def recommend_products():
    """推荐产品（非个性化）"""
    conn = None
    try:
        # 获取推荐数量参数，默认为 10
        limit = request.args.get('limit', default=10, type=int)

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询评价数和平均评分，并按综合排序
            sql = """
                SELECT 
                    p.product_id,
                    p.name AS product_name,
                    p.price,
                    p.stock,
                    u.username AS seller_name,
                    IFNULL(ar.average_stars, 0.00) AS average_rating,
                    IFNULL(ar.review_count, 0) AS rating_count
                FROM products p
                JOIN users u ON p.seller_id = u.user_id
                LEFT JOIN average_ratings ar ON p.product_id = ar.product_id
                ORDER BY ar.review_count DESC, ar.average_stars DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            products = cursor.fetchall()

        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()