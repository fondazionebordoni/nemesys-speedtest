# xmlutils.py
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

from datetime import datetime
import logging
import re
from string import join
from xml.dom import Node
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

from server import Server
from task import Task

tag_task = 'task'
tag_id = 'id'
# tag_upload = 'nftpup'
# att_multiplier = 'mult'
# tag_download = 'nftpdown'
tag_ping = 'nping'
att_icmp = 'icmp'
att_delay = 'delay'
tag_start = 'start'
att_now = 'now'
tag_serverid = 'srvid'
tag_serverip = 'srvip'
tag_servername = 'srvname'
tag_srvlocation = 'srvlocation'
tag_message = 'message'
startformat = '%Y-%m-%d %H:%M:%S'

logger = logging.getLogger(__name__)


def iso2datetime(s):
    """
    La versione 2.5 di python ha un bug nella funzione strptime che non riesce
    a leggere i microsecondi (%f)
    """
    p = s.split('.')
    dt = datetime.strptime(p[0], '%Y-%m-%dT%H:%M:%S')

    # Gstione dei microsecondi
    ms = 0
    try:
        if len(p) > 1:
            ms = int(p[1])
    except Exception:
        ms = 0
    dt.replace(microsecond=ms)
    return dt


def getxml(data):
    if len(data) < 1:
        logger.error('Nessun dato da processare')
        raise Exception('Ricevuto un messaggio vuoto')
    try:
        xml = parseString(data)
    except ExpatError:
        logger.error('Il dato ricevuto non è in formato XML: %s' % data)
        raise Exception('Errore di formattazione del messaggio')
    return xml


# Trasforma l'XML dei task nel prossimo Task da eseguire
def xml2task(data):
    try:
        xml = getxml(data)
    except Exception as e:
        logger.error('Errore durante la conversione dei dati di task')
        raise Exception('Le informazioni per la programmazione delle misure non sono corrette. %s' % e)

    nodes = xml.getElementsByTagName(tag_task)
    if (len(nodes) < 1):
        logger.debug('Nessun task trovato nell\'XML:\n%s' % xml.toxml())
        return None

    # Considera solo il primo task
    node = nodes[0]

    # Aggancio dei dati richiesti
    try:
        task_id = getvalues(node, tag_id)
        ping = getvalues(node, tag_ping)
        start = getvalues(node, tag_start)
        serverid = getvalues(node, tag_serverid)
        serverip = getvalues(node, tag_serverip)
    except IndexError:
        logger.error('L\'XML ricevuto non contiene tutti i dati richiesti. XML: %s' % data)
        raise Exception('Le informazioni per la programmazione delle misure sono incomplete.')

    # Aggancio dei dati opzionali
    servername = None
    srvlocation = None
    message = None
    try:
        servername = getvalues(node, tag_servername)
        srvlocation = getvalues(node, tag_srvlocation)
        #         multiplier = node.getElementsByTagName(tag_upload)[0].getAttribute(att_multiplier)
        nicmp = node.getElementsByTagName(tag_ping)[0].getAttribute(att_icmp)
        delay = node.getElementsByTagName(tag_ping)[0].getAttribute(att_delay)
        now = node.getElementsByTagName(tag_start)[0].getAttribute(att_now)
        message = getvalues(node, tag_message)
    except IndexError:
        pass

    # Verifica che i dati siano compatibili
    # Dati numerici/booleani

    PING = "il numero di ping da effettuare"
    NICMP = "il numero di pacchetti icmp per la prova ping da effettuare (default = 4)"
    DELAY = "il valore di delay, in secondi, tra un ping e l'altro (default = 1)"
    NOW = "indicazione se il task deve essere iniziato subito (default = 0)"

    try:

        results = [ping, nicmp, delay, now]
        strings = [PING, NICMP, DELAY, NOW]
        defaults = [None, "4", "1", "0"]

        for index in range(len(results)):
            value = re.sub("\D", "", results[index])
            if len(value) <= 0:
                logger.error("Il file XML non contiene %s" % strings[index])
                if defaults[index] is not None:
                    value = defaults[index]
                else:
                    raise Exception()
            results[index] = int(value)

        ping = results[0]
        nicmp = results[1]
        delay = results[2]
        now = results[3]

    except Exception:
        raise Exception('Le informazioni per la programmazione delle misure sono errate.')

    try:
        start = datetime.strptime(start, startformat)
    except ValueError:
        logger.error('Errore durante la verifica della compatibilità dei dati orari di task')
        logger.debug('XML: %s' % data)
        print data
        raise Exception('Le informazioni orarie per la programmazione delle misure sono errate.')

    ##TODO: Controllare validità dati IP##

    server = Server(serverid, serverip, servername, srvlocation)
    task = Task(task_id=task_id, start=start, server=server, ping=ping, nicmp=nicmp, delay=delay, now=bool(now),
                message=message)

    return task


def getvalues(node, tag=None):
    if (tag is None):
        values = []
        for child in node.childNodes:
            if child.nodeType == Node.TEXT_NODE:
                # logger.debug('Trovato nodo testo.')
                values.append(child.nodeValue)

        # logger.debug('Value found: %s' % join(values).strip())
        return join(values).strip()

    else:
        return getvalues(node.getElementsByTagName(tag)[0])


def getstarttime(filename):
    '''
    Ricava il tempo di start da un file di misura
    '''
    with open(filename) as f:
        data = f.read()

    try:
        xml = getxml(data)
    except Exception as e:
        logger.error('Errore durante la conversione dei dati di misura contenuti nel file.')
        raise Exception('Le informazioni di misura non sono corrette. %s' % e)

    nodes = xml.getElementsByTagName('measure')
    if (len(nodes) < 1):
        logger.debug('Nessun measure trovato nell\'XML:\n%s' % xml.toxml())
        raise Exception('Nessuna informazione di misura nel file.')

    node = nodes[0]

    # Aggancio dei dati richiesti
    try:
        start = node.getAttribute('start')
    except IndexError:
        logger.error('L\'XML ricevuto non contiene il dato di start. XML: %s' % data)
        raise Exception('Errore durante il controllo dell\'orario di inizio della misura.')

    return iso2datetime(start)
