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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
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
    if self.type == 'download':
      return self._test.get('stats',{}).byte_down_all
    elif self.type == 'upload':
      return self._test.get('stats',{}).byte_up_all
    else:
      return 0

  @property
  def counter_stats(self):
    return self._test.get('stats',{})

  @property
  def errorcode(self, errorcode=None):
    if (errorcode != None):
      if errorcode > 99999 or errorcode < 0:
        errorcode = (errorcode - 90000) % 99999
        # Faccio rimanere nelle ultime 4 cifre l'errore del test #
      self._test['errorcode'] = errorcode
    else:
      return self._test.get('errorcode',0)


  def __str__(self):
    return '|Type:%s|Done:%s|Time:%1.3f|Bytes:%d|BytesOth:%d|Stats:%s|Errorcode:%d|' \
            % (self.type, self.done, self.time, self.bytes, self.bytesOth, self.counter_stats, self.errorcode)

if __name__ == '__main__':
    test = Proof({'type':'download','time':8642,'bytes':50000,'stats':{},'errorcode':0})
    print str(test)
    
    
