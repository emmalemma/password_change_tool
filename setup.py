"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""
import os

from setuptools import setup
import shutil

APP = ['main.py']
DATA_FILES = [
    'managers',
    'rules',
    #'contrib',
]
OPTIONS = {
    'argv_emulation': True,
    #'site_packages': True,
    #'modules':['wx'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

root_dir = os.path.dirname(__file__)
shutil.copytree(os.path.join(root_dir, 'contrib'), os.path.join(root_dir, 'dist/main.app/Contents/Resources/contrib'))