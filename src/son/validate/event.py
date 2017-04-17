import yaml
import logging
import os
import pkg_resources


class EventLogger(object):

    def __init__(self, name):
        self._name = name
        self._log = logging.getLogger(name)
        self._events = dict()
        self.init_events()


        # load events config
        configpath = pkg_resources.resource_filename(
            __name__, os.path.join('eventcfg.yml'))
        with open(configpath, 'r') as _f:
            self._eventdict = yaml.load(_f)

    @property
    def errors(self):
        return self._events['error']

    @property
    def warnings(self):
        return self._events['warning']

    def reset(self):
        self._events.clear()
        self.init_events()

    def init_events(self):
        # initialize events logger
        for l in ['error', 'warning', 'none']:
            self._events[l] = []

    def log(self, msg, event):
        level = self._eventdict[event]

        if level == 'error':
            self._log.error(msg)
        elif level == 'warning':
            self._log.warning(msg)
        elif level == 'none':
            pass

        self._events[level].append(event)


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


if __name__ == "__main__":

    evtlog_ola = get_logger('ola')
    evtlog_ola.log("invalid package format", 'evt_package_invalid_format')

    evtlog_mundo = get_logger('mundo')
    evtlog_mundo.log("invalid md5 in package", 'evt_package_invalid_md5')


    print(evtlog_ola.errors)


