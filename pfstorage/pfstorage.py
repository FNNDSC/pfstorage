#!/usr/bin/env python3.5

import  abc

import  sys
from    io              import  BytesIO as IO
from    http.server     import  BaseHTTPRequestHandler, HTTPServer
from    socketserver    import  ThreadingMixIn
from    webob           import  Response
from    pathlib         import  Path
import  cgi
import  json
import  urllib
import  ast
import  shutil
import  datetime
import  time
import  inspect
import  pprint

import  threading
import  platform
import  socket
import  psutil
import  os
import  multiprocessing
import  pfurl
import  configparser
import  swiftclient

import  pfmisc

# debugging utilities
import  pudb

# pfstorage local dependencies
from    pfmisc._colors      import  Colors
from    pfmisc.debug        import  debug
from    pfmisc.C_snode      import *

# Global vars for comms between StoreHandler and HTTPServer
Gd_args             = {}
Gstr_description    = ""
Gstr_version        = ""

# Horrible global var
G_b_httpResponse            = False

def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate

class S:
    """
    A somewhat cryptically named class that keeps system state.

    Calls to the HTTPServer re-initialize the StoreHandler class -- this 
    effectively means any per-instance state information is lost across
    calls. 

    Barring the use of a module-wide global variable, this class keeps 
    state information as a class (not instance)-variable -- which 
    effectively is analogous to a namespaced global variable.

    State-related class variables can thus be accessed by calling the 
    class directly, 'S'. For example, to change values in the state
    tree structure, simply call 'S.T.<method>'.

    """
    d_state =  {}
    T       = C_stree()
    b_init  = False

    def state_init(self, d_args, str_desc, str_version):
        """
        Populate the internal <self.state> dictionary based on the 
        passed 'args'
        """

        # pudb.set_trace()

        # Initializing from file state will always flush and
        # recreate, destroying any previous state.
        if len(d_args['str_configFileLoad']):
            if Path(d_args['str_configFileLoad']).is_file():
                # Read configuration detail from JSON formatted file
                with open(d_args['str_configFileLoad']) as json_file:
                    S.d_state   = json.load(json_file)
                    S.b_init    = False
        else:
            if not S.b_init:
                S.d_state = {
                    'this': {
                        'name':                 'pfstorage',
                        'version':              str_version,
                        'desc':                 str_desc,
                        'verbosity':            int(d_args['verbosity']),
                        'debugToDir':           d_args['str_debugToDir'],
                        'configFileLoad':       d_args['str_configFileLoad'],
                        'configFileSave':       d_args['str_configFileSave'],
                        'args':                 d_args
                    },
                    "swift": {
                        "auth_url":                 "http://%s:%s/auth/v1.0" % \
                                                    (d_args['ipSwift'], d_args['portSwift']),
                        # "auth_url":                 "http://10.72.76.155:8080/auth/v1.0",
                        "username":                 "chris:chris1234",
                        "key":                      "testing",
                        "container_name":           "users",
                        "auto_create_container":    True,
                        "file_storage":             "swift.storage.SwiftStorage"
                    }
                }

        if not S.b_init:
            S.T.initFromDict(S.d_state)
            S.b_init    = True
        if len(S.T.cat('/this/debugToDir')):
            if not os.path.exists(S.T.cat('/this/debugToDir')):
                os.makedirs(S.T.cat('/this/debugToDir'))

    def __init__(self, *args, **kwargs):
        """
        The logic of this constructor reflects a bit from legacy design 
        patterns of `pfcon` -- specifically the passing of flags in a 
        single structure, and the <self.state> dictionary to try and
        organize the space of <self> variables a bit logically.
        """

        b_test                  = False
        d_args                  = {}
        str_desc                = ''
        str_version             = ''

        # pudb.set_trace()

        for k,v in kwargs.items():
            if k == 'test':     b_test          = True
            if k == 'args':     d_args          = v
            if k == 'desc':     str_desc        = v
            if k == 'version':  str_version     = v

        self.state_init(d_args, str_desc, str_version)

        self.dp                 = pfmisc.debug(    
                                            verbosity   = S.T.cat('/this/verbosity'),
                                            within      = S.T.cat('/this/name')
                                            )
        self.pp                 = pprint.PrettyPrinter(indent=4)

        self.dp.qprint(d_args['desc'], level = 1)
        self.dp.qprint(
            Colors.YELLOW + "\n\t\tInternal data tree:", 
            level   = 1,
            syslog  = False)
        self.dp.qprint(
            C_snode.str_blockIndent(str(S.T), 3, 8), 
            level   = 1,
            syslog  = False)

    def leaf_process(self, **kwargs):
        """
        Process the storage state tree and perform possible env substitutions.
        """
        str_path    = ''
        str_target  = ''
        str_newVal  = ''

        for k,v in kwargs.items():
            if k == 'where':    str_path    = v
            if k == 'replace':  str_target  = v
            if k == 'newVal':   str_newVal  = v

        str_parent, str_file    = os.path.split(str_path)
        str_pwd                 = S.T.cwd()
        if S.T.cd(str_parent)['status']:
            str_origVal     = S.T.cat(str_file)
            str_replacement = str_origVal.replace(str_target, str_newVal)
            S.T.touch(str_path, str_replacement)
            S.T.cd(str_pwd)

    def internalvar_getProcess(self, d_meta):
        """
        process the 'get' directive
        """
        str_var     = d_meta['var']
        d_ret       = {}
        b_status    = False
        T           = C_stree()

        if S.T.isdir(str_var):
            S.T.copy(startPath = str_var, destination = T)
            d_ret                   = dict(T.snode_root)
        else:
            d_ret[str_var]          = S.T.cat(str_var)
        b_status                = True
        return b_status, d_ret

    def internalvar_setProcess(self, d_meta):
        """
        process the 'set' directive
        """
        str_var     = d_meta['var']
        d_ret       = {}
        b_status    = False
        b_tree      = False
                    
        try:
            d_set       = json.loads(d_meta['set'])
        except:
            str_set     = json.dumps(d_meta['set'])
            d_set       = json.loads(str_set)
            if isinstance(d_set, dict):
                b_tree  = True
        if b_tree:
            D       = C_stree()
            D.initFromDict(d_set)
            if not S.T.exists(str_var):
                S.T.mkdir(str_var)
            for topDir in D.lstr_lsnode():
                D.copy(
                        startPath       = '/'+topDir, 
                        destination     = S.T, 
                        pathDiskRoot    = str_var
                    )
            d_ret           = d_set
        else:
            S.T.touch(str_var, d_meta['set'])
            d_ret[str_var]  = S.T.cat(str_var)
        b_status    = True
        return b_status, d_ret

    def internalvar_valueReplaceProcess(self, d_meta):
        """
        process the 'valueReplace' directive

        Find all the values in the internalctl tree
        and replace the value corresponding to 'var' with
        the field of 'valueReplace'
        """

        hits            = 0
        l_fileChanged   = []

        def fileContentsReplaceAtPath(str_path, **kwargs):
            nonlocal    hits
            nonlocal    l_fileChanged
            b_status        = True
            str_target      = ''
            str_value       = ''
            self.dp.qprint('In dir = %s, hits = %d' % (str_path, hits))
            for k, v in kwargs.items():
                if k == 'target':   str_target  = v
                if k == 'value':    str_value   = v
            for str_hit in S.T.lsf(str_path):
                str_content = S.T.cat(str_hit)
                self.dp.qprint('%20s: %20s' % (str_hit, str_content))
                if str_content  == str_target:
                    self.dp.qprint('%20s: %20s' % (str_hit, str_value))
                    S.T.touch(str_hit, str_value)
                    b_status    = True
                    hits        = hits + 1
                    l_fileChanged.append(str_path + '/' + str_hit)

            return {
                    'status':           b_status,
                    'l_fileChanged':    l_fileChanged
                    }

        d_ret       = {}
        b_status    = False
        str_target      = d_meta['var']
        str_value       = d_meta['valueReplace']
        if str_value    == 'ENV':
            if str_target.strip('%') in os.environ:
                str_value   = os.environ[str_target.strip('%')]
        d_ret = S.T.treeExplore(
                f       = fileContentsReplaceAtPath, 
                target  = str_target, 
                value   = str_value
                )
        b_status        = d_ret['status']
        d_ret['hits']   = hits
        return b_status, d_ret

    def internalctl_varprocess(self, *args, **kwargs):
        """

        get/set a specific variable as parsed from the meta JSON.

        :param args:
        :param kwargs:
        :return:
        """

        d_meta          = {}
        d_ret           = {}
        b_status        = False

        for k,v in kwargs.items():
            if k == 'd_meta':   d_meta  = v
            
        if d_meta:
            if 'get' in d_meta.keys():
                b_status, d_ret = self.internalvar_getProcess(d_meta)

            if 'set' in d_meta.keys():
                # pudb.set_trace()
                b_status, d_ret = self.internalvar_setProcess(d_meta)

            if 'valueReplace' in d_meta.keys():
                b_status, d_ret = self.internalvar_setProcess(d_meta)

        return {'d_ret':    d_ret,
                'status':   b_status}

    def internalctl_process(self, *args, **kwargs):
        """

        Process the 'internalctl' action.

                {  "action": "internalctl",
                        "meta": {
                            "var":      "/tree/path",
                            "set":     "<someValue>"
                        }
                }

                {  "action": "internalctl",
                        "meta": {
                            "var":      "/tree/path",
                            "get":      "currentPath"
                        }
                }

        :param args:
        :param kwargs:
        :return:
        """

        d_request           = {}
        b_status            = False
        d_ret               = {
            'status':   b_status
        }

        for k,v in kwargs.items():
            if k == 'request':   d_request   = v
        if d_request:
            d_meta  = d_request['meta']
            d_ret   = self.internalctl_varprocess(d_meta = d_meta)
        return d_ret
            

class PfStorage(metaclass = abc.ABCMeta):

    def __init__(self, *args, **kwargs):
        """
        The logic of this constructor reflects a bit from legacy design 
        patterns of `pfcon` -- specifically the passing of flags in a 
        single structure, and the <self.state> dictionary to try and
        organize the space of <self> variables a bit logically.
        """

        b_test                  = False
        d_args                  = {}
        str_desc                = ''
        str_version             = ''

        # pudb.set_trace()

        for k,v in kwargs.items():
            if k == 'test':     b_test          = True
            if k == 'args':     d_args          = v
            if k == 'desc':     str_desc        = v
            if k == 'version':  str_version     = v

        self.s                  = S(*args, **kwargs)
        self.dp                 = pfmisc.debug(    
                                            verbosity   = S.T.cat('/this/verbosity'),
                                            within      = S.T.cat('/this/name')
                                            )
        self.pp                 = pprint.PrettyPrinter(indent=4)

    def filesFind(self, *args, **kwargs):
        """
        This method simply returns a list of files 
        and directories down a filesystem tree starting 
        from the kwarg:

            root = <someStartPath>

        """
        d_ret      = {
            'status':   False,
            'l_fileFS': [],
            'l_dirFS':  [],
            'numFiles': 0,
            'numDirs':  0
        }
        str_rootPath    = ''
        for k,v in kwargs.items():
            if k == 'root': str_rootPath    = v
        if len(str_rootPath):
            # Create a list of all files down the <str_rootPath>
            for root, dirs, files in os.walk(str_rootPath):
                for filename in files:
                    d_ret['l_fileFS'].append(os.path.join(root, filename))
                    d_ret['status'] = True
                for dirname in dirs:
                    d_ret['l_dirFS'].append(os.path.join(root, dirname))
        
        d_ret['numFiles']   = len(d_ret['l_fileFS'])
        d_ret['numDirs']    = len(d_ret['l_dirFS'])
        return d_ret

    def run(self, str_msg):
        """
        Execute the actual action, essentially a light refactoring
        of the POST actionParse method of the server.

        Essentially, any "action" string passed by the client is mapped
        to a method <action>_process() -- of course assuming that this
        method exists.
        """

        # Default result dictionary. Note that specific methods
        # might return a different dictionary. It is NOT safe to
        # assume that all action processing methods will honor this
        # tempate.
        d_actionResult      = {
            'status':       False,
            'msg':          ''
        }

        d_msg   = json.loads(str_msg)

        if 'action' in d_msg:  
            self.dp.qprint("verb: %s detected." % d_msg['action'], comms = 'status')
            str_method      = '%s_process' % d_msg['action']
            self.dp.qprint("method to call: %s(request = d_msg) " % str_method, comms = 'status')
            try:
                # pudb.set_trace()
                method              = getattr(self, str_method)
                d_actionResult      = method(request = d_msg)
            except:
                str_msg     = "Class '{}' does not implement method '{}'".format(
                                        self.__class__.__name__, 
                                        str_method)
                d_actionResult      = {
                    'status':   False,
                    'msg':      str_msg
                }
                self.dp.qprint(str_msg, comms = 'error')
            self.dp.qprint(json.dumps(d_actionResult, indent = 4), comms = 'tx')
        
        return d_actionResult

    @abc.abstractmethod
    def connect(self, *args, **kwargs):
        """
        The base connection class. 
        
        This handles the connection to the openstorage providing service.
        """

    @abc.abstractmethod
    def ls_process(self, *args, **kwargs):
        """
        The base ls process method. 
        
        This handles the ls processing in the openstorage providing service.
        """

    @abc.abstractmethod
    def ls(self, *args, **kwargs):
        """
        Base listing class.
        
        Provide a listing of resources in the openstorage providing
        service.
        """

    @abc.abstractmethod
    def objExists(self, *args, **kwargs):
        """
        Base object existance class.

        Check if an object exists in the openstorage providing service.
        """

    @abc.abstractmethod
    def objPut(self, *args, **kwargs):
        """
        Base object put method.

        Put a list of (file) objects into storage.
        """

    @abc.abstractmethod
    def objPull(self, *args, **kwargs):
        """
        Base object pull method.

        Pull a list of (file) objects from storage.
        """        

class swiftStorage(PfStorage):

    def __init__(self, *args, **kwargs):
        """
        Core initialization and logic in the base class
        """

        PfStorage.__init__(self, *args, **kwargs)

    @static_vars(str_prependBucketPath = "")
    def connect(self, *args, **kwargs):
        """
        Connect to swift storage and return the connection object,
        as well an optional "prepend" string to fully qualify 
        object location in swift storage.

        The 'prependBucketPath' is somewhat 'legacy' to a similar
        method in charm.py and included here with the idea 
        to eventually converge on a single swift-based intermediary
        library for both pfcon and CUBE.
        """

        b_status                = True

        for k,v in kwargs.items():
            if k == 'prependBucketPath':    self.connect.str_prependBucketPath = v

        d_ret       = {
            'status':               b_status,
            'conn':                 None,
            'prependBucketPath':    self.connect.str_prependBucketPath,
            'user':                 S.T.cat('/swift/username'),
            'key':                  S.T.cat('/swift/key'),
            'authurl':              S.T.cat('/swift/auth_url'),
            'container_name':       S.T.cat('/swift/container_name')
        }

        # initiate a swift service connection, based on internal
        # settings already available in the django variable space.
        try:
            d_ret['conn'] = swiftclient.Connection(
                user    = d_ret['user'],
                key     = d_ret['key'],
                authurl = d_ret['authurl']
            )
        except:
            d_ret['status'] = False

        return d_ret

    def ls_process(self, *args, **kwargs):
        """
        Process the 'ls' directive (in the appropriate subclass).

        For the case of 'swift', the return dictionary contains a 
        key, 'objectDict' containing a list of dictionaries which 
        in turn have keys: 

            'hash', 'last_modified', 'bytes', 'name', 'content-type'

        """
        d_ret       = {'status': False}
        d_ls        = {}
        d_lsFilter  = {}
        d_msg       = {}
        d_meta      = {}
        l_retSpec   = ['name']  

        for k, v in kwargs.items():
            if k == 'request':      d_msg       = v

        if 'meta' in d_msg:
            d_meta  = d_msg['meta']
            if 'retSpec' in d_meta:
                l_retSpec   = d_meta['retSpec']
            d_ls = self.ls(**d_meta)
            d_ret['status'] = d_ls['status']
            if len(l_retSpec):
                d_lsFilter  = [ {x: y[x] for x in l_retSpec} for y in d_ls['objectDict'] ]
                d_ret['ls'] = d_lsFilter
            else:
                d_ret['ls'] = d_ls

        return d_ret

    def ls(self, *args, **kwargs):
        """
        Return a list of objects in the swiftstorage -- 

        The actual object list is returned in 'objectDict' and
        a separate, simplfied list of only filenames is returned
        in 'lsList'. Note that lsList is filtered from 'objectDict'.

        'objectList' contains a list of dictionaries with keys:

            'hash', 'last_modified', 'bytes', 'name'
            
        """

        l_ls                    = []    # The listing of names to return
        ld_obj                  = {}    # List of dictionary objects in swift
        str_path                = '/'
        str_fullPath            = ''
        str_subString           = ''
        b_prependBucketPath     = False
        b_status                = False

        for k,v in kwargs.items():
            if k == 'path':                 str_path            = v
            if k == 'prependBucketPath':    b_prependBucketPath = v
            if k == 'substr':               str_subString       = v

        # Remove any leading noise on the str_path, specifically
        # any leading '.' characters.
        # This is probably not very robust!
        while str_path[:1] == '.':  str_path    = str_path[1:]

        d_conn          = self.connect(**kwargs)
        if d_conn['status']:
            conn        = d_conn['conn']
            if b_prependBucketPath:
                str_fullPath    = '%s%s' % (d_conn['prependBucketPath'], str_path)
            else:
                str_fullPath    = str_path

            # get the full list of objects in Swift storage with given prefix
            ld_obj = conn.get_container( 
                        d_conn['container_name'], 
                        prefix          = str_fullPath,
                        full_listing    = True)[1]
                        
            if len(str_subString):
                ld_obj  = [x for x in ld_obj if str_subString in x['name']]

            l_ls    = [x['name'] for x in ld_obj]
            if len(l_ls):   b_status    = True
        
        return {
            'status':       b_status,
            'objectDict':   ld_obj,
            'lsList':       l_ls,
            'fullPath':     str_fullPath
        }

    def objExists(self, *args, **kwargs):
        """
        Return True/False if passed object exists in swift storage
        """        
        b_exists    = False
        str_obj     = ''

        for k,v in kwargs.items():
            if k == 'obj':                  str_obj             = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        kwargs['path']  = str_obj
        d_swift_ls  = self.ls(*args, **kwargs)
        str_obj     = d_swift_ls['fullPath']

        if d_swift_ls['status']:
            for obj in d_swift_ls['lsList']:
                if obj == str_obj:
                    b_exists = True

        return {
            'status':   b_exists,
            'objPath':  str_obj
        }

    def objPut_process(self, *args, **kwargs):
        """
        Process the 'objPut' directive.
        """
        d_ret       = {
            'status':   False,
            'msg':      "No 'meta' JSON directive found in request"
        }
        d_msg       = {}
        d_meta      = {}
        str_putSpec = ""

        for k, v in kwargs.items():
            if k == 'request':      d_msg       = v

        if 'meta' in d_msg:
            d_meta              = d_msg['meta']
            if 'putSpec' in d_meta:
                str_putSpec         = d_meta['putSpec']
                d_fileList          = self.filesFind(root = str_putSpec)
                if d_fileList['status']:
                    d_meta['fileList']  = d_fileList['l_fileFS']
                    d_ret               = self.objPut(**d_meta)
                else:
                    d_ret['msg']    = 'No valid file list generated'

        return d_ret

    def objPut(self, *args, **kwargs):
        """
        Put an object (or list of objects) into swift storage.

        This method also "maps" tree locations in the local storage
        to new locations in the object storage. For example, assume
        a list of local locations starting with:

                    /home/user/project/data/ ...

        and we want to pack everything in the 'data' dir to 
        object storage, at location '/storage'. In this case, the
        pattern of kwargs specifying this would be:

                    fileList = ['/home/user/project/data/file1',
                                '/home/user/project/data/dir1/file_d1',
                                '/home/user/project/data/dir2/file_d2'],
                    inLocation      = '/storage',
                    mapLocationOver = '/home/user/project/data'

        will replace, for each file in <fileList>, the <mapLocationOver> with
        <inLocation>, resulting in a new list

                    '/storage/file1', 
                    '/storage/dir1/file_d1',
                    '/storage/dir2/file_d2'

        Note that the <inLocation> is subject to <b_prependBucketPath>!

        """
        b_status                = True
        l_localfile             = []    # Name on the local file system
        l_objectfile            = []    # Name in the object storage
        str_swiftLocation       = ''
        str_mapLocationOver     = ''
        str_localfilename       = ''
        str_storagefilename     = ''
        str_prependBucketPath   = ''
        d_ret                   = {
            'status':           b_status,
            'localFileList':    [],
            'objectFileList':   [],
            'localpath':        ''
        }

        d_conn  = self.connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath       = d_conn['prependBucketPath']

        str_swiftLocation               = str_prependBucketPath

        for k,v in kwargs.items():
            if k == 'file':             l_localfile.append(v)
            if k == 'fileList':         l_localfile         = v
            if k == 'inLocation':       str_swiftLocation   = '%s%s' % (str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_objectfile    = [w.replace(str_mapLocationOver, str_swiftLocation) \
                                for w in l_localfile]
        else:
            # Prepend the swiftlocation to each element in the localfile list:
            l_objectfile    = [str_swiftLocation + '{0}'.format(i) for i in l_localfile]

        d_ret['localpath']  = os.path.dirname(l_localfile[0])

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile): 
                try:
                    d_ret['status'] = True and d_ret['status']
                    with open(str_localfilename, 'rb') as fp:
                        d_conn['conn'].put_object(
                            d_conn['container_name'],
                            str_storagefilename,
                            contents=fp.read()
                        )
                except Exception as e:
                    d_ret['error']  = e
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret

    def objPull_process(self, *args, **kwargs):
        """
        Process the 'objPull' directive.
        """
        d_ret       = {
            'status':   False,
            'msg':      "No 'meta' JSON directive found in request"
        }
        d_msg       = {}
        d_meta      = {}

        for k, v in kwargs.items():
            if k == 'request':      d_msg       = v

        if 'meta' in d_msg:
            d_meta  = d_msg['meta']
            d_ret   = self.objPull(**d_meta)

        return d_ret

    def objPull(self, *args, **kwargs):
        """
        Pull an object (or set of objects) from swift storage and
        onto the local filesystem.

        This method can also "map" locations in the object storage
        to new locations in the filesystem storage. For example, assume
        a list of object locations starting with:

                user/someuser/uploads/project/data ...

        and we want to pack everything from 'data' to the local filesystem
        to, for example, 

                /some/dir/data

        In this case, the pattern of kwargs specifying this would be:

                    fromLocation    = user/someuser/uploads/project/data
                    mapLocationOver = /some/dir/data

        if 'mapLocationOver' is not specified, then the local file system
        location will be the 'inLocation' prefixed with a '/'.

        """
        b_status                = True
        l_localfile             = []    # Name on the local file system
        l_objectfile            = []    # Name in the object storage
        str_swiftLocation       = ''
        str_mapLocationOver     = ''
        str_localfilename       = ''
        str_storagefilename     = ''
        str_prependBucketPath   = ''
        d_ret                   = {
            'status':           b_status,
            'localFileList':    [],
            'objectFileList':   [],
            'localpath':        ''
        }

        d_conn  = self.connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath       = d_conn['prependBucketPath']

        str_swiftLocation               = str_prependBucketPath

        for k,v in kwargs.items():
            if k == 'fromLocation':     str_swiftLocation   = '%s%s' % (str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v

        # Get dictionary of objects in storage
        d_ls            = self.ls(*args, **kwargs)

        # List of objects in storage
        l_objectfile    = [x['name'] for x in d_ls['objectDict']]

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_localfile         = [w.replace(str_swiftLocation, str_mapLocationOver) \
                                    for w in l_objectfile]
        else:
            # Prepend a '/' to each element in the l_objectfile:
            l_localfile         = ['/' + '{0}'.format(i) for i in l_objectfile]
            str_mapLocationOver =  '/' + str_swiftLocation

        d_ret['localpath']          = str_mapLocationOver
        d_ret['currentWorkingDir']  = os.getcwd()

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile):
                try:
                    d_ret['status'] = True and d_ret['status']
                    obj_tuple       = d_conn['conn'].get_object(
                                                    d_conn['container_name'],
                                                    str_storagefilename
                                                )
                    str_parentDir   = os.path.dirname(str_localfilename)
                    os.makedirs(str_parentDir, exist_ok = True)
                    with open(str_localfilename, 'wb') as fp:
                        # fp.write(str(obj_tuple[1], 'utf-8'))
                        fp.write(obj_tuple[1])
                except Exception as e:
                    d_ret['error']  = str(e)
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret

class StoreHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        """
        Handler constructor
        """

        global  Gd_args, Gstr_description, Gstr_version

        for k,v in kwargs.items():
            if k == 'args':     Gd_args             = v
            if k == 'desc':     Gstr_description    = v
            if k == 'version':  Gstr_version        = v

        self.storage            = swiftStorage(
                    args        = Gd_args,
                    desc        = Gstr_description,
                    version     = Gstr_version
        )

        self.dp         = pfmisc.debug(    
                                    verbosity   = int(Gd_args['verbosity']),
                                    within      = S.T.cat('/this/name')
                                    )
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        d_server            = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        d_meta              = ast.literal_eval(d_server['meta'])

        d_msg               = {'action': d_server['action'], 'meta': d_meta}
        d_ret               = {}
        print("Request: " + self.headers + '\n' + d_msg)
        self.dp.qprint(self.path, comms = 'rx')
        return d_ret

    def internalctl_process(self, *args, **kwargs):
        """
        Process any internal state directives.
        """

        return self.storage.s.internalctl_process(*args, **kwargs)

    def ls_process(self, *args, **kwargs):
        """
        Process the 'ls' directive -- return an object listing.
        """

        return self.storage.ls_process(*args, **kwargs)

    def objPull_process(self, *args, **kwargs):
        """
        Process the 'objPull' directive
        """

        return self.storage.objPull_process(*args, **kwargs)

    def hello_process(self, *args, **kwargs):
        """

        The 'hello' action is merely to 'speak' with the server. The server
        can return current date/time, echo back a string, query the startup
        command line args, etc.

        This method is a simple means of checking if the server is "up" and
        running.

        :param args:
        :param kwargs:
        :return:
        """
        self.dp.qprint("hello_process()", comms = 'status')
        b_status            = False
        d_ret               = {}
        d_request           = {}
        for k, v in kwargs.items():
            if k == 'request':      d_request   = v

        d_meta  = d_request['meta']
        if 'askAbout' in d_meta.keys():
            str_askAbout    = d_meta['askAbout']
            d_ret['name']       = S.T.cat('/this/name')
            d_ret['version']    = S.T.cat('/this/version')
            if str_askAbout == 'timestamp':
                str_timeStamp   = datetime.datetime.today().strftime('%Y%m%d%H%M%S.%f')
                d_ret['timestamp']              = {}
                d_ret['timestamp']['now']       = str_timeStamp
                b_status                        = True
            if str_askAbout == 'sysinfo':
                d_ret['sysinfo']                = {}
                d_ret['sysinfo']['system']      = platform.system()
                d_ret['sysinfo']['machine']     = platform.machine()
                d_ret['sysinfo']['platform']    = platform.platform()
                d_ret['sysinfo']['uname']       = platform.uname()
                d_ret['sysinfo']['version']     = platform.version()
                d_ret['sysinfo']['memory']      = psutil.virtual_memory()
                d_ret['sysinfo']['cpucount']    = multiprocessing.cpu_count()
                d_ret['sysinfo']['loadavg']     = os.getloadavg()
                d_ret['sysinfo']['cpu_percent'] = psutil.cpu_percent()
                d_ret['sysinfo']['hostname']    = socket.gethostname()
                d_ret['sysinfo']['inet']        = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
                b_status                        = True
            if str_askAbout == 'echoBack':
                d_ret['echoBack']               = {}
                d_ret['echoBack']['msg']        = d_meta['echoBack']
                b_status                        = True

        return { 'd_ret':       d_ret,
                 'status':      b_status}

    def key_dereference(self, *args, **kwargs):
        """
        Given the 'coordinate' JSON payload, deference the 'key' and return
        its value in a dictionary.

        {   
            'status', <status>,
            key': <val>
        }

        """
        self.dp.qprint("key_dereference()", comms = 'status')
        
        b_status    = False
        d_request   = {}
        str_key     = ''
        for k,v in kwargs.items():
            if k == 'request':      d_request   = v

        # self.dp.qprint("d_request = %s" % d_request)

        if 'meta-store' in d_request:
            d_metaStore     = d_request['meta-store']
            if 'meta' in d_metaStore:
                str_storeMeta   = d_metaStore['meta']
                str_storeKey    = d_metaStore['key']
                if str_storeKey in d_request[str_storeMeta].keys():
                    str_key     = d_request[str_storeMeta][str_storeKey]
                    b_status    = True
                    self.dp.qprint("key = %s" % str_key, comms = 'status')
        return {
            'status':   b_status,
            'key':      str_key
        }

    def do_POST_actionParse(self, d_msg):
        """
        Parse the "action" passed by the client.

        Essentially, any "action" string passed by the client is mapped
        to a method <action>_process() -- of course assuming that this
        method exists.
        """

        # Default result dictionary. Note that specific methods
        # might return a different dictionary. It is NOT safe to
        # assume that all action processing methods will honor this
        # tempate.
        d_actionResult      = {
            'status':       True,
            'msg':          ''
        }

        self.dp.qprint("verb: %s detected." % d_msg['action'], comms = 'status')
        str_method      = '%s_process' % d_msg['action']
        self.dp.qprint("method to call: %s(request = d_msg) " % str_method, comms = 'status')
        try:
            # pudb.set_trace()
            method              = getattr(self, str_method)
            d_actionResult      = method(request = d_msg)
        except:
            str_msg     = "Class '{}' does not implement method '{}'".format(
                                    self.__class__.__name__, 
                                    str_method)
            d_actionResult      = {
                'status':   False,
                'msg':      str_msg
            }
            self.dp.qprint(str_msg, comms = 'error')
        self.dp.qprint(json.dumps(d_actionResult, indent = 4), comms = 'tx')
        
        return d_actionResult

    def do_POST_serverctl(self, d_meta):
        """
        """
        d_ctl   = d_meta['ctl']
        d_ret   = {
            'status':   True,
            'msg':      ''
        }
        self.dp.qprint('Processing server ctl...', comms = 'status')
        self.dp.qprint(d_meta, comms = 'rx')
        if 'serverCmd' in d_ctl:
            if d_ctl['serverCmd'] == 'quit':
                self.dp.qprint('Shutting down server', comms = 'status')
                d_ret = {
                    'msg':      'Server shut down',
                    'status':   True
                }
                self.dp.qprint(d_ret, comms = 'tx')
                self.ret_client(d_ret)
                os._exit(0)
        return d_ret

    # def form_get(self, str_verb, data):
    #     """
    #     Returns a form from cgi.FieldStorage
    #     """
    #     return cgi.FieldStorage(
    #         IO(data),
    #         headers = self.headers,
    #         environ =
    #         {
    #             'REQUEST_METHOD':   str_verb,
    #             'CONTENT_TYPE':     self.headers['Content-Type'],
    #         }
    #     )

    def form_get(self, str_verb):
        """
        Returns a form from cgi.FieldStorage
        """
        return cgi.FieldStorage(
            fp = self.rfile,
            headers = self.headers,
            environ =
            {
                'REQUEST_METHOD':   str_verb,
                'CONTENT_TYPE':     self.headers['Content-Type'],
            }
        )

    def getContentLength(self):
        """
        Return headers of the request
        """
        
        # self.dp.qprint('http headers received = \n%s' % self.headers, comms = 'status')
        return int(self.headers['content-length'])

    def unpackForm(self, form, d_form):
        """
        Load the JSON request.

        Note that anecdotal testing at times seemed to have incomplete
        form data. Currently, this method will attempt to wait in the
        hope that the form contents have not been fully transmitted.

        Note this method is very specific to the pf* family comms 
        standards.
        """

        waitLoop    = 5
        waitSeconds = 5
        b_status    = False
        d_msg       = {}

        self.dp.qprint("Unpacking multi-part form message...", comms = 'status')
        self.dp.qprint('form length = %d' % len(form), comms = 'status')
        self.dp.qprint('form keys   = %s' % form.keys())
        for w in range(0, waitLoop):
            if 'd_msg' not in form:
                self.dp.qprint("\tPossibly FATAL error -- no 'd_msg' found in form!",
                                comms = 'error')
                self.dp.qprint("\tWaiting for %d seconds. Waitloop %d of %d..." % \
                                (waitSeconds, w, waitLoop),
                                comms = 'error')
                time.sleep(waitSeconds)
            if len(form) == 3:
                for key in form:
                    self.dp.qprint("\tUnpacking field '%s..." % key, comms = 'rx')
                    if key == "local":
                        d_form[key] = form[key].file
                    else:
                        d_form[key]     = form.getvalue(key)
                b_status    = True
                break
        if b_status:
            d_msg = json.loads(d_form['d_msg'])
        d_msg['status'] = b_status
        if not b_status:
            d_msg['errorMessage'] = "FORM reception possibly incomplete."

        return d_msg

    def do_POST_dataParse(self):
        """
        Return a structure containing the data POSTED by a remote client
        """

        b_fileStream        = False
        d_ret               = {
            'status':       True,
            'mode':         '',
            'd_data':       {},
            'form':         None,
            'd_form':       {}
        }

        self.dp.qprint("Headers received = \n" + str(self.headers), 
                        comms = 'rx')

        if 'Mode' in self.headers:
            if self.headers['mode'] != 'control':
                b_fileStream    = True
                d_ret['mode']   = 'form'
            else:
                d_ret['mode']   = 'control'   
        if b_fileStream:
            form                = self.form_get('POST')
            if len(form):
                d_ret['form']   = form 
                d_ret['d_data'] = self.unpackForm(form, d_ret['d_form'])
                d_ret['status'] = d_ret['d_data']['status']
        else:
            self.dp.qprint("Parsing JSON data...", comms = 'status')
            length          = self.getContentLength()
            d_post          = json.loads(self.rfile.read(length).decode())
            try:
                d_ret['d_data'] = d_post['payload']
            except:
                d_ret['d_data'] = d_post

        return d_ret

    def do_POST(self, *args, **kwargs):
        """
        The main logic for processing POST directives from the client.

        This method will extract both meta (i.e. control-mode)
        as well as payload (i.e. data-mode or form-mode)
        directives .
        """

        # pudb.set_trace()
        b_skipInit  = False
        d_msg       = {
            'status':   False
        }
        d_postParse = {
            'status':   False
        }

        for k,v in kwargs.items():
            if k == 'd_msg':
                d_msg       = v
                b_skipInit  = True
        
        if not b_skipInit: 
            d_postParse     = self.do_POST_dataParse()
            try:
                d_msg                   = d_postParse['d_data']
            except:
                d_msg['errorMessage']   = "No 'd_data' in postParse."

        self.dp.qprint('d_msg = \n%s' % 
                        json.dumps(
                            d_msg, indent = 4
                        ), comms = 'status')

        if d_postParse['status']:
            d_meta      = d_msg['meta']

            if 'action' in d_msg and 'transport' not in d_meta:  
                d_ret   = self.do_POST_actionParse(d_msg)

            if 'ctl' in d_meta:
                d_ret   = self.do_POST_serverctl(d_meta)

            if not b_skipInit: self.ret_client(d_ret)
        else:
            d_ret       = d_msg
        return d_ret

    def ret_client(self, d_ret):
        """
        Simply "writes" the d_ret using json and the client wfile.

        :param d_ret:
        :return:
        """
        # pudb.set_trace()
        if not Gd_args['b_httpResponse']:
            self.wfile.write(json.dumps(d_ret, indent = 4).encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(Response(json.dumps(d_ret, indent=4))).encode())


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """
    Handle requests in a separate thread.
    """

    def col2_print(self, str_left, str_right, level = 1):
        self.dp.qprint(Colors.WHITE +
              ('%*s' % (self.LC, str_left)), 
              end       = '',
              syslog    = False,
              level     = level)
        self.dp.qprint(Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) + 
              Colors.NO_COLOUR,
              syslog    = False,
              level     = level)

    def __init__(self, *args, **kwargs):
        """
        Holder for constructor of class -- allows for explicit setting
        of member 'self' variables.

        :return:
        """
        HTTPServer.__init__(self, *args, **kwargs)
        self.LC     = 40
        self.RC     = 40

    def setup(self, **kwargs):
        global Gd_args
        global Gstr_description
        global Gstr_version

        str_defIP       = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
        str_defIPswift  = str_defIP

        if 'HOST_IP' in os.environ:
            str_defIP       = os.environ['HOST_IP']
            str_defIPswift  = os.environ['HOST_IP']

        # For newer docker-compose
        try:
            swift_service   = socket.gethostbyname('swift_service')
            if swift_service != "127.0.0.1":
                str_defIPswift  = str_defIP
        except:
            pass

        for k,v in kwargs.items():
            if k == 'args': Gd_args             = v
            if k == 'desc': Gstr_description    = v
            if k == 'ver':  Gstr_version        = v

        self.verbosity      = int(Gd_args['verbosity'])
        self.dp             = debug(verbosity = self.verbosity)

        self.col2_print("This host IP:",            str_defIPswift)
        self.col2_print("Self service address:",    Gd_args['ipSelf'])
        self.col2_print("Self service port:",       Gd_args['portSelf'])
        self.col2_print("Swift service address:",   Gd_args['ipSwift'])
        self.col2_print("Swift service port:",      Gd_args['portSwift'])
        self.col2_print("Server listen forever:",   Gd_args['b_forever'])
        self.col2_print("Return HTTP responses:",   Gd_args['b_httpResponse'])

        self.dp.qprint(
                Colors.LIGHT_GREEN + 
                "\n\n\t\t\tWaiting for incoming data...\n" + 
                Colors.NO_COLOUR,
                level   = 1,
                syslog  = False
            )
