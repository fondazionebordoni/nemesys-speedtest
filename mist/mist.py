#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from logger import logging
except IOError as e:
    print "Impossibile inizializzare il logging, assicurarsi che il programma stia girando con i permessi di amministratore."
    import sys
    sys.exit()
# from sysMonitor import interfaces, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_TRAFFIC, RES_HOSTS
from sysMonitor import interfaces, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_TRAFFIC, RES_HOSTS
from threading import Thread, Event, enumerate
from checkSoftware import CheckSoftware
from optionParser import OptionParser
from speedTester import SpeedTester
from sysProfiler import sysProfiler
from collections import deque
from datetime import datetime
from platform import system
from time import sleep
from os import path

import paths
import wx

__version__ = '1.2.0'

SWN = 'MisuraInternet Speed Test'

TOTAL_STEPS = 19

logger = logging.getLogger()

LABEL_MESSAGE = \
'''In quest'area saranno riportati i risultati della misura
espressi attraverso i valori di ping, download e upload.'''

class mistGUI(wx.Frame):
  def __init__(self, *args, **kwds):
    self._version = __version__

    self._stream = deque([], maxlen = 800)
    self._stream_flag = Event()

    self._tester = None
    self._profiler = None
    self._button_play = False
    self._button_check = False
    
    # begin wxGlade: Frame.__init__
    wx.Frame.__init__(self, *args, **kwds)

    # Read server names from configuration
    parser = OptionParser(version=self._version, description='')
    (options, args, md5conf) = parser.parse()
    self._server_list = options.servernames.split(',')
    
    self.SetIcon(wx.Icon(path.join(paths._APP_PATH, u"mist.ico"), wx.BITMAP_TYPE_ICO))
    
    self.staticbox_result_display = wx.StaticBox(self, -1, "Risultati")
    self.staticbox_system_indicators = wx.StaticBox(self, -1, "Indicatori di stato del sistema")
    self.staticbox_messages = wx.StaticBox(self, -1, "Messaggi")
    self.staticbox_servers = wx.StaticBox(self, -1, "Servers")
    self.bitmap_button_play = wx.BitmapButton(self, -1, wx.Bitmap(path.join(paths.ICONS, u"play.png"), wx.BITMAP_TYPE_ANY))
    self.bitmap_button_check = wx.BitmapButton(self, -1, wx.Bitmap(path.join(paths.ICONS, u"check.png"), wx.BITMAP_TYPE_ANY))
    self.bitmap_logo = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"logo_misurainternet.png"), wx.BITMAP_TYPE_ANY))

    #Result labels
    self.label_ping = wx.StaticText(self, -1, "Ping", style = wx.ALIGN_CENTRE)
    self.label_download = wx.StaticText(self, -1, "Download", style = wx.ALIGN_CENTRE)
    self.label_upload = wx.StaticText(self, -1, "Upload", style = wx.ALIGN_CENTRE)
    self.label_ping_result = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
    self.label_download_result = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
    self.label_upload_result = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)

    #Progress gauge
    self.gauge_progress = wx.Gauge(self, -1, TOTAL_STEPS, style = wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        
    #System indicator bitmaps and labels
    self.bitmap_cpu = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_CPU.lower()), wx.BITMAP_TYPE_ANY))
    self.bitmap_ram = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_RAM.lower()), wx.BITMAP_TYPE_ANY))
    self.bitmap_eth = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_ETH.lower()), wx.BITMAP_TYPE_ANY))
    self.bitmap_wifi = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_WIFI.lower()), wx.BITMAP_TYPE_ANY))
#     self.bitmap_hspa = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_HSPA.lower()), wx.BITMAP_TYPE_ANY))
    self.bitmap_hosts = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_HOSTS.lower()), wx.BITMAP_TYPE_ANY))
    self.bitmap_traffic = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_TRAFFIC.lower()), wx.BITMAP_TYPE_ANY))
    self.label_cpu = wx.StaticText(self, -1, "%s\n- - - -" % RES_CPU, style = wx.ALIGN_CENTRE)
    self.label_ram = wx.StaticText(self, -1, "%s\n- - - -" % RES_RAM, style = wx.ALIGN_CENTRE)
    self.label_eth = wx.StaticText(self, -1, "%s\n- - - -" % RES_ETH, style = wx.ALIGN_CENTRE)
    self.label_wifi = wx.StaticText(self, -1, "%s\n- - - -" % RES_WIFI, style = wx.ALIGN_CENTRE)
#     self.label_hspa = wx.StaticText(self, -1, "%s\n- - - -" % RES_HSPA, style = wx.ALIGN_CENTRE)
    self.label_hosts = wx.StaticText(self, -1, "%s\n- - - -" % RES_HOSTS, style = wx.ALIGN_CENTRE)
    self.label_traffic = wx.StaticText(self, -1, "%s\n- - - -" % RES_TRAFFIC, style = wx.ALIGN_CENTRE)
    
    #Messages area
    self.messages_area = wx.TextCtrl(self, -1, "", style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_BESTWRAP | wx.BORDER_NONE)
    self.label_status = wx.StaticText(self, -1, LABEL_MESSAGE, style = wx.ALIGN_CENTRE)
    
#     self.grid_sizer_system_indicators = wx.FlexGridSizer(2, 7, 0, 0)
    self.grid_sizer_system_indicators = wx.FlexGridSizer(2, 6, 0, 0)
    self.grid_sizer_results = wx.FlexGridSizer(2, 3, 0, 0)
    self.grid_sizer_servers = wx.FlexGridSizer(1, 2, 0, 0)
    self.sizer_root = wx.BoxSizer(wx.VERTICAL)
    self.sizer_first_row = wx.BoxSizer(wx.HORIZONTAL)
    self.sizer_results_and_status = wx.BoxSizer(wx.VERTICAL)
    self.sizer_results_frame = wx.StaticBoxSizer(self.staticbox_result_display, wx.VERTICAL)
    self.sizer_messages_frame = wx.StaticBoxSizer(self.staticbox_messages, wx.VERTICAL)
    self.sizer_system_indicators_frame = wx.StaticBoxSizer(self.staticbox_system_indicators, wx.VERTICAL)
    
    #Server choice
    self.sizer_servers_frame = wx.StaticBoxSizer(self.staticbox_servers, wx.VERTICAL)
    self.label_current_server = wx.StaticText(self, -1, "Current server: %s" % self._server_list[0], style=wx.ALIGN_LEFT)
    self.label_server_choice = wx.StaticText(self, -1, "Change server:", style=wx.ALIGN_RIGHT)
    self.text_server_choice = wx.ComboBox(self, choices=self._server_list, style=wx.CB_READONLY)
    self.text_server_choice.SetStringSelection(self._server_list[0])
    self.button_server = wx.Button(self, wx.ID_OK, "go")
    self.hbox_server_choice = wx.BoxSizer(wx.HORIZONTAL)
    self.hbox_server_choice.Add(self.label_server_choice)
    self.hbox_server_choice.Add(self.text_server_choice)
    self.hbox_server_choice.Add(self.button_server)

    self.__set_properties()
    self.__do_layout()
    
    self.Bind(wx.EVT_SIZE, self._on_size)
    self.Bind(wx.EVT_CLOSE, self._on_close)
    self.Bind(wx.EVT_BUTTON, self._play, self.bitmap_button_play)
    self.Bind(wx.EVT_BUTTON, self._check, self.bitmap_button_check)
    self.Bind(wx.EVT_BUTTON, self._server_button_pressed, self.button_server)
    # end wxGlade

  def __set_properties(self):
    # begin wxGlade: Frame.__set_properties
    self.SetTitle("%s - versione %s" % (SWN, self._version))
    self.SetSize((800,460))
    
    self.messages_area_style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_BESTWRAP | wx.BORDER_NONE
    
    self.bitmap_button_play.SetMinSize((120, 120))
    self.bitmap_button_check.SetMinSize((40, 120))
    self.bitmap_logo.SetMinSize((101, 111))
    
    self._font_italic = wx.Font(12, wx.ROMAN, wx.ITALIC, wx.NORMAL, 0, "")
    self._font_italic_bold = wx.Font(12, wx.ROMAN, wx.ITALIC, wx.BOLD, 0, "")
    self._font_normal_bold = wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")
    self._font_normal = wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "")
    
    self.label_status.SetFont(self._font_italic)
    self.label_ping.SetFont(self._font_italic_bold)
    self.label_download.SetFont(self._font_italic_bold)
    self.label_upload.SetFont(self._font_italic_bold)
    self.label_ping_result.SetFont(self._font_normal_bold)
    self.label_download_result.SetFont(self._font_normal_bold)
    self.label_upload_result.SetFont(self._font_normal_bold)
    
    #self.SetBackgroundColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_WINDOW))
    self.messages_area.SetBackgroundColour(wx.Colour(242, 242, 242))
    self.SetBackgroundColour(wx.Colour(242, 242, 242))
    
    self.bitmap_cpu.SetMinSize((60, 60))
    self.bitmap_ram.SetMinSize((60, 60))
    self.bitmap_wifi.SetMinSize((60, 60))
    self.bitmap_hosts.SetMinSize((60, 60))
    self.bitmap_traffic.SetMinSize((60, 60))
    
    self.label_current_server.SetMinSize((180, 26))
    self.label_server_choice.SetMinSize((110, 26))
    self.text_server_choice.SetMinSize((180, 26))
    self.button_server.SetMinSize((30, 26))

    # end wxGlade

  def __do_layout(self):
    # begin wxGlade: Frame.__do_layout
    
    self.grid_sizer_results.Add(self.label_ping, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
    self.grid_sizer_results.Add(self.label_download, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
    self.grid_sizer_results.Add(self.label_upload, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
    
    self.grid_sizer_results.Add(self.label_ping_result, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_results.Add(self.label_download_result, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_results.Add(self.label_upload_result, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    
    self.sizer_results_and_status.Add(self.grid_sizer_results, 0, wx.ALL | wx.EXPAND, 0)
    self.sizer_results_and_status.Add(wx.StaticLine(self, -1), 0, wx.ALL | wx.EXPAND, 4)
    self.sizer_results_and_status.Add(self.label_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
    #self.sizer_results_frame.Add(wx.StaticLine(self, -1, style = wx.LI_VERTICAL), 0, wx.RIGHT | wx.EXPAND, 4)
    
    self.grid_sizer_system_indicators.Add(self.bitmap_cpu, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    self.grid_sizer_system_indicators.Add(self.bitmap_ram, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    self.grid_sizer_system_indicators.Add(self.bitmap_eth, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    self.grid_sizer_system_indicators.Add(self.bitmap_wifi, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
#     self.grid_sizer_system_indicators.Add(self.bitmap_hspa, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    self.grid_sizer_system_indicators.Add(self.bitmap_hosts, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    self.grid_sizer_system_indicators.Add(self.bitmap_traffic, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
    
    self.grid_sizer_system_indicators.Add(self.label_cpu, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_system_indicators.Add(self.label_ram, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_system_indicators.Add(self.label_eth, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_system_indicators.Add(self.label_wifi, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
#     self.grid_sizer_system_indicators.Add(self.label_hspa, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_system_indicators.Add(self.label_hosts, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    self.grid_sizer_system_indicators.Add(self.label_traffic, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
    
    self.grid_sizer_servers.Add(self.label_current_server, 2, wx.ALIGN_LEFT, 0)
    self.grid_sizer_servers.Add(self.hbox_server_choice, 1, wx.RIGHT | wx.ALIGN_RIGHT, 0)
#     self.grid_sizer_servers.Add(self.label_server_choice, 2, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 0)
#     self.grid_sizer_servers.Add(self.text_server_choice, 1,  wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 0)
#     self.grid_sizer_servers.Add(self.button_server, 1,  wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 0)
    
    self.sizer_results_frame.Add(self.sizer_results_and_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    
    self.sizer_first_row.Add(self.bitmap_button_play, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    self.sizer_first_row.Add(self.bitmap_button_check, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
    self.sizer_first_row.Add(self.sizer_results_frame, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
#    self.sizer_first_row.Add(self.sizer_results_and_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    self.sizer_first_row.Add(self.bitmap_logo, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)
    
    self.sizer_messages_frame.Add(self.messages_area, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
    self.sizer_system_indicators_frame.Add(self.grid_sizer_system_indicators, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)
    self.sizer_servers_frame.Add(self.grid_sizer_servers, 0, wx.ALL | wx.EXPAND| wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)

    self.sizer_root.Add(self.sizer_first_row, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    self.sizer_root.Add(self.gauge_progress, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
    self.sizer_root.Add(self.sizer_messages_frame, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    self.sizer_root.Add(self.sizer_system_indicators_frame, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
    self.sizer_root.Add(self.sizer_servers_frame, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 4)

    self.SetSizer(self.sizer_root)
    self.SetSizeHints(800, 460)
    
    self._initial_message()
    # end wxGlade
    
  def _on_size(self, event):
    
    (W, H) = self.GetSize()
    
    extra=0
    if (system().lower().startswith('win')):
      extra = 20
    elif (system().lower().startswith('dar')):
      extra = 60
      
    self.sizer_root.SetMinSize((W, H))
    width_margin = 20
    results_height = 120
    gauge_height = 20
    indicators_height = 120
    servers_height = 60
    self.sizer_results_frame.SetMinSize((W-300, results_height))
    self.gauge_progress.SetMinSize((W-width_margin, gauge_height))
    self.sizer_messages_frame.SetMinSize((W - width_margin, H-results_height - gauge_height - indicators_height - servers_height - (3*width_margin) - extra))
    self.sizer_system_indicators_frame.SetMinSize((W - width_margin, indicators_height))
    self.sizer_servers_frame.SetMinSize((W - width_margin, servers_height))
    
    self.messages_area.SetMinSize((W -(2 * width_margin), H-results_height - gauge_height - indicators_height - servers_height - (4*width_margin) - extra))
    
    self.Refresh()
    self.Layout()
  
  def _on_close(self, event):
    logger.info("Richiesta di close")
    dlg = wx.MessageDialog(self,"\nVuoi davvero chiudere %s?" % SWN, SWN, wx.OK|wx.CANCEL|wx.ICON_QUESTION)
    res = dlg.ShowModal()
    dlg.Destroy()
    if res == wx.ID_OK:
      self._killTester()    
      self.Destroy()
      
  def _play(self, event):
    self._button_play = True
    self._check(None)
    #self.bitmap_button_play.SetBitmapLabel(wx.Bitmap(path.join(paths.ICONS, u"stop.png")))

  def stop(self):
    #self.bitmap_button_play.SetBitmapLabel(wx.Bitmap(path.join(paths.ICONS, u"play.png")))

    self._killTester()
    self._update_messages("Misura terminata\n", 'medium forest green', (12, 93, 92, 1), True)
    if (self._tester.is_oneshot()):
      self._update_interface(">> MISURA TERMINATA <<\nPer la versione completa iscriviti su misurainternet.it", font = (12, 93, 92, 0))
      self._update_messages("Per effettuare altre misure e conservare i tuoi risultati nell'area riservata effettua l'iscrizione su misurainternet.it\n", 'black', (12, 90, 92, 0), True)
    else:
      self._update_interface(">> MISURA TERMINATA <<\nSistema pronto per una nuova misura", font = (12, 93, 92, 0))
      self._update_messages("Sistema pronto per una nuova misura", 'black', (12, 90, 92, 0), True)
    self._enable_button()
    self.update_gauge(TOTAL_STEPS)

  def _killTester(self):
    if (self._tester and self._tester != None):
      self._tester.join()
      for thread in enumerate():
        if thread.isAlive():
          try:
            thread._Thread__stop()
          except:
            logger.error("%s could not be terminated" % str(thread.getName()))
    
  def _server_button_pressed(self, event):
    self.chosen_server = self._server_list[self.text_server_choice.GetSelection()]
    self.label_current_server.SetLabel("Current server: %s" % self.chosen_server)
    
  def _check(self, event):
    self._button_check = True
    self.bitmap_button_play.Disable()
    self.bitmap_button_check.Disable()
    self.text_server_choice.Disable()
    self.button_server.Disable()
    self._reset_info()
    self._update_messages("Profilazione dello stato del sistema di misura", 'black', font = (12, 93, 92, 1))
    self._profiler = sysProfiler(self)
    self._profiler.start()

  def _after_check(self):
    self._update_messages("Profilazione terminata\n", 'medium forest green', font = (12, 93, 92, 1), fill = True)
    if (self._button_play):
      self._button_play = False
      self._button_check = False
      self._tester = SpeedTester(self, self._version, self.chosen_server)
      self._tester.start()
    else:
      # move_on_key()
      self._button_check = False
      self._update_interface(">> PROFILAZIONE TERMINATA <<\nPremere PLAY per effettuare la misura", font = (12, 93, 92, 0))
      self._enable_button()

  def _enable_button(self):
    self.bitmap_button_check.Enable()
    self.text_server_choice.Enable()
    self.button_server.Enable()

    if (self._tester is None or not self._tester.is_oneshot()):
      self.bitmap_button_play.Enable()

  def _update_down(self, downwidth):
    self.label_download_result.SetLabel("%.0f kbps" % downwidth)
    self.Layout()

  def _update_up(self, upwidth):
    self.label_upload_result.SetLabel("%.0f kbps" % upwidth)
    self.Layout()

  def _update_ping(self, rtt):
    self.label_ping_result.SetLabel("%.1f ms" % rtt)
    self.Layout()

  def _update_interface(self, message, font = (12, wx.ITALIC, wx.NORMAL, False)):
    (size, italic, bold, underline) = font
    font = wx.Font(size, wx.ROMAN, italic, bold, underline, "")
    self.label_status.SetFont(font)
    self.label_status.SetLabel(message)
    self.Layout()
  
  def _reset_info(self):
#     checkable_set = set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_HOSTS, RES_TRAFFIC])
    checkable_set = set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HOSTS, RES_TRAFFIC])

    for resource in checkable_set:
      self.set_resource_info(resource, {'status': None, 'info': None, 'value': None})

    self.label_download_result.SetLabel("- - - -")
    self.label_upload_result.SetLabel("- - - -")
    self.label_ping_result.SetLabel("- - - -")
    self.label_status.SetLabel("")

    self.messages_area.Clear()
    self.update_gauge(0)
    self.Layout()

  def update_gauge(self, value=None):
    if (value == None):
      value=self.gauge_progress.GetValue()+1
    self.gauge_progress.SetValue(value)

  def set_resource_info(self, resource, info, message_flag = True):
    res_bitmap = None
    res_label = None

    if info['status'] == None:
      colour = 'gray'
    elif info['status'] == True:
      colour = 'green'
    else:
      colour = 'red'

    if resource == RES_CPU:
      res_bitmap = self.bitmap_cpu
      res_label = self.label_cpu
    elif resource == RES_RAM:
      res_bitmap = self.bitmap_ram
      res_label = self.label_ram
    elif resource == RES_ETH:
      res_bitmap = self.bitmap_eth
      res_label = self.label_eth
    elif resource == RES_WIFI:
      res_bitmap = self.bitmap_wifi
      res_label = self.label_wifi
#     elif resource == RES_HSPA:
#       res_bitmap = self.bitmap_hspa
#       res_label = self.label_hspa
    elif resource == RES_HOSTS:
      res_bitmap = self.bitmap_hosts
      res_label = self.label_hosts
    elif resource == RES_TRAFFIC:
      res_bitmap = self.bitmap_traffic
      res_label = self.label_traffic

    if (res_bitmap != None):
      res_bitmap.SetBitmap(wx.Bitmap(path.join(paths.ICONS, u"%s_%s.png" % (resource.lower(), colour))))

    if (res_label != None):
      if (info['value'] != None):
#         if resource == RES_ETH or resource == RES_WIFI or resource == RES_HSPA:
        if resource == RES_ETH or resource == RES_WIFI:
          status = {-1:"Not Present", 0:"Off Line", 1:"On Line"}
          res_label.SetLabel("%s\n%s" % (resource, status[info['value']]))
        elif resource == RES_CPU or resource == RES_RAM:
          res_label.SetLabel("%s\n%.1f%%" % (resource, float(info['value'])))
        else:
          res_label.SetLabel("%s\n%s" % (resource, info['value']))
      else:
        res_label.SetLabel("%s\n- - - -" % resource)

    if (message_flag) and (info['info'] != None):
      self._update_messages(info['info'], colour)

    self.Layout()

  def _update_messages(self, message, colour = 'black', font = None, fill = False):
    logger.info('Messaggio all\'utente: "%s"' % message)
    self._stream.append((str(message), colour, font, fill))
    if (not self._stream_flag.isSet()):
#      if (system().lower().startswith('win')):
#        writer = Thread(target = self._writer)
#        writer.start()
#      else:
      self._writer()

  def _writer(self):
    self._stream_flag.set()
    while (len(self._stream) > 0):
      
#      basic_font = wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "")
      words = {}
      
      (message, colour, font, fill) = self._stream.popleft()
      date = datetime.today().strftime('%a %d/%m/%Y %H:%M:%S')
      
      last_pos = self.messages_area.GetLastPosition()
      if (last_pos != 0):
        text = "\n"
      else:
        self.messages_area.SetWindowStyleFlag(self.messages_area_style)
        self.messages_area.SetFont(self._font_normal)
        text = ""
      
      date = date + "  "
      text = text + date
      words[date] = (colour, wx.NullColour, self._font_normal)
      
      text = text + message
            
      if fill:
        textcolour = colour
      else:
        textcolour = 'black'
      
      if font != None:
        (size, italic, bold, underline) = font
        font = wx.Font(size, wx.SWISS, italic, bold, underline, "")
      else:
        font = wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "")
      
      words[message] = (textcolour, wx.NullColour, font)
        
      self.messages_area.AppendText(text)
      self.messages_area.SetInsertionPoint(last_pos+1)
      self._set_style(text, words, last_pos)
        
      self.messages_area.ScrollLines(-1)
    self._stream_flag.clear()
    
  def _initial_message(self):

    message = \
'''Benvenuto in %s versione %s

Premendo il tasto CHECK avvierai la profilazione della macchina per la misura.

Premendo il tasto PLAY avvierai una profilazione e il test di misura completo.''' % (SWN, self._version)

    self.messages_area.SetWindowStyleFlag(self.messages_area_style + wx.TE_CENTER)

    self.messages_area.SetFont(wx.Font(12, wx.ROMAN, wx.NORMAL, wx.NORMAL, 0, ""))
    
    self.messages_area.AppendText(message)
    self.messages_area.ScrollLines(-1)
    
    font1 = wx.Font(14, wx.ROMAN, wx.ITALIC, wx.BOLD, 0, "")
    font2 = wx.Font(12, wx.ROMAN, wx.ITALIC, wx.BOLD, 1, "")
    word1 = "Benvenuto in %s versione %s" % (SWN, self._version) 
    words = {word1:(wx.NullColour, wx.NullColour, font1), 'CHECK':('blue', wx.NullColour, font2), 'PLAY':('green', wx.NullColour, font2)}
    
    self._set_style(message, words)
    
    self.Layout()
    
  def _set_style(self, message, words, offset = 0):
    for word in words:
      start = message.find(word) + offset
      end = start + len(word)
      style = words[word]
      self.messages_area.SetStyle(start, end, wx.TextAttr(*style))
      
      
def sleeper():
    sleep(.001)
    return 1 # don't forget this otherwise the timeout will be removed
  
  
  
  
if __name__ == "__main__":

  version = __version__

  logger.info('Starting %s v.%s' % (SWN, version)) 
  
  app = wx.PySimpleApp(0)
  
  checker = CheckSoftware(version)
  check = checker.checkIT()
  
  if check:
    interfaces()
    if (system().lower().startswith('win')):
      wx.CallLater(200, sleeper)
    wx.InitAllImageHandlers()
    GUI = mistGUI(None, -1, "", style = wx.DEFAULT_FRAME_STYLE) #& ~(wx.RESIZE_BORDER | wx.RESIZE_BOX))
    app.SetTopWindow(GUI)
    GUI.Show()
    app.MainLoop()
