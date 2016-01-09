import bottle
import os
import hashlib
import pymysql
import uuid

from configparser import ConfigParser
from pymysql.cursors import SSDictCursor
from sql_queries import *

conf = ConfigParser()
conf.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sibm.ini'))
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
user = {'username': '',
        'password': ''}
connection_credentials = {'host': 'localhost', 'db': 'SIBM', 'user': conf.get('db', 'user'),
                          'passwd': conf.get('db', 'passwd')}


@bottle.route('/error')
def error():
    """
    Display the error page to the user
    :return: error page template
    """
    return bottle.template('error', error='<p style="color: red">We probably did something dumb.</p>')


def verify_credentials(username, password):
    """
    Verify the login credentials of the user with the database
    :param username:
    :param password:
    :return: If the user's credentials are valid
    """
    if not username or not password:
        return False
    conn = None
    try:
        conn = pymysql.connect(**connection_credentials)
        cursor = conn.cursor()
        cursor.execute(VERIFY_USER_QUERY.format(username))
        res = cursor.fetchone()
    except Exception as e:
        bottle.redirect('/error')
        return False
    finally:
        if conn:
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


@bottle.route('/upvote/<post_guid>')
@authenticate
def upvote(post_guid):
    """
    Increment a post's score, redirect to index after
    :param post_guid: post's guid in the database
    :return:
    """
    change_score(post_guid, 1)
    bottle.redirect('/')


@bottle.route('/downvote/<post_guid>')
@authenticate
def downvote(post_guid):
    """
    Decrement a post's score, redirect to index after
    :param post_guid: post's guid in the database
    :return:
    """
    change_score(post_guid, -1)
    bottle.redirect('/')


def change_score(post_guid, score_change):
    """
    Grab post data from the database, update the score and update the database with new score
    :param post_guid: post's guid in the database
    :param score_change: +1 or -1 from either upvote or downvote
    :return:
    """
    conn = pymysql.connect(**connection_credentials)
    cursor = conn.cursor(SSDictCursor)
    cursor.execute(GET_POST_QUERY.format(guid=post_guid))

    # This should only be one record
    res = cursor.fetchall()[0]
    post_score = res['post_score'] + score_change

    cursor.execute(UPDATE_POST_SCORE_QUERY.format(score=post_score, uid=post_guid))
    conn.commit()
    conn.close()


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
    salt = hashlib.md5(username.encode('utf-8')).digest()
    password = hashlib.sha256(salt + bottle.request.forms.get('password').encode('utf-8')).hexdigest()

    conn = pymysql.connect(**connection_credentials)
    cursor = conn.cursor()
    result = '<p style="color:green">Registration Succeeded.</p>'
    success = False
    try:
        cursor.execute(REGISTER_USER_QUERY.format(u=username, p=password))
        conn.commit()
        success = True
    except pymysql.DataError as dataErr:
        conn.rollback()
        resp = '<p style="color:red">Registration Failed. Invalid </p>'.format(dataErr)
    except pymysql.IntegrityError:
        conn.rollback()
        resp = '<p style="color:red">Registration Failed. Username already taken.</p>'
    except Exception as e:
        conn.rollback()
        resp = '<p style="color:red">Registration Failed. {}</p>'.format(e)
    finally:
        conn.close()

    return bottle.template('register', result=result) if success else bottle.template('error', error=resp)


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
    salt = hashlib.md5(username.encode('utf-8')).digest()
    password = hashlib.sha256(salt + bottle.request.forms.get('password').encode('utf-8')).hexdigest()
    user['username'] = username
    user['password'] = password
    if verify_credentials(username, password):
        bottle.redirect('/')
    else:
        return bottle.template('login', failed='Login failed!')


def generate_front_page():
    """
    Query the SIBMPostData table for posts to display
    :return: Front Page posts
    """
    conn = pymysql.connect(**connection_credentials)
    cursor = conn.cursor(SSDictCursor)
    try:
        cursor.execute(SELECT_POST_QUERY)
        recs = cursor.fetchall()

        front_page = '<table class="table table-bordered table-striped table-condensed">\n'
        for rec in recs:
            cont = rec['post_content']
            if len(cont) > 4000:
                cont = cont[:4000] + '...'
            front_page += '\t\t<tr>\n'
            front_page += '\t\t\t<td id="score"><a href="/upvote/{g}">UP</a><br />{score}<br /><a href="/downvote/{g}">DOWN</a></td>\n'.format(score=rec['post_score'], g=rec['post_uuid'])
            front_page += '\t\t\t<td id="cont"><div class="td-cont">{cont}</div></td>\n'.format(cont=cont)
            front_page += '\t\t\t<td id="user">{user}</td>\n'.format(user=rec['username'])
            front_page += '\t\t</tr>\n'
        front_page += '\t</table>\n'

    except Exception as e:
        conn.close()
        return bottle.template('error', error='There was an error generating the Front Page. Sorry!')

    finally:
        conn.close()

    return front_page


@bottle.route('/')
@authenticate
def index():
    """
    Show the index page to the user
    :return: index page template
    """
    front_page = generate_front_page()
    return bottle.template('index', post_data=front_page)


@bottle.route('/make_post', method='GET')
@authenticate
def make_post():
    """
    Show the make_post page to the user
    :return: make_post page template
    """
    return bottle.template('make_post', status='')


@bottle.route('/make_post', method='POST')
@authenticate
def do_make_post():
    """
    Connect to the database, cleanse user input, post data
    :return: make_post page if error else redirect to index
    """
    conn = pymysql.connect(**connection_credentials)
    cursor = conn.cursor()
    post_content = bottle.request.forms.get('post_content')

    failed = False
    try:
        cont = conn.escape(post_content)
        cont = cont.replace("'", '')
        cursor.execute(MAKE_POST_QUERY.format(uid=uuid.uuid4().hex, cont=cont, score=1, user=user['username']))
        conn.commit()
    except Exception as e:
        conn.rollback()
        status = '<p style="color:red">Post failed!</p>'
        failed = True
        print(e)
    finally:
        conn.close()

    if failed:
        return bottle.template('make_post', status=status)
    else:
        bottle.redirect('/')


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
