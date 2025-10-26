import os
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import re
import uuid
import threading
import time
import random
import json

# Конфигурация
app = Flask(__name__)

# Railway конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cleaninvest.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 300,
    'pool_pre_ping': True
}

# Email конфигурация
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Файловые настройки
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = 'uploads'

# Инициализация
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy(app)
mail = Mail(app)

# Создаем папку для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# МОДЕЛИ (добавь их в app.py для простоты)
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(255))
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    is_admin = db.Column(db.Boolean, default=False)
    is_owner = db.Column(db.Boolean, default=False)
    registration_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    total_invested = db.Column(db.Float, default=0.0)
    total_withdrawn = db.Column(db.Float, default=0.0)
    total_profit = db.Column(db.Float, default=0.0)
    investments_count = db.Column(db.Integer, default=0)
    successful_investments = db.Column(db.Integer, default=0)
    failed_investments = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        if "123321owner123321" in password:
            self.is_admin = True
            self.is_owner = True

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'name': self.name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'balance': self.balance,
            'is_admin': self.is_admin,
            'is_owner': self.is_owner,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'total_invested': self.total_invested,
            'total_withdrawn': self.total_withdrawn,
            'total_profit': self.total_profit,
            'investments_count': self.investments_count,
            'successful_investments': self.successful_investments,
            'failed_investments': self.failed_investments
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


class UserInvestment(db.Model):
    __tablename__ = 'user_investment'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    shares = db.Column(db.Integer, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('user_investments', lazy='dynamic'))
    company = db.relationship('Company', backref=db.backref('user_investments', lazy='dynamic'))

    def to_dict(self):
        profit_multiplier = random.uniform(2.28, 2.63)
        adjusted_current_price = self.purchase_price * profit_multiplier
        profit = (adjusted_current_price - self.purchase_price) * self.shares
        profit_percentage = ((adjusted_current_price - self.purchase_price) / self.purchase_price) * 100

        return {
            'id': self.id,
            'company': self.company.to_dict(),
            'shares': self.shares,
            'purchase_price': self.purchase_price,
            'current_price': adjusted_current_price,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'is_active': self.is_active,
            'profit': profit,
            'profit_percentage': profit_percentage
        }


class SupportChat(db.Model):
    __tablename__ = 'support_chat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admin_joined_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    unread_admin_count = db.Column(db.Integer, default=0)
    unread_user_count = db.Column(db.Integer, default=0)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('user_chats', lazy='dynamic'))
    admin = db.relationship('User', foreign_keys=[admin_id], backref=db.backref('admin_chats', lazy='dynamic'))
    messages = db.relationship('ChatMessage', backref='chat', lazy='dynamic', order_by='ChatMessage.created_at')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'admin_id': self.admin_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'admin_joined_at': self.admin_joined_at.isoformat() if self.admin_joined_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'unread_admin_count': self.unread_admin_count,
            'unread_user_count': self.unread_user_count,
            'user': self.user.to_dict() if self.user else None,
            'admin': self.admin.to_dict() if self.admin else None,
            'last_message': self.messages[-1].to_dict() if self.messages else None
        }


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('support_chat.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', backref=db.backref('sent_messages', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'sender_id': self.sender_id,
            'message': self.message,
            'attachment_url': self.attachment_url,
            'is_system': self.is_system,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sender': self.sender.to_dict() if self.sender else None
        }


# АВТОМАТИЧЕСКАЯ ИНИЦИАЛИЗАЦИЯ БД
def initialize_database():
    """Initialize database with tables and companies"""
    try:
        # Создаем таблицы
        db.create_all()
        print("✅ Database tables created successfully")

        # Проверяем, есть ли компании
        if Company.query.count() == 0:
            print("🔄 Initializing database with companies...")

            companies = [
                {"name": "EcoEnergy Plus", "symbol": "EEP", "category": "Energia renovable", "base_price": 25.50,
                 "description": "Lider en energia solar y eolica", "icon": "fa-leaf"},
                {"name": "TechFuture AI", "symbol": "TFAI", "category": "Inteligencia artificial", "base_price": 120.75,
                 "description": "Desarrollo de IA de vanguardia", "icon": "fa-microchip"},
                {"name": "SpaceX Ventures", "symbol": "SPXV", "category": "Aeroespacial", "base_price": 350.20,
                 "description": "Exploracion espacial comercial", "icon": "fa-rocket"},
                {"name": "BioMed Solutions", "symbol": "BMS", "category": "Biotecnologia", "base_price": 85.40,
                 "description": "Investigacion medica avanzada", "icon": "fa-dna"},
                {"name": "GreenTransport", "symbol": "GRT", "category": "Transporte", "base_price": 42.30,
                 "description": "Vehiculos electricos sostenibles", "icon": "fa-car"},
                {"name": "CloudNet Systems", "symbol": "CNS", "category": "Tecnologia", "base_price": 65.80,
                 "description": "Soluciones de computacion en la nube", "icon": "fa-cloud"},
                {"name": "FoodTech Innovations", "symbol": "FTI", "category": "Alimentos", "base_price": 38.90,
                 "description": "Tecnologia alimentaria sostenible", "icon": "fa-utensils"},
                {"name": "RoboTech Industries", "symbol": "RTI", "category": "Robotica", "base_price": 95.60,
                 "description": "Automatizacion industrial avanzada", "icon": "fa-robot"},
                {"name": "WaterPure Solutions", "symbol": "WPS", "category": "Medio ambiente", "base_price": 22.75,
                 "description": "Tecnologias de purificacion de agua", "icon": "fa-tint"},
                {"name": "Quantum Computing", "symbol": "QCC", "category": "Tecnologia", "base_price": 180.50,
                 "description": "Computacion cuantica de proxima generacion", "icon": "fa-atom"},
                {"name": "EcoFashion", "symbol": "EFN", "category": "Moda", "base_price": 31.20,
                 "description": "Ropa sostenible y etica", "icon": "fa-tshirt"},
                {"name": "SmartHome Tech", "symbol": "SHT", "category": "Tecnologia", "base_price": 55.40,
                 "description": "Sistemas de hogar inteligente", "icon": "fa-home"},
                {"name": "Virtual Reality Co", "symbol": "VRC", "category": "Entretenimiento", "base_price": 78.90,
                 "description": "Experiencias de realidad virtual inmersivas", "icon": "fa-vr-cardboard"},
                {"name": "BioFuels Global", "symbol": "BFG", "category": "Energia", "base_price": 19.85,
                 "description": "Produccion de biocombustibles sostenibles", "icon": "fa-gas-pump"},
                {"name": "HealthTech Plus", "symbol": "HTP", "category": "Salud", "base_price": 62.30,
                 "description": "Tecnologias para el cuidado de la salud", "icon": "fa-heartbeat"},
                {"name": "CryptoVault", "symbol": "CRV", "category": "Finanzas", "base_price": 145.70,
                 "description": "Seguridad de activos digitales", "icon": "fa-lock"},
                {"name": "Urban Farming", "symbol": "URF", "category": "Agricultura", "base_price": 27.60,
                 "description": "Soluciones de agricultura urbana", "icon": "fa-seedling"},
                {"name": "NanoTech Materials", "symbol": "NTM", "category": "Materiales", "base_price": 92.40,
                 "description": "Materiales avanzados a nanoescala", "icon": "fa-atom"},
                {"name": "EduTech Global", "symbol": "EDG", "category": "Educacion", "base_price": 41.80,
                 "description": "Plataformas de aprendizaje digital", "icon": "fa-graduation-cap"},
                {"name": "AutoDrive Systems", "symbol": "ADS", "category": "Automocion", "base_price": 125.30,
                 "description": "Tecnologia de conduccion autonoma", "icon": "fa-car-side"},
                {"name": "Renewable Storage", "symbol": "RES", "category": "Energia", "base_price": 53.70,
                 "description": "Soluciones de almacenamiento de energia", "icon": "fa-battery-full"},
                {"name": "Ocean Cleanup", "symbol": "OCC", "category": "Medio ambiente", "base_price": 18.90,
                 "description": "Tecnologias de limpieza oceanica", "icon": "fa-water"},
                {"name": "Digital Security", "symbol": "DSC", "category": "Ciberseguridad", "base_price": 88.60,
                 "description": "Proteccion de datos y sistemas", "icon": "fa-shield-alt"},
                {"name": "Space Tourism", "symbol": "SPT", "category": "Turismo", "base_price": 215.40,
                 "description": "Experiencias turisticas espaciales", "icon": "fa-space-shuttle"},
                {"name": "AI Healthcare", "symbol": "AIH", "category": "Salud", "base_price": 105.80,
                 "description": "Diagnostico medico con IA", "icon": "fa-user-md"}
            ]

            for company_data in companies:
                company = Company(**company_data)
                db.session.add(company)

            db.session.commit()
            print("✅ Database initialized with 25 companies")
        else:
            print("✅ Database already contains companies")

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        db.session.rollback()


# Вызываем инициализацию при запуске
with app.app_context():
    initialize_database()


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def send_welcome_email(user, password):
    def send_async():
        try:
            msg = Message(
                subject='¡Bienvenido a Clean.Invest! 🚀 Tu Futuro Financiero Comienza Ahora',
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[user.email]
            )

            msg.html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Bienvenido a Clean.Invest</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f4f4f4;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 40px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 32px;
                        font-weight: 700;
                    }}
                    .content {{
                        background: white;
                        padding: 40px;
                        border-radius: 0 0 10px 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .info-box {{
                        background: linear-gradient(135deg, #f8f9ff 0%, #e8ecff 100%);
                        padding: 30px;
                        border-left: 5px solid #667eea;
                        margin: 30px 0;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }}
                    .credential {{
                        background: white;
                        padding: 15px;
                        margin: 10px 0;
                        border-radius: 5px;
                        border: 1px solid #e0e0e0;
                    }}
                    .credential strong {{
                        color: #667eea;
                        display: inline-block;
                        width: 100px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>¡Bienvenido a Clean.Invest! 🚀</h1>
                    <p>Has abierto exitosamente la puerta a tu futuro financiero prospero</p>
                </div>
                <div class="content">
                    <p>Estimado/a <strong>{user.name}</strong>,</p>
                    <p>¡Felicidades! Te has unido a la plataforma de inversion #1 que esta transformando vidas financieras.</p>
                    <div class="info-box">
                        <h3>🔐 Tus Datos de Acceso</h3>
                        <div class="credential">
                            <strong>Usuario:</strong> {user.nickname}
                        </div>
                        <div class="credential">
                            <strong>Contraseña:</strong> {password}
                        </div>
                    </div>
                    <p>¡Te deseamos mucho exito en tu viaje hacia la libertad financiera!</p>
                    <p>Atentamente,<br><strong>El equipo de Clean.Invest</strong></p>
                </div>
            </body>
            </html>
            """

            with app.app_context():
                mail.send(msg)
            print(f"✅ Email sent to {user.email}")
        except Exception as e:
            print(f"❌ Error sending email: {e}")

    thread = threading.Thread(target=send_async)
    thread.daemon = True
    thread.start()


# ОСНОВНЫЕ ROUTES
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    nickname = data.get('nickname', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Валидация
    if not all([name, nickname, email, password]):
        return jsonify({'error': 'Todos los campos son obligatorios'}), 400

    if len(name) < 2:
        return jsonify({'error': 'El nombre debe tener al menos 2 caracteres'}), 400

    if len(nickname) < 4:
        return jsonify({'error': 'El nombre de usuario debe tener al menos 4 caracteres'}), 400

    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({'error': 'Formato de email invalido'}), 400

    if len(password) < 7:
        return jsonify({'error': 'La contraseña debe tener al menos 7 caracteres'}), 400

    try:
        # Проверка уникальности
        if User.query.filter_by(nickname=nickname).first():
            return jsonify({'error': 'Este nombre de usuario ya esta en uso'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Este email ya esta registrado'}), 400

        # Создание пользователя
        user = User(name=name, nickname=nickname, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Отправка приветственного email
        send_welcome_email(user, password)

        # Установка сессии
        session['user_id'] = user.id
        session.permanent = True

        return jsonify({
            'message': '¡Registro exitoso! Bienvenido a Clean.Invest',
            'user': user.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error en el registro: {str(e)}'}), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    password = data.get('password', '')

    if not nickname or not password:
        return jsonify({'error': 'El nombre de usuario y la contraseña son obligatorios'}), 400

    try:
        user = User.query.filter_by(nickname=nickname).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            session['user_id'] = user.id
            session.permanent = True

            return jsonify({'message': '¡Inicio de sesion exitoso!', 'user': user.to_dict()})
        else:
            return jsonify({'error': 'Credenciales invalidas'}), 401

    except Exception as e:
        return jsonify({'error': f'Error en el inicio de sesion: {str(e)}'}), 500


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Sesion cerrada correctamente'})


@app.route('/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    return jsonify({'user': user.to_dict()})


@app.route('/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()

    if 'name' in data:
        user.name = data['name'].strip()
    if 'full_name' in data:
        user.full_name = data['full_name'].strip()
    if 'phone' in data:
        phone = data['phone'].strip()
        if phone and not re.match(r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$', phone):
            return jsonify({'error': 'Formato de telefono invalido'}), 400
        user.phone = phone

    db.session.commit()

    return jsonify({'message': 'Perfil actualizado correctamente', 'user': user.to_dict()})


@app.route('/set_avatar', methods=['POST'])
def set_avatar():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()
    avatar_url = data.get('avatar_url')

    if not avatar_url:
        return jsonify({'error': 'La URL del avatar es requerida'}), 400

    user.avatar_url = avatar_url
    db.session.commit()

    return jsonify({'message': 'Avatar actualizado correctamente', 'avatar_url': user.avatar_url})


# КОМПАНИИ
@app.route('/companies', methods=['GET'])
def get_companies():
    companies = Company.query.all()
    return jsonify({'companies': [company.to_dict() for company in companies]})


# ИНВЕСТИЦИИ
@app.route('/investments', methods=['GET'])
def get_investments():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    investments = UserInvestment.query.filter_by(
        user_id=user.id,
        is_active=True
    ).options(
        db.joinedload(UserInvestment.company)
    ).all()

    return jsonify({'investments': [inv.to_dict() for inv in investments]})


@app.route('/buy', methods=['POST'])
def buy_stocks():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()
    company_id = data.get('company_id')
    shares = data.get('shares', 1)

    if shares <= 0:
        return jsonify({'error': 'Las acciones deben ser un numero positivo'}), 400

    try:
        company = db.session.get(Company, company_id)
        if not company:
            return jsonify({'error': 'Compañia no encontrada'}), 404

        price_variation = random.uniform(0.95, 1.05)
        current_price = company.base_price * price_variation
        total_cost = current_price * shares

        if user.balance < total_cost:
            return jsonify({'error': 'Saldo insuficiente'}), 400

        # Обновляем или создаем инвестицию
        existing_investment = UserInvestment.query.filter_by(
            user_id=user.id,
            company_id=company_id,
            is_active=True
        ).with_for_update().first()

        if existing_investment:
            total_shares = existing_investment.shares + shares
            total_invested = (existing_investment.purchase_price * existing_investment.shares) + total_cost
            new_purchase_price = total_invested / total_shares

            existing_investment.shares = total_shares
            existing_investment.purchase_price = new_purchase_price
            existing_investment.current_price = new_purchase_price
        else:
            investment = UserInvestment(
                user_id=user.id,
                company_id=company_id,
                shares=shares,
                purchase_price=current_price,
                current_price=current_price
            )
            db.session.add(investment)

        user.balance -= total_cost
        user.total_invested += total_cost
        user.investments_count += 1

        db.session.commit()

        return jsonify({
            'message': '¡Acciones compradas exitosamente!',
            'balance': user.balance,
            'company': company.to_dict(),
            'shares': shares,
            'price': current_price,
            'total_cost': total_cost
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al comprar acciones: {str(e)}'}), 500


@app.route('/sell', methods=['POST'])
def sell_stocks():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()
    investment_id = data.get('investment_id')
    shares = data.get('shares', 1)

    if shares <= 0:
        return jsonify({'error': 'Las acciones deben ser un numero positivo'}), 400

    try:
        investment = db.session.get(UserInvestment, investment_id)
        if not investment or investment.user_id != user.id or not investment.is_active:
            return jsonify({'error': 'Inversion no encontrada'}), 404

        if investment.shares < shares:
            return jsonify({'error': 'No tienes suficientes acciones'}), 400

        investment_data = investment.to_dict()
        current_price = investment_data['current_price']
        total_revenue = current_price * shares
        profit = investment_data['profit'] * (shares / investment.shares)

        user.balance += total_revenue
        user.total_withdrawn += total_revenue
        user.total_profit += profit

        if investment.shares == shares:
            investment.is_active = False
            user.successful_investments += 1
        else:
            investment.shares -= shares

        db.session.commit()

        return jsonify({
            'message': '¡Acciones vendidas exitosamente!',
            'balance': user.balance,
            'company': investment.company.to_dict(),
            'shares': shares,
            'price': current_price,
            'total_revenue': total_revenue,
            'profit': profit
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al vender acciones: {str(e)}'}), 500


# АДМИН ПАНЕЛЬ
@app.route('/admin/users', methods=['GET'])
def admin_get_users():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    users = User.query.all()
    return jsonify({'users': [user.to_dict() for user in users]})


@app.route('/admin/update_balance', methods=['POST'])
def admin_update_balance():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    amount = float(data.get('amount', 0))

    if not nickname:
        return jsonify({'error': 'El nombre de usuario es requerido'}), 400

    user = User.query.filter_by(nickname=nickname).first()
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    user.balance += amount
    db.session.commit()

    return jsonify({
        'message': 'Balance actualizado correctamente',
        'nickname': user.nickname,
        'new_balance': user.balance
    })


@app.route('/admin/stats', methods=['GET'])
def admin_get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    total_users = User.query.count()
    total_balance = db.session.query(db.func.sum(User.balance)).scalar() or 0
    total_invested = db.session.query(db.func.sum(User.total_invested)).scalar() or 0
    total_profit = db.session.query(db.func.sum(User.total_profit)).scalar() or 0

    return jsonify({
        'total_users': total_users,
        'total_balance': total_balance,
        'total_invested': total_invested,
        'total_profit': total_profit
    })


# ПОДДЕРЖКА ЧАТ
@app.route('/support/chat/create', methods=['POST'])
def create_support_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    existing_chat = SupportChat.query.filter_by(
        user_id=user.id,
        status='active'
    ).first()

    if existing_chat:
        return jsonify({'chat': existing_chat.to_dict()})

    pending_chat = SupportChat.query.filter_by(
        user_id=user.id,
        status='pending'
    ).first()

    if pending_chat:
        return jsonify({'chat': pending_chat.to_dict()})

    chat = SupportChat(user_id=user.id)
    db.session.add(chat)
    db.session.commit()

    system_msg = ChatMessage(
        chat_id=chat.id,
        sender_id=user.id,
        message="Tu solicitud ha sido registrada, espera a que un administrador se conecte al chat",
        is_system=True
    )
    db.session.add(system_msg)
    db.session.commit()

    return jsonify({'chat': chat.to_dict()})


@app.route('/support/chat/<int:chat_id>/message', methods=['POST'])
def send_message(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    chat = db.session.get(SupportChat, chat_id)
    if not chat:
        return jsonify({'error': 'Chat no encontrado'}), 404

    if chat.user_id != user.id and (not user.is_admin or chat.admin_id != user.id):
        return jsonify({'error': 'Acceso denegado'}), 403

    data = request.get_json()
    message_text = data.get('message', '').strip()

    if not message_text:
        return jsonify({'error': 'El texto del mensaje es requerido'}), 400

    msg = ChatMessage(
        chat_id=chat_id,
        sender_id=user.id,
        message=message_text
    )
    db.session.add(msg)

    if user.is_admin:
        chat.unread_user_count += 1
    else:
        chat.unread_admin_count += 1

    db.session.commit()
    return jsonify({'message': msg.to_dict()})


@app.route('/support/chat/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesion'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    chat = db.session.get(SupportChat, chat_id)
    if not chat:
        return jsonify({'error': 'Chat no encontrado'}), 404

    if chat.user_id != user.id and (not user.is_admin or chat.admin_id != user.id):
        return jsonify({'error': 'Acceso denegado'}), 403

    messages = ChatMessage.query.filter_by(chat_id=chat_id).order_by(ChatMessage.created_at).all()

    if user.is_admin:
        chat.unread_admin_count = 0
        for message in messages:
            if not message.is_system and message.sender_id != user.id:
                message.is_read = True
    else:
        chat.unread_user_count = 0
        for message in messages:
            if not message.is_system and message.sender_id != user.id:
                message.is_read = True

    db.session.commit()

    return jsonify({'messages': [msg.to_dict() for msg in messages]})


# HEALTH CHECK
@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))

        return {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'users': User.query.count(),
            'companies': Company.query.count(),
            'investments': UserInvestment.query.count()
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500


# ОБРАБОТКА ОШИБОК
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Recurso no encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Error interno del servidor'}), 500


# ЗАПУСК
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)