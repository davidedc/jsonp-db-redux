import inspect, operator
import urllib
import re
import logging
import webapp2
import json

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app

# only for cleanup mechanism
from datetime import datetime                        # strip for no auto cleanup

# The classes extending db.Model become
# "records" (or, properly, "entities") in the Datastore
# https://developers.google.com/appengine/docs/python/datastore/entities#Python_Kinds_and_identifiers

class LastCleaned(db.Model):                         # strip for no auto cleanup
    lastCleaned = db.DateTimeProperty(auto_now=True) # strip for no auto cleanup

class EntitiesKinds(db.Model):
  theKind = db.StringProperty()

def createEntity(className, jsonObj):
    #if className[0] == "_":
    #    raise Exception("Class name must not start with _")
    if className == "LastCleaned":                                # strip for no auto cleanup
        raise Exception("LastCleaned is a reserved entity kind")  # strip for no auto cleanup
    #Return an empty instance if no jsonObj present
    if jsonObj == None:
        objClass = type(className,(db.Model,),{})
        return objClass()
    if not type(jsonObj) == dict:
        raise Exception("JSON object must start as a dictionary (as opposed to an array or string value)")
    
    #Create entity
    propertyDict = dict()
    #If the property name has ".text" at the end, make it a text object
    for k in jsonObj.keys():
        if len(str(k)) > 5 and str(k).rfind(".text") == len(str(k)) - 5:
            propertyDict[str(k)] = db.TextProperty()
        else:
            propertyDict[str(k)] = db.StringProperty()
    
    objClass = type(className,(db.Model,),propertyDict)
    objEntity = objClass()
    for k in jsonObj.keys():
        objEntity.__setattr__(str(k), json.dumps(jsonObj[k]))
        
    return objEntity

class MainPage(webapp2.RequestHandler):
  def get(self):
    self.redirect("index.html")

class Put(webapp2.RequestHandler):
  def get(self,className,jsonStr):
    logging.error('put being done')
    logging.error('self.request.get: ' + self.request.get('callback'))
    logging.error('keys: ' + str(self.request.GET.keys()))
    logging.error('len: ' + str(len(self.request.GET.keys())))
    jsonObj = json.loads(jsonStr)
    objEntity = createEntity(className, jsonObj)
    theKey = str(objEntity.put())
    if self.request.get('callback'):
        self.response.out.write(self.request.get('callback') + "(\"" + theKey + "\");")
    else:
        self.response.out.write(theKey )

    entityKind = EntitiesKinds(theKind = className)
    v = EntitiesKinds.all().filter('theKind =', className)
    if not v.get():
        entityKind = EntitiesKinds(theKind = className)
        entityKind.put()

class GetWithKey(webapp2.RequestHandler):
  def get(self,keyStr):    
    # the class name is encoded in the key string
    # (in a non-cryptographically secure way)
    # see https://developers.google.com/appengine/docs/python/datastore/keyclass?csw=1#Key_kind
    className = str(db.Key(keyStr).kind())
    #Query for object based on a unique key
    objClass = type(className, (db.Model,), {})
    ent = db.get(keyStr)
    if ent:
        objDict = dict()
        for k in ent.__dict__["_entity"].keys():
                objDict[str(k)] = json.loads(ent.__dict__["_entity"][k])
        objectDump = json.dumps(objDict)
        if self.request.get('callback'):
            self.response.out.write(str(self.request.get('callback')) + "(" + objectDump + ");")
        else:
            self.response.out.write(objectDump)

class GetWithFilter(webapp2.RequestHandler):
  def get(self,className):
    
    classString = str(self.request.get('filter') )
    logging.debug('filter: ' + classString)
    if classString == '':
        #Process get request for all objects of a type
        objEntity = createEntity(className, None)
        query = objEntity.all()
        objArr = list()
        for ent in query:
            objDict = dict()
            for k in ent.__dict__["_entity"].keys():
                    objDict[str(k)] = json.loads(ent.__dict__["_entity"][k])
            objArr.append(objDict)
        objectDump = json.dumps(objArr)
    else:
        jsonStr = urllib.unquote(classString)
        jsonObj = json.loads(jsonStr)
        objEntity = createEntity(className, jsonObj)
        query = objEntity.all()
        #Querying based on filtered information for an object
        #Loop through the keys sent in the object and add query filters
        
        for k in jsonObj.keys():
            query.filter(str(k) + " =", json.dumps(jsonObj.get(k)))
        
        #Return results
        objArr = list()
        for ent in query:
            objDict = dict()
            for k in ent.__dict__["_entity"].keys():
                    objDict[str(k)] = json.loads(ent.__dict__["_entity"][k])
            objArr.append(objDict)
        objectDump = json.dumps(objArr)

    if self.request.get('callback'):
        self.response.out.write(str(self.request.get('callback')) + "(" + objectDump + ");")
    else:
        self.response.out.write(objectDump)


# strip this whole class for no auto cleanup
class WhenLastCleaned(webapp2.RequestHandler):
  def get(self):
    logging.info('WhenLastCleaned()')
    
    # just gets the first entity as there should be
    # only one. all() only constructs the query
    # fetching all entities. Get() then actually
    # runs the query and fetches the first entity
    # only.
    ent = LastCleaned.all().get()

    if ent != None:
        # found a result in the DataStore
        dateAndTimeAsString = str(ent.lastCleaned)
    else:
        dateAndTimeAsString = 'unknown'

    objDict = dict()
    objDict['resetTime'] = json.loads('"'+dateAndTimeAsString+'"')
    objDict['currentTime'] = json.loads('"'+str(datetime.now())+'"')
    self.response.out.write(str(self.request.get('callback')) + "(" + json.dumps(objDict) + ");")
    return

# strip this whole class for no auto cleanup
class CleanAll(webapp2.RequestHandler):
  def get(self):

    # this commented line below should
    # delete all LastCleaned entities but,
    # mysteriously, it doesn't, it leaves out
    # some entities. The long-winded form
    # below does the job instead.
    # db.delete(LastCleaned.all(keys_only=True))
    query = LastCleaned.all(keys_only=True)
    entries =query.fetch(1000)
    db.delete(entries)

    LastCleaned().put()

    # first get all the kinds of the entities
    allEntityKeys = EntitiesKinds.all()

    # loop through the kinds and delete
    # all entities of that kind
    for entityKey in allEntityKeys:
        theKind = str(entityKey.theKind)
        objClass = type(theKind,(db.Model,),{})
        query = objClass.all(keys_only=True)
        entries =query.fetch(1000)
        db.delete(entries)

    # finally delete the table with all the
    # kinds
    db.delete(allEntityKeys)


    self.redirect("index.html")

application = webapp2.WSGIApplication(
                                     [('/', MainPage),
                                      (r'/put/buckets/([^/]*)/(.*)', Put),
                                      (r'/get/keys/(.*)', GetWithKey),
                                      (r'/get/buckets/([^/]*)/', GetWithFilter),
                                      ('/cleanAll', CleanAll), # strip for no auto cleanup
                                      ('/whenLastCleaned', WhenLastCleaned), # strip for no auto cleanup
                                      ],
                                     debug=True)

def main():
  logging.debug('main()')
  run_wsgi_app(application)

if __name__ == "__main__":
  main()