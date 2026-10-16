import os
import sys
sys.path.append(os.getcwd())
try:
    import sqlalchemy
    print("SQLAlchemy found")
except ImportError:
    print("SQLAlchemy NOT found")
