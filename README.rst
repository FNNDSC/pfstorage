###################
pfstorage  v1.1.0.2
###################

.. image:: https://badge.fury.io/py/pfstorage.svg
    :target: https://badge.fury.io/py/pfstorage

.. image:: https://travis-ci.org/FNNDSC/pfstorage.svg?branch=master
    :target: https://travis-ci.org/FNNDSC/pfstorage

.. image:: https://img.shields.io/badge/python-3.5%2B-blue.svg
    :target: https://badge.fury.io/py/pfcon

.. contents:: Table of Contents

********
Overview
********

This repository provides ``pfstorage`` -- a library / module that speaks to an object storage backend (such as *swift*) and also provides logic for handling input/output data locations for the ChRIS system.

pfstorage
=========

Most simply, ``pfstorage`` is a module that offers a regularized interface to some other backend object storage. While currently supporting ``swift``, the long term idea is to support a multitude of backends. By providing its own interface to several storage backends, this module removes the need for client code to change when a different object storage backend is used.

While at its core a module/library, ``pfstorage`` also provides two modes of stand-alone access: (1) a command line script interface mode to the library, and (2) a persistent http server mode. In the command line mode, the main module functions are exposed to appropriate CLI. In the http server mode, a client can use curl-type http calls to call the underlying library functions.

************
Installation
************

Installation is relatively straightforward, and we recommend using either python virtual environments or docker.

Python Virtual Environment
==========================

On Ubuntu, install the Python virtual environment creator

.. code-block:: bash

  sudo apt install virtualenv

Then, create a directory for your virtual environments e.g.:

.. code-block:: bash

  mkdir ~/python-envs

You might want to add to your .bashrc file these two lines:

.. code-block:: bash

    export WORKON_HOME=~/python-envs
    source /usr/local/bin/virtualenvwrapper.sh

Note that depending on distro, the virtualenvwrapper.sh path might be

.. code-block:: bash

    /usr/share/virtualenvwrapper/virtualenvwrapper.sh

Subsequently, you can source your ``.bashrc`` and create a new Python3 virtual environment:

.. code-block:: bash

    source .bashrc
    mkvirtualenv --python=python3 python_env

To activate or "enter" the virtual env:

.. code-block:: bash

    workon python_env

To deactivate virtual env:

.. code-block:: bash

    deactivate

Using the ``fnndsc/pfstorage`` docker container
================================================

The easiest option however, is to just use the ``fnndsc/pfstorage`` dock.

.. code-block:: bash

    docker pull fnndsc/pfstorage
    
and then run (for example in http server mode access to the library):

.. code-block:: bash

    docker run --name pfstorage -v /home:/Users --rm -ti \
           fnndsc/pfstorage \
           --ipSwift localhost \
           --portSwift 8080 \
           --forever \
           --httpResponse \
           --server

or in CLI mode:

.. code-block:: bash

    docker run --name pfstorage -v /home:/Users --rm -ti \
           fnndsc/pfstorage \
           --ipSwift localhost \
           --portSwift 8080 \
           --msg '
            { "action": "ls",
              "meta": {
                            "path":         "",       
                            "retSpec":      ["name", "bytes"]
                      }                                   
            }'
        

*****
Usage
*****

For usage of  ``pfstorage``, consult the relevant wiki pages  <https://github.com/FNNDSC/pfstorage/wiki/pfcon-overview>`.

Command line arguments
======================

.. code-block:: html

        --msg '<JSON_formatted>'
        The action to perform. This can be one of:

            * objPull -- pull data from storage to file system
            * objPush -- push data from file system to storage
            * ls      -- listing of data within storage

        with a JSON formatted string similar to:

            * ls:
            { "action": "ls",
              "meta": {
                            "path":         "",       
                            "retSpec":      ["name", "bytes"]
                      }                                   
            }

            * objPut:
            {  "action": "objPut",
                "meta": {
                            "putSpec":              "./data",
                            "inLocation":           "storage",
                            "mapLocationOver":      "./data"
                        }
            } 

            * objPull:
            {  "action": "objPull",
                "meta": {
                            "path":                 "chris",
                            "substr":               "/018",
                            "fromLocation":         "chris/uploads/DICOM",
                            "mapLocationOver":      "./data"
                        }
            }                     

        [--type <storageBackendType>]
        The type of object storage. Currently this is 'swift'.

        [--ipSwift <swiftIP>]                            
        The IP interface of the object storage service. Default %s.

        [--portSwift <swiftPort>]
        The port of the object storage service. Defaults to '8080'.

        [--ipSelf <selfIP>]                            
        The IP interface of the pfstorage service for server mode. Default %s.

        [--portSelf <selfPort>]
        The port of the pfstorage service for server mode. Defaults to '4055'.

        [--httpResponse]
        In servier mode, send return strings as HTTP formatted replies 
        with content-type html.

        [--configFileLoad <file>]
        Load configuration information from the JSON formatted <file>.

        [--configFileSave <file>]
        Save configuration information to the JSON formatted <file>.

        [-x|--desc]                                     
        Provide an overview help page.

        [-y|--synopsis]
        Provide a synopsis help summary.

        [--version]
        Print internal version number and exit.

        [--debugToDir <dir>]
        A directory to contain various debugging output -- these are typically
        JSON object strings capturing internal state. If empty string (default)
        then no debugging outputs are captured/generated. If specified, then
        ``pfcon`` will check for dir existence and attempt to create if
        needed.

        [-v|--verbosity <level>]
        Set the verbosity level. "0" typically means no/minimal output. Allows for
        more fine tuned output control as opposed to '--quiet' that effectively
        silences everything.


********
EXAMPLES
********

script mode
===========

.. code-block:: bash

    pfstorage                                               \
        --ipSwift localhost                                 \
        --portSwift 8080                                    \
        --verbosity 1                                       \
        --debugToDir /tmp                                   \
        --type swift                                        \
        --msg ' 
        {
            "action":   "ls",
            "meta": {
                "path":         "",       
                "retSpec":      ["name", "bytes"]
            }
        }
        '

server mode
===========

*start server*:

.. code-block:: bash

    pfstorage                                               \
        --ipSwift localhost                                 \
        --portSwift 8080                                    \
        --ipSelf localhost                                  \
        --portSelf 4055                                     \
        --httpResponse                                      \
        --verbosity 1                                       \
        --debugToDir /tmp                                   \
        --type swift                                        \
        --server                                            \
        --forever 

*query server*:

.. code-block:: bash

    pfurl --verb POST --raw                                 \
          --http localhost:4055/api/v1/cmd                  \
          --httpResponseBodyParse                           \
          --jsonwrapper 'payload'                           \
          --msg '
                {
                    "action":   "ls",
                    "meta": {
                        "path":         "",
                        "retSpec":      ["name", "bytes"]
                    }
                }
        '
