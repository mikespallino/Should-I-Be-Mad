import bottle
import os
import hashlib
import MySQLdb
from ConfigParser import ConfigParser


conf = ConfigParser()
conf.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sibm.ini'))
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
user = {'username': '',
        'password': ''}


def verify_credentials(username, password):
    """
    Verify the login credentials of the user with the database
    :param username:
    :param password:
    :return: If the user's credentials are valid
    """
    if not username or not password:
        return False
    conn = MySQLdb.connect(host='localhost', db='SIBM', user=conf.get('db', 'user'), passwd=conf.get('db', 'passwd'))
    cursor = conn.cursor()
    cursor.execute("""SELECT passwd FROM `SIBMUsers` WHERE username="{}";""".format(username))
    res = cursor.fetchone()
    conn.close()
    if not res:
        return False
    else:
        return res[0] == password


def authenticate(func):
    """
    Authentication decorator
    :param func: function to decorate
    :return:
    """

    def authenticate_and_call(*args, **kwargs):
        if not verify_credentials(user['username'], user['password']):
            bottle.redirect('/login')
        return func(*args, **kwargs)

    return authenticate_and_call


@bottle.route('/register')
def register():
    """
    Show the registration page to the user
    :return: registration page template
    """
    return bottle.template('register', result='')


@bottle.route('/register', method='POST')
def do_register():
    """
    Perform registration
    :return: Registration page indicating success or failure
    """
    username = bottle.request.forms.get('username')
    salt = hashlib.md5(username).digest()
    password = hashlib.sha256(salt + bottle.request.forms.get('password')).hexdigest()

    conn = MySQLdb.connect(host='localhost', db='SIBM', user=conf.get('db', 'user'), passwd=conf.get('db', 'passwd'))
    cursor = conn.cursor()
    result = '<p style="color:green">Registration Succeeded.</p>'
    try:
        cursor.execute(
            """INSERT INTO `SIBMUsers` (username, passwd) VALUES ("{u}", "{p}");""".format(u=username, p=password))
        conn.commit()
    except Exception as e:
        conn.rollback()
        result = '<p style="color:red">Registration Failed. {}</p>'.format(
            'Username already taken.' if e[0] == 1062 else e[1])
    finally:
        conn.close()

    return bottle.template('register', result=result)


@bottle.route('/login')
def login():
    """
    Show the login page to the user
    :return: login page template
    """
    return bottle.template('login', failed='')


@bottle.route('/login', method='POST')
def do_login():
    """
    Perform login validation, success redirects to the index page
    :return: login page template showing failure
    """
    username = bottle.request.forms.get('username')
    salt = hashlib.md5(username).digest()
    password = hashlib.sha256(salt + bottle.request.forms.get('password')).hexdigest()
    user['username'] = username
    user['password'] = password
    if verify_credentials(username, password):
        bottle.redirect('/')
    else:
        return bottle.template('login', failed='Login failed!')


@bottle.route('/')
@authenticate
def index():
    """
    Show the index page to the user
    :return: index page template
    """
    return bottle.template('index')


@bottle.route('/static/<filename>')
def serve_static(filename):
    """
    Serve static content (css, js, etc.)
    :param filename: Name of file
    :return: the static file
    """
    return bottle.static_file(filename, root=static_dir)


if __name__ == '__main__':
    bottle.run(host='127.0.0.1', port=8080)
