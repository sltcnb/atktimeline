import os
import secrets
import warnings
import click
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateTimeLocalField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------
# App Configuration
# ---------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///timeline.db'
)

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    # No key supplied: safe to auto-generate for local/dev use, but sessions
    # will not survive a restart and this must never be relied on in production.
    warnings.warn(
        'SECRET_KEY is not set; generating an ephemeral key. '
        'Set SECRET_KEY in the environment for any persistent or production deployment.',
        stacklevel=1,
    )
    _secret_key = secrets.token_hex(32)
app.config['SECRET_KEY'] = _secret_key

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session cookie hardening. SECURE is enabled unless explicitly disabled
# (e.g. for plain-HTTP local development) via SESSION_COOKIE_SECURE=0.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = (
    os.environ.get('SESSION_COOKIE_SECURE', '1') not in ('0', 'false', 'False')
)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'error'


@app.after_request
def set_security_headers(response):
    """Apply conservative security headers to every response."""
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response

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
    timelines = db.relationship('Timeline', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Timeline(db.Model):
    __tablename__ = 'timelines'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    attack_type = db.Column(db.String(100))
    severity = db.Column(db.String(20), default='medium')   # low, medium, high, critical
    status = db.Column(db.String(20), default='open')       # open, investigating, resolved, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    events = db.relationship('TimelineEvent', backref='timeline', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='TimelineEvent.event_time')

    @property
    def severity_color(self):
        return {'low': '#28a745', 'medium': '#ffc107', 'high': '#fd7e14', 'critical': '#dc3545'}.get(self.severity, '#6c757d')

    @property
    def status_color(self):
        return {'open': '#dc3545', 'investigating': '#ffc107', 'resolved': '#28a745', 'closed': '#6c757d'}.get(self.status, '#6c757d')


class TimelineEvent(db.Model):
    __tablename__ = 'timeline_events'
    id = db.Column(db.Integer, primary_key=True)
    event_time = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), nullable=False, default='other')
    source_ip = db.Column(db.String(45))
    destination_ip = db.Column(db.String(45))
    indicator = db.Column(db.String(500))
    mitre_technique = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timeline_id = db.Column(db.Integer, db.ForeignKey('timelines.id'), nullable=False)

    @property
    def type_color(self):
        return {
            'reconnaissance': '#6366f1', 'initial_access': '#f59e0b', 'execution': '#ef4444',
            'persistence': '#e11d48', 'privilege_escalation': '#dc2626', 'defense_evasion': '#78716c',
            'credential_access': '#d97706', 'discovery': '#0ea5e9', 'lateral_movement': '#8b5cf6',
            'collection': '#14b8a6', 'exfiltration': '#f97316', 'command_and_control': '#7c3aed',
            'impact': '#b91c1c', 'detection': '#22c55e', 'response': '#3b82f6',
        }.get(self.event_type, '#6b7280')

    @property
    def type_icon(self):
        return {
            'reconnaissance': 'fa-binoculars', 'initial_access': 'fa-door-open',
            'execution': 'fa-terminal', 'persistence': 'fa-anchor',
            'privilege_escalation': 'fa-arrow-up', 'defense_evasion': 'fa-eye-slash',
            'credential_access': 'fa-key', 'discovery': 'fa-search',
            'lateral_movement': 'fa-arrows-alt', 'collection': 'fa-database',
            'exfiltration': 'fa-upload', 'command_and_control': 'fa-satellite-dish',
            'impact': 'fa-explosion', 'detection': 'fa-bell', 'response': 'fa-shield-alt',
        }.get(self.event_type, 'fa-circle')


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
    attack_type = StringField('Attack Type', validators=[Optional(), Length(max=100)])
    severity = SelectField('Severity', choices=[
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')
    ], default='medium')
    status = SelectField('Status', choices=[
        ('open', 'Open'), ('investigating', 'Investigating'),
        ('resolved', 'Resolved'), ('closed', 'Closed')
    ], default='open')
    submit = SubmitField('Save Timeline')


class EventForm(FlaskForm):
    event_time = DateTimeLocalField('Event Time', format='%Y-%m-%dT%H:%M',
                                    validators=[DataRequired()])
    title = StringField('Event Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    event_type = SelectField('MITRE ATT&CK Phase', choices=[
        ('reconnaissance', 'Reconnaissance'), ('initial_access', 'Initial Access'),
        ('execution', 'Execution'), ('persistence', 'Persistence'),
        ('privilege_escalation', 'Privilege Escalation'), ('defense_evasion', 'Defense Evasion'),
        ('credential_access', 'Credential Access'), ('discovery', 'Discovery'),
        ('lateral_movement', 'Lateral Movement'), ('collection', 'Collection'),
        ('exfiltration', 'Exfiltration'), ('command_and_control', 'Command & Control'),
        ('impact', 'Impact'), ('detection', 'Detection'), ('response', 'Response'),
        ('other', 'Other')
    ])
    source_ip = StringField('Source IP', validators=[Optional(), Length(max=45)])
    destination_ip = StringField('Destination IP', validators=[Optional(), Length(max=45)])
    mitre_technique = StringField('MITRE Technique ID', validators=[Optional(), Length(max=20)])
    indicator = TextAreaField('Indicator / IOC', validators=[Optional()])
    submit = SubmitField('Save Event')

# ---------------------
# Color mapping (template context)
# ---------------------
EVENT_COLORS = {
    'reconnaissance': '#6366f1', 'initial_access': '#f59e0b', 'execution': '#ef4444',
    'persistence': '#e11d48', 'privilege_escalation': '#dc2626', 'defense_evasion': '#78716c',
    'credential_access': '#d97706', 'discovery': '#0ea5e9', 'lateral_movement': '#8b5cf6',
    'collection': '#14b8a6', 'exfiltration': '#f97316', 'command_and_control': '#7c3aed',
    'impact': '#b91c1c', 'detection': '#22c55e', 'response': '#3b82f6', 'other': '#6b7280'
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
    stats = {
        'total': len(timelines),
        'open': sum(1 for t in timelines if t.status in ('open', 'investigating')),
        'critical': sum(1 for t in timelines if t.severity == 'critical'),
        'events': sum(t.events.count() for t in timelines),
    }
    return render_template('dashboard.html', timelines=timelines, stats=stats)


@app.route('/timeline/new', methods=['GET', 'POST'])
@login_required
def new_timeline():
    form = TimelineForm()
    if form.validate_on_submit():
        timeline = Timeline(
            title=form.title.data,
            description=form.description.data,
            attack_type=form.attack_type.data,
            severity=form.severity.data,
            status=form.status.data,
            user_id=current_user.id
        )
        db.session.add(timeline)
        db.session.commit()
        flash('Timeline created!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('create_timeline.html', form=form)


@app.route('/timeline/<int:timeline_id>')
@login_required
def view_timeline(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    events = timeline.events.all()
    return render_template('view_timeline.html', timeline=timeline, events=events)


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
        timeline.attack_type = form.attack_type.data
        timeline.severity = form.severity.data
        timeline.status = form.status.data
        db.session.commit()
        flash('Timeline updated!', 'success')
        return redirect(url_for('view_timeline', timeline_id=timeline.id))
    return render_template('create_timeline.html', form=form, editing=True, timeline=timeline)


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
        event = TimelineEvent(
            event_time=form.event_time.data,
            title=form.title.data,
            description=form.description.data,
            event_type=form.event_type.data,
            source_ip=form.source_ip.data,
            destination_ip=form.destination_ip.data,
            mitre_technique=form.mitre_technique.data,
            indicator=form.indicator.data,
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
    event = TimelineEvent.query.get_or_404(event_id)
    if event.timeline_id != timeline.id:
        abort(404)
    form = EventForm(obj=event)
    if form.validate_on_submit():
        event.event_time = form.event_time.data
        event.title = form.title.data
        event.description = form.description.data
        event.event_type = form.event_type.data
        event.source_ip = form.source_ip.data
        event.destination_ip = form.destination_ip.data
        event.mitre_technique = form.mitre_technique.data
        event.indicator = form.indicator.data
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
    event = TimelineEvent.query.get_or_404(event_id)
    if event.timeline_id != timeline.id:
        abort(404)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'success')
    return redirect(url_for('view_timeline', timeline_id=timeline.id))

@app.route('/timeline/<int:timeline_id>/report')
@login_required
def timeline_report(timeline_id):
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    events = timeline.events.all()
    return render_template('timeline_report.html', timeline=timeline, events=events)


def _pdf_safe(text):
    """Sanitize text for fpdf2 built-in fonts (Latin-1 only). Replaces unencodable chars."""
    if text is None:
        return ''
    return str(text).encode('latin-1', errors='replace').decode('latin-1')


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@app.route('/timeline/<int:timeline_id>/export.pdf')
@login_required
def export_timeline_pdf(timeline_id):
    from fpdf import FPDF
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.user_id != current_user.id:
        abort(403)
    events = timeline.events.all()

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # ── Header block ────────────────────────────────────────────
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 46, 'F')

    pdf.set_xy(15, 10)
    pdf.set_font('Helvetica', 'B', 17)
    pdf.set_text_color(241, 245, 249)
    pdf.cell(0, 9, _pdf_safe(timeline.title), new_x='LMARGIN', new_y='NEXT')

    # Severity + Status filled badges
    pdf.set_x(15)
    for label, color_hex in [
        (timeline.severity.upper(), timeline.severity_color),
        (timeline.status.upper(),   timeline.status_color),
    ]:
        r, g, b = _hex_to_rgb(color_hex)
        badge_text = f" {label} "
        pdf.set_font('Helvetica', 'B', 7.5)
        w = pdf.get_string_width(badge_text) + 2
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w, 6, badge_text, fill=True)
        pdf.cell(3, 6, '')
    pdf.ln()

    # Metadata row
    pdf.set_x(15)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(148, 163, 184)
    meta_parts = []
    if timeline.attack_type:
        meta_parts.append(_pdf_safe(f"Attack: {timeline.attack_type}"))
    meta_parts.append(f"Created: {timeline.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    meta_parts.append(f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    meta_parts.append(f"{len(events)} event{'s' if len(events) != 1 else ''}")
    pdf.cell(0, 5, _pdf_safe("  |  ".join(meta_parts)), new_x='LMARGIN', new_y='NEXT')

    if timeline.description:
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(148, 163, 184)
        desc = timeline.description
        if len(desc) > 150:
            desc = desc[:150] + '...'
        pdf.cell(0, 5, _pdf_safe(desc), new_x='LMARGIN', new_y='NEXT')

    # ── Events ──────────────────────────────────────────────────
    LINE_X = 22   # x-center of the vertical dot line
    DOT_R  = 2.5  # dot radius (mm)
    CARD_X = 30   # left edge of event content
    CARD_W = 165  # content width (CARD_X to 195)

    pdf.set_y(53)

    for idx, event in enumerate(events):
        # Manual page break guard
        if pdf.get_y() > 262:
            pdf.add_page()

        start_y = pdf.get_y()
        dot_cy  = start_y + 4
        ec_r, ec_g, ec_b = _hex_to_rgb(event.type_color)

        # Colored dot
        pdf.set_fill_color(ec_r, ec_g, ec_b)
        pdf.ellipse(LINE_X - DOT_R, dot_cy - DOT_R, DOT_R * 2, DOT_R * 2, 'F')

        # Title (bold, left) + timestamp (small, right)
        pdf.set_xy(CARD_X, start_y)
        timestamp = _pdf_safe(event.event_time.strftime('%b %d, %Y  %H:%M'))
        pdf.set_font('Helvetica', '', 8)
        ts_w = pdf.get_string_width(timestamp) + 2
        title_w = CARD_W - ts_w - 2
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(241, 245, 249)
        pdf.cell(title_w, 6, _pdf_safe(event.title[:65]))
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(ts_w, 6, timestamp, align='R', new_x='LMARGIN', new_y='NEXT')

        # Phase label (colored)
        pdf.set_x(CARD_X)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_text_color(ec_r, ec_g, ec_b)
        pdf.cell(0, 5, _pdf_safe(event.event_type.replace('_', ' ').title()),
                 new_x='LMARGIN', new_y='NEXT')

        # Description
        if event.description:
            pdf.set_x(CARD_X)
            pdf.set_font('Helvetica', 'I', 8)
            pdf.set_text_color(148, 163, 184)
            pdf.multi_cell(CARD_W, 4, _pdf_safe(event.description),
                           new_x='LMARGIN', new_y='NEXT')

        # Tags: Src / Dst / MITRE / IOC
        tags = []
        if event.source_ip:
            tags.append(f"Src: {_pdf_safe(event.source_ip)}")
        if event.destination_ip:
            tags.append(f"Dst: {_pdf_safe(event.destination_ip)}")
        if event.mitre_technique:
            tags.append(f"MITRE: {_pdf_safe(event.mitre_technique)}")
        if event.indicator:
            tags.append(f"IOC: {_pdf_safe(event.indicator[:70])}")
        if tags:
            pdf.set_x(CARD_X)
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(100, 116, 139)
            # \xb7 = Latin-1 middle dot separator
            pdf.cell(0, 5, "   \xb7   ".join(tags), new_x='LMARGIN', new_y='NEXT')

        end_y = pdf.get_y()

        # Connector line + separator between events
        if idx < len(events) - 1:
            pdf.set_draw_color(51, 65, 85)
            pdf.set_line_width(0.4)
            pdf.line(LINE_X, dot_cy + DOT_R, LINE_X, end_y + 5)
            pdf.set_draw_color(30, 41, 59)
            pdf.set_line_width(0.2)
            pdf.line(CARD_X, end_y + 2, 195, end_y + 2)
            pdf.set_y(end_y + 7)
        else:
            pdf.set_y(end_y + 3)

    # Footer
    pdf.set_y(-12)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, _pdf_safe(
        f"ATK Timeline  |  {timeline.title}  |  "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    ), align='C')

    response = make_response(bytes(pdf.output()))
    response.headers['Content-Type'] = 'application/pdf'
    filename = ''.join(c if c.isalnum() or c in '-_' else '_' for c in timeline.title)
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response


# ---------------------
# CLI Commands
# ---------------------
@app.cli.command('create-user')
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def create_user(username, email, password):
    """Create a new user account."""
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
    debug = os.environ.get('FLASK_DEBUG', '1') not in ('0', 'false', 'False')
    app.run(debug=debug, host='127.0.0.1', port=5000)
