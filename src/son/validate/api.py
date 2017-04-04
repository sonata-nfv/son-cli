from flask import Flask, Response, request, redirect
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result

UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)


@app.route('/')
def root():
    pass


@app.route('/validate/package/', methods=['POST'])
def validate_package():

    file = request.files['package']
    filename = secure_filename(file.filename)
    file.save(filename)

    syntax = (False if 'syntax' not in request.form
              else eval(request.form['syntax']))
    integrity = (False if 'integrity' not in request.form
                 else eval(request.form['integrity']))
    topology = (False if 'topology' not in request.form
                else eval(request.form['topology']))

    validator = Validator()
    validator.configure(syntax=syntax, integrity=integrity,
                        topology=topology, debug=app.debug)
    validator.validate_package(filename)
    print_result(validator)

    return "errors: {0}, warnings: {1}".format(validator.error_count,
                                               validator.warning_count)


@app.route('/validate/service/', methods=['POST'])
def validate_service():
    pass


@app.route('/validate/function/', methods=['POST'])
def validate_function():
    pass


def main():
    app.run(
        host='127.0.0.1',
        port=5001,
        debug=True
    )
