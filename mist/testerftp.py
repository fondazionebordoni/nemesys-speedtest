# tester.py
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

import errno
from ftplib import FTP
import ftplib
from optparse import OptionParser
import socket
import sys
import time

from errorcoder import Errorcoder
from fakefile import Fakefile
from logger import logging
import netstat
import paths


logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)

class FtpTester:

  def __init__(self, dev, timeout_secs = 11, bufsize = 8 * 1024):
    
    self._nic_if = dev
    
    self._ftp = None
    self._file = None
    self._filepath = None
    self._maxRetry = 8
    self._bufsize = bufsize
    self._netstat = netstat.get_netstat(dev)
    self._timeout_secs = timeout_secs
    #Ignore any given timeout
    self._timeout_millis = float(timeout_secs * 1000)
    
  def _ftp_down(self):
    size = 0
    elapsed = 0
        
    self._ftp.voidcmd('TYPE I')
    conn = self._ftp.transfercmd('RETR %s' % self._file, rest=None)
    
    start = time.time()
    while True:
      data = conn.recv(self._bufsize)
      size += len(data)
      stop = time.time()
      elapsed = float((stop-start)*1000)
      if (elapsed > self._timeout_millis):
        break
      elif not data:
        break
    
    #logger.info("Elapsed: %s" % (stop-start))
    try:
      conn.close()
      self._ftp.voidresp()
      self._ftp.close()
    except ftplib.all_errors as e:
      if (e.args[0][:3] == '426'):
        pass
      else:
        raise e
    
    stop = time.time()
    elapsed = float((stop-start)*1000)
    return (size, elapsed)
    
  def _ftp_up(self):
    size = 0
    elapsed = 0
    
    self._ftp.voidcmd('TYPE I')
    conn = self._ftp.transfercmd('STOR %s' % self._filepath, rest=None)
    
    start = time.time()
    while True:
      data = self._file.read(self._bufsize)
      if (data == None):
        break
      conn.sendall(data)
      size += len(data)
      stop = time.time()
      elapsed = float((stop-start)*1000)
      if (elapsed > self._timeout_millis):
        break

    try:
      conn.close()
      self._ftp.voidresp()
      self._ftp.close()
    except ftplib.all_errors as e:
      if (e.args[0][:3] == '426'):
        pass
      else:
        raise e
    
    stop = time.time()
    elapsed = float((stop-start)*1000)
    return (size, elapsed)

  def testftpdown(self, server, filename, bytes, username='anonymous', password='anonymous@'):
    
    test = {}
    test['type'] = 'download'
    test['time'] = 0
    test['bytes'] = 0
    test['errorcode'] = 0

    self._file = filename

    try:
      self._ftp = FTP(server, username, password, timeout=self._timeout_secs)
    except ftplib.all_errors as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile aprire la connessione FTP: %s' % (test['errorcode'], e)
      logger.error(error)
      raise Exception(error)
    
    try:
      logger.info('Test initializing....')
      logger.info('File dimension: %s bytes' % bytes)
      start_total_bytes = self._netstat.get_rx_bytes()

      logger.info('Testing.... ')

      # Il risultato deve essere espresso in millisecondi
      (size, elapsed) = self._ftp_down()
      test['bytes'] = size
      test['time'] = elapsed
      
      logger.info('Test stopping.... ')

      end_total_bytes = self._netstat.get_rx_bytes()
      bytes_total = end_total_bytes - start_total_bytes
      if (bytes_total < 0):
          raise Exception("Ottenuto banda negativa, possibile azzeramento dei contatori.")
      test['bytes_total'] = bytes_total
      logger.info("Banda: (%s*8)/%s = %s Kbps" % (size,elapsed,(size*8)/elapsed))

      logger.info('Test done!')

    except ftplib.all_errors as e:
      if ((self._maxRetry > 0) and (e.args[0] == errno.EWOULDBLOCK)):
        self._maxRetry -= 1
        logger.error("[%s] FTP socket error: %s [remaining retry: %d]" % (e.args[0], e, self._maxRetry))
        return self.testftpdown(bytes, filename)
      else:
        self._maxRetry = 8
        test['errorcode'] = errors.geterrorcode(e)
        error = '[%s] Impossibile effettuare il test %s: %s' % (test['errorcode'], test['type'], e)
        logger.error(error)
        raise Exception(error)

    except Exception as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Errore durante la misura %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    self._maxRetry = 8
       
    return test

  def testftpup(self, server, filename, bytes, username='anonymous', password='anonymous@'):
    
    test = {}
    test['type'] = 'upload'
    test['time'] = 0
    test['bytes'] = 0
    test['errorcode'] = 0

    self._file = Fakefile(bytes)
    self._filepath = filename

    try:
      # TODO Il timeout non viene onorato in Python 2.6: http://bugs.python.org/issue8493
      self._ftp = FTP(server, username, password, self._timeout_secs)
    except ftplib.all_errors as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile aprire la connessione FTP: %s' % (test['errorcode'], e)
      logger.error(error)
      raise Exception(error)

    try:
      logger.info('Test initializing....')
      logger.info('File dimension: %s bytes' % bytes)

      # Il risultato deve essere espresso in millisecondi
      start_total_bytes = self._netstat.get_tx_bytes()

      logger.info('Testing.... ')

      (size, elapsed) = self._ftp_up()
      logger.info("Banda: (%s*8)/%s = %s Kbps" % (size,elapsed,(size*8)/elapsed))
      
      logger.info('Test stopping.... ')
      end_total_bytes = self._netstat.get_tx_bytes()
      total_bytes = end_total_bytes - start_total_bytes
      if (total_bytes < 0):
          raise Exception("Ottenuto banda negativa, possibile azzeramento dei contatori.")
      test['bytes'] = size
      test['time'] = elapsed
      test['bytes_total'] = total_bytes

      logger.info('Test done!')

    except ftplib.all_errors as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile effettuare il test %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    except Exception as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Errore durante la misura %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    return test



if __name__ == '__main__':
   if len(sys.argv) < 2:
    import platform
    platform_name = platform.system().lower()
    dev = None
    nap = "eagle2.fub.it"
#     nap = '193.104.137.133'
    import sysMonitor
    dev = sysMonitor.getDev()
    t = FtpTester(dev)
        
    print t.testftpdown(nap, '/download/40000.rnd', 1000000, 'nemesys', '4gc0m244')
    print "\n---------------------------\n"
    print t.testftpup(nap, '/upload/r.raw', 100000000, 'nemesys', '4gc0m244')
    