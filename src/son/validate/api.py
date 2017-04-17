import os
import json
import logging
import coloredlogs
import atexit
from flask import Flask, Response, request, redirect, g
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result

log = logging.getLogger(__name__)

UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def root():
    pass


@app.route('/validate/package/', methods=['POST'])
def validate_package():

    file = request.files['package']
    filepath = upload_file(file)

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


@app.route('/validate/service/', methods=['POST'])
def validate_service():

    file = request.files['service']
    filepath = upload_file(file)

    validator = Validator()
    validator.configure(syntax=True, integrity=False,
                        topology=False, debug=app.debug)
    result = validator.validate_service(filepath)
    print_result(validator, result)
    remove_file(filepath)

    return generate_result(validator)


@app.route('/validate/function/', methods=['POST'])
def validate_function():

    file = request.files['function']
    filepath = upload_file(file)

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


def upload_file(file):
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

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
