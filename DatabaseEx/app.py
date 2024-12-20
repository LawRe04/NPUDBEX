from flask import Flask, send_from_directory
from routes.users import users_bp
from routes.products import products_bp
from routes.orders import orders_bp
from routes.cart import cart_bp
from routes.reviews import reviews_bp
from routes.average_ratings import average_ratings_bp
from routes.admin import logs_bp
from flask_jwt_extended import JWTManager
from flask_cors import CORS  # 导入 Flask-CORS

import os

app = Flask(__name__, static_folder='static')  # 指定静态文件夹路径

# 配置 JWT
app.config['JWT_SECRET_KEY'] = 'your_secret_key_here'  # 设定 JWT 秘钥
jwt = JWTManager(app)

# 精确配置 CORS 允许的来源和请求方式
CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:5000", "http://192.168.50.207:5000"]}})

# 注册蓝图
app.register_blueprint(users_bp, url_prefix='/api')
app.register_blueprint(products_bp, url_prefix='/api')
app.register_blueprint(orders_bp, url_prefix='/api')
app.register_blueprint(cart_bp, url_prefix='/api')
app.register_blueprint(reviews_bp, url_prefix='/api')
app.register_blueprint(average_ratings_bp, url_prefix='/api')
app.register_blueprint(logs_bp, url_prefix='/api')

# 提供 HTML 文件服务
@app.route('/')
def index():
    return send_from_directory(os.getcwd(), 'login.html')  # 从项目根目录加载 login.html

# 如果有其他 HTML 页面，可以类似这样添加路由
@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory(os.getcwd(), filename)  # 从项目根目录加载指定文件

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # 绑定到所有网络接口以允许局域网访问
