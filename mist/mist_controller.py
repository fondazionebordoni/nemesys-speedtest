'''
Created on 13/ott/2015

@author: ewedlund
'''
import gui_event
from speedTester import SpeedTester

class MistController():
    
    def __init__(self, gui, version, profiler, event_dispatcher):
        self._gui = gui
        self._version = version
        self._profiler = profiler
        self._event_dispatcher = event_dispatcher

 
    def play(self):
        '''Function called from GUI'''
        self._gui.set_busy(True)
        self._profiler.profile_once_and_call_back(self.measure)
        #self.measure()

    def check(self):
        '''Function called from GUI'''
        self._gui.set_busy(True)
        self._profiler.profile_once_and_call_back(self.profile_done_callback)

    def profile_done_callback(self, profiler_result = None):
        '''Callback when check is done'''
        self._event_dispatcher.postEvent(gui_event.UpdateEvent("Profilazione terminata", gui_event.UpdateEvent.MAJOR_IMPORTANCE))
        self._event_dispatcher.postEvent(gui_event.AfterCheckEvent())
        self._gui.set_busy(False)


    def measure(self, profiler_result = None):
        '''Callback to continue with measurement after profiling'''
        "TODO: Start background profiler here?"
        speed_tester = SpeedTester(self._version, self._event_dispatcher, do_profile=False)
        speed_tester.start()