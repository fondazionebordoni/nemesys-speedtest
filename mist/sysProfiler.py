#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from sysMonitor import SysMonitor, RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC
from sysMonitor import SysMonitor, RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC
from collections import OrderedDict
from threading import Thread, Event
from logger import logging
from gui_event import ResourceEvent, AfterCheckEvent, ErrorEvent,\
    UpdateEvent, StopEvent

import Queue

logger = logging.getLogger()

ALL_RES = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC]
MESSAGE = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_IP, RES_HOSTS, RES_TRAFFIC]

class sysProfiler(Thread):

  def __init__(self, event_dispatcher, mode = 'check', checkable_set = set(ALL_RES)):
    Thread.__init__(self)
    
    self._event_dispatcher = event_dispatcher
    self._mode = mode
    if (self._mode == 'check'):
      self._settings = [True,False,True,True]
    elif (self._mode == 'tester'):
      self._settings = [False,True,False,False]
      
    
    self._checkable_set = checkable_set
    self._available_check = OrderedDict \
    ([ \
    (RES_DEV, None),\
    (RES_MAC, None),\
    (RES_IP, None),\
    (RES_MASK, None),\
    (RES_OS, None),\
    (RES_CPU, None),\
    (RES_RAM, None),\
    (RES_ETH, None),\
    (RES_WIFI, None),\
#     (RES_HSPA, None),\
    (RES_HOSTS, None),\
    (RES_TRAFFIC, None) \
    ])
    
    self._device = None
    
    self._sys_monitor = SysMonitor()
    self._result_queue = Queue.Queue()
    self._error_queue = Queue.Queue()
    self._profiler_idle = Event()
    self._profiler_idle.set()


  def profile_once_and_call_back(self, callback, resources = set(ALL_RES)):
    profiling_thread = Thread(target = self._do_profile, args = (True, resources, callback))
    profiling_thread.daemon = True
    profiling_thread.start()


  def profile_once(self, resources = set(ALL_RES)):
    return self._do_profile(do_once = True, resources = resources)


  def _do_profile(self, do_once = True, resources = set(ALL_RES), callback = None):
    self._profiler_idle.wait(10.0)
    if not self._profiler_idle.is_set():
      self._error_queue.put("Timed out waiting for profiler")
      "TODO: raise exception, or callback"
      return None
    self._profiler_idle.clear()
    self._check_device()
    sysmon_results = OrderedDict([])
    for res in resources:
      if res in self._available_check:
        result = self._sys_monitor.checkres(res)
        sysmon_results[res] = result#self._sys_monitor.checkres(res).get('value', None)
        message_flag = self._settings[0]
        if (res in MESSAGE):
          "TODO: call back!"
          self._event_dispatcher.postEvent(ResourceEvent(res, sysmon_results[res], message_flag))
    
    results = {}
    for key in sysmon_results:
      results[key] = sysmon_results[key].get('value', None)

    if self._settings[2]:
      "TODO: call back!"
      self._event_dispatcher.postEvent(AfterCheckEvent())

    self._profiler_idle.set()

    if callback != None:
      callback(results)
    else:
      return results

#   def _check_resource(self, resource):
#     val = self._sys_monitor.checkres(resource)
#     self._results[resource] = val
#   
  
  def _check_device(self):
    try:
      ip = self._sys_monitor.checkres(RES_IP)['value']
      dev = self._sys_monitor.checkres(RES_DEV, ip)['value']
    except Exception as e:
      info = {'status':False, 'value':-1, 'info':e}
      self._event_dispatcher.postEvent(ResourceEvent(RES_ETH, info, False))
      self._event_dispatcher.postEvent(ResourceEvent(RES_WIFI, info, False))
      self._event_dispatcher.postEvent(ErrorEvent(e))
      return
      
    if (self._device == None):
      self._device = dev
      if self._settings[3]:
        self._event_dispatcher.postEvent(UpdateEvent("Interfaccia di test: %s" % dev))
        self._event_dispatcher.postEvent(UpdateEvent("Indirizzo IP di rete: %s" % ip))
        self._event_dispatcher.postEvent(UpdateEvent("Interfaccia di rete in esame: %s" % dev))
        
    elif (dev != self._device):
      "TODO: handle at higher level"
      self._event_dispatcher.postEvent(ErrorEvent("Test interrotto per variazione interfaccia di rete di riferimento."))     
      self._event_dispatcher.postEvent(StopEvent()) 
  
  