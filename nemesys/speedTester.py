#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sysmonitor import RES_OS, RES_IP, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_TRAFFIC, RES_HOSTS
from xmlutils import getvalues, getxml, xml2task
from os import path, walk, listdir, remove, removedirs
from sysProfiler import sysProfiler
from threading import Thread, Event
from timeNtp import timestampNtp
from nemesysParser import parse
from deliverer import Deliverer
from datetime import datetime
from urlparse import urlparse
from measure import Measure
from profile import Profile
from logger import logging
from client import Client
from server import Server
from tester import Tester
from time import sleep
from isp import Isp

import httputils
import shutil
import paths
import ping
import wx
import re

## OPTIONAL ##
from task import Task   #for Fake Task#


__version__ = '1.0.4'

logger = logging.getLogger()

TASK_FILE = '40000'

# Tempo di attesa tra una misura e la successiva in caso di misura fallita
TIME_LAG = 5
PING = 'ping'
DOWN = 'down'
UP = 'up'
# Soglia per il rapporto tra traffico 'spurio' e traffico totale
TH_TRAFFIC = 0.1
TH_TRAFFIC_INV = 0.9
# Soglia per numero di pacchetti persi
TH_PACKETDROP = 0.05
MAX_TEST_ERROR = 5

UPLOAD_RETRY = 3



def getclient(options):

  profile = Profile(id = None, upload = options.bandwidthup,
                    download = options.bandwidthdown)
  isp = Isp('fub001')
  return Client(id = options.clientid, profile = profile, isp = isp,
                geocode = None, username = 'speedtest',
                password = options.password)


class speedTester(Thread):

  def __init__(self, gui):
    Thread.__init__(self)
    paths_check = paths.check_paths()
    for check in paths_check:
      logger.info(check)
      
    self._sent = paths.SENT_DAY_DIR
    self._outbox = paths.OUTBOX_DAY_DIR

    self._gui = gui
    self._profiler = sysProfiler(self._gui, 'tester')

    (options, args, md5conf) = parse(__version__)

    self._client = getclient(options)
    self._scheduler = options.scheduler
    self._repository = options.repository
    self._tasktimeout = options.tasktimeout
    self._testtimeout = options.testtimeout
    self._httptimeout = options.httptimeout
    self._md5conf = md5conf
    
    self._deliverer = Deliverer(self._repository, self._client.isp.certificate, self._httptimeout)

    self._running = Event()

  def join(self, timeout = None):
    self._running.clear()
    logger.info("Chiusura del tester")
    #wx.CallAfter(self._gui._update_messages, "Attendere la chiusura del programma...")

  def _get_server(self, servers = set([Server('NAMEX', '193.104.137.133', 'NAP di Roma'), Server('MIX', '193.104.137.4', 'NAP di Milano')])):

    maxREP = 4
    best = {}
    best['start'] = None
    best['delay'] = 8000
    best['server'] = None
    RTT = {}

    wx.CallAfter(self._gui._update_messages, "Scelta del server di misura in corso")

    for server in servers:
      RTT[server.name] = best['delay']

    for repeat in range(maxREP):
      sleep(1)
      wx.CallAfter(self._gui._update_messages, "Test %d di %d di ping." % (repeat+1, maxREP), 'blue')
      wx.CallAfter(self._gui.update_gauge)
      for server in servers:
        try:
          start = None
          delay = 0
          start = datetime.fromtimestamp(timestampNtp())
          delay = ping.do_one("%s" % server.ip, 1) * 1000
          if (delay < RTT[server.name]):
            RTT[server.name] = delay
          if (delay < best['delay']):
            best['start'] = start
            best['delay'] = delay
            best['server'] = server
        except Exception as e:
          logger.info('Errore durante il ping dell\'host %s: %s' % (server.ip, e))
          pass

    if best['server'] != None:
      for server in servers:
        if (RTT[server.name] != 8000):
          wx.CallAfter(self._gui._update_messages, "Distanza dal %s: %.1f ms" % (server.name, RTT[server.name]), 'blue')
        else:
          wx.CallAfter(self._gui._update_messages, "Distanza dal %s: TimeOut" % (server.name), 'blue')
      wx.CallAfter(self._gui._update_messages, "Scelto il server di misura %s" % best['server'].name)
    else:
      wx.CallAfter(self._gui._update_messages, "Impossibile eseguire i test poiche' i server risultano irragiungibili da questa linea. Contattare l'helpdesk del progetto Misurainternet per avere informazioni sulla risoluzione del problema.", 'red')

    return best
  
  def _download_task(self):
    # Scarica il prossimo task dallo scheduler #
    #logger.info('Reading resource %s for client %s' % (self._scheduler, self._client))

    url = urlparse(self._scheduler)
    certificate = self._client.isp.certificate
    connection = httputils.getverifiedconnection(url = url, certificate = certificate, timeout = self._httptimeout)

    try:
      connection.request('GET', '%s?clientid=%s&version=%s&confid=%s' % (url.path, self._client.id, __version__, self._md5conf))
      data = connection.getresponse().read()
      #logger.debug(data)
      task = xml2task(data)
      if (task != None):
        task.ftpdownpath = '/download/'+TASK_FILE+'.rnd'
        self._client.profile.upload = int(TASK_FILE)
      else:
        logger.info('Lo scheduler ha inviato un task vuoto.')
      logger.info("--------[TASK]--------")
      for key, val in task.dict.items():
        logger.info("%s : %s" % (key, val))
    except Exception as e:
      logger.error('Impossibile scaricare lo scheduling. Errore: %s.' % e)
      return None
    
    #task = Task(0, '2010-01-01 10:01:00', Server('NAMEX', '193.104.137.133', 'NAP di Roma'), '/download/%s' % TASK_FILE, 'upload/%s' % TASK_FILE, 4, 4, 10, 4, 4, 0, True)
    return task

  def _test_gating(self, test, testtype):
    '''
    Funzione per l'analisi del contabit ed eventuale gating dei risultati del test
    '''
    stats = test.counter_stats
    logger.info('Sniffer Statistics: %s' % stats)
    continue_testing = False

    logger.info('Analisi della percentuale dei pacchetti persi')
    packet_drop = stats.packet_drop
    packet_tot = stats.packet_tot_all
    if (packet_tot > 0):
      logger.info('Persi %s pacchetti di %s' % (packet_drop, packet_tot))
      packet_ratio = float(packet_drop) / float(packet_tot)
      logger.info('Percentuale di pacchetti persi: %.2f%%' % (packet_ratio * 100))
      if (packet_tot > 0 and packet_ratio > TH_PACKETDROP):
        info = 'Eccessiva presenza di traffico di rete, impossibile analizzare i dati di test'
        wx.CallAfter(self._gui.set_resource_info, RES_TRAFFIC, {'status': False, 'info': info, 'value': None})
        return continue_testing

    else:
      info = 'Errore durante la misura, impossibile analizzare i dati di test'
      wx.CallAfter(self._gui.set_resource_info, RES_TRAFFIC, {'status': False, 'info': info, 'value': None})
      return continue_testing

    if (testtype == DOWN):
      byte_nem = stats.payload_down_nem_net
      byte_all = byte_nem + stats.byte_down_oth_net
      packet_nem = stats.packet_up_nem_net
      packet_all = packet_nem + stats.packet_up_oth_net
    else:
      byte_nem = stats.payload_up_nem_net
      byte_all = byte_nem + stats.byte_up_oth_net
      packet_nem = stats.packet_down_nem_net
      packet_all = packet_nem + stats.packet_down_oth_net

    logger.info('Analisi dei rapporti di traffico')
    if byte_all > 0 and packet_all > 0:
      traffic_ratio = float(byte_all - byte_nem) / float(byte_all)
      packet_ratio_inv = float(packet_all - packet_nem) / float(packet_all)
      value1 = "%.2f%%" % (traffic_ratio * 100)
      value2 = "%.2f%%" % (packet_ratio_inv * 100)
      logger.info('Traffico NeMeSys: [ %d pacchetti di %d totali e %.1f Kbyte di %.1f totali ]' % (packet_nem,  packet_all, byte_nem / 1024.0, byte_all / 1024.0))
      logger.info('Percentuale di traffico spurio: %.2f%% traffico e %.2f%% pacchetti' % (traffic_ratio * 100, packet_ratio_inv * 100))
      if traffic_ratio < 0:
        wx.CallAfter(self._gui._update_messages, 'Errore durante la verifica del traffico di misura: impossibile salvare i dati.', 'red')
        return continue_testing
      elif traffic_ratio < TH_TRAFFIC and packet_ratio_inv < TH_TRAFFIC_INV:
        # Dato da salvare sulla misura
        # test.bytes = byte_all
        info = 'Traffico internet non legato alla misura: percentuali %s/%s' % (value1, value2)
        wx.CallAfter(self._gui.set_resource_info, RES_TRAFFIC, {'status': True, 'info': info, 'value': value1}, False)
        return True
      else:
        info = 'Eccessiva presenza di traffico internet non legato alla misura: percentuali %s/%s' % (value1, value2)
        wx.CallAfter(self._gui.set_resource_info, RES_TRAFFIC, {'status': False, 'info': info, 'value': value1})
        return continue_testing
    else:
      info = 'Errore durante la misura, impossibile analizzare i dati di test'
      wx.CallAfter(self._gui.set_resource_info, RES_TRAFFIC, {'status': False, 'info': info, 'value': 'error'})
      return continue_testing

    return True

  def _get_bandwith(self, test):

    if test.time > 0:
      return int(round(test.bytes * 8 / test.time))
    else:
      raise Exception("Errore durante la valutazione del test")

  def _do_test(self, tester, type, task):
    test_done = 0
    test_good = 0
    test_todo = 0

    best_value = None
    best_test = None
    
    if type == PING:
      stringtype = "ping"
      test_todo = task.ping
    elif type == DOWN:
      stringtype = "ftp download"
      test_todo = task.download
    elif type == UP:
      stringtype = "ftp upload"
      test_todo = task.upload

    self._profiler.set_check(set([RES_HOSTS, RES_TRAFFIC]))
    pre_profiler = self._profiler.get_results()

    while (test_good < test_todo and self._running.isSet()):

      # Esecuzione del test
      test = None
      error = 0
      while (error < MAX_TEST_ERROR and test == None):
        self._profiler.set_check(set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA]))
        profiler = self._profiler.get_results()
        sleep(1)
        
        wx.CallAfter(self._gui._update_messages, "Test %d di %d di %s" % (test_good+1, test_todo, stringtype.upper()), 'blue')
        
        try:
          test_done += 1
          message =  "Tentativo numero %s con %s riusciti su %s da collezionare" % (test_done,test_good,test_todo)
          if type == PING:
            logger.info("[PING] "+message+" [PING]")
            test = tester.testping()
          elif type == DOWN:
            logger.info("[DOWNLOAD] "+message+" [DOWNLOAD]")
            test = tester.testftpdown(self._client.profile.download * task.multiplier * 1000 / 8, task.ftpdownpath)
          elif type == UP:
            logger.info("[UPLOAD] "+message+" [UPLOAD]")
            test = tester.testftpup(self._client.profile.upload * task.multiplier * 1000 / 8, task.ftpuppath)
          else:
            logger.warn("Tipo di test da effettuare non definito!")
        except Exception as e:
          if (self._running.isSet()):
            error += 1
          else:
            error = MAX_TEST_ERROR
          test = None
          wx.CallAfter(self._gui._update_messages, "Errore durante l'esecuzione di un test: %s" % e, 'red')
          wx.CallAfter(self._gui._update_messages, "Ripresa del test tra %d secondi" % TIME_LAG)
          sleep(TIME_LAG)

      if test != None:      
        test.update(pre_profiler)
        test.update(profiler)
        
        if type == PING:
          test_good += 1
          logger.info("[ Ping: %s ] [ Actual Best: %s ]" % (test.time, best_value))
          if best_value == None:
            best_value = 4444
          if test.time < best_value:
            best_value = test.time
            best_test = test
          wx.CallAfter(self._gui.update_gauge)
        else:
          bandwidth = self._get_bandwith(test)
          
          if type == DOWN:
            self._client.profile.download = min(bandwidth, 40000)
            task.update_ftpdownpath(bandwidth)
          elif type == UP:
            self._client.profile.upload = min(bandwidth, 40000)
          else:
            logger.warn("Tipo di test effettuato non definito!")
            
          if test_good > 0:
            # Analisi da contabit
            if (self._test_gating(test, type)):
              logger.info("[ Bandwidth in %s : %s ] [ Actual Best: %s ]" % (type, bandwidth, best_value))
              if best_value == None:
                best_value = 0
              if bandwidth > best_value:
                best_value = bandwidth
                best_test = test
              wx.CallAfter(self._gui.update_gauge)
              test_good += 1
          else:
            wx.CallAfter(self._gui.update_gauge)
            test_good += 1
      
      else:
        raise Exception("Errore: [Test = None] La misurazione non puo' essere completata")

    best_test.done = test_done
    return best_test

  def run(self):

    self._running.set()
    
    wx.CallAfter(self._gui._update_messages, "Inizio dei test di misura.")
    wx.CallAfter(self._gui.update_gauge)

    # Profilazione
    self._profiler.set_check(set([RES_OS, RES_IP]))
    self._profiler.start()
    profiler = self._profiler.get_results()
    sleep(1)
    
    #ping_test = self._get_server()
    #server = ping_test['server']
    
    # TODO task tra Try Except per gestire il fatto che potrebbe non esserci banda.... vedi executer 
    task = self._download_task()
    if task != None:
      try:
        wx.CallAfter(self._gui.update_gauge)
        if (task.server.location != None):
          wx.CallAfter(self._gui._update_messages, "Selezionato il server di misura di %s" % task.server.location,'green')
        
        start_time = datetime.fromtimestamp(timestampNtp())

        (ip, os) = (profiler[RES_IP], profiler[RES_OS])
        tester = Tester(if_ip = ip, host = task.server, timeout = self._testtimeout,
                   username = self._client.username, password = self._client.password)

        measure = Measure(self._client, start_time, task.server, ip, os, __version__)
        #logger.debug("\n\n%s\n\n",str(measure))
        
        test_types = [PING,DOWN,UP]
        
        # Testa i ping
        for type in test_types:
          test = self._do_test(tester, type, task)
          measure.savetest(test)
          wx.CallAfter(self._gui._update_messages, "Elaborazione dei dati")
          # if (move_on_key()):
          if (type == PING):
            wx.CallAfter(self._gui._update_messages, "Tempo di risposta del server: %.1f ms" % test.time, 'green')
            wx.CallAfter(self._gui._update_ping, test.time)
          elif (type == DOWN):
            wx.CallAfter(self._gui._update_messages, "Download bandwith %s kbps" % self._get_bandwith(test), 'green')
            wx.CallAfter(self._gui._update_down, self._get_bandwith(test))
          elif (type == UP):
            wx.CallAfter(self._gui._update_messages, "Upload bandwith %s kbps" % self._get_bandwith(test), 'green')
            wx.CallAfter(self._gui._update_up, self._get_bandwith(test))
          # else:
            # raise Exception("chiave USB mancante")
          #logger.debug("\n\n%s\n\n",str(measure))
        
        stop_time = datetime.fromtimestamp(timestampNtp())
        measure.savetime(start_time,stop_time)
        
        ## Salvataggio della misura ##
        "TODO: measure.save"
        self._save_measure(measure)
        ## Fine Salvataggio ##
        
      except Exception as e:
        logger.warning('Misura sospesa per eccezione: %s.' % e)
        wx.CallAfter(self._gui._update_messages, 'Misura sospesa per errore: %s.' % e, 'red')
    else:
      wx.CallAfter(self._gui._update_messages, "Impossibile eseguire ora i test di misura. Riprovare tra qualche minuto.", 'red')
        
    self._profiler.stop()
    wx.CallAfter(self._gui.stop)
    
    
  def _save_measure(self, measure):
    # Salva il file con le misure
    f = open('%s/measure_%s.xml' % (self._outbox, measure.id), 'w')
    f.write(str(measure))
    # Aggiungi la data di fine in fondo al file
    f.write('\n<!-- [finished] %s -->' % datetime.fromtimestamp(timestampNtp()).isoformat())
    f.close()
    
    self._upload()
    #report = self._upload(f.name)
    
    return f.name
    
    
  def _upload(self, fname = None, delete = True):
    '''
    Cerca di spedire al repository entro il tempo messo a disposizione secondo il parametro httptimeout
    uno o tutti i filename di misura che si trovano nella cartella d'uscita
    '''
    for retry in range(UPLOAD_RETRY):
      allOK = True
      
      filenames = []
      if (fname != None):
        filenames.append(fname)
      else:  
        for root, dirs, files in walk(paths.OUTBOX_DIR):
          for file in files:
            if (re.search('measure_[0-9]{14}.xml',file) != None):
              filenames.append(path.join(root, file))
      
      len_filenames = len(filenames)
      
      if (len_filenames > 0):
        logger.info('Trovati %s file di misura ancora da spedire.' % len_filenames)
        if retry == 0:
          wx.CallAfter(self._gui._update_messages, "Salvataggio delle misure in corso....")
        
        for filename in filenames:
          uploadOK = False
          
          try:
            # Crea il Deliverer che si occupera' della spedizione
            zipname = self._deliverer.pack(filename)
            response = self._deliverer.upload(zipname)

            if (response != None):
              (code, message) = self._parserepositorydata(response)
              code = int(code)
              logger.info('Risposta dal server di upload: [%d] %s' % (code, message))
              uploadOK = not bool(code)
              logger.debug(uploadOK)
              
          except Exception as e:
            logger.error('Errore durante la spedizione del file delle misure %s: %s' % (filename, e))

          finally:
            if path.exists(filename) and uploadOK:
              remove(filename)        # Elimino XML se esiste
            if path.exists(zipname):
              remove(zipname)         # Elimino ZIP se esiste
              
          if uploadOK:
            logger.info('File %s spedito con successo.' % filename)
          else:
            logger.info('Errore nella spedizione del file %s.' % filename)
            sleep_time = 5*(retry+1)
            allOK = False
            
        if allOK:
          wx.CallAfter(self._gui._update_messages, "Salvataggio completato con successo.",'green')
          break
        else:
          wx.CallAfter(self._gui._update_messages, "Tentativo di salvataggio numero %s di %s fallito." % (retry+1, UPLOAD_RETRY),'red')
          if (retry+1)<UPLOAD_RETRY:
            wx.CallAfter(self._gui._update_messages, "Nuovo tentativo fra %s secondi." % sleep_time,'red')
            sleep(sleep_time)
          else:
            wx.CallAfter(self._gui._update_messages, "Impossibile salvare le misure.",'red')
            if delete:
              for filename in filenames:
                if path.exists(filename):
                  remove(filename)        # Elimino XML se esiste
            else:
              title = "Salvataggio Misure"
              message = \
              '''
              Non e' stato possibile salvare le misure per %s volte.
              
              Un nuovo tentativo verra' effettuato:
              1) a seguito della prossima profilazione
              2) a seguito della prossima misura
              3) al prossimo riavvio di NeMeSys Speedtest
              ''' % UPLOAD_RETRY
              msgBox = wx.MessageDialog(None, message, title, wx.OK|wx.ICON_INFORMATION)
              msgBox.ShowModal()
              msgBox.Destroy()

      else:
        logger.info('Nessun file di misura ancora da spedire.') 
        break
        
    self._remEmptyDir(paths.OUTBOX_DIR)
    self._remEmptyDir(paths.SENT_DIR)
        
        
  def _parserepositorydata(self, data):
    '''
    Valuta l'XML ricevuto dal repository, restituisce il codice e il messaggio ricevuto
    '''

    xml = getxml(data)
    if (xml == None):
      logger.error('Nessuna risposta ricevuta')
      return None

    nodes = xml.getElementsByTagName('response')
    if (len(nodes) < 1):
      logger.error('Nessuna risposta ricevuta nell\'XML:\n%s' % xml.toxml())
      return None

    node = nodes[0]

    code = getvalues(node, 'code')
    message = getvalues(node, 'message')
    return (code, message)
    
    
  def _movefiles(self, filename):
    
    dir = path.dirname(filename)
    #pattern = path.basename(filename)[0:-4]
    pattern = path.basename(filename)

    try:
      for file in listdir(dir):
        # Cercare tutti i file che iniziano per pattern
        if (re.search(pattern, file) != None):
          # Spostarli tutti in self._sent
          old = path.join(dir, file)
          new = path.join(self._sent,file)
          shutil.move(old, new)

    except Exception as e:
      logger.error('Errore durante lo spostamento dei file di misura %s' % e)
      
  def _remEmptyDir(self, topdir):
    for root, dirs, files in walk(topdir, topdown=False):
      for dir in range(len(dirs)):
        dirs[dir] = path.join(root,dirs[dir])
        dirs.append(root)
      for dir in dirs:  
        if path.exists(dir):
          if not listdir(dir):  #to check wither the dir is empty
            logger.debug("Elimino la directory vuota: %s" % dir)
            removedirs(dir)
          
if __name__ == "__main__":
  sleep(8)
  test = speedTester(None)
  test._remEmptyDir(paths.OUTBOX_DIR)
  test._remEmptyDir(paths.SENT_DIR)
          
          