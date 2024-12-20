import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required
from routes.admin import log_action

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
                # 记录日志：商品不存在
                action = "加入购物车失败"
                description = f"用户 {user_id} 尝试将不存在的商品 {product_id} 加入购物车"
                log_action(user_id, action, description)

                return jsonify({'error': '商品不存在'}), 404

            # 检查库存是否足够
            if quantity > product['stock']:
                # 记录日志：库存不足
                action = "加入购物车失败"
                description = f"用户 {user_id} 尝试将商品 {product_id} 加入购物车，但库存不足"
                log_action(user_id, action, description)

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
                action = "更新购物车"
                description = f"用户 {user_id} 更新购物车中商品 {product_id} 的数量为 {cart_item['quantity'] + quantity}"
            else:
                # 如果不存在，插入新记录
                cursor.execute(
                    "INSERT INTO cart (product_id, user_id, quantity) VALUES (%s, %s, %s)",
                    (product_id, user_id, quantity)
                )
                action = "加入购物车"
                description = f"用户 {user_id} 将商品 {product_id} 数量 {quantity} 加入购物车"

            # 记录日志：成功加入购物车或更新购物车
            log_action(user_id, action, description)

            conn.commit()
        return jsonify({'message': '商品已加入购物车'}), 201
    except Exception as e:
        # 记录日志：系统错误
        action = "加入购物车失败"
        description = f"用户 {user_id} 尝试将商品 {product_id} 加入购物车时发生系统错误：{str(e)}"
        log_action(user_id, action, description)

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
                # 记录日志：尝试移除不存在的商品
                action = "移除购物车失败"
                description = f"用户 {user_id} 尝试移除购物车中不存在的商品 {product_id}"
                log_action(user_id, action, description)

                return jsonify({'error': '购物车中没有该商品'}), 404

            # 从购物车中删除商品
            cursor.execute("DELETE FROM cart WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            conn.commit()

            # 记录日志：成功移除商品
            action = "移除购物车"
            description = f"用户 {user_id} 将商品 {product_id} 从购物车中移除"
            log_action(user_id, action, description)

        return jsonify({'message': '商品已从购物车中移除'}), 200
    except Exception as e:
        # 记录日志：系统错误
        action = "移除购物车失败"
        description = f"用户 {user_id} 尝试移除商品 {product_id} 时发生系统错误：{str(e)}"
        log_action(user_id, action, description)

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

# 批量从购物车下单
@cart_bp.route('/cart/checkout', methods=['POST'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def checkout_cart():
    """批量下单"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        conn.autocommit = False  # 开启事务管理
        with conn.cursor() as cursor:
            # 查询购物车内容
            sql_cart = """
                SELECT c.product_id, c.quantity, p.price, p.stock
                FROM cart c
                JOIN products p ON c.product_id = p.product_id
                WHERE c.user_id = %s
            """
            cursor.execute(sql_cart, (user_id,))
            cart_items = cursor.fetchall()

            if not cart_items:
                # 记录日志：购物车为空
                action = "批量下单失败"
                description = f"用户 {user_id} 尝试下单时购物车为空"
                log_action(user_id, action, description)

                return jsonify({'error': '购物车为空，无法下单'}), 400

            successful_orders = []
            failed_orders = []

            for item in cart_items:
                product_id = item['product_id']
                quantity = item['quantity']
                price = item['price']
                stock = item['stock']

                if quantity > stock:
                    # 如果库存不足，记录失败原因
                    failed_orders.append({
                        'product_id': product_id,
                        'reason': '库存不足'
                    })
                    # 记录日志：库存不足
                    action = "批量下单失败"
                    description = f"用户 {user_id} 下单商品 {product_id} 时库存不足"
                    log_action(user_id, action, description)

                    continue

                try:
                    # 扣减库存并创建订单
                    total_price = quantity * price
                    sql_order = """
                        INSERT INTO orders (buyer_id, product_id, quantity, total_price, status)
                        VALUES (%s, %s, %s, %s, '已支付')
                    """
                    cursor.execute(sql_order, (user_id, product_id, quantity, total_price))

                    sql_update_stock = "UPDATE products SET stock = stock - %s WHERE product_id = %s"
                    cursor.execute(sql_update_stock, (quantity, product_id))

                    # 从购物车中移除已下单的商品
                    sql_remove_cart = "DELETE FROM cart WHERE product_id = %s AND user_id = %s"
                    cursor.execute(sql_remove_cart, (product_id, user_id))

                    # 成功记录
                    successful_orders.append({
                        'product_id': product_id,
                        'quantity': quantity,
                        'total_price': total_price
                    })

                    # 记录日志：成功下单
                    action = "批量下单成功"
                    description = f"用户 {user_id} 成功下单商品 {product_id}，数量 {quantity}，总价 {total_price}"
                    log_action(user_id, action, description)

                except Exception as e:
                    # 如果当前订单失败，回滚当前循环中的事务
                    conn.rollback()
                    failed_orders.append({
                        'product_id': product_id,
                        'reason': f'处理失败: {str(e)}'
                    })

                    # 记录日志：下单失败
                    action = "批量下单失败"
                    description = f"用户 {user_id} 下单商品 {product_id} 时失败，原因：{str(e)}"
                    log_action(user_id, action, description)

                    continue

            # 如果有成功的订单，提交事务
            if successful_orders:
                conn.commit()
            else:
                conn.rollback()  # 如果所有订单失败，回滚整个事务

            # 记录日志：批量下单完成
            action = "批量下单完成"
            description = (
                f"用户 {user_id} 批量下单完成。成功订单：{len(successful_orders)} 个，失败订单：{len(failed_orders)} 个"
            )
            log_action(user_id, action, description)

            return jsonify({
                'message': '批量下单完成',
                'successful_orders': successful_orders,
                'failed_orders': failed_orders
            }), 200

    except Exception as e:
        # 捕获全局异常并返回
        if conn:
            conn.rollback()

        # 记录日志：系统错误
        action = "批量下单失败"
        description = f"用户 {user_id} 尝试批量下单时发生系统错误：{str(e)}"
        log_action(user_id, action, description)

        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 更新购物车中的商品数量
@cart_bp.route('/cart/<int:product_id>', methods=['PATCH'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def update_cart(product_id):
    """更新购物车中商品的数量"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        # 获取请求数据
        data = request.get_json()
        new_quantity = data.get('quantity')

        # 校验数量
        if not isinstance(new_quantity, int) or new_quantity <= 0:
            action = "更新购物车失败"
            description = f"用户 {user_id} 尝试更新购物车商品 {product_id} 的数量为无效值 {new_quantity}"
            log_action(user_id, action, description)
            return jsonify({'error': '数量必须是正整数'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查购物车中是否有该商品
            cursor.execute(
                "SELECT * FROM cart WHERE product_id = %s AND user_id = %s",
                (product_id, user_id)
            )
            cart_item = cursor.fetchone()
            if not cart_item:
                action = "更新购物车失败"
                description = f"用户 {user_id} 尝试更新购物车，但商品 {product_id} 不在购物车中"
                log_action(user_id, action, description)
                return jsonify({'error': '购物车中没有此商品'}), 404

            # 检查商品库存是否足够
            cursor.execute(
                "SELECT stock FROM products WHERE product_id = %s",
                (product_id,)
            )
            product = cursor.fetchone()
            if not product or new_quantity > product['stock']:
                action = "更新购物车失败"
                description = f"用户 {user_id} 尝试更新购物车商品 {product_id}，但库存不足。请求数量：{new_quantity}，库存：{product['stock'] if product else '商品不存在'}"
                log_action(user_id, action, description)
                return jsonify({'error': '库存不足'}), 400

            # 更新购物车中的数量
            cursor.execute(
                "UPDATE cart SET quantity = %s WHERE product_id = %s AND user_id = %s",
                (new_quantity, product_id, user_id)
            )
            conn.commit()

            action = "更新购物车成功"
            description = f"用户 {user_id} 成功更新购物车商品 {product_id} 的数量为 {new_quantity}"
            log_action(user_id, action, description)

        return jsonify({'message': '购物车已更新'}), 200
    except Exception as e:
        action = "更新购物车失败"
        description = f"用户 {user_id} 更新购物车商品 {product_id} 时发生错误：{str(e)}"
        log_action(user_id, action, description)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

