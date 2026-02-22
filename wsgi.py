# wsgi.py
import sys
import os

# Add your project directory to the sys.path
path = '/home/YOUR_USERNAME/vev-quizer-backend'
if path not in sys.path:
    sys.path.append(path)

# Import your Flask app
from run import app as application

# This is what PythonAnywhere looks for
application = application