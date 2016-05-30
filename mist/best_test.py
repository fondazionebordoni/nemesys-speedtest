'''
Created on 27/mag/2016

@author: ewedlund
'''

class BestTest(object):
    '''
    Structure to save Proof together with other information
    used for sending to backend
    '''


    def __init__(self, proof, profiler_info, n_tests_done):
        '''
        Constructor
        
        Keyword arguments:
        
        proof -- the proof containing test result
        profiler_info -- output from profiler (a dict)
        n_tests_done -- number of tests made from where this test was chosen
        '''
        self._proof = proof
        self._profiler_info = profiler_info
        self._n_tests_done = n_tests_done
        
    @property
    def proof(self):
        return self._proof
    
    @property
    def profiler_info(self):
        return self._profiler_info
    
    @property
    def n_tests_done(self):
        return self._n_tests_done
        