from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, TextAreaField, SelectField,
                     DateTimeLocalField, SubmitField)
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class TimelineForm(FlaskForm):
    title = StringField('Timeline Title', validators=[DataRequired(), Length(max=200)])
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
        ('remediation', 'Remediation'),
    ])
    source_ip = StringField('Source IP', validators=[Optional(), Length(max=45)])
    destination_ip = StringField('Destination IP', validators=[Optional(), Length(max=45)])
    indicator = StringField('Indicator of Compromise', validators=[Optional(), Length(max=500)])
    mitre_technique = StringField('MITRE Technique ID', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Add Event')

