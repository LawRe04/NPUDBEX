import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required
from routes.admin import log_action

reviews_bp = Blueprint('reviews', __name__)

# 新增评价
@reviews_bp.route('/reviews', methods=['POST'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def add_review():
    """新增评价"""
    conn = None
    try:
        data = request.get_json()
        product_id = data['product_id']
        stars = data['stars']
        comment = data.get('comment', '')

        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        if stars < 1 or stars > 5:
            action = "新增评价失败"
            description = f"买家 {user_id} 评价商品 {product_id} 时，星级超出范围: {stars}"
            log_action(user_id, action, description)
            return jsonify({'error': '星级必须在1到5之间'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查商品是否存在
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                action = "新增评价失败"
                description = f"买家 {user_id} 评价商品 {product_id} 时，商品不存在"
                log_action(user_id, action, description)
                return jsonify({'error': '商品不存在'}), 404

            # 检查是否已购买该商品
            cursor.execute("""
                SELECT * FROM orders 
                WHERE product_id = %s AND buyer_id = %s AND status = '已支付'
            """, (product_id, user_id))
            order = cursor.fetchone()
            if not order:
                action = "新增评价失败"
                description = f"买家 {user_id} 评价商品 {product_id} 时，未购买该商品"
                log_action(user_id, action, description)
                return jsonify({'error': '您尚未购买此商品，无法评价'}), 403

            # 检查是否已评价
            cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            review = cursor.fetchone()
            if review:
                # 更新已有评价
                sql = "UPDATE reviews SET stars = %s, comment = %s WHERE product_id = %s AND user_id = %s"
                cursor.execute(sql, (stars, comment, product_id, user_id))
                action = "更新评价成功"
                description = f"买家 {user_id} 更新了商品 {product_id} 的评价，星级: {stars}, 评论: {comment}"
            else:
                # 插入新评价
                sql = "INSERT INTO reviews (product_id, user_id, stars, comment) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (product_id, user_id, stars, comment))
                action = "新增评价成功"
                description = f"买家 {user_id} 对商品 {product_id} 添加了评价，星级: {stars}, 评论: {comment}"
            conn.commit()

            # 记录日志
            log_action(user_id, action, description)

        return jsonify({'message': '评价提交成功'}), 201

    except Exception as e:
        action = "新增评价失败"
        description = f"买家 {user_id} 在评价商品 {product_id} 时发生错误: {str(e)}"
        log_action(user_id, action, description)
        return jsonify({'error': str(e)}), 500

    finally:
        if conn:
            conn.close()

# 删除评价
@reviews_bp.route('/reviews/<int:product_id>', methods=['DELETE'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def delete_review(product_id):
    """删除评价"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查是否有评价
            cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            review = cursor.fetchone()
            if not review:
                action = "删除评价失败"
                description = f"买家 {user_id} 尝试删除商品 {product_id} 的评价，但评价不存在"
                log_action(user_id, action, description)
                return jsonify({'error': '评价不存在'}), 404

            # 删除评价
            cursor.execute("DELETE FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            conn.commit()

            # 记录日志
            action = "删除评价成功"
            description = f"买家 {user_id} 删除了商品 {product_id} 的评价"
            log_action(user_id, action, description)

        return jsonify({'message': '评价已删除'}), 200
    except Exception as e:
        # 记录失败日志
        action = "删除评价失败"
        description = f"买家 {user_id} 删除商品 {product_id} 的评价时发生错误: {str(e)}"
        log_action(user_id, action, description)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 查看商品的所有评价
@reviews_bp.route('/reviews/<int:product_id>', methods=['GET'])
def view_reviews(product_id):
    """查看商品的所有评价"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT r.user_id, u.username, r.stars, r.comment
                FROM reviews r
                JOIN users u ON r.user_id = u.user_id
                WHERE r.product_id = %s
            """
            cursor.execute(sql, (product_id,))
            reviews = cursor.fetchall()
        return jsonify(reviews), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 卖家查看自己商品的所有评价
@reviews_bp.route('/reviews/seller', methods=['GET'])
@jwt_required()
@role_required('seller')  # 仅卖家可访问
def view_seller_reviews():
    """卖家查看自己商品的所有评价"""
    conn = None
    try:
        # 获取当前卖家信息
        current_user = json.loads(get_jwt_identity())
        seller_id = current_user['user_id']  # 获取当前卖家的 ID

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询卖家的商品及其对应的评价
            sql = """
                SELECT 
                    p.product_id, 
                    p.name AS product_name, 
                    r.user_id AS buyer_id,
                    u.username AS buyer_name,
                    r.stars,
                    r.comment
                FROM reviews r
                JOIN products p ON r.product_id = p.product_id
                JOIN users u ON r.user_id = u.user_id
                WHERE p.seller_id = %s
                ORDER BY p.product_id, r.stars DESC
            """
            cursor.execute(sql, (seller_id,))
            reviews = cursor.fetchall()  # 获取所有评价数据

        return jsonify(reviews), 200  # 返回评价列表
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 买家查看自己所有的评价
@reviews_bp.route('/reviews/my', methods=['GET'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def view_my_reviews():
    """查看买家自己发表过的所有评价"""
    conn = None
    try:
        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询买家所有发表的评价（不包含 created_at 字段）
            sql = """
                SELECT 
                    r.product_id, 
                    p.name AS product_name,
                    u.username AS seller_name, 
                    r.stars, 
                    r.comment
                FROM reviews r
                JOIN products p ON r.product_id = p.product_id
                JOIN users u ON p.seller_id = u.user_id
                WHERE r.user_id = %s
            """
            cursor.execute(sql, (user_id,))
            reviews = cursor.fetchall()  # 获取所有评价

        return jsonify(reviews), 200  # 返回评价列表
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 修改评价
@reviews_bp.route('/reviews/<int:product_id>', methods=['PUT'])
@jwt_required()
@role_required('buyer')  # 仅买家可访问
def update_review(product_id):
    """修改评价"""
    conn = None
    try:
        data = request.get_json()
        stars = data['stars']
        comment = data.get('comment', '')

        # 获取当前用户信息
        current_user = json.loads(get_jwt_identity())
        user_id = current_user['user_id']

        if stars < 1 or stars > 5:
            action = "修改评价失败"
            description = f"买家 {user_id} 尝试修改商品 {product_id} 的评价，星级不在合法范围内（1-5）"
            log_action(user_id, action, description)
            return jsonify({'error': '星级必须在1到5之间'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查是否存在评价
            cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            review = cursor.fetchone()
            if not review:
                action = "修改评价失败"
                description = f"买家 {user_id} 尝试修改商品 {product_id} 的评价，但评价不存在"
                log_action(user_id, action, description)
                return jsonify({'error': '评价不存在'}), 404

            # 修改评价
            sql = "UPDATE reviews SET stars = %s, comment = %s WHERE product_id = %s AND user_id = %s"
            cursor.execute(sql, (stars, comment, product_id, user_id))
            conn.commit()

            # 记录成功日志
            action = "修改评价成功"
            description = f"买家 {user_id} 修改了商品 {product_id} 的评价，星级: {stars}, 评论: {comment}"
            log_action(user_id, action, description)

        return jsonify({'message': '评价修改成功'}), 200
    except Exception as e:
        # 记录失败日志
        action = "修改评价失败"
        description = f"买家 {user_id} 修改商品 {product_id} 的评价时发生错误: {str(e)}"
        log_action(user_id, action, description)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 管理员查看所有评价
@reviews_bp.route('/reviews/admin', methods=['GET'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def view_all_reviews():
    """管理员查看所有评价"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询所有评价
            sql = """
                SELECT 
                    r.product_id, 
                    p.name AS product_name, 
                    r.user_id AS buyer_id, 
                    u.username AS buyer_name, 
                    r.stars, 
                    r.comment
                FROM reviews r
                JOIN products p ON r.product_id = p.product_id
                JOIN users u ON r.user_id = u.user_id
                ORDER BY r.product_id, r.stars DESC
            """
            cursor.execute(sql)
            reviews = cursor.fetchall()  # 获取所有评价数据

        return jsonify(reviews), 200  # 返回评价列表
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 管理员删除评价
@reviews_bp.route('/reviews/admin/<int:product_id>/<int:user_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def admin_delete_review(product_id, user_id):
    """管理员删除评价"""
    conn = None
    try:
        # 获取当前管理员信息
        current_user = json.loads(get_jwt_identity())
        admin_id = current_user['user_id']

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查是否有评价
            cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            review = cursor.fetchone()
            if not review:
                # 记录失败日志
                action = "管理员删除评价失败"
                description = f"管理员 {admin_id} 尝试删除商品 {product_id} 用户 {user_id} 的评价，但评价不存在"
                log_action(admin_id, action, description)
                return jsonify({'error': '评价不存在'}), 404

            # 删除评价
            cursor.execute("DELETE FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            conn.commit()

            # 记录成功日志
            action = "管理员删除评价成功"
            description = f"管理员 {admin_id} 删除了商品 {product_id} 用户 {user_id} 的评价"
            log_action(admin_id, action, description)

        return jsonify({'message': '评价已删除（管理员操作）'}), 200
    except Exception as e:
        # 记录失败日志
        action = "管理员删除评价失败"
        description = f"管理员 {admin_id} 删除商品 {product_id} 用户 {user_id} 的评价时发生错误: {str(e)}"
        log_action(admin_id, action, description)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
