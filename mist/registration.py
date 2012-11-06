#!/usr/bin/env python
# -*- coding: utf-8 -*-
# generated by wxGlade 0.6.3 on Wed Apr 11 17:48:58 2012


from logger import logging
import urlparse
import httplib
import paths
import os
import wx

SWN = 'MisuraInternet Speed Test'

logger = logging.getLogger()

configurationServer = 'https://speedtest.agcom244.fub.it/Config'
MAXretry = 3 ## numero massimo di tentativi prima di chiudere la finestra ##


RegInfo = \
{ \
"style":wx.OK|wx.ICON_INFORMATION, \
"title":"Informazioni sulla registrazione", \
"message": \
'''
Verra' ora richiesto il codice licenza per l'attivazione.\n
Il codice licenza e' riportato nella propria area privata
sul sito www.misurainternet.it nella sezione riservata a
%s.\n
Al momento dell'inserimento si prega di verificare
la correttezza del codice licenza e di avere accesso alla rete.\n
Dopo %s tentativi falliti, sara' necessario riavviare
il programma per procedere nuovamente all'inserimento.
''' % (SWN, MAXretry)
}

RegSuccess = \
{ \
"style":wx.OK|wx.ICON_EXCLAMATION, \
"title":"%s Success" % SWN, \
"message":"\nCodice licenza corretto e verificato." \
}

ErrorCode = \
{ \
"style":wx.OK|wx.ICON_ERROR, \
"title":"%s Error" % SWN, \
"message": \
'''
Il codice licenza inserito e' errato.\n
Controllare il codice licenza nella propria
area personale del sito www.misurainternet.it
'''
}

ErrorSave = \
{ \
"style":wx.OK|wx.ICON_ERROR, \
"title":"%s Error" % SWN, \
"message":"\nErrore nel salvataggio del file di configurazione." \
}

ErrorDownload = \
{ \
"style":wx.OK|wx.ICON_ERROR, \
"title":"%s Error" % SWN, \
"message":"\nErrore nel download del file di configurazione\no codice licenza non corretto." \
}

ErrorRetry = \
{ \
"style":wx.OK|wx.ICON_ERROR, \
"title":"%s Error" % SWN, \
"message": \
'''
Il download del file di configurazione e' fallito per %s volte.\n
Riavviare il programma dopo aver verificato la correttezza
del codice di licenza e di avere accesso alla rete.
''' % MAXretry
}

ErrorRegistration = \
{ \
"style":wx.OK|wx.ICON_ERROR, \
"title":"%s Registration Error" % SWN, \
"message": "\nQuesta copia di %s non risulta correttamente registrata." % SWN \
}

def showDialog(dialog):

  msgBox = wx.MessageDialog(None, dialog['message'], dialog['title'], dialog['style'])
  msgBox.ShowModal()
  msgBox.Destroy()
  
  
def getconf(code, filepath, url):
  ## Scarica il file di configurazione dalla url (HTTPS) specificata, salvandolo nel file specificato. ##
  ## Solleva eccezioni in caso di problemi o file ricevuto non corretto. ##
  
  url = urlparse.urlparse(url)
  connection = httplib.HTTPSConnection(host=url.hostname)
  # Warning This does not do any verification of the server’s certificate. #

  connection.request('GET', '%s?clientid=%s' % (url.path, code))
  data = connection.getresponse().read()
  
  #logger.debug(data)
  
  # Controllo se nel file di configurazione è presente il codice di attivazione. #
  if (data.find(code) != -1):
    data2file=open(filepath,'w')
    data2file.write(data)
  else:
    raise Exception('incorrect configuration file.')

  return os.path.exists(filepath)
  
  
def registration(code):
  if len(code)!=32:
    regOK = False
    logger.error("ClientID assente o di errata lunghezza")
    retry=0
    showDialog(RegInfo)
    for retry in range(MAXretry):
      ## Prendo un codice licenza valido sintatticamente  ##
      code = None
      logger.info('Tentativo di registrazione %s di %s' % (retry+1, MAXretry))
      message = "\n    Inserire un codice licenza per %s:    " % SWN
      title = "Tentativo %s di %s" % (retry+1, MAXretry)
      default = "scrivere o incollare qui il codice licenza"
      dlg = wx.TextEntryDialog(None, message, title, default, wx.OK)
      res = dlg.ShowModal()
      code = dlg.GetValue()
      dlg.Destroy()
      logger.info("Codice licenza inserito dall'utente: %s" % code)
      if (res != wx.ID_OK):
        logger.warning('Registration aborted at attemp number %d' %(retry+1))
        break
      
      filepath=paths.CONF_MAIN 
      try:
        if(code != None and len(code) == 32):
          # Prendo il file di configurazione. #
          regOK = getconf(code, filepath, configurationServer)
          if (regOK == True):
            logger.info('Configuration file successfully downloaded and saved')
            showDialog(RegSuccess)
            break
          else:
            logger.error('Configuration file not correctly saved')
            showDialog(ErrorSave)
        else:
          logger.error('Wrong license code')
          showDialog(ErrorCode)
      except Exception as error:
        logger.error('Configuration file not downloaded or incorrect: %s' % error)
        showDialog(ErrorDownload)
      
      if not ( retry+1 < MAXretry ):
        showDialog(ErrorRetry)
        
    if not regOK:
      logger.info('Verifica della registrazione del software fallita')
      showDialog(ErrorRegistration)
    
  else:
    regOK = True
  
  return regOK


if __name__ == '__main__':
  app = wx.PySimpleApp(0)
  registration()
  #getconf('ab0cd1ef2gh3ij4kl5mn6op7qr8st9uv', './../config/client.conf', 'https://finaluser.agcom244.fub.it/Config')
