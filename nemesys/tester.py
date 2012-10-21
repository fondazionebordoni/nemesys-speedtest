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

from datetime import datetime
from timeNtp import timestampNtp
from contabyte import Contabyte
from errorcoder import Errorcoder
from fakefile import Fakefile
from ftplib import FTP
from host import Host
from logger import logging
from optparse import OptionParser
from pcapper import Pcapper
from proof import Proof
from sysmonitor import getIp, getDev
import ftplib
import paths
import ping
import socket
import sys
import time
import errno

ftp = None
file = None
filepath = None
max_retry = 8
max_time = 12000  #240000

#Parametri Sniffer:
BUFF = 22 * 1024000     # MegaByte
SNAPLEN = 160           # Byte
TIMEOUT = 1             # MilliSeconds
PROMISC = 1             # Promisc Mode ON/OFF

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)


class Tester:

  def __init__(self, if_ip, host, username = 'anonymous', password = 'anonymous@', timeout = 60):
    self._if_ip = if_ip
    self._nic_if = getDev(if_ip)
    self._host = host
    self._username = username
    self._password = password
    self._timeout = timeout
    socket.setdefaulttimeout(self._timeout)
    
  def _ftp_down(self, ftp, file):
    size = 0
    elapsed = 0
    
    ftp.voidcmd('TYPE I')
    conn = ftp.transfercmd('RETR %s' % file, rest=None)
    
    start = time.time()
    while True:
      data = conn.recv(8192)
      stop = time.time()
      elapsed = int((stop-start)*1000)
      size += len(data)
      if (elapsed > max_time):
        break
      elif not data:
        break
    
    #logger.info("Elapsed: %s" % (stop-start))
    try:
      conn.close()
      ftp.voidresp()
      ftp.close()
    except ftplib.all_errors as e:
      if (e.args[0][:3] == '426'):
        pass
      else:
        raise e
    
    return (size, elapsed)
    
  def _ftp_up(self, ftp, file, path):
    size = 0
    elapsed = 0
    
    ftp.voidcmd('TYPE I')
    conn = ftp.transfercmd('STOR %s' % path, rest=None)
    
    start = time.time()
    while True:
      data = file.read(8192*4)
      if (data == None):
        break
      conn.sendall(data)
      stop = time.time()
      elapsed = int((stop-start)*1000)
      size += len(data)
      if (elapsed > max_time):
        break
    
    #logger.info("Elapsed: %s" % (stop-start))
    try:
      conn.close()
      ftp.voidresp()
      ftp.close()
    except ftplib.all_errors as e:
      if (e.args[0][:3] == '426'):
        pass
      else:
        raise e
    
    return (size, elapsed)
    
  def testftpdown(self, bytes, filename):
    global ftp, file, max_retry
    
    test = {}
    test['type'] = 'download'
    test['time'] = 0
    test['bytes'] = 0
    test['stats'] = {}
    test['errorcode'] = 0

    file = filename
    timeout = max(self._timeout, 1)

    try:
      # TODO Il timeout non viene onorato in Python 2.6: http://bugs.python.org/issue8493
      #ftp = FTP(self._host.ip, self._username, self._password, timeout=timeout)
      ftp = FTP(self._host.ip, self._username, self._password)
    except ftplib.all_errors as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile aprire la connessione FTP: %s' % (test['errorcode'], e)
      logger.error(error)
      raise Exception(error)
    
    try:
      logger.info('Test initializing....')
      logger.info('File dimension: %s bytes' % bytes)
      # buff = int(max(bytes/2,BUFF))
      pcapper = Pcapper(self._nic_if, BUFF, SNAPLEN, TIMEOUT, PROMISC)
      pcapper.start()

      logger.info('Testing.... ')
      pcapper.sniff(Contabyte(self._if_ip, self._host.ip))

      # Il risultato deve essere espresso in millisecondi
      (size, elapsed) = self._ftp_down(ftp, file)
      test['bytes'] = size
      test['time'] = elapsed
      logger.info("Banda: (%s*8)/%s = %s Kbps" % (size,elapsed,(size*8)/elapsed))
      
      pcapper.stop_sniff(test['type'],test['bytes'])
      test['stats'] = pcapper.get_stats()

      logger.info('Test stopping.... ')
      pcapper.stop()
      pcapper.join()

      logger.info('Test done!')

    except ftplib.all_errors as e:
      pcapper.stop()
      pcapper.join()
      if ((max_retry > 0) and (e.args[0] == errno.EWOULDBLOCK)):
        max_retry -= 1
        logger.error("[%s] FTP socket error: %s [remaining retry: %d]" % (e.args[0], e, max_retry))
        return self.testftpdown(bytes, filename)
      else:
        max_retry = 8
        test['errorcode'] = errors.geterrorcode(e)
        error = '[%s] Impossibile effettuare il test %s: %s' % (test['errorcode'], test['type'], e)
        logger.error(error)
        raise Exception(error)

    except Exception as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Errore durante la misura %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    max_retry = 8
       
    return Proof(test)

  def testftpup(self, bytes, path):
    global ftp, file, filepath  
    filepath = path
    
    test = {}
    test['type'] = 'upload'
    test['time'] = 0
    test['bytes'] = 0
    test['stats'] = {}
    test['errorcode'] = 0

    file = Fakefile(bytes)
    timeout = max(self._timeout, 1)

    try:
      # TODO Il timeout non viene onorato in Python 2.6: http://bugs.python.org/issue8493
      #ftp = FTP(self._host.ip, self._username, self._password, timeout=timeout)
      ftp = FTP(self._host.ip, self._username, self._password)
    except ftplib.all_errors as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile aprire la connessione FTP: %s' % (test['errorcode'], e)
      logger.error(error)
      raise Exception(error)

    try:
      logger.info('Test initializing....')
      logger.info('File dimension: %s bytes' % bytes)
      # buff = int(max(bytes/2,BUFF))
      pcapper = Pcapper(self._nic_if, BUFF, SNAPLEN, TIMEOUT, PROMISC)
      pcapper.start()

      logger.info('Testing.... ')
      pcapper.sniff(Contabyte(self._if_ip, self._host.ip))

      # Il risultato deve essere espresso in millisecondi
      (size, elapsed) = self._ftp_up(ftp, file, filepath)
      test['bytes'] = size
      test['time'] = elapsed
      logger.info("Banda: (%s*8)/%s = %s Kbps" % (size,elapsed,(size*8)/elapsed))
      
      pcapper.stop_sniff(test['type'],test['bytes'])
      test['stats'] = pcapper.get_stats()

      logger.info('Test stopping.... ')
      pcapper.stop()
      pcapper.join()

      logger.info('Test done!')

    except ftplib.all_errors as e:
      pcapper.stop()
      pcapper.join()
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Impossibile effettuare il test %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    except Exception as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Errore durante la misura %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    return Proof(test)


  def testping(self):
    
    # si utilizza funzione ping.py
    test = {}
    test['type'] = 'ping'
    test['time'] = 0
    test['errorcode'] = 0
    
    try:
      # Il risultato deve essere espresso in millisecondi
      RTT = ping.do_one(self._host.ip, self._timeout) * 1000
      if (RTT != None):
        test['time'] = RTT

    except Exception as e:
      test['errorcode'] = errors.geterrorcode(e)
      error = '[%s] Errore durante la misura %s: %s' % (test['errorcode'], test['type'], e)
      logger.error(error)
      raise Exception(error)

    return Proof(test)


def main():
  #Aggancio opzioni da linea di comando

  parser = OptionParser(version = "0.10.1.$Rev$",
                        description = "A simple bandwidth tester able to perform FTP upload/download and PING tests.")
  parser.add_option("-t", "--type", choices = ('ftpdown', 'ftpup', 'ping'),
                    dest = "testtype", default = "ftpdown", type = "choice",
                    help = "Choose the type of test to perform: ftpdown (default), ftpup, ping")
  parser.add_option("-f", "--file", dest = "filename",
                    help = "For FTP download, the name of the file for RETR operation")
  parser.add_option("-b", "--byte", dest = "bytes", type = "int",
                    help = "For FTP upload, the size of the file for STOR operation")
  parser.add_option("-H", "--host", dest = "host",
                    help = "An ipaddress or FQDN of testing host")
  parser.add_option("-u", "--username", dest = "username", default = "anonymous",
                    help = "An optional username to use when connecting to the FTP server")
  parser.add_option("-p", "--password", dest = "password", default = "anonymous@",
                    help = "The password to use when connecting to the FTP server")
  parser.add_option("-P", "--path", dest = "path", default = "",
                    help = "The path where put uploaded file")
  parser.add_option("--timeout", dest = "timeout", default = "30", type = "int",
                    help = "Timeout in seconds for FTP blocking operations like the connection attempt")

  (options, args) = parser.parse_args()
  #TODO inserire controllo host

  t = Tester(getIp(), Host(options.host), options.username, options.password)
  test = None
  print ('Prova: %s' % options.host)

  tests = {
    'ftpdown': t.testftpdown(options.filename),
    'ftpup': t.testftpup(options.bytes, options.path),
    'ping': t.testping(),
  }
  test = tests.get(options.testtype)

  print test
  return None


if __name__ == '__main__':
  if len(sys.argv) < 2:
    s = socket.socket(socket.AF_INET)
    s.connect(('www.fub.it', 80))
    ip = s.getsockname()[0]
    s.close()
    nap = '193.104.137.133'

    TOT = 5

    t1 = Tester(ip, Host(ip = nap), 'nemesys', '4gc0m244')

    for i in range(1, TOT + 1):
      logger.info('Test Download %d/%d' % (i, TOT))
      test = t1.testftpdown('/download/20000.rnd')
      logger.info(test)
      logger.info("Risultato di banda in download: %d" % (test.bytes * 8 / test.time))

    for i in range(1, TOT + 1):
      logger.info('Test Upload %d/%d' % (i, TOT))
      test = t1.testftpup(2048, '/upload/r.raw')
      logger.info(test)
      logger.info("Risultato di banda in upload: %d" % (test.bytes * 8 / test.time))

    for i in range(1, TOT + 1):
      logger.info('\nTest Ping %d/%d' % (i, TOT))
      test = t1.testping()
      logger.info(test)
      logger.info("Risultato ping: %d" % test.time)

  else:
    main()

