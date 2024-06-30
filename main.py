import os
import uuid
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
import pymysql
import requests
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = '#'
app.config['UPLOAD_FOLDER'] = 'static/store/img'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
DEFAULT_AVATAR = 'default_avatar.png'

CLIENT_ID = 'your_client_id'
CLIENT_SECRET = 'your_client_secret'
REDIRECT_URI = 'http://192.168.0.31:5000/callback'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db_connection():
    connection = pymysql.connect(
        host='localhost',
        port=8889,
        user='your_username',
        password='your_password',
        database='your_database_name',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

def create_tables():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                discord_id VARCHAR(255) NOT NULL,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                banner VARCHAR(255),
                icon VARCHAR(255) DEFAULT %s,
                website VARCHAR(255),
                xcom VARCHAR(255),
                mastodon VARCHAR(255),
                is_admin BOOLEAN DEFAULT FALSE,
                UNIQUE(discord_id)
            )
            """, (DEFAULT_AVATAR,))
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                app_name VARCHAR(255) NOT NULL,
                app_type VARCHAR(255),
                short_description TEXT,
                description TEXT,
                app_status VARCHAR(255),
                app_category VARCHAR(255),
                banner1 VARCHAR(255),
                banner2 VARCHAR(255),
                banner3 VARCHAR(255),
                icon VARCHAR(255),
                os_windows BOOLEAN,
                os_macos BOOLEAN,
                os_linux BOOLEAN,
                os_ios BOOLEAN,
                os_android BOOLEAN,
                display_on_app BOOLEAN DEFAULT TRUE,
                display_on_website BOOLEAN DEFAULT TRUE,
                app_official BOOLEAN DEFAULT FALSE,
                app_unofficial BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
            
            connection.commit()
            print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        connection.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/app/<int:app_id>')
def app_detail(app_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql_app = "SELECT * FROM apps WHERE id = %s"
            cursor.execute(sql_app, (app_id,))
            app_data = cursor.fetchone()
            if not app_data:
                return render_template('404.html'), 404  
            
            sql_user = "SELECT * FROM users WHERE id = %s"
            cursor.execute(sql_user, (app_data['user_id'],))
            user_data = cursor.fetchone()
            if user_data:
                app_data['username'] = user_data['username']
    except Exception as e:
        print(f"Error fetching app or user details: {e}")
        return render_template('500.html', error=str(e)), 500
    finally:
        connection.close()

    return render_template('app_detail.html', app_data=app_data)

@app.route('/download')
def download():
    return render_template('download.html')

@app.route('/panel')
def panel():
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))
    try:
        return render_template('panel.html', user=user)
    except Exception as e:
        return str(e), 500

@app.route('/edit')
def edit():
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))
    try:
        return render_template('edit.html', user=user)
    except Exception as e:
        return str(e), 500

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        banner = request.files.get('banner')
        icon = request.files.get('icon')
        website = request.form.get('website')
        xcom = request.form.get('xcom')
        mastodon = request.form.get('mastodon')
        banner_filename = None
        icon_filename = None

        if banner and allowed_file(banner.filename):
            banner_filename = secure_filename(banner.filename)
            banner_filename = ensure_unique_filename(banner_filename)
            banner.save(os.path.join(app.config['UPLOAD_FOLDER'], banner_filename))

        if icon and allowed_file(icon.filename):
            icon_filename = secure_filename(icon.filename)
            icon_filename = ensure_unique_filename(icon_filename)
            icon.save(os.path.join(app.config['UPLOAD_FOLDER'], icon_filename))
        else:
            icon_filename = DEFAULT_AVATAR

        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            UPDATE users 
            SET username=%s, banner=%s, icon=%s, website=%s, xcom=%s, mastodon=%s 
            WHERE discord_id=%s
            """
            cursor.execute(sql, (username, banner_filename, icon_filename, website, xcom, mastodon, user['discord_id']))
            connection.commit()
        connection.close()

        user['username'] = username
        session['discord_user'] = user

        return redirect(url_for('settings'))

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = "SELECT username, email, banner, icon, website, xcom, mastodon FROM users WHERE discord_id=%s"
        cursor.execute(sql, (user['discord_id'],))
        user_data = cursor.fetchone()
    connection.close()

    return render_template('settings.html', user=user, user_data=user_data)

def ensure_unique_filename(filename):
    """
    Проверяет, существует ли файл с указанным именем.
    Если да, добавляет уникальный идентификатор к имени файла.
    """
    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{uuid.uuid4().hex[:6]}{ext}"
    return filename

@app.route('/profile')
def profile():
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT app_name, short_description
            FROM apps
            WHERE user_id = %s
            """
            cursor.execute(sql, (user['id'],))
            apps = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching apps: {e}")
        apps = [] 
    finally:
        connection.close()
    
    try:
        return render_template('profile.html', user=user, apps=apps)
    except Exception as e:
        return str(e), 500

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth')
def auth():
    authorization_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    try:
        code = request.args.get('code')
        token_response = requests.post('https://discord.com/api/oauth2/token', data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'scope': 'identify'
        })

        if token_response.status_code == 200:
            token_data = token_response.json()
            access_token = token_data['access_token']

            user_response = requests.get('https://discord.com/api/users/@me', headers={
                'Authorization': f'Bearer {access_token}'
            })

            if user_response.status_code == 200:
                user_info = user_response.json()
                print("User Info:", user_info)  

                connection = get_db_connection()
                with connection.cursor() as cursor:
                    sql = """
                    INSERT INTO users (discord_id, username, email) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE username=%s, email=%s
                    """
                    cursor.execute(sql, (user_info['id'], user_info['username'], user_info.get('email'), user_info['username'], user_info.get('email')))
                    connection.commit()

                    cursor.execute("SELECT id, is_admin FROM users WHERE discord_id = %s", (user_info['id'],))
                    user_record = cursor.fetchone()
                    user_id = user_record['id']
                    is_admin = user_record['is_admin']
                connection.close()

                session['discord_user'] = {
                    'id': user_id,
                    'discord_id': user_info['id'],
                    'username': user_info['username'],
                    'email': user_info.get('email'),
                    'is_admin': is_admin
                }

                return redirect(url_for('index'))
            else:
                return "Ошибка получения данных пользователя"
        else:
            return "Ошибка получения токена"
    except Exception as e:
        print("Error during callback:", e)
        return render_template('500.html', error=str(e)), 500

def admin_required(f):
    """Decorator to check if user is admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('discord_user')
        if not user or not user.get('is_admin'):
            return render_template('403.html'), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_panel():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM apps")
            apps = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching apps: {e}")
        return render_template('500.html', error=str(e)), 500
    finally:
        connection.close()
    return render_template('admin.html', user=session.get('discord_user'), apps=apps)

@app.route('/update_app_status/<int:app_id>', methods=['POST'])
@admin_required
def update_app_status(app_id):
    app_status = request.form['app_status']
    display_on_app = 'display_on_app' in request.form
    display_on_website = 'display_on_website' in request.form

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
            UPDATE apps
            SET app_status = %s, display_on_app = %s, display_on_website = %s
            WHERE id = %s
            """
            cursor.execute(sql, (app_status, display_on_app, display_on_website, app_id))
            connection.commit()
    except Exception as e:
        print(f"Error updating app status: {e}")
        return render_template('500.html', error=str(e)), 500
    finally:
        connection.close()
    return redirect(url_for('admin_panel'))

@app.route('/store')
def store():
    return render_template('store.html')

@app.route('/logout')
def logout():
    session.pop('discord_user', None)
    return redirect(url_for('index'))

@app.route('/edit_app/<int:user_id>/<int:app_id>/', methods=['GET', 'POST'])
def edit_app(user_id, app_id):
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))

    if user['id'] != user_id:
        return render_template('403.html'), 403 

    connection = get_db_connection()

    if request.method == 'POST':
        app_name = request.form['appName']
        app_type = request.form['appType']
        short_description = request.form['shortDescription']
        description = request.form['description']
        app_status = request.form['appStatus']
        app_category = request.form['appCategory']
        banner1 = request.form['banner1']
        banner2 = request.form['banner2']
        banner3 = request.form['banner3']
        icon = request.form['icon']
        os_windows = 'windows' in request.form
        os_macos = 'macos' in request.form
        os_linux = 'linux' in request.form
        os_ios = 'ios' in request.form
        os_android = 'android' in request.form

        try:
            with connection.cursor() as cursor:
                sql = """
                UPDATE apps SET
                    app_name = %s,
                    app_type = %s,
                    short_description = %s,
                    description = %s,
                    app_status = %s,
                    app_category = %s,
                    banner1 = %s,
                    banner2 = %s,
                    banner3 = %s,
                    icon = %s,
                    os_windows = %s,
                    os_macos = %s,
                    os_linux = %s,
                    os_ios = %s,
                    os_android = %s
                WHERE id = %s AND user_id = %s
                """
                cursor.execute(sql, (
                    app_name, app_type, short_description, description, app_status, app_category, banner1, banner2, banner3, icon,
                    os_windows, os_macos, os_linux, os_ios, os_android, app_id, user['id']
                ))
                connection.commit()
            return redirect(url_for('profile'))
        except Exception as e:
            print(f"Error updating app: {e}")
            return render_template('500.html', error=str(e)), 500
        finally:
            connection.close()
    else:

        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM apps WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (app_id, user_id))
                app_data = cursor.fetchone()
                if not app_data:
                    return render_template('404.html'), 404
        except Exception as e:
            print(f"Error fetching app details: {e}")
            return render_template('500.html', error=str(e)), 500
        finally:
            connection.close()

        return render_template('edit.html', user=user, app_data=app_data)

@app.route('/autor/<string:username>')
def autor_profile(username):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user_data = cursor.fetchone()
            if not user_data:
                return render_template('404.html'), 404 
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return render_template('500.html', error=str(e)), 500
    finally:
        connection.close()
    
    return render_template('autor_profile.html', user_data=user_data)

@app.route('/api')
def api():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.id AS user_id, u.username AS author, u.banner, u.icon, u.website, u.xcom, u.mastodon,
                   a.id AS app_id, a.app_name, a.app_type, a.short_description, a.description, a.app_status,
                   a.app_category, a.banner1, a.banner2, a.banner3, a.icon AS app_icon,
                   a.os_windows, a.os_macos, a.os_linux, a.os_ios, a.os_android,
                   a.display_on_app, a.display_on_website, a.app_official, a.app_unofficial
            FROM users u
            LEFT JOIN apps a ON u.id = a.user_id
        """)
        users_with_apps = cursor.fetchall()
    connection.close()
    return jsonify(users_with_apps)

@app.route('/add_app', methods=['POST'])
def add_app():
    user = session.get('discord_user')
    if not user:
        return redirect(url_for('login'))

    app_name = request.form.get('appName')
    app_type = request.form.get('appType')
    short_description = request.form.get('shortDescription')
    description = request.form.get('description')
    app_status = request.form.get('appStatus')
    app_category = request.form.get('appCategory')
    banner1 = request.form.get('banner1')
    banner2 = request.form.get('banner2')
    banner3 = request.form.get('banner3')
    icon = request.form.get('icon')
    os_windows = 'windows' in request.form
    os_macos = 'macos' in request.form
    os_linux = 'linux' in request.form
    os_ios = 'ios' in request.form
    os_android = 'android' in request.form

    print("User ID:", user['id'])

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT MAX(id) AS max_id FROM apps")
            result = cursor.fetchone()
            next_id = (result['max_id'] or 0) + 1

            sql = """
            INSERT INTO apps (id, user_id, app_name, app_type, short_description, description, app_status, app_category,
                             banner1, banner2, banner3, icon, os_windows, os_macos, os_linux, os_ios, os_android)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (next_id, user['id'], app_name, app_type, short_description, description, app_status,
                                 app_category, banner1, banner2, banner3, icon, os_windows, os_macos, os_linux,
                                 os_ios, os_android))
            connection.commit()
    except Exception as e:
        connection.rollback()
        print("Error inserting app:", e)
        return render_template("500.html", error=str(e)), 500
    finally:
        connection.close()

    return redirect(url_for('profile'))

if __name__ == '__main__':
    create_tables()
    app.run(debug=True, host='0.0.0.0', port=5000)
