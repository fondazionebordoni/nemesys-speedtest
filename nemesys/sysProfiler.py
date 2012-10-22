#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sysmonitor import checkset, RES_OS, RES_IP, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_TRAFFIC, RES_HOSTS
from threading import Thread, Event
from time import sleep
# from usbkey import check_usb, move_on_key
from logger import logging
import sysmonitor
import wx


logger = logging.getLogger()


class sysProfiler(Thread):

  def __init__(self, gui, type = 'check', checkable_set = set([RES_OS, RES_IP, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_HOSTS, RES_TRAFFIC])):
    Thread.__init__(self)

    self._gui = gui
    self._type = type
    self._checkable_set = checkable_set
    self._available_check = {RES_OS:1, RES_IP:2, RES_CPU:3, RES_RAM:4, RES_ETH:5, RES_WIFI:6, RES_HSPA:7, RES_HOSTS:8, RES_TRAFFIC:9}

    self._events = {}
    self._results = {}
    self._cycle = Event()
    self._results_flag = Event()
    self._checkset_flag = Event()
    self._usbkey_ok = False
    self._device = None

  def run(self):

    self._cycle.set()

    while (self._cycle.isSet()):
      self._results_flag.clear()
      self._checkset_flag.clear()

      if (self._type != 'tester'):
        self._usbkey_ok = self._check_usbkey()
      else:
        self._usbkey_ok = True

      if (self._usbkey_ok and self._type != 'usbkey'):
        result = checkset(set([RES_IP]))
        self._results.update(result)
        self._check_device()
        
      if (self._usbkey_ok or self._type == 'usbkey'):
        self._events.clear()
        self._results.clear()

        for res in sorted(self._available_check, key = lambda res: self._available_check[res]):
          if self._checkset_flag.isSet():
            self._events.clear()
            self._results.clear()
            break
          if res in self._checkable_set:
            res_flag = Event()
            self._events[res] = res_flag
            self._events[res].clear()
            self._check_resource(res)

            if self._events[res].isSet():
              del self._events[res]
              if (self._type == 'tester'):
                message_flag = False
              else:
                message_flag = True
              wx.CallAfter(self._gui.set_resource_info, res, self._results[res], message_flag)
        
        self._results_flag.set()

        if (self._type != 'tester'):
          self._cycle.clear()
        else:
          sleep(1)

    if (self._usbkey_ok and self._type == 'check'):
#      self._tester = _Tester(self._gui)
#      self._tester._uploadall()
      wx.CallAfter(self._gui._after_check)

  def stop(self):
    self._cycle.clear()

  def set_check(self, checkable_set = set([RES_OS, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_HOSTS, RES_TRAFFIC])):
    self._checkable_set = checkable_set
    self._checkset_flag.set()

  def _check_resource(self, resource):
    result = checkset(set([resource]))
    self._results.update(result)
    self._events[resource].set()

  def get_results(self):
    self._results_flag.wait()
    self._results_flag.clear()
    if self._checkset_flag.isSet():
      self._results_flag.wait()
      self._results_flag.clear()
    if (self._type == 'usbkey'):
      results = self._usbkey_ok
    else:
      results = {}
      for key in self._results:
        results[key] = self._results[key]['value']
    return results

  def _check_device(self):
    try:
      ip = self._results[RES_IP]['value']
      id = sysmonitor.getDev(ip)
    except Exception as e:
      info = {'status':False, 'value':-1, 'info':''}
      wx.CallAfter(self._gui.set_resource_info, RES_ETH, info, False)
      wx.CallAfter(self._gui.set_resource_info, RES_WIFI, info, False)
      wx.CallAfter(self._gui.set_resource_info, RES_HSPA, info, False)
      wx.CallAfter(self._gui._update_messages, e, 'red')
      return
      
    if (self._device == None):
      self._device = id
      if (self._type != 'tester'):
        dev_info = sysmonitor.getDevInfo(id)
        dev_type = dev_info['type']
        if (dev_type == 14):
          dev_descr = "rete locale via cavo ethernet"
        elif (dev_type == 25):
          dev_descr = "rete locale wireless"
        elif (dev_type == 3 or dev_type == 17):
          dev_descr = "rete mobile su dispositivo hspa"
        else:
          dev_descr = dev_info['descr']
        wx.CallAfter(self._gui._update_interface, dev_descr, ip)
        
        if (dev_info['descr'] != 'none'):
          dev_descr = dev_info['descr'] 
        wx.CallAfter(self._gui._update_messages, "Interfaccia di rete in esame: %s" % dev_descr, 'green')
        wx.CallAfter(self._gui._update_messages, "Indirizzo IP dell'interfaccia di rete in esame: %s" % ip, 'green')
        
    elif (id != self._device):
      self._cycle.clear()
      self._usbkey_ok = False
      wx.CallAfter(self._gui._update_messages, "Test interrotto per variazione interfaccia di rete di riferimento.", 'red')
      wx.CallAfter(self._gui.stop)
      
         
  def _check_usbkey(self):
    check = True
    # if (not check_usb()):
      # self._cycle.clear()
      # logger.info('Verifica della presenza della chiave USB fallita')
      # wx.CallAfter(self._gui._update_messages, "Per l'utilizzo di questo software occorre disporre della opportuna chiave USB. Inserire la chiave nel computer e riavviare il programma.", 'red')
    return check
  
  