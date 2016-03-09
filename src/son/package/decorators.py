import logging
import time


def performance(method):
    def measure(*args, **kwargs):
        log = logging.getLogger(method.__module__)
        start = time.time()
        result = method(*args, **kwargs)
        log.info('{0} executed in {1:.3f} sec'.format(method.__name__, time.time() - start))
        return result

    return measure
