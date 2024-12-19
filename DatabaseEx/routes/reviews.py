import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required

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
            return jsonify({'error': '星级必须在1到5之间'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查商品是否存在
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                return jsonify({'error': '商品不存在'}), 404

            # 检查是否已购买该商品
            cursor.execute("""
                SELECT * FROM orders 
                WHERE product_id = %s AND buyer_id = %s AND status = '已支付'
            """, (product_id, user_id))
            order = cursor.fetchone()
            if not order:
                return jsonify({'error': '您尚未购买此商品，无法评价'}), 403

            # 检查是否已评价
            cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            review = cursor.fetchone()
            if review:
                # 更新已有评价
                sql = "UPDATE reviews SET stars = %s, comment = %s WHERE product_id = %s AND user_id = %s"
                cursor.execute(sql, (stars, comment, product_id, user_id))
            else:
                # 插入新评价
                sql = "INSERT INTO reviews (product_id, user_id, stars, comment) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (product_id, user_id, stars, comment))
            conn.commit()
        return jsonify({'message': '评价提交成功'}), 201
    except Exception as e:
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
                return jsonify({'error': '评价不存在'}), 404

            # 删除评价
            cursor.execute("DELETE FROM reviews WHERE product_id = %s AND user_id = %s", (product_id, user_id))
            conn.commit()
        return jsonify({'message': '评价已删除'}), 200
    except Exception as e:
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