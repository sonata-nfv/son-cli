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
        self._events = list()

        # load events config
        configpath = pkg_resources.resource_filename(
            __name__, os.path.join('eventcfg.yml'))
        with open(configpath, 'r') as _f:
            self._eventdict = yaml.load(_f)

    @property
    def errors(self):
        return list(filter(lambda event: event['level'] == 'error',
                           self._events))

    @property
    def warnings(self):
        return list(filter(lambda event: event['level'] == 'warning',
                    self._events))

    @staticmethod
    def normalize(events):
        norm_events = deepcopy(events)

        idx = 0
        while idx < len(norm_events):
            event = norm_events[idx]
            offset = idx+1
            next_events = norm_events.copy()[offset:]

            for n_idx, n_event in enumerate(next_events):
                n_event = next_events[n_idx]

                if (event['object_id'] == n_event['object_id'] and
                        event['event_code'] == n_event['event_code'] and
                        event['level'] == n_event['level'] and
                        event['scope'] == n_event['scope']):
                    event['messages'] += n_event['messages']
                    norm_events.pop(n_idx+offset)

            idx += 1

        return norm_events

    def reset(self):
        self._events.clear()

    def log(self, msg, object_id, event_code, scope='single'):
        level = self._eventdict[event_code]

        if level == 'error':
            self._log.error(msg)
        elif level == 'warning':
            self._log.warning(msg)
        elif level == 'none':
            pass

        event = dict()
        event['object_id'] = object_id
        event['level'] = level
        event['event_code'] = event_code
        event['scope'] = scope
        event['messages'] = list()
        event['messages'].append(msg)
        self._events.append(event)


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
