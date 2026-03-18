from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timelines = db.relationship('Timeline', backref='author', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Timeline(db.Model):
    __tablename__ = 'timelines'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    attack_type = db.Column(db.String(100), nullable=True)
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    events = db.relationship('TimelineEvent', backref='timeline', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='TimelineEvent.event_time')

    @property
    def severity_color(self):
        colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        return colors.get(self.severity, '#6c757d')

    @property
    def status_color(self):
        colors = {
            'open': '#dc3545',
            'investigating': '#ffc107',
            'resolved': '#28a745',
            'closed': '#6c757d'
        }
        return colors.get(self.status, '#6c757d')

class TimelineEvent(db.Model):
    __tablename__ = 'timeline_events'
    id = db.Column(db.Integer, primary_key=True)
    event_time = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(50), default='action')
    # Types: reconnaissance, initial_access, execution, persistence,
    #        privilege_escalation, defense_evasion, credential_access,
    #        discovery, lateral_movement, collection, exfiltration,
    #        command_and_control, impact, detection, response, remediation
    source_ip = db.Column(db.String(45), nullable=True)
    destination_ip = db.Column(db.String(45), nullable=True)
    indicator = db.Column(db.String(500), nullable=True)  # IOC
    mitre_technique = db.Column(db.String(20), nullable=True)  # e.g., T1059
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timeline_id = db.Column(db.Integer, db.ForeignKey('timelines.id'), nullable=False)

    @property
    def type_icon(self):
        icons = {
            'reconnaissance': 'fa-binoculars',
            'initial_access': 'fa-door-open',
            'execution': 'fa-terminal',
            'persistence': 'fa-anchor',
            'privilege_escalation': 'fa-arrow-up',
            'defense_evasion': 'fa-eye-slash',
            'credential_access': 'fa-key',
            'discovery': 'fa-search',
            'lateral_movement': 'fa-arrows-alt',
            'collection': 'fa-database',
            'exfiltration': 'fa-upload',
            'command_and_control': 'fa-satellite-dish',
            'impact': 'fa-explosion',
            'detection': 'fa-bell',
            'response': 'fa-shield-alt',
            'remediation': 'fa-wrench',
        }
        return icons.get(self.event_type, 'fa-circle')

    @property
    def type_color(self):
        colors = {
            'reconnaissance': '#17a2b8',
            'initial_access': '#dc3545',
            'execution': '#e83e8c',
            'persistence': '#6f42c1',
            'privilege_escalation': '#fd7e14',
            'defense_evasion': '#6c757d',
            'credential_access': '#ffc107',
            'discovery': '#20c997',
            'lateral_movement': '#007bff',
            'collection': '#795548',
            'exfiltration': '#ff5722',
            'command_and_control': '#9c27b0',
            'impact': '#f44336',
            'detection': '#28a745',
            'response': '#2196f3',
            'remediation': '#4caf50',
        }
        return colors.get(self.event_type, '#6c757d')

