#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ctypes
import logging
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
import mist_options
from optionParser import OptionParser
import paths
import sysmonitor


logger = logging.getLogger(__name__)


def main(argv=None):
    ''' Check for sudo on linux and Administrator on Windows'''
    current_os = platform.system().lower()
    if current_os.startswith('lin') or current_os.startswith('darwin'):
        if (os.getenv('SUDO_USER') == None) and (os.getenv('USER') != 'root'):
            is_admin = False
        else:
            is_admin = True
    else:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    if not is_admin:
        sys.stderr.write('Speedtest avviato senza permessi di amministratore - chiusura tester\n')
        sys.exit()
    try:
        paths.check_paths()
        import log_conf
        log_conf.init_log()
    except IOError as e:
        print "Impossibile inizializzare il logging, assicurarsi che il programma stia girando con i permessi di amministratore."
        sys.exit()

    try:
        sysmonitor.SysMonitor().log_interfaces()
    except Exception as e:
        print "Impossibile trovare un interfaccia di rete attiva, verificare la connessione alla rete."
        print "Speedtest non si avvia in assenza di connessione alla rete."
        logger.error("Impossibile trovare interfaccia attiva: %s" % e)
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
        (args_opts, _) = parser.parse_args(argv)
        (file_opts, _, md5conf) = parser.parse()
        SWN = 'MisuraInternet Speed Test'
        logger.info('Starting %s v.%s' % (SWN, FULL_VERSION)) 
        mist(args_opts.text_based, file_opts, md5conf)


    except Exception, e:
        logging.critical("Impossibile avviare il programma", exc_info=True)
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        return 2


def mist(text_based, file_opts, md5conf):
    version = __version__
    if not text_based:
        app = wx.App(False)
    
        # Check if this is the last version
        version_ok = CheckSoftware(version).checkIT()
        
        if not version_ok:
            return
    mist_opts = mist_options.MistOptions(file_opts, md5conf)
    if text_based:
        event_dispatcher = gui_event.CliEventDispatcher()
        GUI = mist_cli.MistCli(event_dispatcher)
        controller = MistController(GUI, version, event_dispatcher, mist_opts)
        GUI.set_listener(controller)
        GUI.start()
    else:
        if (platform.system().lower().startswith('win')):
            wx.CallLater(200, sleeper)
        GUI = mist_gui.mistGUI(None, -1, "", style = wx.DEFAULT_FRAME_STYLE)# ^ wx.RESIZE_BORDER) #& ~(wx.RESIZE_BORDER | wx.RESIZE_BOX))
        event_dispatcher = gui_event.WxGuiEventDispatcher(GUI)
        controller = MistController(GUI, version, event_dispatcher, mist_opts)
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