from datetime import datetime
import uuid
import pymongo
from pathlib import Path

import pytest
from src.endlessdb import (
    EndlessConfiguration,
    EndlessDatabase,
    EndlessCollection,
    EndlessDocument        
)

class TestConfiguration(EndlessConfiguration):
    __test__ = False
    def override(self):
        self.CONFIG_YML = "tests/config.yml"
        self.MONGO_URI = "mongodb://admin:admin@localhost:27017/"

class TestInheritedConfiguration(TestConfiguration):
    __test__ = False
    def override(self):
        self.CONFIG_COLLECTION = "test_config"
        self.MONGO_URI = "mongodb://root:root@localhost:27117/"
        self.MONGO_DATABASE = "tests-endlessdb"

@pytest.mark.skip()
def test_reading_all(edb, edbl, results):
    tests = {
        "✅": {}, 
        "❌": {}
    }
    test = test_reading_db(edb, tests)
    
    for ckey, c in edb:
        cl = c()
        test_reading(cl, edb, ckey, tests)
        test_logic(c, cl, tests)
            
        for dkey, d in c:
            dl = d()
            test_reading(dl, c, dkey, tests)
            test_logic(d, dl, tests)
                
            for pkey, p in d:
                if isinstance(p, EndlessDocument):
                    pl = p()
                    test = test_reading(pl, d, pkey, tests)
                    test = test_logic(p, pl, tests)                    
                else:
                    path = f"{dl.path()}"
                    print(f"✅: read value: {path}")
                    tests[test["pass"]][path] = {
                        "value": p,
                        "pass": "✅"
                    }
    results["test_reading_all"] = {
        "pass": len(tests["❌"]) == 0, 
        "tests": tests
    }
    return tests
    
@pytest.mark.skip()
def test_reading_db(edb, tests):
    edbl = edb()
    test = {
        "str": str(edb),
        "len": len(edb),
        "repr": edbl.repr(),
        "keys": edbl.keys(),
        "mongo": edbl.mongo(),
        "config": edbl.config(),
        "defaults": edbl.defaults()
    }
    test_pass = "✅"
    if not (isinstance(test["len"], int) \
        and isinstance(test["repr"], str) \
        and isinstance(test["keys"], list) \
        and isinstance(test["mongo"], pymongo.database.Database)):
        test_pass = "❌"

    test["pass"] = test_pass   
    tests["reading_db"] = test 
    print(f"{test_pass}: reading db: {edbl.key()}")  
    assert test_pass == "✅"
    
    return test

@pytest.mark.skip()    
def test_reading(ol, parent, k, tests):
    o = parent[k]
    test = {
        "len": len(o),
        "str": str(o)            
    }
    test_pass = "✅" 
    if not (isinstance(test["len"], int) \
        and isinstance(test["str"], str)):
        test_pass = "❌"
    
    test["pass"] = test_pass
    path = ol.path(True)
    tests[test["pass"]][path] = test
    print(f"{test_pass}: reading: {path}")
    assert test_pass == "✅" 
    return test

@pytest.mark.skip()    
def test_logic(o, ol, tests):
    test = {
        "len": ol.len(),
        "repr": ol.repr(),
        "keys": ol.keys(),
        "dict": dict(ol.to_dict()),
        "json": ol.to_json(),
        "parent": ol.parent(),
        "mongo": ol.mongo(),
        "edb": ol.edb()
    }
    test_pass = "✅"
    if not (isinstance(test["len"], int) \
        and isinstance(test["repr"], str) \
        and isinstance(test["keys"], list) \
        and (isinstance(test["dict"], dict) \
            and len(test["keys"]) == len(test["dict"])) \
        and (isinstance(test["json"], str) \
            and test["json"].startswith("{")) \
        and (isinstance(test["parent"], EndlessDatabase) \
            or isinstance(test["parent"], EndlessCollection) \
            or isinstance(test["parent"], EndlessDocument)) \
        and (isinstance(test["mongo"], pymongo.database.Database) \
            or isinstance(test["mongo"], pymongo.collection.Collection)) \
        and isinstance(test["edb"], EndlessDatabase)):
        test_pass = "❌"
    
    if isinstance(o, EndlessDocument):
        test["collection"] = ol.collection()          
        if not (isinstance(test["parent"], EndlessCollection) \
            and isinstance(test["collection"], EndlessCollection) \
            or test_pass == "✅"):
            test_pass = "❌"
    elif isinstance(o, EndlessCollection):
        if not (isinstance(test["parent"], EndlessDatabase) \
            or test_pass == "✅"):
            test_pass = "❌"
    test["pass"] = test_pass
    path = ol.path(True)
    tests[test["pass"]][path] = test
    print(f"{test_pass}: logic: {path}")
    assert test_pass == "✅" 
    return test

@pytest.mark.skip()    
def test_writing(path, edb, edbl, results):
    
    tests = {
        "✅": {}, 
        "❌": {}
    }
    
    col1n = "tests1"
    col1 = edb[col1n]
    col1l = col1()
    doc1uid = f'doc_{str(uuid.uuid4()).replace("-", "")}'
    
    # Testing writing to collection
    col1[doc1uid] = {"property1": 0}    
    doc1 = col1[doc1uid]
    doc1l = doc1()    
    assert doc1.property1 == 0
    
    doc1.property1 = 1
    value = doc1.property1
    assert value == 1
    
    doc1.property2 = 2
    assert doc1.property2 == 2
    
    col1l.mongo().update_one({ "_id": doc1uid }, { "$set": {"property2": 3} }, upsert=True)                
    assert doc1.property2 == 2
    
    doc1.datetime = datetime.now()
    json = doc1l.to_json()
    
    doc1l.reload()
    assert doc1.property2 == 3
    
    doc1l.delete()
    assert  doc1 == None
    #assert col1[doc1uid] == None
    
    col1l.delete()
    assert col1 == None
    
    # Testing doc refference
    
    col1n = "Employee"
    col1 = edb[col1n]
    col1l = col1()
    
    doc1uid = f'doc_{str(uuid.uuid4()).replace("-", "")}'
    col1[doc1uid] = {"Name": "John", "Age": 25}
    doc1 = col1[doc1uid]
    doc1l = doc1()
    
    ######################################################
    
    col2n = "Department"
    col2 = edb[col2n]
    col2l = col2()
    
    doc2uid = f'doc_{str(uuid.uuid4()).replace("-", "")}'
    col2[doc2uid] = {"Name": "IT", "Location": "New York"}
    doc2 = col2[doc2uid]
    doc2l = doc2()
    
    ######################################################
    
    doc1.Department = doc2    
    assert doc1.Department == doc2
    
    doc1l.delete()
    doc2l.delete()
    col1l.delete()
    col2l.delete()
    
    #region TO DO
    
    # tests["val"] = {}
    # tests["val"]["ai"] = cfg.ai
    # tests["val"]["base1"] = cfg.ai.openai.api.base  ### Retrieve key is empty
    # cfg.ai.openai.api.base = "https://openai.com" ### Set empty existing key
    # tests["val"]["base2"] = cfg.ai.openai.api.base ### Retrieve this key
    
    # cfgl.set("ai.openai.api.base", "https://openai.am") ### Update empty existing key by index
    # tests["val"]["base3"] = cfg.ai.openai.api.base ### Retrieve edited existing key
    
    # cfg["ai.openai.api.base"] = "https://openai.ru" ### Set existing key by index
    # tests["val"]["base4"] = cfg["ai.openai.api.base"] ### Retrieve edited existing key by index

    # tests["val"]["base5"] = cfg.test.openai.api.base  ### Retrieve non existing key
    # cfg.test.openai.api.base = "https://openai.com" ### Set non existing key
    # tests["val"]["base6"] = cfg.test.openai.api.base ### Retrieve key
    
    # cfgl.set("test.openai.api.base", "https://openai.am")  ### Set key
    # tests["val"]["base7"] = cfg.test.openai.api.base  ### Retrieve key
    
    # cfg["test.openai.api.base"] = "https://openai.ru"  ### Set key by index
    # tests["val"]["base8"] = cfg["test.openai.api.base"]  ### Retrieve key by index

    # cfg["test.openai.api.base"] = "https://openai.com"  ### Set key by index
    # tests["val"]["base9"] = cfg["test.openai.api.base"]  ### Retrieve key by index

    # tests["val"]["user1"] = cfg.user[157166437]
    # tests["val"]["user_name1"] = cfg["user.157166437"]["first_name"]
    
    # cfg["user.157166437"]["first_name"] = "Andrei"
    # tests["val"]["user_name2"] = cfg["user.157166437"]["first_name"]
    
    # cfg["user.157166437"].first_name = "Andrew"
    # tests["val"]["user_name3"] = cfg["user.157166437"].first_name
    
    # tests["val"]["dialog"] = self.dialog["4f7d2e43-04cb-4cd3-a491-fd5728e33633"]
    
    # test_col = self.test_col
    # doc1uid = str(uuid.uuid4())
    # test_doc = test_col["test_doc"]
    
    # # test_doc.test.api(int).base = 5
    # # try:
    # #     test_doc.test.api(str).base = 7
    # # except Exception as e:     
    # #     pass
    # api = test_doc.test.api
    # base = api.base
    # api.base = 6    
    # base = api.base
    
    # api.base = {"some": "property"}    
    # base = api.base
    
    # api.base = 7
    # base = api.base
    
    # integer = test_doc.base2(int).integer
    # string = test_doc.test.api2.base(str).string
    # value = test_doc.test.api3.base({}).string
    
    # #test_doc.test().delete()
    # none = test_doc.test is None
    
    # value = test_doc.something({ "bla": "bla-bla" }, create=True).haha.bla
    
    # value = test_doc.something({ "bla": "bla-bla-bla" }, rewrite=True).haha.bla
    # value = test_doc.something.hH.bla
    
    # protected = test_doc(protected=True)
    # try:
    #     self["user.157166437"].first_name = "Andrew"
    # except  Exception as e:
    #     pass
    
    # value = test_doc.pro({ "bla": "bla-bla" }, create=True).haha.bla
    
    #endregion TO DO
    
    return tests    

@pytest.mark.skip()
def test_export(path, edbl, results):
    tests = {
        "✅": {}, 
        "❌": {}
    }
    
    f = open(f"{path}/{edbl.key()}.yml", "w")
    f.write(edbl.to_yml())
    f.close()
    
    f = open(f"{path}/{edbl.key()}.json", "w")
    f.write(edbl.to_json())
    f.close() 
    
    return tests

@pytest.fixture
def edb():
    return EndlessDatabase()

def test(edb):
    results = {}    
    path = Path("tests/export")
    path.mkdir(parents=True, exist_ok=True)
    
    edbl = edb()    
    results = {}
       
    #test_reading_all(edb, edbl, results)    
    test_writing(path, edb, edbl, results)
    test_export(path, edbl, results)     

cfg = EndlessConfiguration()
TestConfiguration.apply()
assert cfg.MONGO_URI == "mongodb://admin:admin@localhost:27017/"
TestInheritedConfiguration.apply()

assert cfg.CONFIG_COLLECTION == "test_config"
assert cfg.CONFIG_YML == "tests/config.yml"
assert cfg.MONGO_URI == "mongodb://root:root@localhost:27117/"
assert cfg.MONGO_DATABASE == "tests-endlessdb"
assert cfg.eee == None


