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
    if argv is None:
        argv = sys.argv[1:]
    '''Command line options.'''
    program_name = os.path.basename(sys.argv[0])
    program_version = __version__
    program_build_date = "%s" % __updated__
    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = ''''''

    # TODO: Needs fixing, mixup with optionParser.OptionParser
    parser = OptionParser(version=program_version_string, epilog=program_longdesc)  # , description=program_license)
    parser.add_option("-t", "--text", dest="text_based", action="store_true",
                      help="Senza interfaccia grafica [default: %default]")
    parser.set_defaults(text_based=False)
    (args_opts, _) = parser.parse_args(argv)

    ''' Check for sudo on linux and Administrator on Windows'''
    current_os = platform.system().lower()
    if current_os.startswith('lin') or current_os.startswith('darwin'):
        if (os.getenv('SUDO_USER') is None) and (os.getenv('USER') != 'root'):
            is_admin = False
        else:
            is_admin = True
    else:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    # TODO: Avoid need for admin for creation of log files etc.
    # So we can move this check to later
    if not is_admin:
        sys.stderr.write('Speedtest avviato senza permessi di amministratore - chiusura tester\n')
        if not args_opts.text_based:
            # Display window with message
            app = wx.App(False)
            msgBox = wx.MessageDialog(None,
                                      "\nSpeedtest e' stato avviato senza i permessi di amministratore.\n\n"
                                      "Su sistemi Linux e MacOS va avviato da linea di comando con 'sudo'",
                                      "Attenzione: Speedtest non puo' essere avviato",
                                      style=wx.OK)
            msgBox.ShowModal()
            msgBox.Destroy()
        sys.exit()

    try:
        paths.check_paths()
        import log_conf
        log_conf.init_log()
    except IOError:
        print ("Impossibile inizializzare il logging, assicurarsi che il programma stia girando con "
               "i permessi di amministratore.")
        sys.exit()

    try:
        sysmonitor.SysMonitor().log_interfaces()
    except Exception as e:
        logger.error("Impossibile trovare interfaccia attiva: %s" % e)
        if args_opts.text_based:
            print "Impossibile trovare un interfaccia di rete attiva, verificare la connessione alla rete."
        else:
            app = wx.App(False)
            msgBox = wx.MessageDialog(None,
                                      "\nImpossibile trovare un interfaccia di rete attiva, "
                                      "verificare la connessione alla rete.",
                                      style=wx.OK)
            msgBox.ShowModal()
            msgBox.Destroy()
        sys.exit()

    try:
        SWN = 'MisuraInternet Speed Test'
        logger.info('Starting %s v.%s' % (SWN, FULL_VERSION))
        #         mist(args_opts.text_based, file_opts, md5conf)
        version = __version__
        if not args_opts.text_based:
            app = wx.App(False)

            # Check if this is the last version
            version_ok = CheckSoftware(version).checkIT()

            if not version_ok:
                return
        (file_opts, _, md5conf) = parser.parse()
        mist_opts = mist_options.MistOptions(file_opts, md5conf)
        if args_opts.text_based:
            event_dispatcher = gui_event.CliEventDispatcher()
            GUI = mist_cli.MistCli(event_dispatcher)
            controller = MistController(GUI, version, event_dispatcher, mist_opts)
            GUI.set_listener(controller)
            GUI.start()
        else:
            if platform.system().lower().startswith('win'):
                wx.CallLater(200, sleeper)
            GUI = mist_gui.mistGUI(None, -1, "",
                                   style=wx.DEFAULT_FRAME_STYLE)
            event_dispatcher = gui_event.WxGuiEventDispatcher(GUI)
            controller = MistController(GUI, version, event_dispatcher, mist_opts)
            GUI.init_frame(version, event_dispatcher)
            GUI.set_listener(controller)
            app.SetTopWindow(GUI)
            GUI.Show()
            app.MainLoop()
    except Exception, e:
        logging.critical("Impossibile avviare il programma", exc_info=True)
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        return 2


def sleeper():
    sleep(.001)
    return 1  # don't forget this otherwise the timeout will be removed


if __name__ == "__main__":
    main()
