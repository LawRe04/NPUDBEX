from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.permissions import role_required
from db import get_connection
import json

# 日志管理blueprint
logs_bp = Blueprint('logs', __name__)

# 添加日志记录的工具函数
def log_action(user_id, action, description):
    """记录用户操作日志"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO logs (user_id, action, description) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, action, description))
            conn.commit()
    except Exception as e:
        print(f"日志记录失败: {e}")
    finally:
        if conn:
            conn.close()

# 管理员查看所有日志
@logs_bp.route('/admin/logs', methods=['GET'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def view_logs():
    """查看系统日志"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    l.log_id,
                    l.user_id,
                    u.username,
                    l.action,
                    l.description,
                    l.timestamp
                FROM logs l
                LEFT JOIN users u ON l.user_id = u.user_id
                ORDER BY l.timestamp DESC
            """
            cursor.execute(sql)
            logs = cursor.fetchall()
        return jsonify(logs), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@logs_bp.route('/admin/stats/users', methods=['GET'])
@jwt_required()
@role_required('admin')
def user_statistics():
    """统计用户数量（包括总数、买家、卖家）"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询用户总数、买家总数、卖家总数
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_users,
                    SUM(CASE WHEN role = 'buyer' THEN 1 ELSE 0 END) AS total_buyers,
                    SUM(CASE WHEN role = 'seller' THEN 1 ELSE 0 END) AS total_sellers
                FROM users
            """)
            stats = cursor.fetchone()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@logs_bp.route('/admin/stats/products', methods=['GET'])
@jwt_required()
@role_required('admin')
def product_statistics():
    """统计商品总数及库存不足的商品数量"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询商品总数及库存不足的商品数量
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_products,
                    SUM(CASE WHEN stock < 10 THEN 1 ELSE 0 END) AS low_stock_products
                FROM products
            """)
            stats = cursor.fetchone()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@logs_bp.route('/admin/stats/orders', methods=['GET'])
@jwt_required()
@role_required('admin')
def order_statistics():
    """统计订单总数及完成和取消的订单数"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询订单总数及完成、取消的订单数量
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_orders,
                    SUM(CASE WHEN status = '已支付' THEN 1 ELSE 0 END) AS completed_orders,
                    SUM(CASE WHEN status = '已取消' THEN 1 ELSE 0 END) AS canceled_orders,
                    SUM(CASE WHEN status = '已支付' THEN total_price ELSE 0 END) AS total_sales
                FROM orders
            """)
            stats = cursor.fetchone()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@logs_bp.route('/admin/stats/top-products', methods=['GET'])
@jwt_required()
@role_required('admin')
def top_products():
    """统计最热销的商品（按销量排序）"""
    conn = None
    try:
        limit = int(request.args.get('limit', 10))  # 可选参数，默认返回前10
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询销量最高的商品
            cursor.execute("""
                SELECT 
                    p.product_id, 
                    p.name AS product_name, 
                    SUM(o.quantity) AS total_sales
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
                WHERE o.status = '已支付'
                GROUP BY p.product_id, p.name
                ORDER BY total_sales DESC
                LIMIT %s
            """, (limit,))
            top_products = cursor.fetchall()
        return jsonify(top_products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@logs_bp.route('/admin/stats/logs', methods=['GET'])
@jwt_required()
@role_required('admin')
def logs_statistics():
    """统计日志记录"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询日志总数及按用户分布的操作记录数
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_logs,
                    COUNT(DISTINCT user_id) AS unique_users
                FROM logs
            """)
            stats = cursor.fetchone()

            # 查询最近的日志
            cursor.execute("""
                SELECT 
                    user_id, 
                    action, 
                    description, 
                    timestamp 
                FROM logs
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent_logs = cursor.fetchall()

        # 格式化返回的日志记录
        recent_logs_formatted = [
            {
                "user_id": log["user_id"],
                "action": log["action"],
                "description": log["description"],
                "timestamp": log["timestamp"].strftime("%Y-%m-%d %H:%M:%S")  # 格式化时间为易读形式
            }
            for log in recent_logs
        ]

        return jsonify({'stats': stats, 'recent_logs': recent_logs_formatted}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
