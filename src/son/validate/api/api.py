import os
import json
import logging
import coloredlogs
import atexit
import urllib.request as urllib2
import urllib.parse as urlparse
import shutil
import time
from son.package.md5 import generate_hash
from flask import Flask, request
from flask_cache import Cache
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result
from son.workspace.workspace import Workspace
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


log = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_pyfile('settings.py')
cache = Cache(app, config={'CACHE_TYPE': 'redis'})

# keep temporary request errors
req_errors = []


class ValidateWatcher(FileSystemEventHandler):

    def __init__(self, path, callback, filename=None):
        self.path = path
        self.filename = filename
        self.callback = callback
        self.observer = Observer()
        self.observer.schedule(self, self.path,
                               recursive=False if self.filename else True)
        self.observer.start()
        #self.observer.join()

    def on_modified(self, event):
        print(self.filename)
        print(event.src_path)
        print(event)

        if not event.is_directory and event.src_path.endswith(self.filename):
            self.observer.stop()
            self.callback(self.path)
        elif not self.filename and event.is_directory:
            self.observer.stop()
            self.callback(self.path)
        else:
            log.error("Internal error: unknown watcher event")


def initialize(debug=False):
    log.info("Initializing validator service")
    cache.clear()
    cache.add('debug', debug)
    cache.add('artifacts', list())
    cache.add('resources', dict())
    cache.add('watches', dict())

    os.makedirs(app.config['ARTIFACTS_DIR'], exist_ok=True)
    set_artifact(app.config['ARTIFACTS_DIR'])


def install_watcher(watch_path, obj_type, syntax, integrity, topology):
    log.debug("Setting watcher for {0} validation on path: {1}"
              .format(obj_type, watch_path))
    if os.path.isdir(watch_path):
        ValidateWatcher(watch_path, _validate_object_from_watch)

    elif os.path.isfile(watch_path):
        filename = os.path.basename(watch_path)
        dirname = os.path.dirname(watch_path)
        ValidateWatcher(dirname, _validate_object_from_watch,
                        filename=filename)

    set_watch(watch_path, obj_type, syntax, integrity, topology)


def load_watch_dirs(workspace):
    if not workspace:
        return

    log.info("Loading validator watchers")

    for watch_path, watch in workspace.validate_watchers.items():
        if watch_exists(watch_path):
            log.warning("Watcher path '{0}' does not exist. Ignoring."
                        .format(watch_path))
            continue

        log.debug("Loading validator watcher: {0}".format(watch_path))

        assert watch['type'] == 'project' or watch['type'] == 'package' or \
            watch['type'] == 'service' or watch['type'] == 'function'

        install_watcher(watch_path, watch['type'], watch['syntax'],
                        watch['integrity'], watch['topology'])

        _validate_object(watch_path, watch['type'], watch['syntax'],
                         watch['topology'], watch['integrity'])


def set_watch(path, obj_type, syntax, integrity, topology):
    log.debug("Caching watch '{0}".format(path))
    watches = cache.get('watches')
    if not watch_exists(path):
        watches[path] = dict()

    watches[path]['type'] = obj_type
    watches[path]['syntax'] = syntax
    watches[path]['integrity'] = integrity
    watches[path]['topology'] = topology

    cache.set('watches', watches)


def watch_exists(path):
    return path in cache.get('watches').keys()


def get_watch(path):
    if not watch_exists(path):
        return
    return cache.get('watches')[path]


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


def set_resource(key, obj_type, syntax, integrity, topology,
                 result=None, net_topology=None, net_fwgraph=None):

    assert obj_type or syntax or topology or integrity or \
           result or net_topology or net_fwgraph

    log.debug("Caching resource '{0}'".format(key))
    resources = cache.get('resources')
    if key not in resources.keys():
        resources[key] = dict()

    resources[key]['type'] = obj_type
    resources[key]['syntax'] = syntax
    resources[key]['integrity'] = integrity
    resources[key]['topology'] = topology

    if result:
        resources[key]['result'] = result
    if net_topology:
        resources[key]['net_topology'] = net_topology
    if net_fwgraph:
        resources[key]['net_fwgraph'] = net_fwgraph

    cache.set('resources', resources)


def resource_exits(key):
    return key in cache.get('resources').keys()


def get_resource(key):
    if not resource_exits(key):
        return
    return cache.get('resources')[key]


def get_resource_key(path):

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


def _validate_object_from_watch(path):
    if not watch_exists(path):
        log.error("Invalid cached watch. Cannot proceed with validation")
        return

    watch = get_watch(path)
    log.debug("Validating {0} from watch: {1}".format(watch['type'], path))
    result = _validate_object(path, watch['type'], watch['syntax'],
                              watch['integrity'], watch['topology'])

    # re-schedule watcher
    install_watcher(path, watch['type'], watch['syntax'], watch['integrity'],
                    watch['topology'])

    if not result:
        return
    log.debug(result)


def _validate_object_from_request(object_type):
    assert object_type == 'project' or object_type == 'package' or \
           object_type == 'service' or object_type == 'function'

    path = process_request()
    if not path:
        return render_errors(), 400

    syntax = eval(request.form['syntax']) \
        if 'syntax' in request.form else True
    integrity = eval(request.form['integrity']) \
        if 'integrity' in request.form else False
    topology = eval(request.form['topology']) \
        if 'topology' in request.form else False

    return _validate_object(path, object_type, syntax, integrity, topology)


def validate_parameters(obj_type, syntax, integrity, topology):
    assert obj_type == 'project' or obj_type == 'package' or \
           obj_type == 'service' or obj_type == 'function'

    if obj_type == 'service' and (integrity or topology):
        return "Invalid parameters: cannot validate integrity and/or " \
               "topology of a standalone service"


def _validate_object(path, obj_type, syntax, integrity, topology):
    # protect against incorrect parameters
    perrors = validate_parameters(obj_type, syntax, integrity, topology)
    if perrors:
        return perrors, 400

    key = get_resource_key(path)
    log.info("Validating {0} '{1}' --> MD5 hash: {2}"
             .format(obj_type, path, key))

    resource = get_resource(key)
    if resource and resource['type'] == obj_type and \
            resource['syntax'] == syntax and \
            resource['integrity'] == integrity and \
            resource['topology'] == topology:
        log.info("Returning cached result for '{0}'".format(key))
        return resource['result']

    validator = Validator()
    validator.configure(syntax, integrity, topology, debug=cache.get('debug'))
    # remove default dpath
    validator.dpath = None
    val_function = getattr(validator, 'validate_' + obj_type)

    result = val_function(path)
    print_result(validator, result)
    json_result = gen_report_result(key, validator)
    net_topology = gen_report_net_topology(validator)
    # todo: missing topology and fwgraphs
    set_resource(key, obj_type, syntax, integrity, topology,
                 result=json_result, net_topology=net_topology)

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
    return _validate_object_from_request('project')


@app.route('/validate/package', methods=['POST'])
def validate_package():
    return _validate_object_from_request('package')


@app.route('/validate/service', methods=['POST'])
def validate_service():
    return _validate_object_from_request('service')


@app.route('/validate/function', methods=['POST'])
def validate_function():
    return _validate_object_from_request('function')


@app.route('/report/result/<string:resource_id>', methods=['GET'])
def report_result(resource_id):
    if not resource_exits(resource_id) or \
            'result' not in get_resource(resource_id).keys():
        return '', 404
    return get_resource(resource_id)['result']


@app.route('/report/topology/<string:resource_id>', methods=['GET'])
def report_topology(resource_id):
    if not resource_exits(resource_id) or \
            'net_topology' not in get_resource(resource_id).keys():
        return '', 404
    return get_resource(resource_id)['net_topology']


@app.route('/report/fwgraph/<string:resource_id>', methods=['GET'])
def report_fwgraph(resource_id):
    if not resource_exits(resource_id) or \
            'net_fwgraph' not in get_resource(resource_id).keys():
        return '', 404
    return get_resource(resource_id)['net_fwgraph']


def gen_report_result(resource_id, validator):
    report = dict()
    report['resource_id'] = resource_id
    report['error_count'] = validator.error_count
    report['warning_count'] = validator.warning_count

    if validator.error_count:
        report['errors'] = validator.errors
    if validator.warning_count:
        report['warnings'] = validator.warnings
    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def gen_report_net_topology(validator):
    report = list()
    for sid, service in validator.storage.services.items():
        graph_repr = ''
        if not service.complete_graph:
            return
        for line in service.complete_graph:
            if not line:
                continue
            graph_repr += line
        report.append(graph_repr)

    return json.dumps(report)


def gen_report_net_fwgraph(validator):
    report = dict()
    for sid, service in validator.storage.services.items():
        pass


def get_local(path):
    artifact_root = add_artifact_root()
    if os.path.isfile(path):
        filepath = os.path.join(artifact_root, os.path.basename(path))
        log.debug("Copying local file: '{0}'".format(filepath))
        shutil.copyfile(path, filepath)
        set_artifact(filepath)

    elif os.path.isdir(path):
        dirname = os.path.basename(os.path.abspath(path))
        filepath = os.path.join(artifact_root, dirname)
        log.debug("Copying local tree: '{0}'".format(filepath))
        shutil.copytree(path, filepath)
        set_artifact(filepath)
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

    import argparse

    parser = argparse.ArgumentParser(
        description="SONATA Validator API. By default service runs on"
                    " 127.0.0.1:5001\n"
    )
    parser.add_argument(
        "--mode",
        choices=['service', 'local'],
        default='service',
        help="Specify the mode of operation. 'service' mode will run as "
             "a stateless service only. 'local' mode will run as a "
             "service and will also provide automatic monitoring and "
             "validation of local SDK projects, services, etc. that are "
             "configured in the developer workspace",
        required=False
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
        help="Only valid in 'local' mode. "
             "Specify the directory of the SDK workspace. "
             "Validation objects defined in the workspace configuration will "
             "be monitored and automatically validated. "
             "If not specified will assume '{}'"
             .format(Workspace.DEFAULT_WORKSPACE_DIR),
        default=Workspace.DEFAULT_WORKSPACE_DIR,
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

    coloredlogs.install(level='debug' if args.debug else 'info')

    initialize(debug=args.debug)

    if args.mode == 'local' and args.workspace:
        ws_root = os.path.expanduser(args.workspace)
        ws = Workspace.__create_from_descriptor__(ws_root)
        if not ws:
            log.error("Could not find a SONATA workspace "
                      "at the specified location")
            exit(1)

        load_watch_dirs(ws)

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=False,
    )

    # enforce debug (if is the case) after app init
    if args.debug:
        coloredlogs.install(level='debug')
