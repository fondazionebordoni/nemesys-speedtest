# proof.py
# -*- coding: utf8 -*-

# Copyright (c) 2010 Fondazione Ugo Bordoni.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

class Proof:

    def __init__(self, test = {}):
        self._test = {}
        self.clear()
        self.update(test)
        
    def update(self, test):
        self._test.update(test)
        
    def clear(self):
        self._test.clear()
    
    def dict(self):
        return self._test
    
    
    @property
    def type(self):
        return self._test.get('type','test')
    
    @property
    def done(self):
        return self._test.get('done',0)

    @property
    def time(self):
        #!# Values must be saved in milliseconds #!#
        return self._test.get('time',0)

    @property
    def bytes(self):
        return self._test.get('bytes',0)
    
    @property
    def bytesOth(self):
        return self._test.get('bytes_total',0) - self._test.get('bytes',0)

    @property
    def bytesTot(self):
        return self._test.get('bytes_total',0)

    def __str__(self):
        return '|Type:%s|Done:%s|Time:%1.3f|Bytes:%d|BytesOth:%d|' \
                        % (self.type, self.done, self.time, self.bytes, self.bytesOth)

if __name__ == '__main__':
    test = Proof()
    test.update({'type':'download','time':10,'bytes':30000, 'bytes_total':51000})
        
        
