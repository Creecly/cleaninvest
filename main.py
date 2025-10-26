import os
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from datetime import datetime, timezone
import re
import threading
import time

# Конфигурация
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cleaninvest.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy(app)
mail = Mail(app)


# Модели
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    registration_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'name': self.name,
            'email': self.email,
            'balance': self.balance
        }


class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'symbol': self.symbol,
            'category': self.category,
            'base_price': self.base_price,
            'description': self.description,
            'icon': self.icon
        }


# Создаем таблицы
with app.app_context():
    db.create_all()


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not all([data.get('name'), data.get('nickname'), data.get('email'), data.get('password')]):
        return jsonify({'error': 'Todos los campos son obligatorios'}), 400

    try:
        if User.query.filter_by(nickname=data['nickname']).first():
            return jsonify({'error': 'Este nombre de usuario ya esta en uso'}), 400

        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Este email ya esta registrado'}), 400

        user = User(
            name=data['name'],
            nickname=data['nickname'],
            email=data['email']
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id

        return jsonify({
            'message': '¡Registro exitoso!',
            'user': user.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error en el registro: {str(e)}'}), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data.get('nickname') or not data.get('password'):
        return jsonify({'error': 'Credenciales incompletas'}), 400

    try:
        user = User.query.filter_by(nickname=data['nickname']).first()

        if user and user.check_password(data['password']):
            session['user_id'] = user.id
            return jsonify({'message': '¡Inicio de sesion exitoso!', 'user': user.to_dict()})
        else:
            return jsonify({'error': 'Credenciales invalidas'}), 401

    except Exception as e:
        return jsonify({'error': f'Error en el inicio de sesion: {str(e)}'}), 500


@app.route('/companies', methods=['GET'])
def get_companies():
    try:
        companies = Company.query.all()
        return jsonify({'companies': [company.to_dict() for company in companies]})
    except Exception as e:
        return jsonify({'error': f'Error al obtener empresas: {str(e)}'}), 500


@app.route('/health')
def health_check():
    try:
        db.session.execute('SELECT 1')
        return {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'users': User.query.count(),
            'companies': Company.query.count()
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500


# Важно - эта часть должна быть в конце
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)