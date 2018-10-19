import os

from .settings import *

ALLOWED_HOSTS = ['app']
DEBUG = False
PRODUCTION = True
SECRET_KEY = os.environ.get('SECRET_KEY')
