import os
import json
import logging
import coloredlogs
import atexit
import urllib.request as urllib2
import urllib.parse as urlparse
import shutil
import time
from flask import Flask, request
from son.package.md5 import generate_hash
from flask_cache import Cache
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result


log = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_pyfile('settings.py')
cache = Cache(app, config={'CACHE_TYPE': 'redis'})


def initialize():
    cache.clear()
    cache.add('artifacts', list())
    cache.add('resources', dict())

    os.makedirs(app.config['ARTIFACTS_DIR'], exist_ok=True)
    set_artifact(app.config['ARTIFACTS_DIR'])


def set_artifact(artifact_path):
    log.debug("Caching artifact '{0}'".format(artifact_path))
    artifacts = cache.get('artifacts')
    artifacts.append(artifact_path)
    cache.set('artifacts', artifacts)


def add_artifact_root():
    artifact_root = os.path.join(app.config['ARTIFACTS_DIR'],
                                 str(time.time() * 1000))
    os.makedirs(artifact_root, exist_ok=False)
    set_artifact(artifact_root)
    return artifact_root


def set_resource(key, resource):
    log.debug("Caching resource '{0}'".format(key))
    resources = cache.get('resources')
    resources[key] = resource
    cache.set('resources', resources)


def get_resource(key):
    if key not in cache.get('resources'):
        return
    return cache.get('resources')[key]



def get_resource_key(path):
    print(os.path.abspath(path))
    return generate_hash(os.path.abspath(path))


def preprocess_request():
    source = request.form['source']

    if source == 'local' and 'path' in request.form:
        path = get_local(request.form['path'])
        if not path:
            return

    elif source == 'url' and 'path' in request.form:
        path = get_url(request.form['path'])

    elif source == 'embedded' and 'file' in request.files:
        path = get_file(request.files['file'])

    else:
        print('error')
        return

    return path


@app.route('/')
def root():
    pass


@app.route('/flush/resources', methods=['POST'])
def flush_resources():
    cache.set('resources', dict())
    return '', 200


@app.route('/flush/artifacts', methods=['POST'])
def flush_artifacts():
    cache.set('artifacts', list())
    return '', 200


@app.route('/roni', methods=['POST'])
def roni():

    if not preprocess_request():
        return '', 400

    return '', 200


@app.route('/validate/package', methods=['POST'])
def validate_package():

    path = preprocess_request()
    if not path:
        return 'Bad request body', 400

    log.info("Validating package '{0}'".format(path))

    key = get_resource_key(path)

    log.debug("MD5 hash: '{0}'".format(key))
    resource = get_resource(key)
    if resource:
        log.debug("Returning cached result for '{0}'".format(key))
        return resource

    syntax = (False if 'syntax' not in request.form
              else eval(request.form['syntax']))
    integrity = (False if 'integrity' not in request.form
                 else eval(request.form['integrity']))
    topology = (False if 'topology' not in request.form
                else eval(request.form['topology']))

    validator = Validator()
    validator.configure(syntax=syntax, integrity=integrity,
                        topology=topology, debug=app.debug)
    result = validator.validate_package(path)
    print_result(validator, result)
    json_result = generate_result(validator)
    set_resource(key, json_result)

    return json_result


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


def get_local(path):
    artifact_root = add_artifact_root()
    if os.path.isfile(path):
        filepath = os.path.join(artifact_root, os.path.basename(path))
        log.debug("Copying local file: '{0}'".format(filepath))
        shutil.copyfile(path, filepath)
        set_artifact(filepath)

    elif os.path.isdir(path):
        dirname = os.path.basename(os.path.dirname(path))
        filepath = os.path.join(artifact_root, dirname)
        log.debug("Copying local tree: '{0}'".format(filepath))
        shutil.copytree(path, filepath)
        for root, dirs, files in os.walk(filepath):
            for d in dirs:
                set_artifact(os.path.join(root, d))
            for f in files:
                set_artifact(os.path.join(root, f))
    else:
        log.error("Invalid local path: '{0}'".format(path))
        return

    return filepath


def get_file(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(add_artifact_root(), filename)
    file.save(filepath)
    set_artifact(filepath)
    return filepath


def get_url(url):
    u = urllib2.urlopen(url)
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    filepath = os.path.join(add_artifact_root(), os.path.basename(path))

    with open(filepath, 'wb') as f:
        block_sz = 8192
        while True:
            buffer = u.read(block_sz)
            if not buffer:
                break
            f.write(buffer)

    set_artifact(filepath)
    return filepath


def remove_file(filepath):
    os.remove(filepath)


@atexit.register
def remove_artifacts():

    log.info("Removing artifacts")

    for artifact in cache.get('artifacts')[::-1]:
        try:
            os.remove(artifact) if os.path.isfile(artifact) \
                                 else os.rmdir(artifact)
            log.debug("DELETED '{}'".format(artifact))
        except OSError:
            log.debug("FAILED '{}".format(artifact))
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
        default=app.config['HOST'],
        help="Bind address for this service",
        required=False
    )
    parser.add_argument(
        "--port",
        default=app.config['PORT'],
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
        default=app.config['DEBUG'],
        help="Sets verbosity level to debug",
        required=False,
        action="store_true"
    )

    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level='debug')

    initialize()
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
