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

class Add(webapp2.RequestHandler):
  def get(self):
    logging.debug('add being done')
    if self.request.get('jsonp') and len(self.request.GET.keys()) >= 2:
        className = str(self.request.GET.keys()[0])
        jsonStr = urllib.unquote(str(self.request.get(className)))
        jsonObj = json.loads(jsonStr)
        objEntity = createEntity(className, jsonObj)
        self.response.out.write(self.request.get('jsonp') + "(\"" + str(objEntity.put()) + "\");")

        entityKind = EntitiesKinds(theKind = className)
        v = EntitiesKinds.all().filter('theKind =', className)
        if not v.get():
            entityKind = EntitiesKinds(theKind = className)
            entityKind.put()

class Get(webapp2.RequestHandler):
  def get(self):
    
    if self.request.get('jsonp') and len(self.request.GET.keys()) >= 2:
        className = str(self.request.GET.keys()[0])
        if str.lower(className) == "jsonp":
            raise Exception("Expected JSON object name as first parameter.")
        classString = str(self.request.get(className))
        if classString == "*":
            #Process get request for all objects of a type
            objEntity = createEntity(className, None)
            query = objEntity.all()
            objArr = list()
            for ent in query:
                objDict = dict()
                for k in ent.__dict__["_entity"].keys():
                        objDict[str(k)] = json.loads(ent.__dict__["_entity"][k])
                objArr.append(objDict)
            self.response.out.write(str(self.request.get('jsonp')) + "(" + json.dumps(objArr) + ");")
        elif not re.compile('\W').match(classString):
            #Query for object based on a unique key
            objClass = type(className, (db.Model,), {})
            keyStr = classString
            ent = db.get(keyStr)
            if ent:
                objDict = dict()
                for k in ent.__dict__["_entity"].keys():
                        objDict[str(k)] = json.loads(ent.__dict__["_entity"][k])
                self.response.out.write(str(self.request.get('jsonp')) + "(" + json.dumps(objDict) + ");")
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
            
            self.response.out.write(str(self.request.get('jsonp')) + "(" + json.dumps(objArr) + ");")

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
    self.response.out.write(str(self.request.get('jsonp')) + "(" + json.dumps(objDict) + ");")
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
                                      ('/add', Add),
                                      ('/get', Get),
                                      ('/cleanAll', CleanAll), # strip for no auto cleanup
                                      ('/whenLastCleaned', WhenLastCleaned), # strip for no auto cleanup
                                      ],
                                     debug=True)

def main():
  logging.debug('main()')
  run_wsgi_app(application)

if __name__ == "__main__":
  main()