from flask import Flask
from routes.users import users_bp
from routes.products import products_bp
from routes.orders import orders_bp
from flask_jwt_extended import JWTManager

app = Flask(__name__)

# 配置 JWT
app.config['JWT_SECRET_KEY'] = 'your_secret_key_here'  # 设定 JWT 秘钥
jwt = JWTManager(app)

# 注册蓝图
app.register_blueprint(users_bp, url_prefix='/api')
app.register_blueprint(products_bp, url_prefix='/api')
app.register_blueprint(orders_bp, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True)
