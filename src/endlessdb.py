from abc import abstractmethod
import base64
import os
import re
import uuid
import bson
import pymongo.collection
import pymongo.database
import yaml
import uuid
import json
import pymongo
import inspect
import logging

from typing import Any
from pathlib import Path, PosixPath
from datetime import datetime
from bson.objectid import ObjectId
from functools import partial

class Formatter(logging.Formatter):

    default = "\x1b[39;20m\x1b[49;20m"
    
    white_background = "\x1b[47;20m"
    cyan_background = "\x1b[46;20m"
    
    white = "\x1b[37;20m"
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    
    bold_blue = "\x1b[34;1m"
    bold_magenta = "\x1b[35;1m"
    bold_green = "\x1b[32;1m"
    bold_white = "\x1b[37;1m"
    bold_red = "\x1b[31;1m"
    bold_yellow = "\x1b[33;1m"
    
    reset = "\x1b[0m"
    
    _levelname = f"{bold_yellow}[{bold_red}%(levelname)s{bold_yellow}]{default}"
    _application = f"{bold_yellow}[{bold_magenta}%(name)s{bold_yellow}]{default}"
    _time = f"{bold_yellow}[{bold_white}%(asctime)s{bold_yellow}]{default}"
    
    _title = f"{_levelname}{_application}{_time} "
    _format = f"%(message)s{reset}"
    
    FORMATS = {
        logging.DEBUG: f"{blue}{_title}{blue}{_format}",
        logging.INFO: f"{green}{_title}{green}{_format}",
        logging.WARNING: f"{yellow}{_title}{yellow}{_format}",
        logging.ERROR: f"{red}{_title}{red}{_format}",
        logging.CRITICAL: f"{bold_red}{_title}{bold_red}{_format}",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class Logger:
    
    def __init__(self, name):
        self._name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(Logger._ch)
        self._logger.propagate = False
        
    def init():
        Logger._ch = logging.StreamHandler()
        Logger._ch.setLevel(logging.DEBUG)
        Logger._ch.setFormatter(Formatter())
    
    def __str__(self) -> str:
        return f"📝{self._name}Logger"
        
    def __repr__(self) -> str:
        return self.__str__()
        
    def debug(self, msg):
        self._logger.debug(msg)

    def info(self, msg):
        self._logger.info(msg)
    
    def warning(self, msg):
        self._logger.warning(msg)
        
    def error(self, msg):
        self._logger.error(msg)

class EndlessConfiguration():
    _override = {}
    
    def __init__(self) -> None:
        if type(self) == EndlessConfiguration:
            self.MONGO_HOST = os.environ.get("CORE_MONGO_HOST", "mongo")
            self.MONGO_PORT = int(os.environ.get("CORE_MONGO_PORT", 27017))
            self.MONGO_USER = os.environ.get("CORE_MONGO_USER", "root")
            self.MONGO_PASSWORD = os.environ.get("CORE_MONGO_PASSWORD", "root")
            self.MONGO_DATABASE = os.environ.get("CORE_MONGO_DATABASE", "endlessdb")
            self.MONGO_URI = "mongodb://localhost:27017/"
            self.MONGO_DATABASE = "endlessdb"
            
            self.CONFIG_COLLECTION = "config"
            self.CONFIG_YML: str = "~/config.yml"            
        else:
            self.override()
    
    def __str__(self) -> str:
        return f"⚙️Endlessdb configuration({self.__class__.__name__})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    @classmethod
    def apply(cls):
        if issubclass(cls, EndlessConfiguration):
            if len(cls.__bases__) > 0 and issubclass(cls.__bases__[0], EndlessConfiguration):
                EndlessConfiguration._override[str(cls.__bases__[0])] = cls()
    
    @abstractmethod
    def override(self):
        pass
    
    def __getattr__(self, key: str) -> Any:
        c = type(self)
        cs = str(c)
        _ov = None
        if cs in EndlessConfiguration._override:
            _ov = EndlessConfiguration._override[cs].__getattr__(key)
            
        if _ov is not None:
            return  _ov
        
        if key in self.__dict__:
            return self.__dict__[key]
        
        return None 
        
    def __getitem__(self, key: str) -> Any:
        return self.__getattr__(key)
         
    def __getattribute__(self, name: str) -> Any:
        if name == "__class__":
            return type(self)
        
        _dict = super().__getattribute__("__dict__")
        if name == "__dict__":
            return _dict
        
        _dir = dir(self)        
        if name in _dict \
            or name not in _dir:
            return self.__getattr__(name)
        
        return super().__getattribute__(name)
    
#region 📌Common

def re_mask_subgroup(subgroup, mask, m):
    if m.group(subgroup) not in [None, '']:
        start = m.start(subgroup)
        end = m.end(subgroup)
        length = end - start
        return m.group()[:start] + mask*length + m.group()[end:]

def get_obj_dict(obj):
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return obj.__str__()

def is_magic_method(method):
    if isinstance(method, int):
        return False
    
    return method.startswith("__") and method.endswith("__")

### Class for wrapping logic container (TO DO) 

class w():    
    def __init__(self, d) -> Any:
        self.d = d
        
    def __getattr__(self, key: str) -> Any:
        return self.d[key]
    
    def __setattr__(self, key: str, value: Any) -> None:
        self.d[key] = value

#endregion 📌Common

#region 📌Logic

class DocumentLogicContainer():   
    
    #region 📌Magic
    
    def __init__(self, _, key, obj, parent_logic, virtual):
        self.uuid = str(uuid.uuid4())
        self._ = _
        self.__ = _.__dict__
        self._key = key
        self._keys = []
        self._path = f"{parent_logic.path(True)}/{key}"
        self._parent_logic = parent_logic
        self._iteration = None
        
        self.static = False
        self.debug = False      
        self.virtual = virtual
        self.protected = parent_logic.protected
        
        self.descendant_expected = None
        self.descendant_create = False
        self.descendant_rewrite = False
        self.descendant_exception = False
        
        self._reload(obj) 
    
    def __call__(self):
        return self._
    
    #endregion 📌Magic
    
    #region 📌Methods
    
    def __repr__(self) -> str:
        return f"🧩logic({self.repr()})"
    
    def _reload(self, obj):
        mongo = None
        _self = self._ 
        if obj is None:
            _parent = self.parent()
            if isinstance(_parent, EndlessCollection):
                mongo = self.mongo()
                if mongo is None:
                    collection = self.collection()
                    collection().reload()
                    return                    
                else:
                    obj = mongo.find_one({"_id": self._key})
                    if obj is None:
                        self.virtual = True
                        return
                    else:
                        self.virtual = False                        
            else:
                _parent()._reload(None)
                return       
            
        if self._key is None:
            path = self._path.split("/")
            try:
                self._key = int(path[-1])
                pass
            except:
                self._key = path[-1]
            
        virtual = self.virtual
                       
        _keys  = self._keys.copy()
        self._keys.clear()
        _path = f"{self.path(True)}"
        _edb = self.edb()
        for _key in obj:
            value = obj[_key]
            self._keys.append(_key)  
            
            if isinstance(value, bson.dbref.DBRef):
                value = _edb[value.collection][value.id]                                
                
            if self.descendant_expected is None:
                if isinstance(value, EndlessDocument) or isinstance(value, dict):                
                    if self.static:                
                        if _key in self.__ and isinstance(self.__[_key], EndlessDocument):
                            _self[_key]()._reload(value)
                        else:
                            self.__[_key] = self.descendant(_key, value, virtual, False)                       
                    else:
                        if isinstance(value, EndlessDocument) and isinstance(value().parent(), EndlessCollection):
                            document = value
                        else:    
                            _property_path = f"{_path}/{_key}"
                            if mongo is None:
                                document = self.descendant(_key, value, virtual, False)                                    
                            else:
                                documents = self.edb()().documents()
                                if _property_path in documents:
                                    document = documents[_property_path]
                                else:
                                    document = None
                                
                                if document is not None:
                                    document()._reload(value)
                                else:
                                    document = self.descendant(_key, value, virtual, False) 
                                    documents[_property_path] = document
                            
                        self.__[_key] = document
                else:
                    if isinstance(value, ObjectId):                   
                        self.__[_key] = str(value)                    
                    else:
                        self.__[_key] = value
            else:
                if inspect.isclass(self.descendant_expected):
                    _type = self.descendant_expected
                else:
                    _type = type(self.descendant_expected)
                
                if isinstance(value, _type):
                    self.__[_key] = value                    
                
        for _key in _keys:
            if _key not in self._keys:
                del self.__[_key]                        
            
    def repr(self, srepr = None) -> str:
        parent = self.parent()
        repr = ""
        if self.debug:
            repr += "🐞"
        
        repr += "📑"
        
        if self.descendant_expected is not None:
            repr += "🔎"
        else:
            if self.virtual:
                repr += "🆕"        
        
        if self.protected:
            repr += "🔒"
        else:
            repr += "🔓"
        
        repr += f"{self._key}"            
        repr += "{" + f"ℓ{self.len()}" + "}"
        
        
        if srepr is not None:
            repr = f'{repr}/{srepr}'
        
        if parent is None:
            return repr           
        else:
            return parent().repr(repr)            
    
    def descendant(self, key, obj, virtual = False, reload = True):
        edb = self.edb()
        if edb is not None:
            documents = self.edb()().documents()
            _path = f"{self.path(True)}/{key}"
            if _path in documents:
                property = documents[_path]
            else:
                property = EndlessDocument(key, obj, self, virtual)
                documents[_path] = property
        
        return EndlessDocument(key, obj, self, virtual)

    def len(self):
        return len(self._keys)
    
    def key(self):
        return self._key
    
    def relative_path(self, current = None):
        if current is None:
            _path = str(self._key)
        else:    
            _path = f"{self._key}/{current}"
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return  _path
        
        return f"{self._parent_logic.relative_path(_path)}"
        
    def path(self, full = False):
        if full:
            return self._path
        else:
            return self.relative_path();    
    
    def parent(self):
        return self._parent_logic()
    
    def keys(self):
        return self._keys
    
    def mongo(self) -> pymongo.collection.Collection:
        return self.collection()().mongo()
    
    def reload(self):
        #if not self.virtual:
        self._reload(None)
        return self._  
    
    def delete(self):
        if isinstance(self._parent_logic, CollectionLogicContainer):
            self.mongo().delete_one({ "_id": self._key })
            documents = self._parent_logic.edb()().documents()
            path = self.path(True)
            if path in documents:
                document = documents[path]
                document().virtual = True
                del documents[path]
        else:
            self._parent_logic.delete()
        
    def edb(self):
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return self._parent_logic.edb()
        
        return self._parent_logic._parent_logic.edb()        
        
    def collection(self):
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return self._parent_logic()
        
        return self._parent_logic.collection()
    
    def to_ref(self):
        return { 
            "$ref": self.collection()().key(), 
            "$id": self._key
        }
        
    def to_dict(self, *args, **kwargs):
        if "exclude" in kwargs:
            exclude = kwargs["exclude"]
        else:
            exclude = []
            
        if "ref_to_id" in kwargs and kwargs["ref_to_id"]:
            ref_to_id = True
        else:
            ref_to_id = False
            
        _self = self._
        for key in self._keys:
            if key in exclude:
                continue
            value = _self[key]
            if isinstance(value, EndlessDocument):
                if ref_to_id:
                    data = value().key()
                else:
                    data = dict(value().to_dict())
                yield (key, data)
            else:
                yield (key, value)
            
    def to_json(self, *args, **kwargs):
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False
        
        _dict = dict(self.to_dict(**kwargs))
        _json = json.dumps(
            _dict, 
            default=get_obj_dict, 
            ensure_ascii=False
        )           
        
        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")
        
        return _json    

    def to_yml(self):
        _dict = dict(self.to_dict())
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)           
        return _yaml
    
    #endregion 📌Methods
    
class CollectionLogicContainer():   
      
    #region 📌Magic
    
    def __init__(self, _, edb, key, yml = None, defaults = None, _mongo = None):
        self.protected = False
        self.static = False
        self.debug = False
        
        if isinstance(key, PosixPath):
            _key = key.stem
        else:
            _key = key
            
        self._ = _
        self.__ = _.__dict__
        self._edb = edb
        if edb is None:
            self._collection = None            
        else:
            if _mongo is None:
                self._collection = edb().mongo()[_key]                
            else:
                self._collection = _mongo[_key]
            
        self._keys = []        
        self._key = _key
        
        self.defaults = defaults
            
        if self._collection is None:
            if yml is None:            
                raise Exception(f"Yoi must provide either yml or edb object for {self}")
            else:
                self._reload(yml)
        
        pass
    
    def __call__(self):
        return self._
    
    def __repr__(self) -> str:
        return f"🧩logic:({self.repr()})"
    
    #endregion 📌Magic
    
    #region 📌Methods
    
    def _reload(self, yml):
        for _key in yml:
            value = yml[_key]
            self._keys.append(_key)  
            #self.__slots__.append(key)
            if isinstance(value, dict):
                self.__[_key] = self.descendant(_key, value)
            elif isinstance(value, ObjectId):                   
                self.__[_key] = str(value)
            else:
                self.__[_key] = value                
    
    def descendant(self, key, value, virtual = False):
        if self._edb is not None:
            _path = f"{self.path(True)}/{key}"
            documents = self._edb().documents()
            if _path in documents:
                document = documents[_path]
                document().reload()            
            else:
                document = EndlessDocument(key, value, self, virtual)
                if not self.debug:
                    documents[_path] = document
        
        return EndlessDocument(key, value, self, virtual)

    def len(self):
        collection = self.mongo()
        if collection is not None:            
            return collection.count_documents({})
        
        return len(self._keys)
    
    def key(self):
        return self._key
    
    def path(self, full = True):
        if full:
            if self._edb is None:            
                return f"yml/{self._key}"
            return f"{self._edb().key()}/{self._key}"
        else:
            return self._key
        
    def repr(self, srepr = None):
        parent = self.parent()
        repr = ""
        if self.debug:
            repr += "🐞"
        
        if self._edb is None:
            repr = f"⚓{self.path(True)}"
        else:    
            repr += "📚"
            
            if self.protected:
                repr += "🔒"
            else:
                repr += "🔓"
            
            repr += f"{self._key}"
            repr += "{" + f"ℓ{self.len()}" + "}"
            
        if srepr is not None:
            repr += f'/{srepr}'        
               
        if parent is None:
            return repr           
        else:
            return parent().repr(repr)            
    
    def keys(self):
        if self._collection is None:
            return self._keys
        
        try:
            return self._collection.distinct("_id")
        except Exception as e:
            keys = []   
            
        return keys    
        
    def set(self, path: str, value: Any, descendant_expected = None):
        if self.protected:
            raise Exception(f"{self} is protected and read-only")
        
        if descendant_expected is not None and inspect.isclass(descendant_expected):
            if not isinstance(value, descendant_expected):
                raise Exception(f"Value must be instance of {descendant_expected}")
        
        collection = self.mongo()
        if collection == None:
            raise Exception(f"{self} is read-only") 
        else:
            _path = path.split(".")
            path_length = len(_path)   
            
            if path_length == 1:
                _data = { "$set": value }
            else:
                _data = { "$set": {} }             
                _currentPath = _data["$set"]                                                
                for i in range(1, path_length):
                    _currentPath[_path[i]] = {}
                    if i < path_length - 1:
                        _currentPath = _currentPath[_path[i]]                    
                if isinstance(value, EndlessDocument):
                    _value = value()
                    _currentPath[_path[i]] = _value.to_ref()
                else:
                    _currentPath[_path[i]] = value
            
            try:
                _id = int(_path[0])
                pass
            except:
                _id = _path[0]
            
            collection.update_one({ "_id": _id }, _data, upsert=True)        
            #if not isinstance(value, dict):
            _path = f"{self.path(True)}/{_path[0]}"
            documents = self._edb().documents()
            #_path = f"{self._key}.{path}"
            if _path in documents:
                documents[_path]().reload()
    
    def find(self, filter):
        r = self.mongo().find(filter, {"_id": 1})
        if r is not None and len(r) > 0:
            for document in r:
                yield self.descendant(document["_id"], None)
        else:
            yield None
        
    def find_one(self, filter):
        document = self.mongo().find_one(filter, {"_id": 1})
        if document is not None:
            return self.descendant(document["_id"], None)       
        else:
            return None
        
    def reload(self):
        if self._edb is None:
           with open(self._key, 'r') as stream:
            try:         
                yml = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(f'YAML parsing error:\n{exc}')
                raise exc
        else:
            raise Exception(f"{self} can reload only yml collction")
        
        self._reload(yml)
            
    def mongo(self) -> pymongo.collection.Collection:
        return self._collection
    
    def collections(self):
        return self._parent_logic.collections()
    
    def parent(self):
        return self.edb()
        
    def edb(self):
        return self._edb
    
    def delete(self):
        collections = self._edb().collections()
        if self._key in collections:
            del collections[self._key]
            
        self._collection.drop()
        self.virtual = True
    
    def to_dict(self, *args, **kwargs):
        _self = self._
        keys = self.keys()
        for key in keys:
            data = dict(_self[key]().to_dict(**kwargs))
            yield (key, data)
    
    def to_json(self, *args, **kwargs):
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False
        
        _dict = dict(self.to_dict(**kwargs))
        _json = json.dumps(_dict, default=get_obj_dict, ensure_ascii=False) 
        
        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")
                 
        return _json   

    def to_yml(self):
        _dict = dict(self.to_dict())
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)           
        return _yaml
    
    def from_yml(path): 
        with open(path, 'r') as stream:
            try:         
                yml = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(f'YAML parsing error:\n{exc}')
                raise exc
            
        return EndlessCollection(path.name, None, yml)

    #endregion 📌Methods
    
class DatabaseLogicContainer():
    
    _collections: dict
    _documents: dict
        
    #region 📌Magic
    
    def __call__(self):
        return self._
        
    def __init__(self, _, url = None, host = "localhost", port = 27017, user = "", password = ""):
        self._cfg = EndlessConfiguration()
        self.debug = False
        self._ = _
        self.__ = _.__dict__          
        self._collections = {}
        self._documents = {}
        self._defaults_collection = CollectionLogicContainer.from_yml(self._cfg.CONFIG_YML)
        defaults = self.defaults()
        
        self._url = self.url_info(self._cfg.MONGO_URI)
        self._key = self._cfg.MONGO_DATABASE
        
        self._mongo = pymongo.MongoClient(self._cfg.MONGO_URI, connect=False)
        self._edb = self._mongo[self._key]
        
        self._collections[self._cfg.CONFIG_COLLECTION] = EndlessCollection(self._cfg.CONFIG_COLLECTION, self(), None, defaults, self._edb)
    
    def __repr__(self) -> str:
        return f"🧩logic:({self.repr()})"
           
    #endregion 📌Magic
             
    #region 📌Methods
           
    def repr(self, srepr = None):
        repr = ""
        if self.debug:
            repr += "🐞"
            
        if self._edb is None:            
            repr += f"📀"
        else:
            repr += "💿"
        
        repr += f"{self._key}"
        repr += "{" + f"ℓ{self.len()}" + "}"
        
        if srepr is None:
            return f"{repr}"
        else:
            return f'{repr}/{srepr}'       
    
    def len(self):
        return len(self.keys())
    
    def key(self):
        return self._key
        
    def keys(self):
        _filter = {"name": {"$regex": r"^(?!^%s$).+$" % self._cfg.CONFIG_COLLECTION}}
        return self.mongo().list_collection_names(filter=_filter)
        
    def mongo(self) -> pymongo.database.Database:
        return self._edb
    
    def parent():
        return None
    
    def config(self):
        return self._collections[self._cfg.CONFIG_COLLECTION]
    
    def defaults(self):
        return self._defaults_collection
    
    def documents(self):
        return self._documents
    
    def collections(self):
        return self._collections
    
    def url_info(self, url):
        pattern = r"(?i)^mongodb\:\/\/(?P<user>.*):(?P<password>.*)\@(?P<host>.*)\:(?P<port>\d+)\/(?P<database>.*)?\?(?P<paramaters>.*)?$"
        masked = re.sub(pattern, partial(re_mask_subgroup, "password", "*"), url)
        
        return {"url": url, "masked": masked}                  
    
    def build_url(self, host, port, user, password):        
        return f"mongodb://{user}:{password}@{host}:{port}/?authMechanism=SCRAM-SHA-256"
    
    def to_dict(self):
        _self = self._
        keys = self.keys()
        for key in keys:
            data = dict(_self[key]().to_dict())
            yield (key, data)            
            
    def to_json(self, *args, **kwargs):
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False
            
        _dict = dict(self.to_dict())
        _json = json.dumps(_dict, default=get_obj_dict, ensure_ascii=False)
        
        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")
                   
        return _json    

    def to_yml(self):
        _dict = dict(self.to_dict())
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)           
        return _yaml
    
    def load_defaults(self):
        defaults = self.defaults()
        config = self.config()
        if defaults.config_collection_rewrite:
            for key, value in defaults:
                if isinstance(value, EndlessDocument):
                    _value = value()
                    data = dict(_value.to_dict())
                    config[key] = data
        
    #endregion 📌Methods
    
#endregion 📌Logic

#region 📌Endless

class EndlessDocument():
    
    def __init__(self, key, obj, parent_logic, virtual = False):
        self.__dict__["***"] = DocumentLogicContainer(self, key, obj, parent_logic, virtual)                                   
    
    #region 📌Magoc
    
    def __call__(self, descendant_expected = None, **kwargs) -> DocumentLogicContainer:
        _self = self.__dict__["***"]       
        _parent = _self.parent()()
        if _parent.protected:
            _self.protected = True
        
        if _parent.static:
            _self.static = True
        
        if _parent.debug:
            _self.debug = True
        
        ret = False        
        if "debug" in kwargs and kwargs["debug"]:
            _self.debug = kwargs["debug"] == True
            ret = True
            
        if "protected" in kwargs and kwargs["protected"]:
            _self.protected = kwargs["protected"] == True
            ret = True
        
        if "static" in kwargs and kwargs["static"]:
            _self.static = kwargs["static"] == True
            ret = True
        
        if "exception" in kwargs and kwargs["exception"]:
            _self.descendant_exception = kwargs["exception"] == True
            ret = True
                
        if "create" in kwargs and kwargs["create"]:
            _self.descendant_create = kwargs["create"] == True            
            ret = True
            
        if descendant_expected is not None:
            document = EndlessDocument(_self.key(), dict(_self.to_dict()), _parent, True)
            documentl = document()
            documentl.descendant_expected = descendant_expected
            documentl.descendant_create = _self.descendant_expected
            documentl.descendant_exception = _self.descendant_exception
            if _parent.debug:
                documentl.debug = True
            
            return document
        
        if ret:
            return self
        else:
            return _self
    
    def __delete__(self, instance):
        pass
    
    def __del__(self):
        pass
    
    def __len__(self):                
        return self().len()
    
    def __str__(self) -> str:                
        _self = self.__dict__["***"]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"
        if _self.virtual:
            _str += "*"
        return _str
    
    def __repr__(self) -> str:
        _self = self.__dict__["***"]               
        return _self.repr()
    
    def __eq__(self, other):
        _self = self.__dict__["***"]
        if other is None:
            return _self.virtual
        if isinstance(other, EndlessDocument):
            return _self.path(True) == other().path(True)
        
        raise Exception("This type of comparsion is not supported yet")
    
    def __iter__(self):
        _self = self.__dict__["***"]
        for key in _self.keys():
            if key in self.__dict__:
                yield key, self.__dict__[key]
            else:
                path = f"{_self.path(True)}/{key}"
                documents =_self.edb()().documents()
                if path in documents:
                    yield key, documents[path]
                else:
                    raise Exception(f"Property {key} not found in {self}")
            
    def __setattr__(self, key: str, value):
        if key == "id" or key == "_id":
            raise Exception(f"Id is read-only")
        
        valid_types = [EndlessDocument, str, int, float, bool, dict, list, bytes, bytearray, datetime, uuid.UUID, type(None)]
        if not type(value) in valid_types:
            raise Exception(f"Value must be instance of {valid_types}")
             
        _self = self.__dict__["***"]
        if _self.protected:
            raise Exception(f"{self} is protected and read-only")
        
        if is_magic_method(key):
            key = "*" + key
        
        _path = _self.path().replace("/", ".")
        _self.collection()().set(f"{_path}.{key}", value, _self.descendant_expected)
    
    def __getattr__(self, key: str):
        if key == "id" or key == "_id":
            return self.__dict__["***"].key()
        
        _self = self.__dict__["***"]                
        descendant_expected = _self.descendant_expected
        descendant_expected_is_type = inspect.isclass(descendant_expected)
        if descendant_expected_is_type:            
           value = descendant_expected()
        else:
            value = descendant_expected
            
        if value is not None:
            if _self.descendant_rewrite:
                _self.collection().set(_self.path(), value, descendant_expected)
                return value
            
        if key in self.__dict__:
            if _self.descendant_exception and descendant_expected_is_type:
                if not isinstance(self.__dict__[key], descendant_expected):
                    if not (descendant_expected is dict and isinstance(self.__dict__[key], EndlessDocument)):                        
                        raise Exception(f"Property {key} is not instance of {descendant_expected}")
                    
            return self.__dict__[key]
        elif _self.descendant_exception:
            raise Exception(f"Property {key} not found in {self}")
        
        return _self.descendant(key, None, True)
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self.__getattr__(key)
        
        if is_magic_method(key):
            key = "*" + key        
            
        path = key.split(".", 1)
        if len(path) > 1:
            return self[path[0]][path[1]]
        
        return self.__getattr__(key)
     
    def __setitem__(self, key, value):        
        if is_magic_method(key):
            key = "*" + key
                    
        path = key.split(".", 1)
        if len(path) > 1:
            self[path[0]][path[1]] = value
            return  
        
        return self.__setattr__(key, value)

class EndlessCollection():
    
    #__slots__ = ["__dict__"]
    
    def __init__(self, key, edb = None, yml = None, defaults = None, _database = None):
        self.__dict__["***"] = CollectionLogicContainer(self, edb, key, yml, defaults, _database)                                               
    
    def __call__(self, *args, **kwargs) -> CollectionLogicContainer:        
        _self = self.__dict__["***"]       
        
        ret = False
        if "debug" in kwargs and kwargs["debug"]:
            _self.debug = kwargs["debug"] == True
            ret = True
            
        if "protected" in kwargs and kwargs["protected"]:
            _self.protected = kwargs["protected"] == True
            ret = True
            
        if "static" in kwargs and kwargs["static"]:
            _self.static = kwargs["static"] == True
            ret = True
            
        if ret:
            return self
        else:
            return _self
    
    def __eq__(self, other):
        _self = self.__dict__["***"]
        if other is None:
            return _self.virtual
        
    def __delete__(self, instance):
        pass
              
    def __len__(self):
        _self = self.__dict__["***"]
        return _self.len()
            
    def __str__(self) -> str:
        _self = self.__dict__["***"]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"
        
        return _str    
    
    def __repr__(self) -> str:
        _self = self.__dict__["***"]
        return _self.repr()
    
    def __iter__(self):
        _self = self.__dict__["***"]
        for key in _self.keys():
            yield key, self.__getattr__(key)
                   
    def __getattr__(self, key):
        _self = self.__dict__["***"]
        collection = _self.mongo()
        if key in self.__dict__:
            if collection is None or key not in _self.keys:
                return self.__dict__[key]
        
        if collection == None:
            return None
        else:
            _path = f"{_self.path(True)}/{key}"
            documents = _self._edb().documents()
            #_path = f"{self._key}.{path}"
            if _path in documents:
                document = documents[_path]
                document().reload()
                return document
            
            _obj = collection.find_one({"_id": key})
            defaults = _self.defaults
            if _obj is None and defaults is not None:
                default_value = _self.defaults[key]
                if default_value is not None:
                    if isinstance(default_value, EndlessDocument):
                        _path = default_value().path()
                        _data = dict(default_value().to_dict())
                        _self.set(_path, _data)
                        #collection.update_one({ "_id": key }, _data, upsert=True) 
                        _obj = collection.find_one({"_id": key})
                    else:
                        _self.set(_path, default_value)
                        return default_value              
            
            #path = f"{_self.key()}/{key}"
            if _obj is None:
                document = _self.descendant(key, None, True)            
            else:    
                document = _self.descendant(key, _obj)
                
            documents[_path] = document
            return document            
    
    def __setattr__(self, key, value):
        _self = self.__dict__["***"]
        if is_magic_method(key):
            key = "*" + key
            
        collection = _self.mongo()
        if collection is None:
            raise Exception(f"{self} is read-only")
        
        if isinstance(value, dict):
            collection.update_one({'_id': key }, {"$set": value}, upsert=True)            
            _path = f"{_self.path(True)}/{key}"
            documents = _self.edb()().documents()
            if _path in documents:
                documents[_path]().reload()                         
        else:
            raise Exception(f"You must pass dict value with filled _id pproperty {self}")
    
    def __getitem__(self, key):
        if key is None:
            return None
        
        _self = self.__dict__["***"]
        if is_magic_method(key):
            key = "*" + key
                        
        try:
            key = int(key)
        except:
            pass
        
        if isinstance(key, int):
            return self.__getattr__(key)
        
        path = key.replace("/", ".").split(".", 1)
        if len(path) > 1:
            next_path = path[0]
            try:
                next_path = int(next_path)
            except:
                pass            
            return self[next_path][path[1]]
        
        return self.__getattr__(key)
     
    def __setitem__(self, key, value):
        if is_magic_method(key):
            key = "*" + key
            
        try:
            key = int(key)
        except:
            pass            
        if isinstance(key, int):
            return self.__setattr__(key, value)
            
        path = key.split(".", 1)
        if len(path) > 1:
            next_path = path[0]
            try:
                next_path = int(next_path)
            except:
                pass            
            self[next_path][path[1]] = value
            return
        
        return self.__setattr__(key, value)
   
class EndlessDatabase():
    
    def __init__(self, url = None, host = None, port = None, user = None, password = None):
        self.__dict__["***"] = DatabaseLogicContainer(self, url, host, port, user, password)        
       
    def __call__(self, *args, **kwargs) -> DatabaseLogicContainer:
        _self = self.__dict__["***"]       
        
        ret = False
        if "debug" in kwargs and kwargs["debug"]:
            _self.debug = kwargs["debug"] == True
            ret = True
        
        if "protected" in kwargs and kwargs["protected"]:
            _self.protected = kwargs["protected"] == True
            ret = True
        
        if ret:
            self
        else:
            return _self
    
    def __delete__(self, instance):
        pass
              
    def __len__(self):
        _self = self.__dict__["***"]
        return _self.len()
    
    def __str__(self) -> str:
        _self = self.__dict__["***"]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"
        return _str
    
    def __repr__(self) -> str:
        _self = self.__dict__["***"]
        return _self.repr()         
    
    def __getattr__(self, key):
        _self = self.__dict__["***"]
        if key in self.__dict__:
            return self.__dict__[key]
        
        try:
            key = int(key)
        except:
            pass
        if isinstance(key, int):
            raise Exception(f"There is no numeric keys in edb")
        
        path = key.split("/", 1)
        if len(path) > 1:
            next_path = path[0]
            try:
                next_path = int(next_path)
            except:
                pass
            if isinstance(key, int):
                raise Exception(f"There is no numeric keys in edb")
        
            return self[next_path][path[1]]
        
        collections = _self.collections()
        if not _self.debug and key in collections:
            return collections[key]     
           
        collection = EndlessCollection(key, self)        
        if not _self.debug:
            collections[key] = collection
                    
        return collection
    
    def __setattr__(self, key, value):
        try:
            key = int(key)
        except:
            pass
        if isinstance(key, int):
            raise Exception(f"There is no numeric keys in edb")
        
        path = key.split("/", 1)
        if len(path) > 1:
            next_path = path[0]
            try:
                next_path = int(next_path)
            except:
                pass
            if isinstance(key, int):
                raise Exception(f"There is no numeric keys in edb")
        
            self[next_path][path[1]] = value
            return
        
        raise Exception(f"This is edb root and it is read-only")
    
    def __setitem__(self, key, value):
        self.__setattr__(key, value)
            
    def __getitem__(self, key):
        return self.__getattr__(key)      
    
    def __iter__(self):
        _self = self.__dict__["***"]
        for key in _self.keys():
            yield key, self.__getattr__(key)  

#endregion 📌Endless