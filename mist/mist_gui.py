'''
Created on 12/ott/2015

@author: ewedlund
'''
import gui_event
import paths
import test_type
import wx

from collections import deque
from datetime import datetime
from logger import logging
from os import path
from platform import system
"TODO: move from sysmonitor"
from sysMonitor import RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_TRAFFIC, RES_HOSTS 
from threading import Event#, enumerate

TOTAL_STEPS = 19 + 8 # 4 http up + 4 http down
LABEL_MESSAGE = \
'''In quest'area saranno riportati i risultati della misura
espressi attraverso i valori di ping, download e upload.'''
SWN = 'MisuraInternet Speed Test'
logger = logging.getLogger()

class mistGUI(wx.Frame):
    def __init__(self, *args, **kwds):
        
        wx.Frame.__init__(self, *args, **kwds)

    def init_frame(self, version, event_dispatcher):
        self._version = version
        self._event_dispatcher = event_dispatcher
        self._stream = deque([], maxlen=800)
        self._stream_flag = Event()

        self._tester = None
        self._profiler = None
        self._button_play = False
        self._button_check = False
        
        # begin wxGlade: Frame.__init__
        
        self.SetIcon(wx.Icon(path.join(paths._APP_PATH, u"mist.ico"), wx.BITMAP_TYPE_ICO))
        
        self.sizer_1_staticbox = wx.StaticBox(self, -1, "Risultati")
        self.sizer_2_staticbox = wx.StaticBox(self, -1, "Indicatori di stato del sistema")
        self.sizer_3_staticbox = wx.StaticBox(self, -1, "Messaggi")
        self.bitmap_button_play = wx.BitmapButton(self, -1, wx.Bitmap(path.join(paths.ICONS, u"play.png"), wx.BITMAP_TYPE_ANY))
        self.bitmap_button_check = wx.BitmapButton(self, -1, wx.Bitmap(path.join(paths.ICONS, u"check.png"), wx.BITMAP_TYPE_ANY))
        self.bitmap_logo = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"logo_misurainternet.png"), wx.BITMAP_TYPE_ANY))
        self.bitmap_cpu = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_CPU.lower()), wx.BITMAP_TYPE_ANY))
        self.bitmap_ram = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_RAM.lower()), wx.BITMAP_TYPE_ANY))
        self.bitmap_eth = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_ETH.lower()), wx.BITMAP_TYPE_ANY))
        self.bitmap_wifi = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_WIFI.lower()), wx.BITMAP_TYPE_ANY))
#         self.bitmap_hspa = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_HSPA.lower()), wx.BITMAP_TYPE_ANY))
        self.bitmap_hosts = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_HOSTS.lower()), wx.BITMAP_TYPE_ANY))
        self.bitmap_traffic = wx.StaticBitmap(self, -1, wx.Bitmap(path.join(paths.ICONS, u"%s_gray.png" % RES_TRAFFIC.lower()), wx.BITMAP_TYPE_ANY))
        self.label_cpu = wx.StaticText(self, -1, "%s\n- - - -" % RES_CPU, style=wx.ALIGN_CENTRE)
        self.label_ram = wx.StaticText(self, -1, "%s\n- - - -" % RES_RAM, style=wx.ALIGN_CENTRE)
        self.label_eth = wx.StaticText(self, -1, "%s\n- - - -" % RES_ETH, style=wx.ALIGN_CENTRE)
        self.label_wifi = wx.StaticText(self, -1, "%s\n- - - -" % RES_WIFI, style=wx.ALIGN_CENTRE)
#         self.label_hspa = wx.StaticText(self, -1, "%s\n- - - -" % RES_HSPA, style = wx.ALIGN_CENTRE)
        self.label_hosts = wx.StaticText(self, -1, "%s\n- - - -" % RES_HOSTS, style=wx.ALIGN_CENTRE)
        self.label_traffic = wx.StaticText(self, -1, "%s\n- - - -" % RES_TRAFFIC, style=wx.ALIGN_CENTRE)
        self.gauge = wx.Gauge(self, -1, TOTAL_STEPS, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        
        self.label_test_message = wx.StaticText(self, -1, "Versione sperimentale Multi sessione\nper il confronto FTP - HTTP", style=wx.ALIGN_CENTRE)
        self.label_test_message.SetForegroundColour((0, 0, 255))
#         self.label_ping = wx.StaticText(self, -1, "Ping", style = wx.ALIGN_CENTRE)
#         self.label_http_down = wx.StaticText(self, -1, "HTTP Down", style = wx.ALIGN_CENTRE)
#        self.label_http_up = wx.StaticText(self, -1, "HTTP Up", style = wx.ALIGN_CENTRE)
#         self.label_ftp_down = wx.StaticText(self, -1, "FTP Down", style = wx.ALIGN_CENTRE)
#        self.label_ftp_up = wx.StaticText(self, -1, "FTP Up", style = wx.ALIGN_CENTRE)
        
#         self.label_ping_res = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
#         self.label_http_down_res = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
#        self.label_http_up_res = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
#         self.label_ftp_down_res = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
#        self.label_ftp_up_res = wx.StaticText(self, -1, "- - - -", style = wx.ALIGN_CENTRE)
        
        self.messages_area = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_BESTWRAP | wx.BORDER_NONE)
        self.label_interface = wx.StaticText(self, -1, LABEL_MESSAGE, style=wx.ALIGN_CENTRE)
#         self.grid_sizer_system_indicators = wx.FlexGridSizer(2, 7, 0, 0)
        self.grid_sizer_system_indicators = wx.FlexGridSizer(2, 6, 0, 0)
        # 5 columns: ping, http down, http up, ftp down, ftp up
#        self.grid_sizer_results = wx.FlexGridSizer(2, 5, 0, 0)
        self.grid_sizer_results = wx.FlexGridSizer(2, 3, 0, 0)

        self.sizer_main_window = wx.BoxSizer(wx.VERTICAL)
        self.sizer_main_row = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_results = wx.BoxSizer(wx.VERTICAL)
        self.sizer_results_outer = wx.StaticBoxSizer(self.sizer_1_staticbox, wx.VERTICAL)
        self.sizer_messages_area = wx.StaticBoxSizer(self.sizer_3_staticbox, wx.VERTICAL)
        self.sizer_system_status = wx.StaticBoxSizer(self.sizer_2_staticbox, wx.VERTICAL)
        
        self.__set_properties()
        self.__do_layout()
        
        # end wxGlade
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_BUTTON, self._on_play, self.bitmap_button_play)
        self.Bind(wx.EVT_BUTTON, self._on_check, self.bitmap_button_check)
        
#         self._event_dispatcher = gui_event.WxGuiEventDispatcher(self)
        self.Bind(gui_event.EVT_UPDATE, self._on_update)
        self.Bind(gui_event.EVT_PROGRESS, self._on_progress)
        self.Bind(gui_event.EVT_RESULT, self._on_result)
        self.Bind(gui_event.EVT_ERROR, self._on_error)
        self.Bind(gui_event.EVT_RESOURCE, self._on_resource)
        self.Bind(gui_event.EVT_STOP, self._on_stop)
        self.Bind(gui_event.EVT_AFTER_CHECK, self._on_after_check)



    def __set_properties(self):
        # begin wxGlade: Frame.__set_properties
        self.SetTitle("%s - versione %s" % (SWN, self._version))
        self.SetSize((800, 460))
        
        self.messages_area_style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_BESTWRAP | wx.BORDER_NONE
        
        self.bitmap_button_play.SetMinSize((120, 120))
        self.bitmap_button_check.SetMinSize((40, 120))
        self.bitmap_logo.SetMinSize((101, 111))
        self.bitmap_cpu.SetMinSize((60, 60))
        self.bitmap_ram.SetMinSize((60, 60))
        self.bitmap_wifi.SetMinSize((60, 60))
        self.bitmap_hosts.SetMinSize((60, 60))
        self.bitmap_traffic.SetMinSize((60, 60))
        
        self._font_italic = wx.Font(10, wx.ROMAN, wx.ITALIC, wx.NORMAL, 0, "")
        self._font_italic_bold = wx.Font(10, wx.ROMAN, wx.ITALIC, wx.BOLD, 0, "")
#        self._font_normal = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")
        self._font_normal = wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")
        
        self.label_interface.SetFont(self._font_italic)
        self.label_test_message.SetFont(self._font_italic_bold)
#         self.label_ping.SetFont(self._font_italic_bold)
#         self.label_http_down.SetFont(self._font_italic_bold)
#         self.label_http_up.SetFont(self._font_italic_bold)
#         self.label_ftp_down.SetFont(self._font_italic_bold)
#         self.label_ftp_up.SetFont(self._font_italic_bold)
#         self.label_ping_res.SetFont(self._font_normal)
#         self.label_http_down_res.SetFont(self._font_normal)
#         self.label_http_up_res.SetFont(self._font_normal)
#         self.label_ftp_down_res.SetFont(self._font_normal)
#         self.label_ftp_up_res.SetFont(self._font_normal)
        
        # self.SetBackgroundColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_WINDOW))
        self.messages_area.SetBackgroundColour(wx.Colour(242, 242, 242))
        self.SetBackgroundColour(wx.Colour(242, 242, 242))
        
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: Frame.__do_layout
        
        self.grid_sizer_system_indicators.Add(self.bitmap_cpu, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        self.grid_sizer_system_indicators.Add(self.bitmap_ram, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        self.grid_sizer_system_indicators.Add(self.bitmap_eth, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        self.grid_sizer_system_indicators.Add(self.bitmap_wifi, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
#         self.grid_sizer_system_indicators.Add(self.bitmap_hspa, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        self.grid_sizer_system_indicators.Add(self.bitmap_hosts, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        self.grid_sizer_system_indicators.Add(self.bitmap_traffic, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 24)
        
        self.grid_sizer_system_indicators.Add(self.label_cpu, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.grid_sizer_system_indicators.Add(self.label_ram, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.grid_sizer_system_indicators.Add(self.label_eth, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.grid_sizer_system_indicators.Add(self.label_wifi, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
#         self.grid_sizer_system_indicators.Add(self.label_hspa, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.grid_sizer_system_indicators.Add(self.label_hosts, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.grid_sizer_system_indicators.Add(self.label_traffic, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        
#         self.grid_sizer_results.Add(self.label_ping, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_http_down, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_http_up, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_ftp_down, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_ftp_up, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)

        self.grid_sizer_results.Add(self.label_test_message, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_ping, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
#         self.grid_sizer_results.Add(self.label_http_down, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
# #         self.grid_sizer_results.Add(self.label_http_up, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)
#         self.grid_sizer_results.Add(self.label_ftp_down, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 44)
# #         self.grid_sizer_results.Add(self.label_ftp_up, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)
#         
#         self.grid_sizer_results.Add(self.label_ping_res, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
#         self.grid_sizer_results.Add(self.label_http_down_res, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
# #         self.grid_sizer_results.Add(self.label_http_up_res, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
#         self.grid_sizer_results.Add(self.label_ftp_down_res, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
#         self.grid_sizer_results.Add(self.label_ftp_up_res, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        
        self.sizer_results.Add(self.grid_sizer_results, 0, wx.ALL | wx.EXPAND, 0)
        self.sizer_results.Add(wx.StaticLine(self, -1), 0, wx.ALL | wx.EXPAND, 4)
        self.sizer_results.Add(self.label_interface, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
        # self.sizer_results_outer.Add(wx.StaticLine(self, -1, style = wx.LI_VERTICAL), 0, wx.RIGHT | wx.EXPAND, 4)
        
        self.sizer_results_outer.Add(self.sizer_results, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
        
        self.sizer_main_row.Add(self.bitmap_button_play, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.sizer_main_row.Add(self.bitmap_button_check, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
        self.sizer_main_row.Add(self.sizer_results_outer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        self.sizer_main_row.Add(self.bitmap_logo, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 2)
        
        self.sizer_messages_area.Add(self.messages_area, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
        self.sizer_system_status.Add(self.grid_sizer_system_indicators, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 8)

        self.sizer_main_window.Add(self.sizer_main_row, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
        self.sizer_main_window.Add(self.gauge, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 0)
        self.sizer_main_window.Add(self.sizer_messages_area, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)
        self.sizer_main_window.Add(self.sizer_system_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL, 4)

        self.SetSizer(self.sizer_main_window)
        self.SetSizeHints(800, 460)
        
        self._initial_message()
        # end wxGlade
        
    def _on_size(self, gui_event):
        
        (W, H) = self.GetSize()
        
        extra = 0
        if (system().lower().startswith('win')):
            extra = 20
        elif (system().lower().startswith('dar')):
            extra = 60
            
        self.sizer_main_window.SetMinSize((W, H))
        self.sizer_results_outer.SetMinSize((W - 300, 120))
        self.gauge.SetMinSize((W - 20, 20))
        self.sizer_messages_area.SetMinSize((W - 20, H - (310 + extra)))
        self.sizer_system_status.SetMinSize((W - 20, 120))
        
        self.messages_area.SetMinSize((W - 40, H - (330 + extra)))
        
        self.Refresh()
        self.Layout()
    
    def _on_close(self, gui_event):
        logger.info("Richiesta di close")
        dlg = wx.MessageDialog(self, "\nVuoi davvero chiudere %s?" % SWN, SWN, wx.OK | wx.CANCEL | wx.ICON_QUESTION)
        res = dlg.ShowModal()
        dlg.Destroy()
        if res == wx.ID_OK:
            self._killTester()        
            self.Destroy()
            
    def _on_play(self, gui_event):
        self._reset_info()
        try:
            self._listener.play()
        except AttributeError:
            logger.error("Nessun listener adatto configurato, impossibile procedere")
#         self._button_play = True
#         self._on_check(None)
        # self.bitmap_button_play.SetBitmapLabel(wx.Bitmap(path.join(paths.ICONS, u"stop.png")))

    def _killTester(self):
        if (self._tester and self._tester != None):
            self._tester.join()
            for thread in enumerate():
                if thread.isAlive():
                    try:
                        thread._Thread__stop()
                    except:
                        logger.error("%s could not be terminated" % str(thread.getName()))
        
    def _on_check(self, gui_event):
        self._reset_info()
        self._update_messages("Profilazione dello stato del sistema di misura", 'black', font=(12, 93, 92, 1))
        try:
            self._listener.check()
        except AttributeError:
            logger.error("Nessun listener adatto configurato, impossibile procedere")
#         self._button_check = True
#         self.bitmap_button_play.Disable()
#         self.bitmap_button_check.Disable()
#         self._reset_info()
#         self._update_messages("Profilazione dello stato del sistema di misura", 'black', font=(12, 93, 92, 1))
#         self._profiler = sysProfiler(self._event_dispatcher)
#         self._profiler.start()

    def _on_after_check(self, gui_event):
        "TODO: "
#         self._update_messages("Profilazione terminata\n", 'medium forest green', font=(12, 93, 92, 1), fill=True)
#         if (self._button_play):
#             self._button_play = False
#             self._button_check = False
#             self._tester = SpeedTester(self._version, self._event_dispatcher)
#             self._tester.start()
#         else:
#             # move_on_key()
#             self._button_check = False
        self._update_interface(">> PROFILAZIONE TERMINATA <<\nPremere PLAY per effettuare la misura", font=(12, 93, 92, 0))
#             self._enable_button()

    def _enable_button(self):
        self.bitmap_button_check.Enable()
        if (self._tester is None or not self._tester.is_oneshot()):
            self.bitmap_button_play.Enable()

    def _update_http_down(self, downwidth):
            pass
#         self.label_http_down_res.SetLabel("%.0f kbps" % downwidth)
#         self.Layout()

    def _update_http_up(self, upwidth):
            pass
#         self.label_http_up_res.SetLabel("%.0f kbps" % upwidth)
#         self.Layout()

    def _update_ftp_down(self, downwidth):
            pass
#         self.label_ftp_down_res.SetLabel("%.0f kbps" % downwidth)
#         self.Layout()

    def _update_ftp_up(self, upwidth):
            pass
#         self.label_ftp_up_res.SetLabel("%.0f kbps" % upwidth)
#         self.Layout()

    def _update_ping(self, rtt):
            pass
#         self.label_ping_res.SetLabel("%.1f ms" % rtt)
#         self.Layout()

    def _update_interface(self, message, font=(10, 93, 90, 0)):
        (size, italic, bold, underline) = font
        font = wx.Font(size, wx.ROMAN, italic, bold, underline, "")
        self.label_interface.SetFont(font)
        self.label_interface.SetLabel(message)
        self.Layout()
    
    def _reset_info(self):
#         checkable_set = set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_HOSTS, RES_TRAFFIC])
        checkable_set = set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HOSTS, RES_TRAFFIC])

        for resource in checkable_set:
            self._set_resource_info(resource, {'status': None, 'info': None, 'value': None})

#         self.label_http_down_res.SetLabel("- - - -")
# #         self.label_http_up_res.SetLabel("- - - -")
#         self.label_ftp_down_res.SetLabel("- - - -")
# #         self.label_ftp_up_res.SetLabel("- - - -")
#         self.label_ping_res.SetLabel("- - - -")
        self.label_interface.SetLabel("")

        self.messages_area.Clear()
        self._update_gauge(0)
        self.Layout()


    def _on_progress(self, gui_event):
        self._update_gauge()

    def _update_gauge(self, value=None):
        if (value == None):
            value = self.gauge.GetValue() + 1
        self.gauge.SetValue(value)

    def _on_resource(self, resource_event):
        self._set_resource_info(resource_event.getResource(), resource_event.getValue(), resource_event.getMessageFlag())

    def _set_resource_info(self, resource, info, message_flag=True):
        res_bitmap = None
        res_label = None
        print info
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
#         elif resource == RES_HSPA:
#             res_bitmap = self.bitmap_hspa
#             res_label = self.label_hspa
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
#                 if resource == RES_ETH or resource == RES_WIFI or resource == RES_HSPA:
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


    def _on_update(self, update_event):
        if update_event.getImportance() == gui_event.UpdateEvent.MAJOR_IMPORTANCE:
            font = (12, 93, 92, 1)
        else:
            font = None
        self._update_messages(update_event.getMessage(), font=font)

    
    def _update_messages(self, message, colour='black', font=None, fill=False):
        logger.info('Messaggio all\'utente: "%s"' % message)
        self._stream.append((str(message), colour, font, fill))
        if (not self._stream_flag.isSet()):
#            if (system().lower().startswith('win')):
#                writer = Thread(target = self._writer)
#                writer.start()
#            else:
            self._writer()


    def _on_result(self, result_event):
        result_test_type = result_event.getType()
        result_value = result_event.getValue()
        font = (12, 93, 92, 1)
        color = 'green'
        if result_test_type == test_type.PING or result_test_type == test_type.PING_WITH_SLEEP:
            message = "Tempo di risposta del server: %.1f ms" % result_value
            update_method = self._update_ping
        elif result_test_type == test_type.FTP_DOWN:
            message = "Download (FTP): %.0f kbps" % result_value
            update_method = self._update_ftp_down
        elif result_test_type == test_type.FTP_UP:
            message = "Upload (FTP): %.0f kbps" % result_value
            update_method = self._update_ftp_up
        elif result_test_type == test_type.HTTP_DOWN:
            message = "Download (HTTP): %.0f kbps" % result_value
            update_method = self._update_http_down
        elif result_test_type == test_type.HTTP_UP:
            message = "Upload (HTTP): %.0f kbps" % result_value
            update_method = self._update_http_up
        elif result_test_type == test_type.HTTP_DOWN_MULTI:
            message = "Download (HTTP MULTI): %.0f kbps" % result_value
            update_method = self._update_http_down
        elif result_test_type == test_type.HTTP_UP_MULTI:
            message = "Upload (HTTP MULTI): %.0f kbps" % result_value
            update_method = self._update_http_up
        else: 
            logger.error("Unknown result %s: %s" % (result_test_type, result_value))
        self._update_messages(message, color, font)
        update_method(result_value)


    def _on_error(self, error_event):
        logger.info("Got error gui_event")
        self._update_messages(error_event.getMessage(), 'red')


    def _on_stop(self, stop_event):
        self._killTester()
        self._update_messages("Misura terminata\n", 'medium forest green', (12, 93, 92, 1), True)
        if (stop_event.isOneShot()):
            self._update_interface(">> MISURA TERMINATA <<\nPer la versione completa iscriviti su misurainternet.it", font=(12, 93, 92, 0))
            self._update_messages("Per effettuare altre misure e conservare i tuoi risultati nell'area riservata effettua l'iscrizione su misurainternet.it\n", 'black', (12, 90, 92, 0), True)
        else:
            self._update_interface(">> MISURA TERMINATA <<\nSistema pronto per una nuova misura", font=(12, 93, 92, 0))
            self._update_messages("Sistema pronto per una nuova misura", 'black', (12, 90, 92, 0), True)
        self._enable_button()
        self._update_gauge(TOTAL_STEPS)


    def _writer(self):
        self._stream_flag.set()
        while (len(self._stream) > 0):
            
            basic_font = wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "")
            words = {}
            
            (message, colour, font, fill) = self._stream.popleft()
            date = datetime.today().strftime('%a %d/%m/%Y %H:%M:%S')
            
            last_pos = self.messages_area.GetLastPosition()
            if (last_pos != 0):
                text = "\n"
            else:
                self.messages_area.SetWindowStyleFlag(self.messages_area_style)
                self.messages_area.SetFont(basic_font)
                text = ""
            
            date = date + "    "
            text = text + date
            words[date] = (colour, wx.NullColour, basic_font)
            
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
            self.messages_area.SetInsertionPoint(last_pos + 1)
            self._set_style(text, words, last_pos)
                
            self.messages_area.ScrollLines(-1)
        self._stream_flag.clear()
        
    def _initial_message(self):

        message = \
'''Benvenuto in %s versione %s

Premendo il tasto CHECK avvierai la profilazione della macchina per la misura.

Premendo il tasto PLAY avvierai una profilazione e il test di misura completo.''' % (SWN, self._version)

        self.messages_area.SetWindowStyleFlag(self.messages_area_style + wx.TE_CENTER)

        self.messages_area.SetFont(wx.Font(10, wx.ROMAN, wx.NORMAL, wx.NORMAL, 0, ""))
        
        self.messages_area.AppendText(message)
        self.messages_area.ScrollLines(-1)
        
        font1 = wx.Font(12, wx.ROMAN, wx.ITALIC, wx.BOLD, 0, "")
        font2 = wx.Font(10, wx.ROMAN, wx.ITALIC, wx.BOLD, 1, "")
        word1 = "Benvenuto in %s versione %s" % (SWN, self._version) 
        words = {word1:(wx.NullColour, wx.NullColour, font1), 'CHECK':('blue', wx.NullColour, font2), 'PLAY':('green', wx.NullColour, font2)}
        
        self._set_style(message, words)
        
        self.Layout()
        
    def _set_style(self, message, words, offset=0):
        for word in words:
            start = message.find(word) + offset
            end = start + len(word)
            style = words[word]
            self.messages_area.SetStyle(start, end, wx.TextAttr(*style))

    def set_listener(self, listener):
        self._listener = listener

    def set_busy(self, is_busy):
        if is_busy:
            self.bitmap_button_play.Disable()
            self.bitmap_button_check.Disable()
        else:
            "TODO: handle one-shot elsewhere"
            self.bitmap_button_check.Enable()
            if (self._tester is None or not self._tester.is_oneshot()):
                self.bitmap_button_play.Enable()
