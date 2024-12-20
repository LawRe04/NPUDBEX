from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required
import json
from routes.admin import log_action

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

        if role not in ['buyer', 'seller']:
            return jsonify({'error': '非法角色，无法注册为管理员'}), 400

        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查用户名是否已存在
            cursor.execute("SELECT COUNT(*) AS count FROM users WHERE username = %s", (username,))
            result = cursor.fetchone()
            if result['count'] > 0:
                return jsonify({'error': '用户名已存在'}), 409

            # 插入新用户
            sql = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, password, role))
            conn.commit()

            # 添加日志记录
            action = "用户注册"
            description = f"新用户注册: 用户名 {username}, 角色 {role}"
            log_action(None, action, description)  # 无法确定 user_id，因此传递 None

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

                # 添加日志记录
                action = "用户登录"
                description = f"用户 {username} 登录成功"
                log_action(user['user_id'], action, description)

                return jsonify({
                    'message': '登录成功',
                    'token': access_token
                }), 200
            else:
                # 记录失败登录尝试
                action = "登录失败"
                description = f"用户 {username} 尝试登录，但用户名或密码错误"
                log_action(None, action, description)  # 无法获取 user_id 时，设置为 None

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

