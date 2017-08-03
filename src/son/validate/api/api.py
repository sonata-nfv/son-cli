import hashlib
import os
import sys
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
from flask_cors import CORS
from werkzeug.utils import secure_filename
from son.validate.validate import Validator, print_result
from son.workspace.workspace import Workspace
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from son.validate.event import EventLogger

log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config.from_pyfile('settings.py')

# config cache
if app.config['CACHE_TYPE'] == 'redis':

    redis_auth = app.config['REDIS_USER'] + ':' + app.config[
        'REDIS_PASSWD'] + '@' \
        if app.config['REDIS_USER'] and app.config['REDIS_PASSWD'] else ''
    redis_url = 'redis://' + redis_auth + app.config['REDIS_HOST'] + \
                ':' + app.config['REDIS_PORT']

    cache = Cache(app, config={'CACHE_TYPE': 'redis',
                               'CACHE_DEFAULT_TIMEOUT': 0,
                               'CACHE_REDIS_URL': redis_url})

elif app.config['CACHE_TYPE'] == 'simple':
    cache = Cache(app, config={'CACHE_TYPE': 'simple',
                               'CACHE_DEFAULT_TIMEOUT': 0})

else:
    print("Invalid cache type.")
    sys.exit(1)


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
        # self.observer.join()

    def on_modified(self, event):
        print(self.filename)
        print(event.src_path)
        print(event)

        self.observer.stop()
        self.callback(self.path)

        # if not event.is_directory and self.filename and \
        #         event.src_path.endswith(self.filename):
        #     self.observer.stop()
        #     self.callback(self.path)
        # elif not self.filename and event.is_directory:
        #     self.observer.stop()
        #     self.callback(self.path)
        # else:
        #     log.error("Internal error: unknown watcher event")


def initialize(debug=False):
    log.info("Initializing validator service")

    try:
        cache.clear()
    except:
        sys.exit(1)

    cache.add('debug', debug)
    cache.add('artifacts', list())
    cache.add('validations', dict())
    cache.add('resources', dict())
    cache.add('latest', dict())
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

        assert (watch['type'] == 'project' or watch['type'] == 'package' or
                watch['type'] == 'service' or watch['type'] == 'function')

        install_watcher(watch_path, watch['type'], watch['syntax'],
                        watch['integrity'], watch['topology'])

        _validate_object(watch_path, watch_path, watch['type'],
                         watch['syntax'], watch['topology'],
                         watch['integrity'])


def set_watch(path, obj_type, syntax, integrity, topology):
    log.debug("Caching watch '{0}".format(path))
    watches = cache.get('watches')

    if not watches:
        watches = dict()

    if not watch_exists(path):
        watches[path] = dict()

    watches[path]['type'] = obj_type
    watches[path]['syntax'] = syntax
    watches[path]['integrity'] = integrity
    watches[path]['topology'] = topology

    cache.set('watches', watches)


def watch_exists(path):
    if not cache.get('watches'):
        return False
    return path in cache.get('watches').keys()


def get_watch(path):
    if not watch_exists(path):
        return
    return cache.get('watches')[path]


def set_artifact(artifact_path):
    log.debug("Caching artifact '{0}'".format(artifact_path))
    artifacts = cache.get('artifacts')
    if not artifacts:
        artifacts = list()
    artifacts.append(artifact_path)
    cache.set('artifacts', artifacts)


def add_artifact_root():
    artifact_root = os.path.join(app.config['ARTIFACTS_DIR'],
                                 str(time.time() * 1000))
    os.makedirs(artifact_root, exist_ok=False)
    set_artifact(artifact_root)
    return artifact_root


def update_latest(path, vid):
    log.debug("Updating latest validation for {0}: {1}".format(path, vid))
    latest = cache.get('latest')
    if not latest:
        latest = dict()

    latest[path] = vid
    cache.set('latest', latest)


def get_resource(rid):
    if not resource_exists(rid):
        return
    return cache.get('resources')[rid]


def resource_exists(rid):
    if not cache.get('resources'):
        return False
    return rid in cache.get('resources').keys()


def update_resource_validation(rid, vid):
    if not validation_exists(vid):
        log.error("Internal error: failed to update resource")
        return

    if not resource_exists(rid):
        return

    log.debug("Updating resource '{0}' to: '{1}'".format(rid, vid))
    resources = cache.get('resources')
    resources[rid]['latest_vid'] = vid
    cache.set('resources', resources)


def set_resource(rid, path, obj_type, syntax, integrity, topology):

    log.debug("Caching resource {0}".format(rid))
    resources = cache.get('resources')
    if not resources:
        resources = dict()

    if not resource_exists(rid):
        resources[rid] = dict()

    resources[rid]['path'] = path
    resources[rid]['type'] = obj_type
    resources[rid]['syntax'] = syntax
    resources[rid]['integrity'] = integrity
    resources[rid]['topology'] = topology

    cache.set('resources', resources)


def set_validation(vid, result=None, net_topology=None, net_fwgraph=None):
    assert result or net_topology or net_fwgraph

    log.debug("Caching validation '{0}'".format(vid))
    validations = cache.get('validations')

    if not validations:
        validations = dict()

    if vid not in validations.keys():
        validations[vid] = dict()

    if result:
        validations[vid]['result'] = result
    if net_topology:
        validations[vid]['net_topology'] = net_topology
    if net_fwgraph:
        validations[vid]['net_fwgraph'] = net_fwgraph

    cache.set('validations', validations)


def validation_exists(vid):
    if not cache.get('validations'):
        return False
    return vid in cache.get('validations').keys()


def get_validation(vid):
    if not validation_exists(vid):
        return
    return cache.get('validations')[vid]


def gen_resource_key(path, otype, s, i, t):
    assert (type(path) == str and type(otype) == str)

    res_hash = hashlib.md5()
    res_hash.update(path.encode('utf-8'))
    res_hash.update(otype.encode('utf-8'))
    if s:
        res_hash.update('syntax'.encode('utf-8'))
    if i:
        res_hash.update('integrity'.encode('utf-8'))
    if t:
        res_hash.update('topology'.encode('utf-8'))

    return res_hash.hexdigest()


def gen_validation_key(path):
    val_hash = hashlib.md5()

    # generate path hash
    val_hash.update(str(generate_hash(os.path.abspath(path)))
                    .encode('utf-8'))

    # validation event config must also be included
    val_hash.update(repr(sorted(EventLogger.load_eventcfg().items()))
                    .encode('utf-8'))

    return val_hash.hexdigest()


def process_request():
    source = request.form['source']
    if source == 'local' and 'path' in request.form:
        keypath = request.form['path']
        path = get_local(request.form['path'])
        if not path:
            return None, None

    elif source == 'url' and 'path' in request.form:
        keypath = request.form['path']
        path = get_url(request.form['path'])

    elif source == 'embedded' and 'file' in request.files:
        keypath = secure_filename(request.files['file'].filename)
        path = get_file(request.files['file'])

    else:
        req_errors.append('Invalid source, path or file parameters')
        return None, None

    return keypath, path


def _validate_object_from_watch(path):
    if not watch_exists(path):
        log.error("Invalid cached watch. Cannot proceed with validation")
        return

    watch = get_watch(path)
    log.debug("Validating {0} from watch: {1}".format(watch['type'], path))
    result = _validate_object(path, path, watch['type'], watch['syntax'],
                              watch['integrity'], watch['topology'])

    # re-schedule watcher
    install_watcher(path, watch['type'], watch['syntax'], watch['integrity'],
                    watch['topology'])

    if not result:
        return
    log.debug(result)


@app.before_request
def before():
    log.debug('headers: {0}'.format(request.headers))
    log.debug('body: {0}'.format(request.get_data()))


def _validate_object_from_request(object_type):

    assert object_type == 'project' or object_type == 'package' or \
           object_type == 'service' or object_type == 'function'

    keypath, path = process_request()
    if not keypath or not path:
        return render_errors(), 400

    syntax = str2bool(request.form['syntax']) \
        if 'syntax' in request.form else True
    integrity = str2bool(request.form['integrity']) \
        if 'integrity' in request.form else False
    topology = str2bool(request.form['topology']) \
        if 'topology' in request.form else False

    pkg_signature = request.form['pkg_signature'] \
        if 'pkg_signature' in request.form else None
    pkg_pubkey = request.form['pkg_pubkey'] \
        if 'pkg_pubkey' in request.form else None
    if not (pkg_signature and pkg_pubkey) and (pkg_signature or pkg_pubkey):
        req_errors.append("For package signature validation both "
                          "'pkg_signature' and 'pkg_pubkey' fields must be "
                          "set")
        return render_errors(), 400

    return _validate_object(keypath, path, object_type, syntax, integrity,
                            topology, pkg_signature=pkg_signature,
                            pkg_pubkey=pkg_pubkey)


def _events_config():

    if not request.form:
        return 'No events to configure', 400

    eventdict = EventLogger.load_eventcfg()

    for event in request.form.keys():
        if event not in eventdict:
            req_errors.append("Invalid event '{0}'".format(event))
            continue

        event_value = str(request.form[event]).lower()
        if not (event_value == 'error' or event_value == 'warning' or
                event_value == 'none'):
            req_errors.append("Invalid value for event '{0}': '{1}'"
                              .format(event, event_value))
            continue

        eventdict[event] = event_value

    if req_errors:
        return render_errors(), 400

    EventLogger.dump_eventcfg(eventdict)
    return 'OK', 200


def _events_list():
    eventdict = EventLogger.load_eventcfg()
    return json.dumps(eventdict, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


def validate_parameters(obj_type, syntax, integrity, topology):
    assert obj_type == 'project' or obj_type == 'package' or \
           obj_type == 'service' or obj_type == 'function'

    if obj_type == 'service' and (integrity or topology):
        return "Invalid parameters: cannot validate integrity and/or " \
               "topology of a standalone service"


def _validate_object(keypath, path, obj_type, syntax, integrity, topology,
                     pkg_signature=None, pkg_pubkey=None):
    # protect against incorrect parameters
    perrors = validate_parameters(obj_type, syntax, integrity, topology)
    if perrors:
        return perrors, 400

    rid = gen_resource_key(keypath, obj_type, syntax, integrity, topology)
    vid = gen_validation_key(path)

    resource = get_resource(rid)
    validation = get_validation(vid)

    if resource and validation:
        log.info("Returning cached result for '{0}'".format(vid))
        update_resource_validation(rid, vid)
        return validation['result']

    log.info("Starting validation [type={}, path={}, flags={}"
             "resource_id:={}, validation_id={}]"
             .format(obj_type, path, get_flags(syntax, integrity, topology),
                     rid, vid))

    set_resource(rid, keypath, obj_type, syntax, integrity, topology)

    validator = Validator()
    validator.configure(syntax, integrity, topology, debug=app.config['DEBUG'],
                        pkg_signature=pkg_signature, pkg_pubkey=pkg_pubkey)
    # remove default dpath
    validator.dpath = None
    val_function = getattr(validator, 'validate_' + obj_type)

    result = val_function(path)
    print_result(validator, result)
    json_result = gen_report_result(rid, validator)
    net_topology = gen_report_net_topology(validator)
    net_fwgraph = gen_report_net_fwgraph(validator)

    set_validation(vid, result=json_result, net_topology=net_topology,
                   net_fwgraph=net_fwgraph)
    update_resource_validation(rid, vid)

    return json_result


def render_errors():
    error_str = ''
    for error in req_errors:
        error_str += error + '\n'
    req_errors.clear()
    return error_str


@app.route('/')
def root():
    return '', 204


@app.route('/flush/validations', methods=['POST'])
def flush_validations():
    cache.set('validations', dict())
    return 'ok', 200


@app.route('/flush/artifacts', methods=['POST'])
def flush_artifacts():
    cache.set('artifacts', list())
    return 'ok', 200


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


@app.route('/events/config', methods=['POST'])
def events_config():
    return _events_config()


@app.route('/events/list', methods=['GET'])
def events_list():
    return _events_list()


@app.route('/validations', methods=['GET'])
def validations():
    """ retrieve list of available validations in cache """
    return gen_validations()


@app.route('/watches', methods=['GET'])
def watches():
    """ retrieve list of watched validations """
    return gen_watches()


@app.route('/report', methods=['GET'])
def report():
    """ retrieve latest validated resources"""
    return gen_report()


@app.route('/report/result/<string:resource_id>', methods=['GET'])
def report_result(resource_id):
    vid = get_resource(resource_id)['latest_vid']
    if (not validation_exists(vid) or
            'result' not in get_validation(vid).keys()):
        return '', 404

    return get_validation(vid)['result']


@app.route('/report/topology/<string:resource_id>', methods=['GET'])
def report_topology(resource_id):
    vid = get_resource(resource_id)['latest_vid']
    if (not validation_exists(vid) or
            'net_topology' not in get_validation(vid).keys()):
        return '', 404
    return get_validation(vid)['net_topology']


@app.route('/report/fwgraph/<string:resource_id>', methods=['GET'])
def report_fwgraph(resource_id):
    vid = get_resource(resource_id)['latest_vid']
    if (not validation_exists(vid) or
            'net_fwgraph' not in get_validation(vid).keys()):
        return '', 404
    return get_validation(vid)['net_fwgraph']


def gen_watches():
    # retrieve dictionary of watched resources, in the format:
    # path: { type | syntax | integrity | topology }
    report = dict()
    watches = cache.get('watches')
    if not watches:
        return '', 204
    for path, watch in watches.items():
        report[path] = dict()
        report[path]['type'] = watch['type']
        report[path]['syntax'] = watch['syntax']
        report[path]['integrity'] = watch['integrity']
        report[path]['topology'] = watch['topology']

    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def gen_validations():
    # retrieve dictionary of cached validations, in the format:
    # validation_id: { type | path | syntax | integrity | topology }
    report = dict()
    validations = cache.get('validations')
    if not validations:
        return '', 204

    for vid, validation in validations.items():
        report[vid] = dict()
        report[vid]['type'] = validation['type']
        report[vid]['path'] = validation['path']
        report[vid]['syntax'] = validation['syntax']
        report[vid]['integrity'] = validation['integrity']
        report[vid]['topology'] = validation['topology']

    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def gen_report():
    # resource_id {type | path | syntax | integrity | topology }
    report = dict()
    resources = cache.get('resources')
    validations = cache.get('validations')

    if not resources or not validations:
        return '', 204

    for rid, resource in resources.items():

        # omit resources that don't have a validation available
        vid = resource['latest_vid']
        if not validation_exists(vid):
            continue

        report[rid] = dict()
        report[rid]['type'] = resource['type']
        report[rid]['path'] = resource['path']
        report[rid]['syntax'] = resource['syntax']
        report[rid]['integrity'] = resource['integrity']
        report[rid]['topology'] = resource['topology']

    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def gen_report_result(resource_id, validator):

    print("building result report for {0}".format(resource_id))
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

    # TODO: temp patch for returning only the topology of the first service
    if len(report) > 0:
        report = report[0]
        return report

    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


def gen_report_net_fwgraph(validator):
    report = list()
    for sid, service in validator.storage.services.items():
        report.append(service.fw_graphs)

    # TODO: temp patch for returning only the fwgraph of the first service
    if len(report) > 0:
        report = report[0]

    return json.dumps(report, sort_keys=True,
                      indent=4, separators=(',', ': ')).encode('utf-8')


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


def get_flags(syntax, integrity, topology):
    return ('s' if syntax else '' +
            'i' if integrity else '' +
            't' if topology else '')


@atexit.register
def remove_artifacts():
    log.info("Removing artifacts")
    artifacts = cache.get('artifacts')
    if not artifacts:
        return
    for artifact in artifacts[::-1]:
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
        choices=['stateless', 'local'],
        default='stateless',
        help="Specify the mode of operation. 'stateless' mode will run as "
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
    app.config['DEBUG'] = True if args.debug else False

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
