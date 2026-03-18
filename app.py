import os
import click
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateTimeLocalField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------
# App Configuration
# ---------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///timeline.db'
)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'error'

# ---------------------
# Models
# ---------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timelines = db.relationship('Timeline', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Timeline(db.Model):
    __tablename__ = 'timelines'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    events = db.relationship('Event', backref='timeline', lazy=True, cascade='all, delete-orphan',
                             order_by='Event.event_time')


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    event_time = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), nullable=False, default='other')
    source_ip = db.Column(db.String(45))
    dest_ip = db.Column(db.String(45))
    artifact = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timeline_id = db.Column(db.Integer, db.ForeignKey('timelines.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------
# Forms
# ---------------------
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class TimelineForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Timeline')


class EventForm(FlaskForm):
    event_time = DateTimeLocalField('Event Time', format='%Y-%m-%dT%H:%M',
                                     validators=[DataRequired()])
    title = StringField('Event Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    event_type = SelectField('MITRE ATT&CK Phase', choices=[
        ('reconnaissance', 'Reconnaissance'),
        ('initial_access', 'Initial Access'),
        ('execution', 'Execution'),
        ('persistence', 'Persistence'),
        ('privilege_escalation', 'Privilege Escalation'),
        ('defense_evasion', 'Defense Evasion'),
        ('credential_access', 'Credential Access'),
        ('discovery', 'Discovery'),
        ('lateral_movement', 'Lateral Movement'),
        ('collection', 'Collection'),
        ('exfiltration', 'Exfiltration'),
        ('command_and_control', 'Command & Control'),
        ('impact', 'Impact'),
        ('detection', 'Detection'),
        ('response', 'Response'),
        ('other', 'Other')
    ])
    source_ip = StringField('Source IP', validators=[Optional(), Length(max=45)])
    dest_ip = StringField('Destination IP', validators=[Optional(), Length(max=45)])
    artifact = TextAreaField('Artifact / IOC', validators=[Optional()])
    submit = SubmitField('Save Event')

# ---------------------
# Color mapping
# ---------------------
EVENT_COLORS = {
    'reconnaissance': '#6366f1',
    'initial_access': '#f59e0b',
    'execution': '#ef4444',
    'persistence': '#e11d48',
    'privilege_escalation': '#dc2626',
    'defense_evasion': '#78716c',
    'credential_access': '#d97706',
    'discovery': '#0ea5e9',
    'lateral_movement': '#8b5cf6',
    'collection': '#14b8a6',
    'exfiltration': '#f97316',
    'command_and_control': '#7c3aed',
    'impact': '#b91c1c',
    'detection': '#22c55e',
    'response': '#3b82f6',
    'other': '#6b7280'
}

@app.context_processor
def inject_event_colors():
    return dict(event_colors=EVENT_COLORS)

# ---------------------
# Routes
# ---------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    flash('Registration is disabled. Contact an administrator.', 'error')
    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    timelines = Timeline.query.filter_by(user_id=current_user.id).order_by(Timeline.updated_at.desc()).all()
    return render_template('dashboard.html', timelines=timelines)


@app.route('/timeline/new', methods=['GET', 'POST'])
@login_required
def new_timeline():
    form = TimelineForm()
    if form.validate_on_submit():
        timeline = Timeline(
            title=form.title.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(timeline)
        db.session.commit()
        flash('Timeline created!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('new_timeline.html', form=form)


@app.route('/timeline/<int:timeline_id>')
@login_required
def view_timeline(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    return render_template('view_timeline.html', timeline=timeline)


@app.route('/timeline/<int:timeline_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_timeline(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    form = TimelineForm(obj=timeline)
    if form.validate_on_submit():
        timeline.title = form.title.data
        timeline.description = form.description.data
        db.session.commit()
        flash('Timeline updated!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('new_timeline.html', form=form, editing=True, timeline=timeline)


@app.route('/timeline/<int:timeline_id>/delete', methods=['POST'])
@login_required
def delete_timeline(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    db.session.delete(timeline)
    db.session.commit()
    flash('Timeline deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/timeline/<int:timeline_id>/event/new', methods=['GET', 'POST'])
@login_required
def add_event(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            event_time=form.event_time.data,
            title=form.title.data,
            description=form.description.data,
            event_type=form.event_type.data,
            source_ip=form.source_ip.data,
            dest_ip=form.dest_ip.data,
            artifact=form.artifact.data,
            timeline_id=timeline.id
        )
        db.session.add(event)
        db.session.commit()
        flash('Event added!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('add_event.html', form=form, timeline=timeline)


@app.route('/timeline/<int:timeline_id>/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(timeline_id, event_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    event = Event.query.get_or_404(event_id)
    if event.timeline_id != timeline.id:
        abort(404)
    form = EventForm(obj=event)
    if form.validate_on_submit():
        event.event_time = form.event_time.data
        event.title = form.title.data
        event.description = form.description.data
        event.event_type = form.event_type.data
        event.source_ip = form.source_ip.data
        event.dest_ip = form.dest_ip.data
        event.artifact = form.artifact.data
        db.session.commit()
        flash('Event updated!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('add_event.html', form=form, timeline=timeline, editing=True, event=event)


@app.route('/timeline/<int:timeline_id>/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(timeline_id, event_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    event = Event.query.get_or_404(event_id)
    if event.timeline_id != timeline.id:
        abort(404)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'success')
    return redirect(url_for('view_timeline', timeline_id=timeline.id))

# ---------------------
# CLI Commands
# ---------------------
@app.cli.command('create-user')
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def create_user(username, email, password):
    """Create a new user account locally."""
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        click.echo('Error: Username or email already exists.')
        return
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'User "{username}" created successfully.')


@app.cli.command('init-db')
def init_db():
    """Initialize database tables."""
    db.create_all()
    click.echo('Database tables created.')

# ---------------------
# Run
# ---------------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
