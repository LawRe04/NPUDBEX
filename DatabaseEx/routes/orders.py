from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required
import json  # 导入 JSON 模块
from routes.admin import log_action  # 导入日志记录函数

orders_bp = Blueprint('orders', __name__)

# 买家创建订单
@orders_bp.route('/orders', methods=['POST'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def create_order():
    """创建订单"""
    current_user = json.loads(get_jwt_identity())  # 将字符串转换回字典
    buyer_id = current_user['user_id']  # 获取买家 ID

    data = request.get_json()
    product_id = int(data['product_id'])
    quantity = int(data['quantity'])

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 获取产品价格和库存
            cursor.execute("SELECT price, stock FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()

            if not product:
                # 记录日志：产品不存在
                action = "创建订单失败"
                description = f"用户 {buyer_id} 尝试创建订单，但产品 {product_id} 不存在"
                log_action(buyer_id, action, description)
                return jsonify({'error': '产品不存在'}), 404

            price = float(product['price'])
            stock = int(product['stock'])

            if quantity > stock:
                # 记录日志：库存不足
                action = "创建订单失败"
                description = f"用户 {buyer_id} 尝试创建订单，产品 {product_id} 库存不足。请求数量：{quantity}，库存：{stock}"
                log_action(buyer_id, action, description)
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

            # 记录日志：订单创建成功
            action = "创建订单成功"
            description = f"用户 {buyer_id} 成功创建订单。产品ID：{product_id}，数量：{quantity}，总价：{total_price}"
            log_action(buyer_id, action, description)

        return jsonify({'message': '订单创建成功'}), 201

    except Exception as e:
        # 记录日志：订单创建失败
        action = "创建订单失败"
        description = f"用户 {buyer_id} 创建订单时发生错误：{str(e)}"
        log_action(buyer_id, action, description)
        return jsonify({'error': str(e)}), 500

    finally:
        if conn:
            conn.close()

# 获取所有订单
@orders_bp.route('/orders', methods=['GET'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def get_orders():
    """获取所有订单，包括买家ID和卖家ID"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询所有订单，包含买家ID和卖家ID
            sql = """
                SELECT 
                    o.order_id,
                    o.product_id,
                    o.buyer_id,
                    p.seller_id,
                    o.quantity,
                    o.total_price,
                    o.status
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
            """
            cursor.execute(sql)
            orders = cursor.fetchall()

        # 返回包含所有订单的 JSON 数据
        return jsonify(orders), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 买家获取自己的订单
@orders_bp.route('/orders/my', methods=['GET'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def get_my_orders():
    """获取买家的所有订单，包括商品名称和商家名"""
    current_user = json.loads(get_jwt_identity())  # 获取当前用户信息
    buyer_id = current_user['user_id']  # 获取买家 ID

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询当前买家的订单，包含商品名称和商家名称
            sql = """
            SELECT 
                o.order_id, 
                o.product_id, 
                o.quantity, 
                o.total_price, 
                o.status, 
                p.name AS product_name, 
                u.username AS seller_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN users u ON p.seller_id = u.user_id
            WHERE o.buyer_id = %s
            """
            cursor.execute(sql, (buyer_id,))
            orders = cursor.fetchall()
        return jsonify(orders), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 卖家获取自己的销售订单
@orders_bp.route('/orders/sales', methods=['GET'])
@jwt_required()
@role_required('seller')  # 仅卖家可访问
def get_sales_orders():
    """获取卖家的所有销售订单"""
    current_user = json.loads(get_jwt_identity())  # 获取当前用户信息
    seller_id = current_user['user_id']  # 获取卖家 ID

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询卖家相关的订单
            sql = """
            SELECT o.order_id, o.buyer_id, o.product_id, o.quantity, o.total_price, o.status, p.name AS product_name
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            WHERE p.seller_id = %s
            """
            cursor.execute(sql, (seller_id,))
            sales_orders = cursor.fetchall()
        return jsonify(sales_orders), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 更新订单状态
@orders_bp.route('/orders/<int:order_id>', methods=['PUT'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def update_order(order_id):
    """更新订单状态"""
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
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def delete_order(order_id):
    """删除订单"""
    current_user = json.loads(get_jwt_identity())  # 获取当前管理员身份信息
    admin_id = current_user['user_id']  # 管理员 ID

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查订单是否存在
            cursor.execute("SELECT * FROM orders WHERE order_id=%s", (order_id,))
            order = cursor.fetchone()

            if not order:
                # 记录日志：订单不存在
                action = "删除订单失败"
                description = f"管理员 {admin_id} 尝试删除订单，但订单 {order_id} 不存在"
                log_action(admin_id, action, description)
                return jsonify({'error': '订单不存在'}), 404

            # 删除订单
            sql = "DELETE FROM orders WHERE order_id=%s"
            cursor.execute(sql, (order_id,))
            conn.commit()

            # 记录日志：订单删除成功
            action = "删除订单成功"
            description = f"管理员 {admin_id} 成功删除订单 {order_id}"
            log_action(admin_id, action, description)

        return jsonify({'message': '订单删除成功'}), 200

    except Exception as e:
        # 记录日志：订单删除失败
        action = "删除订单失败"
        description = f"管理员 {admin_id} 删除订单 {order_id} 时发生错误：{str(e)}"
        log_action(admin_id, action, description)
        return jsonify({'error': str(e)}), 500

    finally:
        if conn:
            conn.close()
