#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from sysMonitor import SysMonitor, RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC
from sysMonitor import SysMonitor, RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC
from collections import OrderedDict
from threading import Thread, Event
from time import sleep
from logger import logging
import wx


logger = logging.getLogger()

# ALL_RES = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC]
# MESSAGE = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_IP, RES_HOSTS, RES_TRAFFIC]
ALL_RES = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_DEV, RES_MAC, RES_IP, RES_MASK, RES_HOSTS, RES_TRAFFIC]
MESSAGE = [RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_IP, RES_HOSTS, RES_TRAFFIC]

class sysProfiler(Thread):

  def __init__(self, gui, mode = 'check', checkable_set = set(ALL_RES)):
    Thread.__init__(self)
    
    self._gui = gui
    self._mode = mode
    self._settings = [False,False,False,False]
    
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
    
    self._events = OrderedDict([])
    self._results = OrderedDict([])
    
    self._cycle_flag = Event()
    self._results_flag = Event()
    self._checkres_flag = Event()
    
    self._device = None
    
    self._checker = SysMonitor()
    
  def run(self):
    
    self._cycle_flag.set()
    
    while (self._cycle_flag.isSet()):
      
      ## settings = [message, cycle, return, device] ##
      if (self._mode == 'check'):
        self._settings = [True,False,True,True]
      elif (self._mode == 'tester'):
        self._settings = [False,True,False,False]
      
      self._results_flag.clear()
      self._checkres_flag.clear()
      
      self._check_device()
        
      self._events.clear()
      self._results.clear()
      
      for res in self._available_check:
        if self._checkres_flag.isSet():
          self._events.clear()
          self._results.clear()
          break
        if res in self._checkable_set:
          res_flag = Event()
          self._events[res] = res_flag
          self._events[res].clear()
          self._check_resource(res)
          self._events[res].wait()
          del self._events[res]
          message_flag = self._settings[0]
          if (res in MESSAGE):
            wx.CallAfter(self._gui.set_resource_info, res, self._results[res], message_flag)
        
      self._results_flag.set()
      
      if self._settings[1]:
        sleep(0.8)
      else:
        self._cycle_flag.clear()

    if self._settings[2]:
#      self._tester = _Tester(self._gui)
#      self._tester._uploadall()
      wx.CallAfter(self._gui._after_check)
  
  def _check_resource(self, resource):
    val = self._checker.checkres(resource)
    self._results[resource] = val
    self._events[resource].set()
  
  def _check_device(self):
    try:
      ip = self._checker.checkres(RES_IP)['value']
      dev = self._checker.checkres(RES_DEV, ip)['value']
    except Exception as e:
      info = {'status':False, 'value':-1, 'info':e}
      wx.CallAfter(self._gui.set_resource_info, RES_ETH, info, False)
      wx.CallAfter(self._gui.set_resource_info, RES_WIFI, info, False)
#       wx.CallAfter(self._gui.set_resource_info, RES_HSPA, info, False)
      wx.CallAfter(self._gui._update_messages, e, 'red')
      return
      
    if (self._device == None):
      self._device = dev
      if self._settings[3]:
#         dev_info = self._checker._getDevInfo(dev)
#         dev_type = dev_info['type']
#         dev_descr = dev_info['descr']
#         
#         if (dev_type == 'Ethernet 802.3'):
#           dev_descr = "rete locale via cavo ethernet"
#         elif (dev_type == 'Wireless'):
#           dev_descr = "rete locale wireless"
#         elif (dev_type == 'WWAN') or (dev_type == 'External Modem'):
#           dev_descr = "rete mobile su dispositivo hspa"
          
#        wx.CallAfter(self._gui._update_interface, "Interfaccia di test: %s\nIndirizzo IP di rete: %s" % (dev_descr,ip))
        wx.CallAfter(self._gui._update_interface, "Interfaccia di test: %s\nIndirizzo IP di rete: %s" % (dev,ip))
        
#        dev_descr = dev_info['descr'] 
        
#        wx.CallAfter(self._gui._update_messages, "Interfaccia di rete in esame: %s" % dev_descr, 'green')
        wx.CallAfter(self._gui._update_messages, "Interfaccia di rete in esame: %s" % dev, 'green')
        
    elif (dev != self._device):
      self._cycle_flag.clear()
      wx.CallAfter(self._gui._update_messages, "Test interrotto per variazione interfaccia di rete di riferimento.", 'red')
      wx.CallAfter(self._gui.stop)
  
  def get_results(self):
    self._results_flag.wait()
    self._results_flag.clear()
    if self._checkres_flag.isSet():
      self._results_flag.wait()
      self._results_flag.clear()
    results = {}
    for key in self._results:
      results[key] = self._results[key].get('value',None)
    return results
  
  def set_check(self, checkable_set = set(ALL_RES)):
    self._checkable_set = checkable_set
    self._checkres_flag.set()
  
  def stop(self):
    self._cycle_flag.clear()
  
  