import os
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import re
import uuid
import threading
import time

from config import config
from models import db, User, Company, UserInvestment, SupportChat, ChatMessage
from utils import cache_result, monitor_performance, invalidate_cache_pattern


def create_app(config_name=None):
    app = Flask(__name__)

    # Load configuration
    config_name = config_name or os.getenv('FLASK_CONFIG', 'default')
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    mail = Mail(app)

    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Helper functions
    def send_welcome_email(user, password):
        """Send welcome email asynchronously"""

        def send_async():
            try:
                msg = Message(
                    subject='¡Bienvenido a Clean.Invest! 🚀 Tu Futuro Financiero Comienza Ahora',
                    sender=app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[user.email]
                )

                # HTML template (same as before)
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

        # Send email in background thread
        thread = threading.Thread(target=send_async)
        thread.daemon = True
        thread.start()

    # Routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/register', methods=['POST'])
    @monitor_performance
    def register():
        data = request.get_json()
        name = data.get('name', '').strip()
        nickname = data.get('nickname', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        # Validation
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
            # Check uniqueness
            if User.query.filter_by(nickname=nickname).first():
                return jsonify({'error': 'Este nombre de usuario ya esta en uso'}), 400

            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Este email ya esta registrado'}), 400

            # Create user
            user = User(name=name, nickname=nickname, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Send welcome email
            send_welcome_email(user, password)

            # Set session
            session['user_id'] = user.id
            session.permanent = True

            # Invalidate cache
            invalidate_cache_pattern("user_*")

            return jsonify({
                'message': '¡Registro exitoso! Bienvenido a Clean.Invest',
                'user': user.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {e}")
            return jsonify({'error': 'Error en el registro. Intente nuevamente.'}), 500

    @app.route('/login', methods=['POST'])
    @monitor_performance
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
            print(f"Login error: {e}")
            return jsonify({'error': 'Error en el inicio de sesion'}), 500

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

    @app.route('/companies', methods=['GET'])
    @cache_result(timeout=600)  # Cache for 10 minutes
    def get_companies():
        companies = Company.query.all()
        return jsonify({'companies': [company.to_dict() for company in companies]})

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
    @monitor_performance
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

            import random
            price_variation = random.uniform(0.95, 1.05)
            current_price = company.base_price * price_variation
            total_cost = current_price * shares

            if user.balance < total_cost:
                return jsonify({'error': 'Saldo insuficiente'}), 400

            # Update or create investment
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

            # Invalidate cache
            invalidate_cache_pattern("user_*")

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
            print(f"Buy stocks error: {e}")
            return jsonify({'error': 'Error al comprar acciones'}), 500

    @app.route('/health')
    def health_check():
        """Health check endpoint for Railway"""
        try:
            # Check database connection
            db.session.execute('SELECT 1')

            return {
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'users': User.query.count(),
                'companies': Company.query.count(),
                'investments': UserInvestment.query.count()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }, 500

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

    return app


# Create app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)