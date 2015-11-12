'''
Created on 08/ott/2015

@author: ewedlund
'''


'''Global test types'''
PING_WITH_SLEEP = 0
PING = 1
FTP_UP = 2
FTP_DOWN = 3
HTTP_UP = 4
HTTP_DOWN = 5
HTTP_UP_MULTI = 6
HTTP_DOWN_MULTI = 7
HTTP_DOWN_MULTI_4 = 8
HTTP_DOWN_MULTI_6 = 9
HTTP_DOWN_MULTI_7 = 10
HTTP_DOWN_MULTI_8 = 11
HTTP_DOWN_LONG = 12
HTTP_UP_MULTI_4 = 13
HTTP_UP_MULTI_6 = 14


STRING_TYPES = {PING: "ping", 
                FTP_UP: "ftp upload", 
                FTP_DOWN: "ftp download",
                HTTP_UP: "http upload",
                HTTP_DOWN: "http download",
                HTTP_UP_MULTI: "http upload multisession",
                HTTP_UP_MULTI_4: "http upload 4 sessioni",
                HTTP_UP_MULTI_6: "http upload 6 sessioni",
                HTTP_DOWN_MULTI: "http download multisession",
                HTTP_DOWN_MULTI_4:'http down 4 sessioni',
                HTTP_DOWN_MULTI_6: 'http down 6 sessioni',
                HTTP_DOWN_MULTI_7: 'http down 7 sessioni',
                HTTP_DOWN_MULTI_8: 'http down 8 sessioni',
                HTTP_DOWN_LONG: 'http_down_long'
                }
STRING_TYPES_SHORT = {PING: "ping", 
                FTP_UP: "ftp up", 
                FTP_DOWN: "ftp down",
                HTTP_UP: "http up",
                HTTP_DOWN: "http down",
                HTTP_UP_MULTI: "http up multi",
                HTTP_UP_MULTI_4: "http up multi 4",
                HTTP_UP_MULTI_6: "http up multi 6",
                HTTP_DOWN_MULTI: "http down multi",
                HTTP_DOWN_MULTI_4:'http down 4',
                HTTP_DOWN_MULTI_6: 'http down 6',
                HTTP_DOWN_MULTI_7: 'http down 7',
                HTTP_DOWN_MULTI_8: 'http down 8',
                HTTP_DOWN_LONG: 'http_down_long'
}


def get_string_type(from_type):
    if from_type in STRING_TYPES:
        return STRING_TYPES[from_type]
    else:
        return "Tipo di misura sconosciuta"

def get_string_type_short(from_type):
    if from_type in STRING_TYPES_SHORT:
        return STRING_TYPES_SHORT[from_type]
    else:
        return "sconosciuta"

def get_xml_string(from_type):
    if is_http_up(from_type):
        return "upload_http"
    elif is_http_down(from_type):
        return "download_http"
    elif is_ftp_up(from_type):
        return "upload"
    elif is_ftp_down(from_type):
        return "download"
    elif is_ping(from_type):
        return "ping"
    else:
        return "unknown"

def is_http(from_type):
    if "http" in get_string_type_short(from_type):
        return True
    return False

def is_http_up(from_type):
    if "http up" in get_string_type_short(from_type):
        return True
    return False

def is_http_down(from_type):
    if "http down" in get_string_type_short(from_type):
        return True
    return False

def is_ftp_up(from_type):
    if "ftp up" in get_string_type_short(from_type):
        return True
    return False

def is_ftp_down(from_type):
    if "ftp down" in get_string_type_short(from_type):
        return True
    return False

def is_ping(from_type):
    if "ping" in get_string_type_short(from_type):
        return True
    return False

