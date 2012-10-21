#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ConfigParser import ConfigParser, NoOptionError
from optparse import OptionParser
from logger import logging
from os import path
import hashlib
import paths

logger = logging.getLogger()

class OptionParser(OptionParser):

  def check_required(self, opt):
    response = True
    option = self.get_option(opt).dest
    #logger.debug(getattr(self.values, option))
    if getattr(self.values, option) is None:
      response = False
      self.error('%s option not supplied' % option)
    return response
    
def parse(version):
  '''
  Parsing dei parametri da linea di comando
  '''

  config = ConfigParser()

  if (path.exists(paths.CONF_MAIN)):
    config.read(paths.CONF_MAIN)
    logger.info('Caricata configurazione da %s' % paths.CONF_MAIN)

  parser = OptionParser(version = version, description = '')

  # Task options
  # --------------------------------------------------------------------------
  section = 'task'
  if (not config.has_section(section)):
    config.add_section(section)

  option = 'tasktimeout'
  value = '3600'
  try:
    value = config.getint(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--task-timeout', dest = option, type = 'int', default = value,
                    help = 'global timeout (in seconds) for each task [%s]' % value)

  option = 'testtimeout'
  value = '60'
  try:
    value = config.getint(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--test-timeout', dest = option, type = 'float', default = value,
                    help = 'timeout (in seconds as float number) for each test in a task [%s]' % value)
  
  option = 'httptimeout'
  value = '60'
  try:
    value = config.getint(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--http-timeout', dest = option, type = 'int', default = value,
                    help = 'timeout (in seconds) for http operations [%s]' % value)
  
  option = 'scheduler'
  value = 'https://speedtest.agcom244.fub.it/Scheduler'
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('-s', '--scheduler', dest = option, default = value,
                    help = 'complete url for schedule download [%s]' % value)
  
  option = 'repository'
  value = 'https://speedtest.agcom244.fub.it/Upload'
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('-r', '--repository', dest = option, default = value,
                    help = 'upload URL for deliver measures\' files [%s]' % value)
  
  option = 'progressurl'
  value = 'https://speedtest.agcom244.fub.it/ProgressXML'
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--progress-url', dest = option, default = value,
                    help = 'complete URL for progress request [%s]' % value)
  
  # Client options
  # --------------------------------------------------------------------------
  section = 'client'
  if (not config.has_section(section)):
    config.add_section(section)

  option = 'clientid'
  value = ''
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    pass
  parser.add_option('-c', '--clientid', dest = option, default = value,
                    help = 'client identification string [%s]' % value)

  option = 'username'
  value = 'anonymous'
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--username', dest = option, default = value,
                    help = 'username for FTP login [%s]' % value)

  option = 'password'
  value = '@anonymous'
  try:
    value = config.get(section, option)
  except (ValueError, NoOptionError):
    config.set(section, option, value)
  parser.add_option('--password', dest = option, default = value,
                    help = 'password for FTP login [%s]' % value)

  # Profile options
  # --------------------------------------------------------------------------
  section = 'profile'
  if (not config.has_section(section)):
    config.add_section(section)

  option = 'bandwidthup'
  value = 2048
  try:
    value = config.getint(section, option)
  except (ValueError, NoOptionError):
    pass
  parser.add_option('--up', dest = option, default = value, type = 'int',
                    help = 'upload bandwidth [%s]' % value)

  option = 'bandwidthdown'
  value = 2048
  try:
    value = config.getint(section, option)
  except (ValueError, NoOptionError):
    pass
  parser.add_option('--down', dest = option, default = value, type = 'int',
                    help = 'download bandwidth [%s]' % value)

  with open(paths.CONF_MAIN, 'w') as file:
    config.write(file)

  (options, args) = parser.parse_args()
  #logger.debug(options)

  # Verifica che le opzioni obbligatorie siano presenti
  # --------------------------------------------------------------------------

  try:

    if not parser.check_required('--clientid'):
      config.set('client', 'clientid', options.clientid)

    if not parser.check_required('--up'):
      config.set('profile', 'bandwidthup', options.bandwidthup)

    if not parser.check_required('--down'):
      config.set('profile', 'bandwidthdown', options.bandwidthdown)

  finally:
    with open(paths.CONF_MAIN, 'w') as file:
      config.write(file)

  with open(paths.CONF_MAIN, 'r') as file:
    md5 = hashlib.md5(file.read()).hexdigest()

  return (options, args, md5)