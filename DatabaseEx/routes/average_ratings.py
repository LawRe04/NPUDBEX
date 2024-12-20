import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from routes.permissions import role_required

average_ratings_bp = Blueprint('average_ratings', __name__)

def create_triggers():
    """创建触发器，用于在相关表发生变化时自动处理依赖关系"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 创建触发器：在新增商品时添加平均星级初始行
            cursor.execute("""
                CREATE TRIGGER before_insert_product
                AFTER INSERT ON products
                FOR EACH ROW
                BEGIN
                    INSERT INTO average_ratings (product_id, average_stars, review_count)
                    VALUES (NEW.product_id, 0.00, 0);
                END;
            """)

            # 创建触发器：在删除商品前删除所有相关评价
            cursor.execute("""
                CREATE TRIGGER before_delete_product_reviews
                BEFORE DELETE ON products
                FOR EACH ROW
                BEGIN
                    DELETE FROM reviews WHERE product_id = OLD.product_id;
                END;
            """)

            # 创建触发器：在删除商品前删除 average_ratings
            cursor.execute("""
                CREATE TRIGGER before_delete_product_ratings
                BEFORE DELETE ON products
                FOR EACH ROW
                BEGIN
                    DELETE FROM average_ratings WHERE product_id = OLD.product_id;
                END;
            """)

            # 创建触发器：在新增评价时更新平均星级
            cursor.execute("""
                CREATE TRIGGER after_insert_review
                AFTER INSERT ON reviews
                FOR EACH ROW
                BEGIN
                    UPDATE average_ratings
                    SET average_stars = (
                        SELECT AVG(stars)
                        FROM reviews
                        WHERE product_id = NEW.product_id
                    ),
                    review_count = (
                        SELECT COUNT(*)
                        FROM reviews
                        WHERE product_id = NEW.product_id
                    )
                    WHERE product_id = NEW.product_id;
                END;
            """)

            # 创建触发器：在更新评价时更新平均星级
            cursor.execute("""
                CREATE TRIGGER after_update_review
                AFTER UPDATE ON reviews
                FOR EACH ROW
                BEGIN
                    UPDATE average_ratings
                    SET average_stars = (
                        SELECT AVG(stars)
                        FROM reviews
                        WHERE product_id = NEW.product_id
                    ),
                    review_count = (
                        SELECT COUNT(*)
                        FROM reviews
                        WHERE product_id = NEW.product_id
                    )
                    WHERE product_id = NEW.product_id;
                END;
            """)

            # 创建触发器：在删除评价时更新平均星级
            cursor.execute("""
                CREATE TRIGGER after_delete_review
                AFTER DELETE ON reviews
                FOR EACH ROW
                BEGIN
                    UPDATE average_ratings
                    SET average_stars = (
                        SELECT IFNULL(AVG(stars), 0)
                        FROM reviews
                        WHERE product_id = OLD.product_id
                    ),
                    review_count = (
                        SELECT COUNT(*)
                        FROM reviews
                        WHERE product_id = OLD.product_id
                    )
                    WHERE product_id = OLD.product_id;
                END;
            """)

            # 创建触发器：在删除商品前删除所有相关订单
            cursor.execute("""
                CREATE TRIGGER before_delete_cascade_orders
                BEFORE DELETE ON products
                FOR EACH ROW
                BEGIN
                    DELETE FROM orders WHERE product_id = OLD.product_id;
                END;
            """)
            conn.commit()
    except Exception as e:
        print(f"Error creating triggers: {e}")
    finally:
        if conn:
            conn.close()

# 手动触发触发器创建
@average_ratings_bp.route('/create_triggers', methods=['POST'])
@jwt_required()
@role_required('admin')  # 仅管理员可访问
def setup_triggers():
    """手动创建触发器"""
    try:
        create_triggers()
        return jsonify({'message': '触发器已创建'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 查看某商品的平均星级
@average_ratings_bp.route('/average_ratings/<int:product_id>', methods=['GET'])
def get_average_rating(product_id):
    """获取某商品的平均星级和评价数量"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT product_id, average_stars, review_count
                FROM average_ratings
                WHERE product_id = %s
            """
            cursor.execute(sql, (product_id,))
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': '商品不存在或尚无评价'}), 404
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
