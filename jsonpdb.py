import inspect, operator
import urllib
import re
import logging

from django.utils import simplejson as json
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

def createEntity(className, jsonObj):
    if className[0] == "_":
        raise Exception("Class name must not start with _")
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

class MainPage(webapp.RequestHandler):
  def get(self):
    self.redirect("index.html")

class Add(webapp.RequestHandler):
  def post(self):
    if self.request.get('jsonp') and len(self.request.GET.keys()) >= 2:
        className = str(self.request.get.keys()[0])
        jsonStr = urllib.unquote(str(self.request.get(className)))
        jsonObj = json.loads(jsonStr)
        objEntity = createEntity(className, jsonObj)
        self.response.out.write(self.request.get('jsonp') + "(\"" + str(objEntity.put()) + "\");")

class Get(webapp.RequestHandler):
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

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/add', Add),
                                      ('/get', Get)],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()