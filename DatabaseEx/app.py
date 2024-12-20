from flask import Flask
from routes.users import users_bp
from routes.products import products_bp
from routes.orders import orders_bp
from routes.cart import cart_bp
from routes.reviews import reviews_bp
from routes.average_ratings import average_ratings_bp
from routes.admin import logs_bp
from flask_jwt_extended import JWTManager
from flask_cors import CORS  # 导入 Flask-CORS

app = Flask(__name__)

# 配置 JWT
app.config['JWT_SECRET_KEY'] = 'your_secret_key_here'  # 设定 JWT 秘钥
jwt = JWTManager(app)

# 允许跨域请求
CORS(app)  # 允许所有域名访问

# 注册蓝图
app.register_blueprint(users_bp, url_prefix='/api')
app.register_blueprint(products_bp, url_prefix='/api')
app.register_blueprint(orders_bp, url_prefix='/api')
app.register_blueprint(cart_bp, url_prefix='/api')
app.register_blueprint(reviews_bp, url_prefix='/api')
app.register_blueprint(average_ratings_bp, url_prefix='/api')
app.register_blueprint(logs_bp, url_prefix='/api')


if __name__ == '__main__':
    app.run(debug=True)
