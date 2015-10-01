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

from errorcoder import Errorcoder
from host import Host
from logger import logging
from optparse import OptionParser
import paths
import ping
import socket
import sys
from testerhttp import HttpTester
from testerftp import FtpTester

HTTP_BUFF = 8*1024

logger = logging.getLogger()
errors = Errorcoder(paths.CONF_ERRORS)


class Tester:

  def __init__(self, dev, ip, host, username = 'anonymous', password = 'anonymous@', timeout = 11):
    
    self._nic_if = dev
    self._if_ip = ip
    self._host = host
    
    self._ftp = None
    self._file = None
    self._filepath = None
    self._maxRetry = 8
    
    self._username = username
    self._password = password
    self._timeout = timeout
    
    self._testerhttp = HttpTester(dev, timeout, HTTP_BUFF)
    self._testerftp = FtpTester(dev, timeout, HTTP_BUFF)
    
    

  def testhttpdown(self, callback_update_speed):
      url = "http://%s/file.rnd" % self._host.ip
      return self._testerhttp.test_down_multisession(url, 10, callback_update_speed)    
 
  def testhttpdownlong(self, callback_update_speed):
      url = "http://%s/file.rnd" % self._host.ip
      return self._testerhttp.test_down(url, 30, callback_update_speed)    
 
  def testhttpup(self):
      url = "http://%s/file.rnd" % self._host.ip
      return self._testerhttp.test_up(url)    
     
  def testftpdown(self, bytes, filename):
    return self._testerftp.testftpdown(self._host.ip, filename, bytes, self._username, self._password)

  def testftpup(self, bytes, filename):
    return self._testerftp.testftpup(self._host.ip, filename, bytes, self._username, self._password)

  def testping(self):
    
    # si utilizza funzione ping.py
    test = {}
    test['type'] = 'ping'
    test['time'] = 0
    test['errorcode'] = 0
    
    self._timeout = float(22)
    
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

    return test
  
  


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

    t1 = Tester("eth0", ip, Host(ip = nap), 'nemesys', '4gc0m244')

    for i in range(1, TOT + 1):
      logger.info('Test Download %d/%d' % (i, TOT))
      test = t1.testftpdown(10000000, '/download/40000.rnd')
      logger.info(test)
      logger.info("Risultato di banda in download: %d" % (test['bytes_total'] * 8 / test['time']))

    for i in range(1, TOT + 1):
      logger.info('Test Upload %d/%d' % (i, TOT))
      test = t1.testftpup(10000000, '/upload/r.raw')
      logger.info(test)
      logger.info("Risultato di banda in upload: %d" % (test['bytes_total'] * 8 / test['time']))

    for i in range(1, TOT + 1):
      logger.info('\nTest Ping %d/%d' % (i, TOT))
      test = t1.testping()
      logger.info(test)
      logger.info("Risultato ping: %d" % test['time'])

  else:
    main()

