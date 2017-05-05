import os

HOST = os.environ.get('VAPI_HOST') or '0.0.0.0'
PORT = os.environ.get('VAPI_PORT') or 5001
CACHE_TYPE = os.environ.get('VAPI_CACHE_TYPE') or 'redis'
ARTIFACTS_DIR = os.environ.get('VAPI_ARTIFACTS_DIR') or \
                os.path.join(os.getcwd(), 'artifacts')

DEBUG = os.environ.get('VAPI_DEBUG') or False
