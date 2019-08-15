import sys
import os
# Make sure we are running python3.5+
if 10 * sys.version_info[0]  + sys.version_info[1] < 35:
    sys.exit("Sorry, only Python 3.5+ is supported.")

from setuptools import setup


def readme():
    print("Current dir = %s" % os.getcwd())
    print(os.listdir())
    with open('README.rst') as f:
        return f.read()

setup(
      name             =   'pfstorage',
      version          =   '1.0.0.0',
      description      =   'openstorage interface',
      long_description =   readme(),
      author           =   'Rudolph Pienaar',
      author_email     =   'rudolph.pienaar@gmail.com',
      url              =   'https://github.com/FNNDSC/pfstorage',
      packages         =   ['pfstorage'],
      install_requires =   ['pycurl', 'pyzmq', 'webob', 'pudb', 'psutil', 'pfurl', 'pfmisc', 'python-swiftclient'],
      test_suite       =   'nose.collector',
      tests_require    =   ['nose'],
      scripts          =   ['bin/pfstorage'],
      license          =   'MIT',
      zip_safe         =   False
     )
