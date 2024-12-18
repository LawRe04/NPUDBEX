from flask import Blueprint, request, jsonify
from db import get_connection

orders_bp = Blueprint('orders', __name__)

# 买家创建订单
@orders_bp.route('/orders', methods=['POST'])
def create_order():
    """创建订单"""
    data = request.get_json()
    buyer_id = int(data['buyer_id'])
    product_id = int(data['product_id'])
    quantity = int(data['quantity'])

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 获取产品价格
            cursor.execute("SELECT price, stock FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()

            if not product:
                return jsonify({'error': '产品不存在'}), 404

            price = float(product['price'])  # 转换价格为浮点数
            stock = int(product['stock'])  # 转换库存为整数

            if quantity > stock:
                return jsonify({'error': '库存不足'}), 400

            total_price = price * quantity

            # 创建订单
            sql = """
            INSERT INTO orders (buyer_id, product_id, quantity, total_price, status)
            VALUES (%s, %s, %s, %s, '已支付')
            """
            cursor.execute(sql, (buyer_id, product_id, quantity, total_price))

            # 更新库存
            cursor.execute("UPDATE products SET stock = stock - %s WHERE product_id = %s", (quantity, product_id))

            conn.commit()

        return jsonify({'message': '订单创建成功'}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if conn:
            conn.close()

# 获取所有订单
@orders_bp.route('/orders', methods=['GET'])
def get_orders():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM orders")
            orders = cursor.fetchall()
        return jsonify(orders), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 更新订单状态
@orders_bp.route('/orders/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    data = request.get_json()
    status = data['status']

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "UPDATE orders SET status=%s WHERE order_id=%s"
            cursor.execute(sql, (status, order_id))
            conn.commit()
        return jsonify({'message': '订单状态更新成功'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 删除订单
@orders_bp.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "DELETE FROM orders WHERE order_id=%s"
            cursor.execute(sql, (order_id,))
            conn.commit()
        return jsonify({'message': '订单删除成功'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
