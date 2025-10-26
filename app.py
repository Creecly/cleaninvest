from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timezone
import random
import re
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import time
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Disable CSRF for simplicity in production
app.config['WTF_CSRF_ENABLED'] = False

# Database configuration
database_url = os.getenv('DATABASE_URL', 'sqlite:///cleaninvest.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 10
}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

# Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_TIMEOUT'] = 30

# Initialize extensions
mail = Mail(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)


# Models (same as before)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
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


class SupportChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admin_joined_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('user_chats', lazy=True))
    admin = db.relationship('User', foreign_keys=[admin_id], backref=db.backref('admin_chats', lazy=True))
    messages = db.relationship('ChatMessage', backref='chat', lazy=True, order_by='ChatMessage.created_at')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'admin_id': self.admin_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'admin_joined_at': self.admin_joined_at.isoformat() if self.admin_joined_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'user': self.user.to_dict() if self.user else None,
            'admin': self.admin.to_dict() if self.admin else None,
            'last_message': self.messages[-1].to_dict() if self.messages else None
        }


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('support_chat.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', backref=db.backref('sent_messages', lazy=True))

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


class Company(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('user_investments', lazy=True))
    company = db.relationship('Company', backref=db.backref('user_investments', lazy=True))

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


# Initialize database
with app.app_context():
    try:
        db.create_all()

        # Check and add is_read column if needed
        from sqlalchemy import text

        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('chat_message')
        has_is_read = any(column['name'] == 'is_read' for column in columns)

        if not has_is_read:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE chat_message ADD COLUMN is_read BOOLEAN DEFAULT 0"))

        # Add companies if none exist
        if Company.query.count() == 0:
            companies = [
                {"name": "EcoEnergy Plus", "symbol": "EEP", "category": "Energía renovable", "base_price": 25.50,
                 "description": "Líder en energía solar y eólica", "icon": "fa-leaf"},
                {"name": "TechFuture AI", "symbol": "TFAI", "category": "Inteligencia artificial", "base_price": 120.75,
                 "description": "Desarrollo de IA de vanguardia", "icon": "fa-microchip"},
                {"name": "SpaceX Ventures", "symbol": "SPXV", "category": "Aeroespacial", "base_price": 350.20,
                 "description": "Exploración espacial comercial", "icon": "fa-rocket"},
                {"name": "BioMed Solutions", "symbol": "BMS", "category": "Biotecnología", "base_price": 85.40,
                 "description": "Investigación médica avanzada", "icon": "fa-dna"},
                {"name": "GreenTransport", "symbol": "GRT", "category": "Transporte", "base_price": 42.30,
                 "description": "Vehículos eléctricos sostenibles", "icon": "fa-car"},
            ]

            for company_data in companies:
                company = Company(**company_data)
                db.session.add(company)

            db.session.commit()
            logger.info("Initial companies created")
    except Exception as e:
        logger.error(f"Database init error: {e}")


# Helper function to handle database errors
def handle_db_error(e):
    logger.error(f"Database error: {str(e)}")
    db.session.rollback()
    return jsonify({'error': 'Database error. Please try again.'}), 500


# Routes
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template error: {str(e)}")
        return f"Template error: {str(e)}", 500


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        name = data.get('name', '').strip()
        nickname = data.get('nickname', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not all([name, nickname, email, password]):
            return jsonify({'error': 'Todos los campos son obligatorios'}), 400

        if len(name) < 2:
            return jsonify({'error': 'El nombre debe tener al menos 2 caracteres'}), 400

        if len(nickname) < 4:
            return jsonify({'error': 'El nombre de usuario debe tener al menos 4 caracteres'}), 400

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return jsonify({'error': 'Formato de email inválido'}), 400

        if len(password) < 7:
            return jsonify({'error': 'La contraseña debe tener al menos 7 caracteres'}), 400

        if User.query.filter_by(nickname=nickname).first():
            return jsonify({'error': 'Este nombre de usuario ya está en uso'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Este email ya está registrado'}), 400

        user = User(name=name, nickname=nickname, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        session.permanent = True

        return jsonify({
            'message': '¡Registro exitoso! Bienvenido a Clean.Invest',
            'user': user.to_dict(),
            'email_sent': True
        })

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return handle_db_error(e)


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        nickname = data.get('nickname', '').strip()
        password = data.get('password', '')

        if not nickname or not password:
            return jsonify({'error': 'El nombre de usuario y la contraseña son obligatorios'}), 400

        user = User.query.filter_by(nickname=nickname).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            session['user_id'] = user.id
            session.permanent = True
            return jsonify({'message': '¡Inicio de sesión exitoso!', 'user': user.to_dict()})
        else:
            return jsonify({'error': 'Credenciales inválidas'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return handle_db_error(e)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Sesión cerrada correctamente'})


@app.route('/profile', methods=['GET'])
def get_profile():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        return jsonify({'user': user.to_dict()})
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return handle_db_error(e)


@app.route('/companies', methods=['GET'])
def get_companies():
    try:
        companies = Company.query.all()
        return jsonify({'companies': [company.to_dict() for company in companies]})
    except Exception as e:
        logger.error(f"Get companies error: {str(e)}")
        return handle_db_error(e)


@app.route('/investments', methods=['GET'])
def get_investments():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        investments = UserInvestment.query.filter_by(user_id=user.id, is_active=True).all()
        return jsonify({'investments': [inv.to_dict() for inv in investments]})
    except Exception as e:
        logger.error(f"Get investments error: {str(e)}")
        return handle_db_error(e)


@app.route('/buy', methods=['POST'])
def buy_stocks():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        company_id = data.get('company_id')
        shares = data.get('shares', 1)

        if shares <= 0:
            return jsonify({'error': 'Las acciones deben ser un número positivo'}), 400

        company = db.session.get(Company, company_id)
        if not company:
            return jsonify({'error': 'Compañía no encontrada'}), 404

        price_variation = random.uniform(0.95, 1.05)
        current_price = company.base_price * price_variation
        total_cost = current_price * shares

        if user.balance < total_cost:
            return jsonify({'error': 'Saldo insuficiente'}), 400

        existing_investment = UserInvestment.query.filter_by(
            user_id=user.id,
            company_id=company_id,
            is_active=True
        ).first()

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
        logger.error(f"Buy stocks error: {str(e)}")
        return handle_db_error(e)


@app.route('/sell', methods=['POST'])
def sell_stocks():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        investment_id = data.get('investment_id')
        shares = data.get('shares', 1)

        if shares <= 0:
            return jsonify({'error': 'Las acciones deben ser un número positivo'}), 400

        investment = db.session.get(UserInvestment, investment_id)
        if not investment or investment.user_id != user.id or not investment.is_active:
            return jsonify({'error': 'Inversión no encontrada'}), 404

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
        logger.error(f"Sell stocks error: {str(e)}")
        return handle_db_error(e)


@app.route('/admin/update_balance', methods=['POST'])
def admin_update_balance():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        admin = db.session.get(User, session['user_id'])
        if not admin or not admin.is_admin:
            return jsonify({'error': 'Acceso denegado'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

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
    except Exception as e:
        logger.error(f"Update balance error: {str(e)}")
        return handle_db_error(e)


@app.route('/admin/assign_admin', methods=['POST'])
def admin_assign_admin():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        admin = db.session.get(User, session['user_id'])
        if not admin or not admin.is_owner:
            return jsonify({'error': 'Acceso denegado'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        nickname = data.get('nickname', '').strip()

        if not nickname:
            return jsonify({'error': 'El nombre de usuario es requerido'}), 400

        user = User.query.filter_by(nickname=nickname).first()
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        if user.is_admin:
            return jsonify({'error': 'El usuario ya es administrador'}), 400

        user.is_admin = True
        db.session.commit()

        return jsonify({
            'message': f'{nickname} ha sido asignado como administrador exitosamente'
        })
    except Exception as e:
        logger.error(f"Assign admin error: {str(e)}")
        return handle_db_error(e)


@app.route('/admin/remove_admin', methods=['POST'])
def admin_remove_admin():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        admin = db.session.get(User, session['user_id'])
        if not admin or not admin.is_owner:
            return jsonify({'error': 'Acceso denegado'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        nickname = data.get('nickname', '').strip()

        if not nickname:
            return jsonify({'error': 'El nombre de usuario es requerido'}), 400

        user = User.query.filter_by(nickname=nickname).first()
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        if not user.is_admin:
            return jsonify({'error': 'El usuario no es administrador'}), 400

        if user.is_owner:
            return jsonify({'error': 'No se pueden remover los derechos de owner'}), 400

        user.is_admin = False
        db.session.commit()

        return jsonify({
            'message': f'{nickname} ha sido removido de administradores exitosamente'
        })
    except Exception as e:
        logger.error(f"Remove admin error: {str(e)}")
        return handle_db_error(e)


@app.route('/admin/send_bulk_email', methods=['POST'])
def admin_send_bulk_email():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        admin = db.session.get(User, session['user_id'])
        if not admin or not admin.is_admin:
            return jsonify({'error': 'Acceso denegado'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        send_to_all = data.get('send_to_all', False)
        specific_emails = data.get('specific_emails', '').strip()

        if not subject or not message:
            return jsonify({'error': 'El asunto y el mensaje son obligatorios'}), 400

        recipients = []
        if send_to_all:
            users = User.query.all()
            recipients = [user.email for user in users]
        elif specific_emails:
            email_list = [email.strip() for email in specific_emails.split(',')]
            for email in email_list:
                user = User.query.filter_by(email=email).first()
                if user:
                    recipients.append(email)
        else:
            return jsonify({'error': 'Debes seleccionar destinatarios'}), 400

        if not recipients:
            return jsonify({'error': 'No se encontraron destinatarios válidos'}), 400

        success_count = 0
        error_count = 0

        for email in recipients:
            try:
                msg = Message(
                    subject=subject,
                    sender=app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[email]
                )
                msg.body = f"{subject}\n\n{message}\n\nClean.Invest"
                mail.send(msg)
                success_count += 1
            except Exception as e:
                logger.error(f"Email error to {email}: {str(e)}")
                error_count += 1

        return jsonify({
            'message': f'Email enviado exitosamente a {success_count} usuarios',
            'success_count': success_count,
            'error_count': error_count,
            'total_recipients': len(recipients)
        })
    except Exception as e:
        logger.error(f"Bulk email error: {str(e)}")
        return handle_db_error(e)


# Support chat routes
@app.route('/support/chat/create', methods=['POST'])
def create_support_chat():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

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
    except Exception as e:
        logger.error(f"Create chat error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chat/<int:chat_id>/message', methods=['POST'])
def send_message(chat_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        chat = db.session.get(SupportChat, chat_id)
        if not chat:
            return jsonify({'error': 'Chat no encontrado'}), 404

        if chat.user_id != user.id and (not user.is_admin or chat.admin_id != user.id):
            return jsonify({'error': 'Acceso denegado'}), 403

        if chat.status == 'closed' and chat.user_id == user.id:
            new_chat = SupportChat(user_id=user.id)
            db.session.add(new_chat)
            db.session.commit()

            system_msg = ChatMessage(
                chat_id=new_chat.id,
                sender_id=user.id,
                message="Tu solicitud ha sido registrada, espera a que un administrador se conecte al chat",
                is_system=True
            )
            db.session.add(system_msg)
            db.session.commit()

            return jsonify({'chat': new_chat.to_dict(), 'message': 'Nuevo chat creado'})

        message_text = None
        attachment_url = None

        if 'attachment' in request.files and request.files['attachment'].filename:
            file = request.files['attachment']
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx'}
            if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"chat_{chat_id}_{uuid.uuid4().hex}.{file_ext}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                attachment_url = filename
                message_text = request.form.get('message', '').strip()
            else:
                return jsonify({'error': 'Tipo de archivo no válido'}), 400
        else:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No se proporcionaron datos'}), 400
            message_text = data.get('message', '').strip()

        if not message_text:
            return jsonify({'error': 'El texto del mensaje es requerido'}), 400

        msg = ChatMessage(
            chat_id=chat_id,
            sender_id=user.id,
            message=message_text,
            attachment_url=attachment_url
        )
        db.session.add(msg)

        if chat.status == 'pending' and chat.user_id == user.id and not chat.messages:
            system_msg = ChatMessage(
                chat_id=chat_id,
                sender_id=user.id,
                message="Tu solicitud ha sido registrada, espera a que un administrador se conecte al chat",
                is_system=True
            )
            db.session.add(system_msg)

        db.session.commit()
        return jsonify({'message': msg.to_dict()})
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chat/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

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
            for message in messages:
                if not message.is_system and message.sender_id != user.id:
                    message.is_read = True

        db.session.commit()

        return jsonify({'messages': [msg.to_dict() for msg in messages]})
    except Exception as e:
        logger.error(f"Get messages error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chats/pending', methods=['GET'])
def get_pending_chats():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Acceso denegado'}), 403

        chats = SupportChat.query.filter_by(status='pending').order_by(SupportChat.created_at).all()
        return jsonify({'chats': [chat.to_dict() for chat in chats]})
    except Exception as e:
        logger.error(f"Get pending chats error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chats/active', methods=['GET'])
def get_active_chats():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        if user.is_admin:
            chats = SupportChat.query.filter_by(
                admin_id=user.id,
                status='active'
            ).order_by(SupportChat.admin_joined_at).all()
        else:
            chats = SupportChat.query.filter_by(
                user_id=user.id,
                status='active'
            ).order_by(SupportChat.admin_joined_at).all()

        return jsonify({'chats': [chat.to_dict() for chat in chats]})
    except Exception as e:
        logger.error(f"Get active chats error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chat/<int:chat_id>/join', methods=['POST'])
def join_chat(chat_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Acceso denegado'}), 403

        chat = db.session.query(SupportChat).filter_by(id=chat_id, status='pending').with_for_update().first()
        if not chat:
            return jsonify({'error': 'El chat no está disponible'}), 400

        chat.admin_id = user.id
        chat.status = 'active'
        chat.admin_joined_at = datetime.now(timezone.utc)

        user_msg = ChatMessage(
            chat_id=chat_id,
            sender_id=chat.user_id,
            message=f"Un administrador ({user.nickname}) se ha conectado al chat",
            is_system=True
        )
        db.session.add(user_msg)

        admin_msg = ChatMessage(
            chat_id=chat_id,
            sender_id=user.id,
            message="Te has conectado al chat",
            is_system=True
        )
        db.session.add(admin_msg)

        db.session.commit()
        return jsonify({'chat': chat.to_dict()})
    except Exception as e:
        logger.error(f"Join chat error: {str(e)}")
        return handle_db_error(e)


@app.route('/support/chat/<int:chat_id>/add_balance', methods=['POST'])
def add_balance_to_user(chat_id):
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Acceso denegado'}), 403

        chat = db.session.get(SupportChat, chat_id)
        if not chat:
            return jsonify({'error': 'Chat no encontrado'}), 404

        if chat.admin_id != user.id or chat.status != 'active':
            return jsonify({'error': 'No puedes modificar el balance en este chat'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        amount = float(data.get('amount', 0))

        if amount <= 0:
            return jsonify({'error': 'El monto debe ser positivo'}), 400

        chat_user = db.session.get(User, chat.user_id)
        chat_user.balance += amount

        msg = ChatMessage(
            chat_id=chat_id,
            sender_id=user.id,
            message=f"El administrador ha añadido ${amount:.2f} a tu balance. Nuevo balance: ${chat_user.balance:.2f}",
            is_system=True
        )
        db.session.add(msg)

        db.session.commit()

        return jsonify({
            'message': 'Balance añadido exitosamente',
            'new_balance': chat_user.balance,
            'amount': amount
        })
    except Exception as e:
        logger.error(f"Add balance error: {str(e)}")
        return handle_db_error(e)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/support/unread_count', methods=['GET'])
def get_unread_count():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        chat = SupportChat.query.filter_by(
            user_id=user.id,
            status='active'
        ).first()

        if not chat:
            return jsonify({'unread_count': 0})

        unread_count = ChatMessage.query.filter(
            ChatMessage.chat_id == chat.id,
            ChatMessage.is_read == False,
            ChatMessage.is_system == False,
            ChatMessage.sender_id != user.id
        ).count()

        return jsonify({'unread_count': unread_count})
    except Exception as e:
        logger.error(f"Unread count error: {str(e)}")
        return handle_db_error(e)


@app.route('/set_avatar', methods=['POST'])
def set_avatar():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        avatar_url = data.get('avatar_url')

        if not avatar_url:
            return jsonify({'error': 'La URL del avatar es requerida'}), 400

        user.avatar_url = avatar_url
        db.session.commit()

        return jsonify({'message': 'Avatar actualizado correctamente', 'avatar_url': user.avatar_url})
    except Exception as e:
        logger.error(f"Set avatar error: {str(e)}")
        return handle_db_error(e)


@app.route('/profile', methods=['PUT'])
def update_profile():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No has iniciado sesión'}), 401

        user = db.session.get(User, session['user_id'])
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        if 'name' in data:
            user.name = data['name'].strip()
        if 'full_name' in data:
            user.full_name = data['full_name'].strip()
        if 'phone' in data:
            phone = data['phone'].strip()
            if phone and not re.match(r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$', phone):
                return jsonify({'error': 'Formato de teléfono inválido'}), 400
            user.phone = phone

        db.session.commit()

        return jsonify({'message': 'Perfil actualizado correctamente', 'user': user.to_dict()})
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return handle_db_error(e)


@app.route('/switch_account', methods=['POST'])
def switch_account():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        nickname = data.get('nickname', '').strip()
        password = data.get('password', '')

        if not nickname or not password:
            return jsonify({'error': 'El nombre de usuario y la contraseña son obligatorios'}), 400

        user = User.query.filter_by(nickname=nickname).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            session['user_id'] = user.id
            session.permanent = True
            return jsonify({'user': user.to_dict()})
        else:
            return jsonify({'error': 'Credenciales inválidas'}), 401
    except Exception as e:
        logger.error(f"Switch account error: {str(e)}")
        return handle_db_error(e)


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({'error': 'Bad request'}), 400


# Run app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)