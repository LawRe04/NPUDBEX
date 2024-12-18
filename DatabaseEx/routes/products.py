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
    """获取所有产品"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM products")
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
        price = data.get('price')
        stock = data.get('stock')

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
