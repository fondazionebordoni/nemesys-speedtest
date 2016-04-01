#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from logger import logging
except IOError as e:
    print "Impossibile inizializzare il logging, assicurarsi che il programma stia girando con i permessi di amministratore."
    import sys
    sys.exit()
# from sysMonitor import interfaces, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_TRAFFIC, RES_HOSTS
#from sysMonitor import interfaces#, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_TRAFFIC, RES_HOSTS
import os
import platform
import sys
from time import sleep
import wx

from _generated_version import __version__, FULL_VERSION, __updated__
from checkSoftware import CheckSoftware
import gui_event
import mist_cli
from mist_controller import MistController
import mist_gui
from optionParser import OptionParser
import sysMonitor
from sysProfiler import sysProfiler


# from optparse import OptionParser
logger = logging.getLogger()


def main(argv=None):
    ''' Check for sudo on linux'''
    current_os = platform.system().lower()
    if current_os.startswith('lin') or current_os.startswith('darwin'):
        if (os.getenv('SUDO_USER') == None) and (os.getenv('USER') != 'root'):
            logger.error('Speedtest avviato senza privilegi di root - chiusura tester')
            sys.stderr.write('Speedtest avviato senza privilegi di root - chiusura tester\n')
            sys.stderr.write('Avviare con \'sudo\'\n')
            sys.exit()
    '''Command line options.'''
    program_name = os.path.basename(sys.argv[0])
    program_version = __version__
    program_build_date = "%s" % __updated__

    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = '''''' 

    if argv is None:
        argv = sys.argv[1:]
    try:
        'TODO: Needs fixing, mixup with optionParser.OptionParser'
        parser = OptionParser(version=program_version_string, epilog=program_longdesc)#, description=program_license)
#         parser.add_option("--task-file", dest="task_file", help="read task from file [default: %default]", metavar="FILE")
#         parser.add_option("-c", "--check", dest="check", action="store_true", help="Fare solo la verifica del sistema, senza misura [default: %default]")
        parser.add_option("-t", "--text", dest="text_based", action="store_true", help="Senza interfaccia grafica [default: %default]")
#         parser.add_option("--no-profile", dest="no_profile", action="store_true", help="Non profilare il sistema durante la misura [default: %default]")
#         parser.add_option("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %default]")

        # set defaults
#         parser.set_defaults(check = False, measure = False, text_based = False, task_file = None)
        parser.set_defaults(text_based = False)

        # process options
        (opts, _) = parser.parse_args(argv)

        SWN = 'MisuraInternet Speed Test'
        logger.info('Starting %s v.%s' % (SWN, FULL_VERSION)) 
        mist(text_based = opts.text_based, task_file = None, no_profile = False)#opts.no_profile)
        # MAIN BODY #
#        mist_cli = MistCli()
        # Register for events
        # Do profile
        # Do tests
        # (Send results?)
        # Ask if user wants to repeat


    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help\n")
        return 2


def mist(text_based, task_file, no_profile):
    version = __version__
    if not text_based:
        app = wx.App(False)
    
        # Check if this is the last version
        version_ok = CheckSoftware(version).checkIT()
        
        if not version_ok:
            return
    # Logs all network interfaces
    sysMonitor.interfaces()
    if text_based:
        event_dispatcher = gui_event.CliEventDispatcher()
        GUI = mist_cli.MistCli(event_dispatcher)
        profiler = sysProfiler(event_dispatcher)
        controller = MistController(GUI, version, profiler, event_dispatcher, task_file, no_profile)
        GUI.set_listener(controller)
        GUI.start()
    else:
        if (platform.system().lower().startswith('win')):
            wx.CallLater(200, sleeper)
        GUI = mist_gui.mistGUI(None, -1, "", style = wx.DEFAULT_FRAME_STYLE)# ^ wx.RESIZE_BORDER) #& ~(wx.RESIZE_BORDER | wx.RESIZE_BOX))
        event_dispatcher = gui_event.WxGuiEventDispatcher(GUI)
        profiler = sysProfiler(event_dispatcher)
        controller = MistController(GUI, version, profiler, event_dispatcher, task_file, no_profile)
        GUI.init_frame(version, event_dispatcher)
        GUI.set_listener(controller)
        app.SetTopWindow(GUI)
        GUI.Show()
        app.MainLoop()
 
def sleeper():
    sleep(.001)
    return 1 # don't forget this otherwise the timeout will be removed
  
  
if __name__ == "__main__":
    main()