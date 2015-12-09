import bottle
import os

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

@bottle.route('/')
def index():
    return bottle.template('index')

@bottle.route('/static/<filename>')
def serve_static(filename):
    return bottle.static_file(filename, root=static_dir)

if __name__ == '__main__':
    bottle.run(host='127.0.0.1', port=8080)