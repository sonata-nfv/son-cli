import os
import json
import logging
import requests
import hashlib
import coloredlogs
import atexit
import urllib.request as urllib2
import urllib.parse as urlparse
import werkzeug.exceptions
import shutil
import time
from flask import Flask, request, abort
from son.package.md5 import generate_hash
from flask_cache import Cache
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result
from son.workspace.workspace import Workspace


log = logging.getLogger(__name__)

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'redis'})
app.config['artifacts_dir'] = 'uploads'


def initialize():
    cache.clear()
    cache.set('artifacts', dict())
    cache.set('resources', dict())


def get_artifact(artifact_id):
    return cache.get('artifacts')[artifact_id]


def add_artifact(artifact_id):
    if not cache.get(artifact_id):
        cache.set(artifact_id, )


def get_cache_key(path):
    print(os.path.abspath(path))
    return generate_hash(os.path.abspath(path))


def preprocess_request():
    source = request.form['source']

    if source == 'local' and 'file' in request.form:
        path = get_local(request.form['file'])
        if not os.path.isfile(path):
            return

    elif source == 'local' and 'path' in request.form:
        path = get_local(request.form['path'])
        if not os.path.isdir(path):

            return

        print("all good")

    elif source == 'url' and 'file' in request.form:
        path = get_url(request.form['file'])

    elif source == 'file' and 'file' in request.form:
        path = get_file(request.form['file'])

    else:
        return

    key = get_cache_key(path)

    print(key)
    if cache.get(key):
        print("already cached [ ", key, ": ", path + "]")
    else:
        cache.set(key, 'ola')


@app.route('/')
def root():
    pass


@app.route('/test-cache', methods=['POST'])
def test():
    key = request.form['asd']

    if cache.get(key):
        print("Returning cached: ", key)
    else:
        cache.set(key, 'ola')

    return cache.get(key)


@app.route('/flush-cache', methods=['POST'])
def flush():
    cache.clear()
    return '', 200



@app.route('/roni', methods=['POST'])
def roni():

    if not preprocess_request():
        return '', 400

    return '', 200



@app.route('/validate/package', methods=['POST'])
def validate_package():

    preprocess_request()

    file = request.files['package']
    filepath = get_file(file)

    syntax = (False if 'syntax' not in request.form
              else eval(request.form['syntax']))
    integrity = (False if 'integrity' not in request.form
                 else eval(request.form['integrity']))
    topology = (False if 'topology' not in request.form
                else eval(request.form['topology']))

    validator = Validator()
    validator.configure(syntax=syntax, integrity=integrity,
                        topology=topology, debug=app.debug)
    result = validator.validate_package(filepath)
    print_result(validator, result)
    remove_file(filepath)

    return generate_result(validator)


@app.route('/validate/service', methods=['POST'])
def validate_service():

    file = request.files['service']
    filepath = get_file(file)

    validator = Validator()
    validator.configure(syntax=True, integrity=False,
                        topology=False, debug=app.debug)
    result = validator.validate_service(filepath)
    print_result(validator, result)
    remove_file(filepath)

    return generate_result(validator)


@app.route('/validate/function', methods=['POST'])
def validate_function():

    file = request.files['function']
    filepath = get_file(file)

    validator = Validator()
    validator.configure(syntax=True, integrity=False,
                        topology=False, debug=app.debug)
    result = validator.validate_function(filepath)
    print_result(validator, result)
    remove_file(filepath)

    return generate_result(validator)


def generate_result(validator):
    report = dict()
    report['error_count'] = validator.error_count
    report['warning_count'] = validator.warning_count

    if validator.error_count:
        report['errors'] = validator.errors
    if validator.warning_count:
        report['warnings'] = validator.warnings
    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('ascii')


def create_artifact():

    artifact = time.time()*1000


def get_local(path):

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = None
    if os.path.isfile(path):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'],
                                os.path.basename(path))
        log.debug("Copying local file: ", filepath)
        shutil.copyfile(path, filepath)

    elif os.path.isdir(path):

        filepath = os.path.join(app.config['UPLOAD_FOLDER'],
                                os.path.basename(path))
        log.debug("Copying local tree: ", filepath)
        shutil.copytree(path, filepath)

    print(filepath)
    return filepath


def get_file(file):
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return filepath


def get_url(url):
    u = urllib2.urlopen(url)
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'],
                            os.path.basename(path))

    with open(filepath, 'wb') as f:
        block_sz = 8192
        while True:
            buffer = u.read(block_sz)
            if not buffer:
                break
            f.write(buffer)

    return filepath

def remove_file(filepath):
    os.remove(filepath)


@atexit.register
def clear_artifacts():
    log.debug("Cleaning up")
    try:
        os.rmdir(app.config['UPLOAD_FOLDER'], )
    except OSError:
        pass


def main():

    coloredlogs.install(level='info')
    import argparse

    parser = argparse.ArgumentParser(
        description="SONATA Validator API. By default service runs on"
                    " 127.0.0.1:5001\n"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address for this service",
        required=False
    )
    parser.add_argument(
        "--port",
        default=5001,
        type=int,
        help="Bind port number",
        required=False
    )
    parser.add_argument(
        "-w", "--workspace",
        help=""
             "Specify the directory of the SDK workspace. Projects defined "
             "in the workspace configuration will be monitored and "
             "automatically validated",
        required=False
    )
    parser.add_argument(
        "--debug",
        default=False,
        help="Sets verbosity level to debug",
        required=False,
        action="store_true"
    )

    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level='debug')

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
