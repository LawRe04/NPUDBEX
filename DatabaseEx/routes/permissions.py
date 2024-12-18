import json
from functools import wraps
from flask_jwt_extended import get_jwt_identity
from flask import jsonify

def role_required(required_role):
    """校验用户角色"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 反序列化 identity 字符串为字典
            current_user = json.loads(get_jwt_identity())
            if current_user.get('role') != required_role:
                return jsonify({'error': '权限不足，无法访问此资源'}), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator
