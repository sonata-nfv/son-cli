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

# keep temporary request errors
req_errors = []


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


def set_resource(key, type=None, result=None, topology=None, fwgraph=None):
    assert type or result or topology or fwgraph

    log.debug("Caching resource '{0}'".format(key))
    resources = cache.get('resources')
    if key not in resources.keys():
        resources[key] = dict()

    if type:
        resources[key]['type'] = type
    if result:
        resources[key]['result'] = result
    if topology:
        resources[key]['topology'] = topology
    if fwgraph:
        resources[key]['fwgraph'] = fwgraph

    cache.set('resources', resources)


def get_resource(key):
    if key not in cache.get('resources'):
        return
    return cache.get('resources')[key]


def get_resource_key(path):
    print(os.path.abspath(path))
    return generate_hash(os.path.abspath(path))


def process_request():
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
        req_errors.append('Invalid source, path or file parameters')
        return

    return path


def _validate_object(object_type):
    assert object_type == 'project' or object_type == 'package' or \
           object_type == 'service' or object_type == 'function'

    path = process_request()
    if not path:
        return render_errors(), 400

    log.info("Validating {0} '{1}'".format(object_type, path))
    key = get_resource_key(path)
    log.debug("MD5 hash key: '{}'".format(key))

    resource = get_resource(key)
    if resource and resource['type'] == object_type:
        log.debug("Returning cached result for '{0}'".format(key))
        return resource['result']

    validator = Validator()
    validator.configure(syntax=request.form['syntax'] or False,
                        integrity=request.form['integrity'] or False,
                        topology=request.form['topology'] or False,
                        debug=app.debug)

    val_function = getattr(validator, 'validate_' + object_type)
    result = val_function(path)
    print_result(validator, result)
    json_result = generate_result(validator)
    # todo: missing topology and fwgraphs
    set_resource(key, type=object_type, result=json_result)

    return json_result


def render_errors():
    error_str = ''
    for error in req_errors:
        error_str += error + '\n'
    req_errors.clear()
    return error_str


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


@app.route('/validate/project', methods=['POST'])
def validate_project():
    return _validate_object('project')


@app.route('/validate/package', methods=['POST'])
def validate_package():
    return _validate_object('package')


@app.route('/validate/service', methods=['POST'])
def validate_service():
    return _validate_object('service')


@app.route('/validate/function', methods=['POST'])
def validate_function():
    return _validate_object('function')


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
        req_errors.append("Invalid local path: '{0}'".format(path))
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
