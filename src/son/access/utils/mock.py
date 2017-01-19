"""
This mock tool tries to emulate Gatekeeper responses on the
User Management component that is still under development.

This enables a REST API that returns a JWT to the son-access
component when it tries to authenticate a user.
"""

import time
import traceback
import os
import json
import jwt
from flask import Flask, session, request, make_response, jsonify


logins = {'tester': '1234'}


def token(data):
    encoded = jwt.encode(data, 'secret', algorithm='HS256')
    return encoded


def payload(username):
    """
    try:
        user = User.objects.get(email=post_data['email'])
        user.match_password(post_data['password'])
    except (User.DoesNotExist, User.PasswordDoesNotMatch):
        return json_response({'message': 'Wrong credentials'}, status=400)

    payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(seconds=self.JWT_EXP_DELTA_SECONDS)
    }
    jwt_token = jwt.encode(payload, self.JWT_SECRET, self.JWT_ALGORITHM)
    return json_response({'token': jwt_token.decode('utf-8')})
    """

    return {
        'exp':  time.time() + 60 * 60,
        'iat': time.time(),
        'iss': 'JWT_ISSUER',
        'scopes': ['get_services', 'get_functions', 'get_packages'],
        'user': {
            'username': username
        }
    }


app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.errorhandler(Exception)
def internal_error(error):
    """
    app.logger.error("Exception:\n" + str())
    :param error:
    :return:
    """
    message = dict(status=500, message='Internal Server Error: ' + str(traceback.format_exc()))
    resp = jsonify(message)
    resp.status_code = 500

    return make_response(resp, 500)


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    if logins[str(username)] == password:
        payload_data = payload(username)
        access_token = token(payload_data)

        resp = jsonify(access_token)
        resp.headers['Content-Type'] = 'application/json'
        resp.status_code = 200
        return resp

    else:
        return make_response(jsonify({'error': 'Invalid username or password'}), 401)


def main():
    app.run(
        host='127.0.0.1',
        port=5001,
        debug=False
    )

if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=5001,
        debug=True
    )
