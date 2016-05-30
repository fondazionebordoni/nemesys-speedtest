# result_sender.py
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
'''
Created on 22/apr/2016

@author: ewedlund
'''

from datetime import datetime
import logging
import os
import re
import time

import gui_event
from timeNtp import timestampNtp
import paths
import xmlutils


logger = logging.getLogger(__name__)
MAX_SEND_RETRY = 3

def save_and_send_measure(measure, event_dispatcher, deliverer):
    # Salva il file con le misure
    f = open(os.path.join(paths.OUTBOX_DAY_DIR, 'measure_%s.xml' % measure.id), 'w')
    f.write(str(measure))
    # Aggiungi la data di fine in fondo al file
    f.write('\n<!-- [finished] %s -->' % datetime.fromtimestamp(timestampNtp()).isoformat())
    f.close()
    num_sent_files = upload(event_dispatcher, deliverer)
    return num_sent_files



def upload(event_dispatcher, deliverer, fname=None, delete=True):
    '''
    Cerca di spedire al repository entro il tempo messo a disposizione secondo il parametro httptimeout
    uno o tutti i filename di misura che si trovano nella cartella d'uscita
    '''
    num_sent_files = 0
    for retry in range(MAX_SEND_RETRY):
        allOK = True
        
        filenames = []
        if (fname != None):
            filenames.append(fname)
        else:    
            for root, _, files in os.walk(paths.OUTBOX_DIR):
                for xmlfile in files:
                    if (re.search('measure_[0-9]{14}.xml', xmlfile) != None):
                        filenames.append(os.path.join(root, xmlfile))
        
        len_filenames = len(filenames)
        
        if (len_filenames > 0):
            logger.info('Trovati %s file di misura ancora da spedire.' % len_filenames)
            if retry == 0:
                event_dispatcher.postEvent(gui_event.UpdateEvent("Salvataggio delle misure in corso...."))
            
            for filename in filenames:
                uploadOK = False
                
                try:
                    # Crea il Deliverer che si occupera' della spedizione
                    zipname = deliverer.pack(filename)
                    response = deliverer.upload(zipname)

                    if (response != None):
                        (code, message) = parserepositorydata(response)
                        code = int(code)
                        logger.info('Risposta dal server di upload: [%d] %s' % (code, message))
                        uploadOK = not bool(code)
                        # logger.debug(uploadOK)
                        
                except Exception as e:
                    logger.error('Errore durante la spedizione del file delle misure %s: %s' % (filename, e), exc_info=True)

                finally:
                    if os.path.exists(filename) and uploadOK:
                        os.remove(filename)    # Elimino XML se esiste
                    if os.path.exists(zipname):
                        os.remove(zipname)    # Elimino ZIP se esiste
                        
                if uploadOK:
                    logger.info('File %s spedito con successo.' % filename)
                    num_sent_files += num_sent_files
                else:
                    logger.info('Errore nella spedizione del file %s.' % filename)
                    sleep_time = 5 * (retry + 1)
                    allOK = False
                    
            if allOK:
                event_dispatcher.postEvent(gui_event.UpdateEvent("Salvataggio completato con successo.", gui_event.UpdateEvent.MAJOR_IMPORTANCE))
                break
            else:
                event_dispatcher.postEvent(gui_event.ErrorEvent("Tentativo di salvataggio numero %s di %s fallito." % (retry + 1, MAX_SEND_RETRY)))
                if (retry + 1) < MAX_SEND_RETRY:
                    event_dispatcher.postEvent(gui_event.ErrorEvent("Nuovo tentativo fra %s secondi." % sleep_time))
                    time.sleep(sleep_time)
                else:
                    event_dispatcher.postEvent(gui_event.ErrorEvent("Impossibile salvare le misure."))
                    for filename in filenames:
                        if os.path.exists(filename):
                            os.remove(filename)    # Elimino XML se esiste

        else:
            logger.info('Nessun file di misura ancora da spedire.') 
            break

    return num_sent_files


def parserepositorydata(data):
    '''
    Valuta l'XML ricevuto dal repository, restituisce il codice e il messaggio ricevuto
    '''
    xml = xmlutils.getxml(data)
    if (xml == None):
        logger.error('Nessuna risposta ricevuta')
        return None

    nodes = xml.getElementsByTagName('response')
    if (len(nodes) < 1):
        logger.error('Nessuna risposta ricevuta nell\'XML:\n%s' % xml.toxml())
        return None

    node = nodes[0]

    code = xmlutils.getvalues(node, 'code')
    message = xmlutils.getvalues(node, 'message')
    return (code, message)
