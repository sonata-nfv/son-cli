#  Copyright (c) 2015 SONATA-NFV, UBIWHERE, i2CAT,
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, UBIWHERE, i2CAT
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

"""
This mock tool tries to emulate Gatekeeper responses on the
User Management component that is still under development.

This enables a REST API that returns a JWT to the son-access
component when it tries to authenticate a user.
"""
import time
import traceback
import json
import jwt
from flask import Flask, request, make_response, jsonify


logins = {'tester': '1234'}


def token(data):
    encoded = jwt.encode(data, 'secret', algorithm='HS256')
    return str(encoded, 'UTF8')


def payload(username):
    """
    try:
        user = User.objects.get(email=post_data['email'])
        user.match_password(post_data['password'])
    except (User.DoesNotExist, User.PasswordDoesNotMatch):
        return json_response({'message': 'Wrong credentials'}, status=400)

    payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + 
                   timedelta(seconds=self.JWT_EXP_DELTA_SECONDS)
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
    message = dict(status=500, message='Internal Server Error: ' +
                                       str(traceback.format_exc()))
    resp = jsonify(message)
    resp.status_code = 500

    return make_response(resp, 500)


@app.route('/api/v2/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    print('username=', username)
    print('password=', password)

    if logins[str(username)] == password:
        print('ACCEPTED')
        payload_data = payload(username)
        print('payload_data=', payload_data)
        access_token = token(payload_data)
        print('access_token=', access_token)
        try:
            resp = jsonify(access_token)
            print('response=', resp)
        except Exception as e:
            print('ERROR=', e)
        resp.headers['Content-Type'] = 'application/json'
        resp.status_code = 200
        return resp

    else:
        return make_response(jsonify(
            {'error': 'Invalid username or password'}), 401)


@app.route('/api/v2/packages', methods=['POST'])
def packages():
    print('Package received')
    return make_response(jsonify({'OK': 'Package received'}), 200)


@app.route('/api/v2/requests', methods=['POST'])
def requests():
    print('Instantiation request received')
    return make_response(jsonify({'OK': 'Instantiation initiated'}), 200)


@app.route('/api/v2/signature', methods=['PUT'])
def signature():
    print('Signature update received')
    public_key = json.loads(request.data.decode('utf-8'))
    print('public_key=', public_key['public_key'])

    return make_response(jsonify({'OK': 'Update done'}), 200)


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
