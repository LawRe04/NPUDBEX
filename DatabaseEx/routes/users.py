from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required
import json

users_bp = Blueprint('users', __name__)

@users_bp.route('/users/register', methods=['POST'])
def register_user():
    """用户注册"""
    conn = None
    try:
        data = request.get_json()
        username = data['username']
        password = data['password']
        role = data['role']

        # 后端限制：role 只能是 buyer 或 seller
        if role not in ['buyer', 'seller']:
            return jsonify({'error': '非法角色，无法注册为管理员'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, password, role))
            conn.commit()
        return jsonify({'message': '用户注册成功'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@users_bp.route('/users/login', methods=['POST'])
def login_user():
    """用户登录"""
    conn = None
    try:
        data = request.get_json()
        username = data['username']
        password = data['password']

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "SELECT user_id, role FROM users WHERE username=%s AND password=%s"
            cursor.execute(sql, (username, password))
            user = cursor.fetchone()

            if user:
                # 将字典转换为 JSON 字符串
                identity = json.dumps({'user_id': user['user_id'], 'role': user['role']})
                access_token = create_access_token(identity=identity)
                return jsonify({
                    'message': '登录成功',
                    'token': access_token
                }), 200
            else:
                return jsonify({'error': '用户名或密码错误'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@users_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def get_users():
    """获取所有用户"""
    conn = None
    try:
        # 将 identity 转回字典
        current_user = json.loads(get_jwt_identity())
        if current_user.get('role') != 'admin':
            return jsonify({'error': '权限不足，无法访问此资源'}), 403

        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@users_bp.route('/users/me', methods=['GET'])
@jwt_required()
def get_user_info():
    """获取当前用户的信息（非管理员查看自身信息）"""
    conn = None
    try:
        # 将 identity 转回字典
        current_user = json.loads(get_jwt_identity())
        user_id = current_user.get('user_id')

        conn = get_connection()
        with conn.cursor() as cursor:
            sql = "SELECT user_id, username, role FROM users WHERE user_id=%s"
            cursor.execute(sql, (user_id,))
            user_info = cursor.fetchone()

            if not user_info:
                return jsonify({'error': '用户不存在'}), 404

        return jsonify({'user_info': user_info}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()