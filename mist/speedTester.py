#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from sysMonitor import RES_OS, RES_IP, RES_DEV, RES_MAC, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_HSPA, RES_TRAFFIC, RES_HOSTS
from sysMonitor import RES_OS, RES_IP, RES_DEV, RES_MAC, RES_CPU, RES_RAM, RES_ETH, RES_WIFI, RES_TRAFFIC, RES_HOSTS
from xmlutils import getvalues, getxml, xml2task
from os import path, walk, listdir, remove, removedirs
from optionParser import OptionParser
from sysProfiler import sysProfiler
from threading import Thread, Event
from timeNtp import timestampNtp
from deliverer import Deliverer
from datetime import datetime
from urlparse import urlparse
from measure import Measure
from measurementexception import MeasurementException
from profile import Profile
from logger import logging
from client import Client
from server import Server
from tester import Tester
from proof import Proof
from time import sleep
from isp import Isp

import gui_event
import httputils
import shutil
import paths
import ping
import test_type
import wx
import re

logger = logging.getLogger()

TASK_FILE = '40000'

TH_PACKETDROP = 0.05    # Soglia per numero di pacchetti persi #
TH_TRAFFIC = 0.1    # Soglia per il rapporto tra traffico 'spurio' e traffico totale #
TH_INVERTED = 0.9    # Soglia per il rapporto tra traffico 'spurio' e traffico totale nella direzione opposta a quella di test #

TIME_LAG = 5    # Tempo di attesa tra una misura e la successiva in caso di misura fallita #
MAX_TEST_RETRY = 3
MAX_SEND_RETRY = 3


class SpeedTester(Thread):

    def __init__(self, version, event_dispatcher, do_profile = True):
        Thread.__init__(self)
        
        paths_check = paths.check_paths()
        for check in paths_check:
            logger.info(check)
            
        self._sent = paths.SENT_DAY_DIR
        self._outbox = paths.OUTBOX_DAY_DIR

        self._version = version
        self._event_dispatcher = event_dispatcher
        self._do_profile = do_profile
        self._profiler = sysProfiler(event_dispatcher, 'tester')

        parser = OptionParser(version=self._version, description='')
        (options, _, md5conf) = parser.parse()

        self._client = self._getclient(options)
        self._scheduler = options.scheduler
        self._repository = options.repository
        self._tasktimeout = options.tasktimeout
        self._testtimeout = options.testtimeout
        self._httptimeout = options.httptimeout
        self._md5conf = md5conf
        
        self._deliverer = Deliverer(self._repository, self._client.isp.certificate, self._httptimeout)

        self._running = Event()
    
    def is_oneshot(self):
        return self._client.is_oneshot()
    
    def stop(self, timeout=None):
        self._running.clear()
        logger.info("Chiusura del tester")

    def is_running(self):
        return self._running.is_set()

    def _getclient(self, options):

        profile = Profile(id=None, upload=options.bandwidthup,
                                            download=options.bandwidthdown)
        isp = Isp('fub001')
        return Client(id=options.clientid, profile=profile, isp=isp,
                                    geocode=None, username='speedtest',
                                    password=options.password)

    
    def _get_server(self, servers=set([Server('NAMEX', '193.104.137.133', 'NAP di Roma'), Server('MIX', '193.104.137.4', 'NAP di Milano')])):

        maxREP = 4
        best = {}
        best['start'] = None
        best['delay'] = 8000
        best['server'] = None
        RTT = {}

        self._event_dispatcher.postEvent(gui_event.UpdateEvent("Scelta del server di misura in corso"))

        for server in servers:
            RTT[server.name] = best['delay']

        for _ in range(maxREP):
            sleep(1)
#             self._event_dispatcher.postEvent(gui_event.UpdateEvent("Test %d di %d di ping." % (repeat + 1, maxREP)))
#             self._event_dispatcher.postEvent(gui_event.ProgressEvent(float(repeat + 1)/maxREP))
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
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Distanza dal %s: %.1f ms" % (server.name, RTT[server.name])))
                else:
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Distanza dal %s: TimeOut" % (server.name)))
            self._event_dispatcher.postEvent(gui_event.UpdateEvent("Scelto il server di misura %s" % best['server'].name, gui_event.UpdateEvent.MAJOR_IMPORTANCE))
        else:
            self._event_dispatcher.postEvent(gui_event.ErrorEvent("Impossibile eseguire i test poiche' i server risultano irragiungibili da questa linea. Contattare l'helpdesk del progetto Misurainternet per avere informazioni sulla risoluzione del problema."))

        return best
    
    
    def _download_task(self, server=None):
        '''Scarica il prossimo task dallo scheduler'''

        try:
            url = urlparse(self._scheduler)
            certificate = self._client.isp.certificate
            
            connection = httputils.getverifiedconnection(url=url, certificate=certificate, timeout=self._httptimeout)
            if (server != None):
                connection.request('GET', '%s?clientid=%s&version=%s&confid=%s&server=%s' % (url.path, self._client.id, self._version, self._md5conf, server.ip))
            else:
                connection.request('GET', '%s?clientid=%s&version=%s&confid=%s' % (url.path, self._client.id, self._version, self._md5conf))
            
            data = connection.getresponse().read()
            task = xml2task(data)
            
            if (task == None): 
                logger.info('Lo scheduler ha inviato un task vuoto.')
            else:
                task.ftpdownpath = '/download/' + TASK_FILE + '.rnd'
                self._client.profile.upload = int(TASK_FILE)
                logger.info("--------[ TASK ]--------")
                for key, val in task.dict.items():
                    logger.info("%s : %s" % (key, val))
                logger.info("------------------------")
                
        except Exception as e:
            logger.error('Impossibile scaricare lo scheduling. Errore: %s.' % e)
            return None
        
        return task
    
    
    def _test_gating(self, test, testtype):
        '''
        Funzione per l'analisi del contabit ed eventuale gating dei risultati del test
        '''
        test_status = False

        byte_nem = test['bytes']
        byte_all = test['bytes_total']
        logger.info('Analisi dei rapporti di traffico')
        logger.debug('Dati per la soglia: byte_nem: %d | byte_all: %d' % (byte_nem, byte_all))
        if byte_all > 0:
            traffic_ratio = float(byte_all - byte_nem) / float(byte_all)
            value1 = "%.2f%%" % (traffic_ratio * 100)
#             logger.info('Traffico MIST: [ %d pacchetti di %d totali e %.1f Kbyte di %.1f totali ]' % (packet_nem, packet_all, byte_nem / 1024.0, byte_all / 1024.0))
            if (0 <= traffic_ratio <= TH_TRAFFIC):
                test_status = True
                info = 'Traffico internet non legato alla misura: percentuale %s' % value1
                self._event_dispatcher.postEvent(gui_event.ResourceEvent(RES_TRAFFIC, {'status': True, 'info': info, 'value': value1}, False))
            elif (traffic_ratio > TH_TRAFFIC):
                info = 'Eccessiva presenza di traffico internet non legato alla misura: percentuale %s' % value1
                self._event_dispatcher.postEvent(gui_event.ResourceEvent(RES_TRAFFIC, {'status': False, 'info': info, 'value': value1}, True))
            else:
                self._event_dispatcher.postEvent(gui_event.ErrorEvent('Errore durante la verifica del traffico di misura: impossibile salvare i dati.'))
        else:
            info = 'Errore durante la misura, impossibile analizzare i dati di test'
            self._event_dispatcher.postEvent(gui_event.ResourceEvent(RES_TRAFFIC, {'status': False, 'info': info, 'value': 'error'}, True))
        
        return test_status
    
    
    def _get_bandwidth(self, myProof):
         
        if myProof.time > 0:
            return float( ( myProof.bytes + myProof.bytesOth ) * 8 / myProof.time )
        else:
            raise Exception("Errore durante la valutazione del test")
    
    def _get_partial_bandwidth(self, secs):         
        return float(sum(secs))/len(secs)
    
    def _get_bandwidth_from_test(self, test):

        try:
            return self._get_partial_bandwidth(test['rate_tot_secs'])
        except KeyError:
            if test['time'] > 0:
                return float( test['bytes_total'] * 8 )/ test['time'] 
            else:
                raise Exception("Errore durante la valutazione del test")
    
    def _get_max_http_bandwidth(self, test):

        rate_max = test.dict().get('rate_max', 0) 
        if rate_max > 0:
            return rate_max
        else:
            return self._get_bandwidth(test)
    
    def receive_partial_results(self, **args):
        '''Intermediate results from tester'''
        speed = args['speed']
        logger.info("Got partial result: %f", speed)
        self._event_dispatcher.postEvent(gui_event.ResultEvent(test_type.HTTP_DOWN, speed, is_intermediate = True))
#         self._event_dispatcher.postEvent(gui_event.UpdateEvent("%d: %f kb/s" % (args['second'], args['speed'])))
    
    def _do_test(self, tester, t_type, task, previous_profiler_result):
        test_done = 0
        test_good = 0
        test_todo = 0
        retry = 0
        best_value = None
        myProof = None
#         self._event_dispatcher.postEvent(gui_event.ProgressEvent(0))
        
        if t_type == test_type.PING:
            test_todo = task.ping
#         elif t_type == test_type.FTP_DOWN:
#             test_todo = task.download
#         elif t_type == test_type.FTP_UP:
#             test_todo = task.upload
        elif test_type.is_http_down(t_type):
            test_todo = task.http_download
        elif test_type.is_http_up(t_type):
            test_todo = task.http_upload

        while (test_good < test_todo) and self._running.is_set():
            self._progress += self._progress_step
            self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        

            if self._do_profile:
                profiler_result = self._profiler.profile_once(set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI]))
            sleep(1)
            
            self._event_dispatcher.postEvent(gui_event.UpdateEvent("Test %d di %d di %s" % (test_good + 1, test_todo, test_type.get_string_type(t_type ).upper())))
            
            myProof = Proof()
            myProof.update(previous_profiler_result)
            myProof.update(profiler_result)
            
            try:
                test_done += 1
                message = "Tentativo numero %s con %s riusciti su %s da collezionare" % (test_done, test_good, test_todo)
                
                short_string = test_type.get_string_type_short(t_type ).upper()
                logger.info("[%s] %s [%s]" % (short_string, message, short_string))
                if t_type == test_type.PING:
                    testres = tester.testping()
                elif t_type == test_type.HTTP_DOWN:
                    testres = tester.testhttpdown(self.receive_partial_results)
                elif t_type == test_type.HTTP_UP:
                    pass
#                     testres = tester.testhttpup(self.receive_partial_results, num_sessions=1)
                else:
                    logger.warn("Tipo di test da effettuare non definito: %s" % test_type.get_string_type(t_type))

                if t_type == test_type.PING:
                    logger.info("[ Ping: %s ] [ Actual Best: %s ]" % (testres['time'], best_value))
                    self._event_dispatcher.postEvent(gui_event.ResultEvent(test_type.PING, testres['time'], is_intermediate = True))
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Risultato %s (%s di %s): %.1f ms" % (test_type.get_string_type(t_type ).upper(), test_good + 1, test_todo, testres['time'])))
                    if best_value == None:
                        best_value = 4444
                    if testres['time'] < best_value:
                        best_value = testres['time']
                        myProof.update(testres)
                        best_testres = testres
                        
                else:
                    bandwidth = self._get_bandwidth_from_test(testres)
                    self._event_dispatcher.postEvent(gui_event.ResultEvent(t_type, (bandwidth), is_intermediate = True))
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Risultato %s (%s di %s): %s" % (test_type.get_string_type(t_type ).upper(), test_good + 1, test_todo, int(bandwidth))))
#                     if t_type == test_type.FTP_DOWN or t_type == test_type.FTP_UP:
#                             self._event_dispatcher.postEvent(gui_event.UpdateEvent("Tempo di trasferimento: %d" % testres['time']))
                    if test_good >= 0:
                        if not (self._test_gating(testres, t_type )):
                            raise Exception("superata la soglia di traffico spurio.")
                        else:                            
                            logger.info("[ Bandwidth in %s : %s ] [ Actual Best: %s ]" % (t_type , bandwidth, best_value))
                            if best_value == None:
                                best_value = 0
                            if bandwidth > best_value:
                                best_value = bandwidth
                                best_testres = testres
                    else:
                        best_testres = testres
                        
                test_good += 1
                self._progress += self._progress_step
                self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        

            except Exception as e:
                self._event_dispatcher.postEvent(gui_event.ErrorEvent("Errore durante l'esecuzione di un test: %s" % e))
                retry += 1
                if (retry < MAX_TEST_RETRY):
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Ripresa del test tra %d secondi" % TIME_LAG))
                    sleep(TIME_LAG)
                else:
                    raise Exception("Superato il numero massimo di errori possibili durante una misura.")
        if self._running.is_set():            
            best_testres['done'] = test_done
            myProof.update(best_testres)
        return myProof
    
    
    def run(self):

        self._running.set()
        
        self._event_dispatcher.postEvent(gui_event.UpdateEvent("Inizio dei test di misura", gui_event.UpdateEvent.MAJOR_IMPORTANCE))
        self._progress = 0.01
        self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        

        profiler_result = self._profiler.profile_once(set([RES_IP, RES_DEV, RES_OS, RES_MAC]))
        self._profiler.profile_in_background(set([RES_CPU, RES_RAM, RES_ETH, RES_WIFI]))
        self._progress += 0.01
        self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        

        server = None        
        if (self.is_oneshot()):
            ping_test = self._get_server()
            server = ping_test['server']

        task = self._download_task(server)
        self._progress += 0.01
        self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        
        
        if task == None:
            self._event_dispatcher.postEvent(gui_event.ErrorEvent("Impossibile eseguire ora i test di misura. Riprovare tra qualche secondo."))
        else:
            try:
#                 self._event_dispatcher.postEvent(gui_event.ProgressEvent())

                test_types = [test_type.PING, test_type.HTTP_DOWN] 
                total_num_tasks = 0
                for t_type in test_types:
                    total_num_tasks += 4
                total_num_tasks *= 2 # Multiply by 2 to make two progress per task
                total_num_tasks += 3 # Two profilations and save test
                self._progress_step = (1.0 - self._progress)/total_num_tasks

                if (task.server.location != None):
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Selezionato il server di misura di %s" % task.server.location, gui_event.UpdateEvent.MAJOR_IMPORTANCE))
                
                start_time = datetime.fromtimestamp(timestampNtp())

                (ip, dev, os, mac) = (profiler_result[RES_IP], profiler_result[RES_DEV], profiler_result[RES_OS], profiler_result[RES_MAC])
                tester = Tester(dev=dev, ip=ip, host=task.server, timeout=self._testtimeout,
                                     username=self._client.username, password=self._client.password)

                measure = Measure(self._client, start_time, task.server, ip, os, mac, self._version)
                
                profiler_result = self._profiler.profile_once(set([RES_HOSTS, RES_TRAFFIC]))
                self._progress += self._progress_step
                self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        
#                 profiler = self._profiler.get_results()
                sleep(1)

#                                             test_type.HTTP_UP, 
                task.set_ftpup_bytes(int(self._client.profile.upload * task.multiplier * 1000 / 8))
                for t_type in test_types:
                    if not self._running.isSet():
                        # Has been interrupted
                        self._profiler.stop_background_profiling()
                        return
                    best_bandwidth = 0
                    try:
                        sleep(1)
                        test = self._do_test(tester, t_type, task, profiler_result)
                        measure.savetest(test) # Saves test in XML file
                        self._event_dispatcher.postEvent(gui_event.UpdateEvent("Elaborazione dei dati"))
                        if t_type != test_type.PING:
                            bandwidth = self._get_bandwidth_from_test(test._test)
                            if (bandwidth > best_bandwidth):
                                self._client.profile.download = min(bandwidth, 100000)
                                if test_type.is_http_down(t_type):
                                        task.update_ftpdownpath(bandwidth)
                                else:
                                        task.set_ftpup_bytes(int(bandwidth / 8 * 10000))
                                best_bandwidth = bandwidth

                        "TODO: clean up"
                        if t_type == test_type.PING:
                            self._event_dispatcher.postEvent(gui_event.ResultEvent(t_type, test.time))
#                         elif t_type == test_type.FTP_DOWN or t_type == test_type.FTP_UP:
#                             self._event_dispatcher.postEvent(gui_event.ResultEvent(t_type, self._get_bandwidth(test)))
                        elif test_type.is_http(t_type):
                            self._event_dispatcher.postEvent(gui_event.ResultEvent(t_type , self._get_partial_bandwidth(test._test['rate_tot_secs'])))
                    except MeasurementException as e:
                            self._event_dispatcher.postEvent(gui_event.ErrorEvent("Errore durante il test: %s" % e.message))
        
                
                stop_time = datetime.fromtimestamp(timestampNtp())
                measure.savetime(start_time, stop_time)
                
                logger.debug(measure)
                
                # # Salvataggio della misura ##
                "TODO: measure.save"
                self._progress += self._progress_step
                self._event_dispatcher.postEvent(gui_event.ProgressEvent(self._progress))        
                
                self._save_measure(measure)
                self._event_dispatcher.postEvent(gui_event.ProgressEvent(1))
                # # Fine Salvataggio ##
                
            except Exception as e:
                logger.warning('Misura sospesa per eccezione: %s.' % e)
                import traceback
                traceback.print_exc(e)
                self._event_dispatcher.postEvent(gui_event.ErrorEvent('Misura sospesa per errore: %s' % e))
                
        self._profiler.stop_background_profiling()
        self._event_dispatcher.postEvent(gui_event.StopEvent(is_oneshot=self.is_oneshot()))
    
    
    def _save_measure(self, measure):
        # Salva il file con le misure
        f = open('%s/measure_%s.xml' % (self._outbox, measure.id), 'w')
        f.write(str(measure))
        # Aggiungi la data di fine in fondo al file
        f.write('\n<!-- [finished] %s -->' % datetime.fromtimestamp(timestampNtp()).isoformat())
        f.close()
 
        self._upload()
        
        return f.name
    
    
    def _upload(self, fname=None, delete=True):
        '''
        Cerca di spedire al repository entro il tempo messo a disposizione secondo il parametro httptimeout
        uno o tutti i filename di misura che si trovano nella cartella d'uscita
        '''
        for retry in range(MAX_SEND_RETRY):
            allOK = True
            
            filenames = []
            if (fname != None):
                filenames.append(fname)
            else:    
                for root, _, files in walk(paths.OUTBOX_DIR):
                    for xmlfile in files:
                        if (re.search('measure_[0-9]{14}.xml', xmlfile) != None):
                            filenames.append(path.join(root, xmlfile))
            
            len_filenames = len(filenames)
            
            if (len_filenames > 0):
                logger.info('Trovati %s file di misura ancora da spedire.' % len_filenames)
                if retry == 0:
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Salvataggio delle misure in corso...."))
                
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
                            # logger.debug(uploadOK)
                            
                    except Exception as e:
                        logger.error('Errore durante la spedizione del file delle misure %s: %s' % (filename, e))

                    finally:
                        if path.exists(filename) and uploadOK:
                            remove(filename)    # Elimino XML se esiste
                        if path.exists(zipname):
                            remove(zipname)    # Elimino ZIP se esiste
                            
                    if uploadOK:
                        logger.info('File %s spedito con successo.' % filename)
                        if (self._client.is_oneshot()):
                            remove(paths.CONF_MAIN)
                    else:
                        logger.info('Errore nella spedizione del file %s.' % filename)
                        sleep_time = 5 * (retry + 1)
                        allOK = False
                        
                if allOK:
                    self._event_dispatcher.postEvent(gui_event.UpdateEvent("Salvataggio completato con successo.", gui_event.UpdateEvent.MAJOR_IMPORTANCE))
                    break
                else:
                    self._event_dispatcher.postEvent(gui_event.ErrorEvent("Tentativo di salvataggio numero %s di %s fallito." % (retry + 1, MAX_SEND_RETRY)))
                    if (retry + 1) < MAX_SEND_RETRY:
                        self._event_dispatcher.postEvent(gui_event.ErrorEvent("Nuovo tentativo fra %s secondi." % sleep_time))
                        sleep(sleep_time)
                    else:
                        self._event_dispatcher.postEvent(gui_event.ErrorEvent("Impossibile salvare le misure."))
                        if delete:
                            for filename in filenames:
                                if path.exists(filename):
                                    remove(filename)    # Elimino XML se esiste
                        else:
                            "TODO: non sembra utilizzato, togliere?"
                            title = "Salvataggio Misure"
                            message = \
                            '''
                            Non e' stato possibile salvare le misure per %s volte.
                            
                            Un nuovo tentativo verra' effettuato:
                            1) a seguito della prossima profilazione
                            2) a seguito della prossima misura
                            3) al prossimo riavvio di MisuraInternet Speed Test
                            ''' % MAX_SEND_RETRY
                            msgBox = wx.MessageDialog(None, message, title, wx.OK | wx.ICON_INFORMATION)
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
        
        filedir = path.dirname(filename)
        # pattern = path.basename(filename)[0:-4]
        pattern = path.basename(filename)

        try:
            for f in listdir(filedir):
                # Cercare tutti i file che iniziano per pattern
                if (re.search(pattern, f) != None):
                    # Spostarli tutti in self._sent
                    old = path.join(filedir, f)
                    new = path.join(self._sent, f)
                    shutil.move(old, new)

        except Exception as e:
            logger.error('Errore durante lo spostamento dei file di misura %s' % e)
    
    
    def _remEmptyDir(self, topdir):
        for root, dirs, _ in walk(topdir, topdown=False):
            for filedir in range(len(dirs)):
                dirs[filedir] = path.join(root, dirs[filedir])
                dirs.append(root)
            for filedir in dirs:    
                if path.exists(filedir):
                    if not listdir(filedir):    # to check wither the dir is empty
                        logger.info("Elimino la directory vuota: %s" % filedir)
                        removedirs(filedir)




if __name__ == "__main__":
    sleep(8)
    test = SpeedTester(None)
    test._remEmptyDir(paths.OUTBOX_DIR)
    test._remEmptyDir(paths.SENT_DIR)
                    
                    
