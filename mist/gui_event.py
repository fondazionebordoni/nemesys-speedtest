'''
Created on 05/ott/2015

@author: ewedlund
'''

import wx
        
myEVT_UPDATE = wx.NewEventType()
EVT_UPDATE = wx.PyEventBinder(myEVT_UPDATE)        

myEVT_RESULT = wx.NewEventType()
EVT_RESULT = wx.PyEventBinder(myEVT_RESULT)        

myEVT_ERROR = wx.NewEventType()
EVT_ERROR = wx.PyEventBinder(myEVT_ERROR)        

myEVT_PROGRESS = wx.NewEventType()
EVT_PROGRESS = wx.PyEventBinder(myEVT_PROGRESS)        

myEVT_RESOURCE = wx.NewEventType()
EVT_RESOURCE = wx.PyEventBinder(myEVT_RESOURCE)        

myEVT_STOP = wx.NewEventType()
EVT_STOP = wx.PyEventBinder(myEVT_STOP)        


class UpdateEvent(wx.PyCommandEvent):
    '''Update message area'''
    
    MAJOR_IMPORTANCE = "major"
    MINOR_IMPORTANCE = "minor"

    def __init__(self, message = None, importance = None):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_UPDATE)
        self._message = message
        self._importance = importance
        
    #TODO use property
    def getMessage(self):
        return self._message
    
    def getImportance(self):
        return self._importance
    
class ResultEvent(wx.PyCommandEvent):
    '''Update message area'''

    def __init__(self, res_type, value):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_RESULT)
        self._res_type = res_type
        self._value = value
        
    #TODO use property
    def getType(self):
        return self._res_type
    
    def getValue(self):
        return self._value
    
class ErrorEvent(wx.PyCommandEvent):
    '''Update message area'''

    def __init__(self, message = None, severity = None):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_ERROR)
        self._message = message
        self._severity = severity
        
    #TODO use property
    def getMessage(self):
        return self._message
    
    def getSeverity(self):
        return self._severity
    

class ProgressEvent(wx.PyCommandEvent):
    '''Update message area'''

    def __init__(self, value = None):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_PROGRESS)
        self._value = value
        
    #TODO use property
    def getValue(self):
        return self._value
    
class ResourceEvent(wx.PyCommandEvent):
    '''Update message area'''

    def __init__(self, resource, value, message_flag = None):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_RESOURCE)
        self._resource = resource
        self._value = value
        self._message_flag = message_flag
        
    #TODO use property
    def getResource(self):
        return self._resource
    
    def getValue(self):
        return self._value
    
    def getMessageFlag(self):
        return self._message_flag
    
class StopEvent(wx.PyCommandEvent):
    '''Tell GUI that speed tester has finished'''

    def __init__(self):
        '''Creates the event object'''
        wx.PyCommandEvent.__init__(self, myEVT_STOP)
    