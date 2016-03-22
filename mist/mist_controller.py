'''
Created on 13/ott/2015

@author: ewedlund
'''
import gui_event
from speedTester import SpeedTester

class MistController():
    
    def __init__(self, gui, version, profiler, event_dispatcher, task_file = None, no_profile = False, auto = False):
        self._gui = gui
        self._version = version
        self._profiler = profiler
        self._event_dispatcher = event_dispatcher
        self._task_file = task_file
        self._do_profile = (no_profile == False)
        self._auto = auto

 
    def play(self):
        '''Function called from GUI'''
        self._gui.set_busy(True)
        if False: #self._do_profile:
            self._profiler.profile_once_and_call_back(callback = self.measure, report_progress = True)
        else:
            self.measure(None)
        #self.measure()

    def check(self):
        '''Function called from GUI'''
        self._gui.set_busy(True)
        self._profiler.profile_once_and_call_back(callback = self.profile_done_callback, report_progress = True)

    def profile_done_callback(self, profiler_result = None):
        '''Callback when check is done'''
        self._event_dispatcher.postEvent(gui_event.UpdateEvent("Profilazione terminata", gui_event.UpdateEvent.MAJOR_IMPORTANCE))
        self._event_dispatcher.postEvent(gui_event.AfterCheckEvent())
        self._gui.set_busy(False)


    def measure(self, profiler_result = None):
        '''Callback to continue with measurement after profiling'''
        "TODO: Start background profiler here?"
#         self._event_dispatcher.postEvent(gui_event.AfterCheckEvent())
#        speed_tester = SpeedTester(self._version, self._event_dispatcher, do_profile = self._do_profile, task_file=self._task_file)
        speed_tester = SpeedTester(self._version, self._event_dispatcher, do_profile = True)
        speed_tester.start()
