from ...src.endlessdb import EndlessDatabase

class EndlessService():
    
    DEBUG = False
    
    def __init__(self, edb, config_key):
        if edb is None:
            edb = EndlessDatabase()
        self._edb = edb
        _config = self._edb().config()
        self._cfg = _config[config_key]
        self.DEBUG = self._cfg(False, create=True).debug
        self._edb().load_defaults()