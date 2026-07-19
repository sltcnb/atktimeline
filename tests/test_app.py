"""Smoke and security tests for the ATK Timeline app."""
import os

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SESSION_COOKIE_SECURE', '0')

import app as app_module  # noqa: E402


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / 'test.db'
    app_module.app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
        WTF_CSRF_ENABLED=True,
    )
    with app_module.app.app_context():
        app_module.db.drop_all()
        app_module.db.create_all()
        user = app_module.User(username='analyst', email='a@example.com')
        user.set_password('pw12345')
        app_module.db.session.add(user)
        app_module.db.session.commit()
    with app_module.app.test_client() as client:
        yield client


def _login(client):
    page = client.get('/login')
    token = _extract_csrf(page.data)
    return client.post(
        '/login',
        data={'username': 'analyst', 'password': 'pw12345', 'csrf_token': token},
        follow_redirects=True,
    )


def _extract_csrf(html):
    import re
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1).decode() if match else ''


def test_index_redirects_to_login(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_dashboard_requires_login(client):
    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_registration_disabled(client):
    resp = client.get('/register', follow_redirects=True)
    assert b'disabled' in resp.data.lower()


def test_login_and_dashboard(client):
    resp = _login(client)
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data or b'dashboard' in resp.data


def test_security_headers_present(client):
    resp = client.get('/login')
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'DENY'


def test_delete_requires_csrf_token(client):
    _login(client)
    # POST without a CSRF token must be rejected.
    resp = client.post('/timeline/1/delete')
    assert resp.status_code == 400


def test_cannot_access_other_users_timeline(client):
    _login(client)
    # Create a timeline owned by a second user directly.
    with app_module.app.app_context():
        other = app_module.User(username='other', email='o@example.com')
        other.set_password('pw12345')
        app_module.db.session.add(other)
        app_module.db.session.commit()
        tl = app_module.Timeline(title='secret', user_id=other.id)
        app_module.db.session.add(tl)
        app_module.db.session.commit()
        tl_id = tl.id
    resp = client.get(f'/timeline/{tl_id}')
    assert resp.status_code == 403
