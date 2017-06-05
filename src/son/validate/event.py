import yaml
import logging
import os
import pkg_resources
import uuid
from copy import deepcopy


class EventLogger(object):

    def __init__(self, name):
        self._name = name
        self._log = logging.getLogger(name)
        self._events = dict()

        # load events config
        configpath = pkg_resources.resource_filename(
            __name__, os.path.join('eventcfg.yml'))
        with open(configpath, 'r') as _f:
            self._eventdict = yaml.load(_f)

    @property
    def errors(self):
        return list(filter(lambda event: event['level'] == 'error',
                           self._events.values()))

    @property
    def warnings(self):
        return list(filter(lambda event: event['level'] == 'warning',
                    self._events.values()))

    def reset(self):
        self._events.clear()

    def log(self, header, msg, source_id, event_code, event_id=None,
            detail_event_id=None):
        level = self._eventdict[event_code]
        key = self.get_key(source_id, event_code, level)

        if key not in self._events.keys():
            event = self._events[key] = dict()
            event['source_id'] = source_id
            event['event_code'] = event_code
            event['level'] = level
            event['event_id'] = event_id if event_id else source_id
            event['header'] = header
            event['detail'] = list()

            # log header upon new key
            if level == 'error':
                self._log.error(header)
            elif level == 'warning':
                self._log.warning(header)
            elif level == 'none':
                pass

        else:
            event = self._events[key]

        if not msg:
            return

        # log message
        if level == 'error':
            self._log.error(msg)
        elif level == 'warning':
            self._log.warning(msg)
        elif level == 'none':
            pass

        msg_dict = dict()
        msg_dict['message'] = msg
        msg_dict['detail_event_id'] = detail_event_id \
            if detail_event_id else event['event_id']
        event['detail'].append(msg_dict)

    @staticmethod
    def get_key(source_id, event_code, level):
        return source_id + '-' + event_code + '-' + level


class LoggerManager(object):

    def __init__(self):
        self._loggers = dict()

    def get_logger(self, name):
        if name not in self._loggers.keys():
            self._loggers[name] = EventLogger(name)

        return self._loggers[name]


EventLogger.manager = LoggerManager()


def get_logger(name):
    if not name:
        return
    return EventLogger.manager.get_logger(name)


def generate_evt_id():
    return str(uuid.uuid4())
