import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required

cart_bp = Blueprint('cart', __name__)

# 加入购物车
@cart_bp.route('/cart', methods=['POST'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def add_to_cart():
    """将商品加入购物车"""
    conn = None
    try:
        data = request.get_json()
        product_id = data['product_id']
        quantity = data['quantity']

        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查商品是否存在
            cursor.execute("SELECT stock FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                return jsonify({'error': '商品不存在'}), 404

            # 检查库存是否足够
            if quantity > product['stock']:
                return jsonify({'error': '库存不足'}), 400

            # 检查购物车中是否已存在该商品
            cursor.execute("SELECT quantity FROM cart WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            cart_item = cursor.fetchone()
            if cart_item:
                # 如果已存在，更新数量
                cursor.execute(
                    "UPDATE cart SET quantity = quantity + %s WHERE product_id = %s AND user_id = %s",
                    (quantity, product_id, user_id)
                )
            else:
                # 如果不存在，插入新记录
                cursor.execute(
                    "INSERT INTO cart (product_id, user_id, quantity) VALUES (%s, %s, %s)",
                    (product_id, user_id, quantity)
                )
            conn.commit()
        return jsonify({'message': '商品已加入购物车'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 从购物车删除商品
@cart_bp.route('/cart/<int:product_id>', methods=['DELETE'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def remove_from_cart(product_id):
    """将商品从购物车中移除"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查购物车中是否存在该商品
            cursor.execute("SELECT * FROM cart WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            cart_item = cursor.fetchone()
            if not cart_item:
                return jsonify({'error': '购物车中没有该商品'}), 404

            # 从购物车中删除商品
            cursor.execute("DELETE FROM cart WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            conn.commit()
        return jsonify({'message': '商品已从购物车中移除'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 查看购物车内容
@cart_bp.route('/cart', methods=['GET'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def view_cart():
    """查看购物车内容"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询购物车中属于当前用户的所有商品
            sql = """
                SELECT c.product_id, p.name AS product_name, c.quantity, p.price, (c.quantity * p.price) AS total_price
                FROM cart c
                JOIN products p ON c.product_id = p.product_id
                WHERE c.user_id = %s
            """
            cursor.execute(sql, (user_id,))
            cart_items = cursor.fetchall()

        return jsonify(cart_items), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
