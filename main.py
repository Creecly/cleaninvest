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

# Загружаем переменные окружения из .env файла
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_production'  # Замените на свой секретный ключ

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///cleaninvest.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Настройки для почты
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Инициализация почты
mail = Mail(app)

# Создаем папку для загрузок, если она не существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# Модель пользователя
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
        # Автоматическое назначение прав owner если пароль содержит специальную комбинацию
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
    is_read = db.Column(db.Boolean, default=False)  # Добавлено для отслеживания прочитанных сообщений

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


# Функция для отправки приветственного email
def send_welcome_email(user, password):
    try:
        msg = Message(
            subject='¡Bienvenido a Clean.Invest! 🚀 Tu Futuro Financiero Comienza Ahora',
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=[user.email]
        )

        # HTML шаблон письма на испанском
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
                .header p {{
                    margin: 10px 0 0 0;
                    font-size: 18px;
                    opacity: 0.9;
                }}
                .content {{
                    background: white;
                    padding: 40px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .welcome-text {{
                    font-size: 18px;
                    color: #555;
                    margin-bottom: 30px;
                }}
                .info-box {{
                    background: linear-gradient(135deg, #f8f9ff 0%, #e8ecff 100%);
                    padding: 30px;
                    border-left: 5px solid #667eea;
                    margin: 30px 0;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .info-box h3 {{
                    color: #667eea;
                    margin-top: 0;
                    font-size: 20px;
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
                .button {{
                    display: inline-block;
                    padding: 15px 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 30px;
                    margin: 30px 0;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                    transition: all 0.3s ease;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
                }}
                .features {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 30px 0;
                }}
                .feature {{
                    padding: 20px;
                    background: #f8f9ff;
                    border-radius: 8px;
                    text-align: center;
                }}
                .feature-icon {{
                    font-size: 30px;
                    color: #667eea;
                    margin-bottom: 10px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    color: #666;
                    font-size: 14px;
                    padding-top: 20px;
                    border-top: 1px solid #e0e0e0;
                }}
                .warning {{
                    background: #fff3cd;
                    color: #856404;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    border-left: 4px solid #ffc107;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>¡Bienvenido a Clean.Invest! 🚀</h1>
                <p>Has abierto exitosamente la puerta a tu futuro financiero próspero</p>
            </div>

            <div class="content">
                <p class="welcome-text">
                    Estimado/a <strong>{user.name}</strong>,
                </p>

                <p class="welcome-text">
                    ¡Felicidades! Te has unido a la plataforma de inversión #1 que está transformando vidas financieras. 
                    En Clean.Invest, no solo inviertes tu dinero, inviertes en tu futuro.
                </p>

                <div class="info-box">
                    <h3>🔐 Tus Datos de Acceso</h3>
                    <div class="credential">
                        <strong>Usuario:</strong> {user.nickname}
                    </div>
                    <div class="credential">
                        <strong>Contraseña:</strong> {password}
                    </div>
                </div>

                <div class="warning">
                    <strong>⚠️ Importante:</strong> Guarda esta información en un lugar seguro. 
                    No compartas tus credenciales con nadie.
                </div>

                <div class="features">
                    <div class="feature">
                        <div class="feature-icon">📈</div>
                        <h4>Rendimientos Excepcionales</h4>
                        <p>Promedio del 18% anual</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🛡️</div>
                        <h4>Seguridad Máxima</h4>
                        <p>Protección de nivel bancario</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🤖</div>
                        <h4>IA Avanzada</h4>
                        <p>Algoritmos inteligentes</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">💬</div>
                        <h4>Soporte 24/7</h4>
                        <p>Ayuda cuando la necesites</p>
                    </div>
                </div>

                <p style="text-align: center;">
                    <a href="http://localhost:5000" class="button">Comenzar a Invertir Ahora</a>
                </p>

                <p style="text-align: center; color: #666; font-style: italic;">
                    "El mejor momento para invertir fue ayer. El segundo mejor momento es ahora."
                </p>

                <p>
                    Tu cuenta ya ha sido creada con un balance inicial de <strong>${user.balance:.2f}</strong> 
                    para que comiences tu viaje de inversión inmediatamente.
                </p>

                <p>
                    ¿Necesitas ayuda? Nuestro equipo de soporte está disponible 24/7 para asistirte en cada paso.
                </p>

                <p>
                    ¡Te deseamos mucho éxito en tu viaje hacia la libertad financiera!
                </p>

                <p style="margin-top: 30px;">
                    Atentamente,<br>
                    <strong>El equipo de Clean.Invest</strong><br>
                    <em>Tu socio en el camino hacia la prosperidad</em>
                </p>
            </div>

            <div class="footer">
                <p>© 2024 Clean.Invest - Todos los derechos reservados</p>
                <p>Este es un correo automático, por favor no responda a este mensaje.</p>
                <p>Si tienes preguntas, contacta a nuestro soporte: support@cleaninvest.com</p>
            </div>
        </body>
        </html>
        """

        mail.send(msg)
        print(f"✅ Email enviado exitosamente a {user.email}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar email: {str(e)}")
        return False


# Функция для отправки уведомления о росте акции
def send_stock_growth_email(user, company, growth_percentage):
    try:
        msg = Message(
            subject='🚀 ¡ALERTA DE CRECIMIENTO! Tu inversión está disparada - Clean.Invest',
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=[user.email]
        )

        # HTML шаблон письма о росте акции
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Alerta de Crecimiento - Clean.Invest</title>
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
                .alert-header {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    padding: 40px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    animation: pulse 2s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.02); }}
                    100% {{ transform: scale(1); }}
                }}
                .alert-header h1 {{
                    margin: 0;
                    font-size: 32px;
                    font-weight: 700;
                }}
                .alert-header p {{
                    margin: 10px 0 0 0;
                    font-size: 20px;
                    opacity: 0.9;
                }}
                .content {{
                    background: white;
                    padding: 40px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .growth-box {{
                    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
                    padding: 30px;
                    border-left: 5px solid #10b981;
                    margin: 30px 0;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    text-align: center;
                }}
                .growth-percentage {{
                    font-size: 48px;
                    font-weight: 700;
                    color: #10b981;
                    margin: 20px 0;
                }}
                .company-name {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 10px;
                }}
                .urgent-notice {{
                    background: #fef2f2;
                    color: #991b1b;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    border-left: 4px solid #ef4444;
                    font-weight: 600;
                }}
                .button {{
                    display: inline-block;
                    padding: 15px 40px;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 30px;
                    margin: 20px 0;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
                    transition: all 0.3s ease;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 30px 0;
                }}
                .stat {{
                    padding: 20px;
                    background: #f8f9ff;
                    border-radius: 8px;
                    text-align: center;
                }}
                .stat-value {{
                    font-size: 24px;
                    font-weight: 700;
                    color: #667eea;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    color: #666;
                    font-size: 14px;
                    padding-top: 20px;
                    border-top: 1px solid #e0e0e0;
                }}
            </style>
        </head>
        <body>
            <div class="alert-header">
                <h1>🚀 ¡ALERTA URGENTE!</h1>
                <p>Tu inversión está disparada</p>
            </div>

            <div class="content">
                <p>Estimado/a <strong>{user.name}</strong>,</p>

                <p>¡Tenemos noticias increíbles para ti! El mercado está experimentando un movimiento histórico y tus inversiones están beneficiándose enormemente.</p>

                <div class="growth-box">
                    <div class="company-name">{company.name}</div>
                    <div class="growth-percentage">+{growth_percentage}%</div>
                    <p style="font-size: 18px; color: #666;">CRECIMIENTO EXPONENCIAL</p>
                </div>

                <div class="urgent-notice">
                    ⚠️ <strong>AVISO URGENTE:</strong> El mercado es volátil y esta oportunidad puede no durar mucho. 
                    Te recomendamos considerar vender parte de tus acciones para asegurar tus ganancias mientras el mercado está estable.
                </div>

                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">📈 Máximo Histórico</div>
                        <p>Las acciones nunca han estado tan altas</p>
                    </div>
                    <div class="stat">
                        <div class="stat-value">⏰ Oportunidad Limitada</div>
                        <p>Actúa ahora antes de la corrección</p>
                    </div>
                </div>

                <p style="text-align: center;">
                    <a href="http://localhost:5000" class="button">Vender Acciones Ahora</a>
                </p>

                <p style="text-align: center; color: #666; font-style: italic;">
                    "En el mercado de valores, el tiempo es dinero. No dejes pasar esta oportunidad única."
                </p>

                <p>
                    Nuestros analistas predicen una posible corrección del mercado en las próximas horas. 
                    Los inversores inteligentes están asegurando sus ganancias ahora mismo.
                </p>

                <p>
                    Recuerda: <strong>Es mejor tomar ganancias seguras que arriesgarlo todo por un poco más.</strong>
                </p>

                <p style="margin-top: 30px;">
                    Atentamente,<br>
                    <strong>El equipo de Clean.Invest</strong><br>
                    <em>Tu guía en el camino hacia la prosperidad</em>
                </p>
            </div>

            <div class="footer">
                <p>© 2024 Clean.Invest - Todos los derechos reservados</p>
                <p>Este es un correo automático con información importante sobre tus inversiones</p>
                <p>Inversiones conllevan riesgos. Invierte responsablemente.</p>
            </div>
        </body>
        </html>
        """

        mail.send(msg)
        print(f"✅ Email de crecimiento enviado a {user.email}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar email de crecimiento: {str(e)}")
        return False


# Создаем таблицы при первом запуске
with app.app_context():
    # Проверяем, существует ли база данных
    db.create_all()

    # Проверяем, существует ли столбец is_read в таблице chat_message
    from sqlalchemy import text

    inspector = db.inspect(db.engine)

    # Проверяем, существует ли столбец is_read
    columns = inspector.get_columns('chat_message')
    has_is_read = any(column['name'] == 'is_read' for column in columns)

    if not has_is_read:
        # Добавляем столбец is_read, если его нет
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE chat_message ADD COLUMN is_read BOOLEAN DEFAULT 0"))
        print("✅ Столбец is_read добавлен в таблицу chat_message")

    # Проверяем, есть ли уже компании
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
            {"name": "CloudNet Systems", "symbol": "CNS", "category": "Tecnología", "base_price": 65.80,
             "description": "Soluciones de computación en la nube", "icon": "fa-cloud"},
            {"name": "FoodTech Innovations", "symbol": "FTI", "category": "Alimentos", "base_price": 38.90,
             "description": "Tecnología alimentaria sostenible", "icon": "fa-utensils"},
            {"name": "RoboTech Industries", "symbol": "RTI", "category": "Robótica", "base_price": 95.60,
             "description": "Automatización industrial avanzada", "icon": "fa-robot"},
            {"name": "WaterPure Solutions", "symbol": "WPS", "category": "Medio ambiente", "base_price": 22.75,
             "description": "Tecnologías de purificación de agua", "icon": "fa-tint"},
            {"name": "Quantum Computing", "symbol": "QCC", "category": "Tecnología", "base_price": 180.50,
             "description": "Computación cuántica de próxima generación", "icon": "fa-atom"},
            {"name": "EcoFashion", "symbol": "EFN", "category": "Moda", "base_price": 31.20,
             "description": "Ropa sostenible y ética", "icon": "fa-tshirt"},
            {"name": "SmartHome Tech", "symbol": "SHT", "category": "Tecnología", "base_price": 55.40,
             "description": "Sistemas de hogar inteligente", "icon": "fa-home"},
            {"name": "Virtual Reality Co", "symbol": "VRC", "category": "Entretenimiento", "base_price": 78.90,
             "description": "Experiencias de realidad virtual inmersivas", "icon": "fa-vr-cardboard"},
            {"name": "BioFuels Global", "symbol": "BFG", "category": "Energía", "base_price": 19.85,
             "description": "Producción de biocombustibles sostenibles", "icon": "fa-gas-pump"},
            {"name": "HealthTech Plus", "symbol": "HTP", "category": "Salud", "base_price": 62.30,
             "description": "Tecnologías para el cuidado de la salud", "icon": "fa-heartbeat"},
            {"name": "CryptoVault", "symbol": "CRV", "category": "Finanzas", "base_price": 145.70,
             "description": "Seguridad de activos digitales", "icon": "fa-lock"},
            {"name": "Urban Farming", "symbol": "URF", "category": "Agricultura", "base_price": 27.60,
             "description": "Soluciones de agricultura urbana", "icon": "fa-seedling"},
            {"name": "NanoTech Materials", "symbol": "NTM", "category": "Materiales", "base_price": 92.40,
             "description": "Materiales avanzados a nanoescala", "icon": "fa-atom"},
            {"name": "EduTech Global", "symbol": "EDG", "category": "Educación", "base_price": 41.80,
             "description": "Plataformas de aprendizaje digital", "icon": "fa-graduation-cap"},
            {"name": "AutoDrive Systems", "symbol": "ADS", "category": "Automoción", "base_price": 125.30,
             "description": "Tecnología de conducción autónoma", "icon": "fa-car-side"},
            {"name": "Renewable Storage", "symbol": "RES", "category": "Energía", "base_price": 53.70,
             "description": "Soluciones de almacenamiento de energía", "icon": "fa-battery-full"},
            {"name": "Ocean Cleanup", "symbol": "OCC", "category": "Medio ambiente", "base_price": 18.90,
             "description": "Tecnologías de limpieza oceánica", "icon": "fa-water"},
            {"name": "Digital Security", "symbol": "DSC", "category": "Ciberseguridad", "base_price": 88.60,
             "description": "Protección de datos y sistemas", "icon": "fa-shield-alt"},
            {"name": "Space Tourism", "symbol": "SPT", "category": "Turismo", "base_price": 215.40,
             "description": "Experiencias turísticas espaciales", "icon": "fa-space-shuttle"},
            {"name": "AI Healthcare", "symbol": "AIH", "category": "Salud", "base_price": 105.80,
             "description": "Diagnóstico médico con IA", "icon": "fa-user-md"}
        ]

        for company_data in companies:
            company = Company(**company_data)
            db.session.add(company)

        db.session.commit()
        print("✅ Compañías iniciales creadas exitosamente")


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
        return jsonify({'error': 'Formato de email inválido'}), 400

    if len(password) < 7:
        return jsonify({'error': 'La contraseña debe tener al menos 7 caracteres'}), 400

    # Проверка уникальности
    if User.query.filter_by(nickname=nickname).first():
        return jsonify({'error': 'Este nombre de usuario ya está en uso'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Este email ya está registrado'}), 400

    # Создание пользователя
    user = User(name=name, nickname=nickname, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Отправка приветственного email
    print(f"📧 Enviando email de bienvenida a {email}...")
    email_sent = send_welcome_email(user, password)

    # Установка сессии
    session['user_id'] = user.id
    session.permanent = True

    response_data = {
        'message': '¡Registro exitoso! Bienvenido a Clean.Invest',
        'user': user.to_dict(),
        'email_sent': email_sent
    }

    if not email_sent:
        response_data[
            'warning'] = 'Registro exitoso pero no se pudo enviar el email de bienvenida. Revisa tu configuración de correo.'

    return jsonify(response_data)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
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


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Sesión cerrada correctamente'})


@app.route('/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    return jsonify({'user': user.to_dict()})


@app.route('/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

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
            return jsonify({'error': 'Formato de teléfono inválido'}), 400
        user.phone = phone

    db.session.commit()

    return jsonify({'message': 'Perfil actualizado correctamente', 'user': user.to_dict()})


@app.route('/set_avatar', methods=['POST'])
def set_avatar():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

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


@app.route('/companies', methods=['GET'])
def get_companies():
    companies = Company.query.all()
    return jsonify({'companies': [company.to_dict() for company in companies]})


@app.route('/investments', methods=['GET'])
def get_investments():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    investments = UserInvestment.query.filter_by(user_id=user.id, is_active=True).all()

    return jsonify({'investments': [inv.to_dict() for inv in investments]})


@app.route('/buy', methods=['POST'])
def buy_stocks():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()
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

    # Отправляем email о росте акции через 30 секунд после покупки
    import threading
    def send_growth_notification():
        import time
        time.sleep(30)  # Ждем 30 секунд
        growth_percentage = random.uniform(120, 250)  # Рост от 120% до 250%

        # Используем контекст приложения для отправки email
        with app.app_context():
            send_stock_growth_email(user, company, growth_percentage)

    thread = threading.Thread(target=send_growth_notification)
    thread.daemon = True
    thread.start()

    return jsonify({
        'message': '¡Acciones compradas exitosamente!',
        'balance': user.balance,
        'company': company.to_dict(),
        'shares': shares,
        'price': current_price,
        'total_cost': total_cost
    })


@app.route('/sell', methods=['POST'])
def sell_stocks():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json()
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


@app.route('/admin/users', methods=['GET'])
def admin_get_users():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    users = User.query.all()
    return jsonify({'users': [user.to_dict() for user in users]})


@app.route('/admin/update_balance', methods=['POST'])
def admin_update_balance():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

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


@app.route('/admin/assign_admin', methods=['POST'])
def admin_assign_admin():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_owner:
        return jsonify({'error': 'Acceso denegado. Solo el owner puede asignar admins'}), 403

    data = request.get_json()
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


@app.route('/admin/remove_admin', methods=['POST'])
def admin_remove_admin():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_owner:
        return jsonify({'error': 'Acceso denegado. Solo el owner puede remover admins'}), 403

    data = request.get_json()
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


@app.route('/admin/user_info/<int:user_id>', methods=['GET'])
def admin_get_user_info(user_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    return jsonify({'user': user.to_dict()})


@app.route('/admin/stats', methods=['GET'])
def admin_get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

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


# Новый роут для массовой рассылки
@app.route('/admin/send_bulk_email', methods=['POST'])
def admin_send_bulk_email():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    admin = db.session.get(User, session['user_id'])
    if not admin or not admin.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    data = request.get_json()
    subject = data.get('subject', '').strip()
    message = data.get('message', '').strip()
    send_to_all = data.get('send_to_all', False)
    specific_emails = data.get('specific_emails', '').strip()

    if not subject or not message:
        return jsonify({'error': 'El asunto y el mensaje son obligatorios'}), 400

    # Определяем получателей
    recipients = []
    if send_to_all:
        # Отправляем всем пользователям
        users = User.query.all()
        recipients = [user.email for user in users]
    elif specific_emails:
        # Отправляем указанным email
        email_list = [email.strip() for email in specific_emails.split(',')]
        # Проверяем существование пользователей
        for email in email_list:
            user = User.query.filter_by(email=email).first()
            if user:
                recipients.append(email)
    else:
        return jsonify({'error': 'Debes seleccionar destinatarios'}), 400

    if not recipients:
        return jsonify({'error': 'No se encontraron destinatarios válidos'}), 400

    # Отправляем письма
    success_count = 0
    error_count = 0

    for email in recipients:
        try:
            msg = Message(
                subject=subject,
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[email]
            )
            msg.html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{subject}</title>
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
                        padding: 30px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background: white;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 20px;
                        color: #666;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{subject}</h1>
                </div>
                <div class="content">
                    {message.replace('\n', '<br>')}
                </div>
                <div class="footer">
                    <p>© 2024 Clean.Invest - Todos los derechos reservados</p>
                </div>
            </body>
            </html>
            """
            mail.send(msg)
            success_count += 1
        except Exception as e:
            print(f"Error enviando a {email}: {str(e)}")
            error_count += 1

    return jsonify({
        'message': f'Email enviado exitosamente a {success_count} usuarios',
        'success_count': success_count,
        'error_count': error_count,
        'total_recipients': len(recipients)
    })


# --- Роуты для чата поддержки ---

@app.route('/support/chat/create', methods=['POST'])
def create_support_chat():
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


@app.route('/support/chat/<int:chat_id>/message', methods=['POST'])
def send_message(chat_id):
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


@app.route('/support/chat/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
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

    # Отмечаем сообщения как прочитанные если это не системные сообщения от других пользователей
    if user.is_admin:
        for message in messages:
            if not message.is_system and message.sender_id != user.id:
                message.is_read = True

    db.session.commit()

    return jsonify({'messages': [msg.to_dict() for msg in messages]})


@app.route('/support/chats/pending', methods=['GET'])
def get_pending_chats():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    chats = SupportChat.query.filter_by(status='pending').order_by(SupportChat.created_at).all()
    return jsonify({'chats': [chat.to_dict() for chat in chats]})


@app.route('/support/chats/active', methods=['GET'])
def get_active_chats():
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


@app.route('/support/chats/closed', methods=['GET'])
def get_closed_chats():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    chats = SupportChat.query.filter_by(status='closed').order_by(SupportChat.closed_at.desc()).all()
    return jsonify({'chats': [chat.to_dict() for chat in chats]})


@app.route('/support/chat/<int:chat_id>/join', methods=['POST'])
def join_chat(chat_id):
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


@app.route('/support/chat/<int:chat_id>/leave', methods=['POST'])
def leave_chat(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'error': 'Acceso denegado'}), 403

    chat = db.session.get(SupportChat, chat_id)
    if not chat:
        return jsonify({'error': 'Chat no encontrado'}), 404

    if chat.admin_id != user.id or chat.status != 'active':
        return jsonify({'error': 'No puedes abandonar este chat'}), 400

    chat.admin_id = None
    chat.status = 'pending'
    chat.admin_joined_at = None

    msg = ChatMessage(
        chat_id=chat_id,
        sender_id=user.id,
        message="El administrador ha abandonado el chat. Puedes enviar un nuevo mensaje para crear una nueva solicitud.",
        is_system=True
    )
    db.session.add(msg)

    db.session.commit()
    return jsonify({'chat': chat.to_dict()})


@app.route('/support/chat/<int:chat_id>/close', methods=['POST'])
def close_chat(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    chat = db.session.get(SupportChat, chat_id)
    if not chat:
        return jsonify({'error': 'Chat no encontrado'}), 404

    if not user.is_admin or chat.admin_id != user.id:
        return jsonify({'error': 'Acceso denegado'}), 403

    chat.status = 'closed'
    chat.closed_at = datetime.now(timezone.utc)

    admin_id = chat.admin_id
    chat.admin_id = None

    msg = ChatMessage(
        chat_id=chat_id,
        sender_id=admin_id,
        message="El chat ha sido cerrado. Si necesitas más ayuda, envía un nuevo mensaje.",
        is_system=True
    )
    db.session.add(msg)

    db.session.commit()
    return jsonify({'chat': chat.to_dict()})


@app.route('/support/chat/<int:chat_id>/add_balance', methods=['POST'])
def add_balance_to_user(chat_id):
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


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/support/unread_count', methods=['GET'])
def get_unread_count():
    if 'user_id' not in session:
        return jsonify({'error': 'No has iniciado sesión'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    # Получаем активный чат пользователя
    chat = SupportChat.query.filter_by(
        user_id=user.id,
        status='active'
    ).first()

    if not chat:
        return jsonify({'unread_count': 0})

    # Считаем непрочитанные сообщения (не системные и не от текущего пользователя)
    unread_count = ChatMessage.query.filter(
        ChatMessage.chat_id == chat.id,
        ChatMessage.is_read == False,
        ChatMessage.is_system == False,
        ChatMessage.sender_id != user.id
    ).count()

    return jsonify({'unread_count': unread_count})


if __name__ == '__main__':
    print("🚀 Iniciando Clean.Invest...")
    print("📧 Configuración de correo:")
    print(f"   - Servidor: {app.config['MAIL_SERVER']}")
    print(f"   - Usuario: {app.config['MAIL_USERNAME']}")
    print(f"   - Remitente: {app.config['MAIL_DEFAULT_SENDER']}")
    app.run(debug=True, host='0.0.0.0', port=5000)