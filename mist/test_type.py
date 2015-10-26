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

STRING_TYPES = {PING: "ping", 
                FTP_UP: "ftp upload", 
                FTP_DOWN: "ftp download",
                HTTP_UP: "http upload",
                HTTP_DOWN: "http download",
                HTTP_UP_MULTI: "http upload multisession",
                HTTP_DOWN_MULTI: "http download multisession"}
STRING_TYPES_SHORT = {PING: "ping", 
                FTP_UP: "ftp up", 
                FTP_DOWN: "ftp down",
                HTTP_UP: "http up",
                HTTP_DOWN: "http down",
                HTTP_UP_MULTI: "http up multi",
                HTTP_DOWN_MULTI: "http down multi"}


def get_string_type(from_type):
    if from_type in STRING_TYPES:
        return STRING_TYPES[from_type]
    else:
        return ""

def get_string_type_short(from_type):
    if from_type in STRING_TYPES_SHORT:
        return STRING_TYPES_SHORT[from_type]
    else:
        return ""

# TODO add string type

# TEST_PING = TestType(TestType.PING, "ping", "ping")
# TEST_HTTP_UP = TestType(TestType.HTTP_UP, "HTTP upload", "HTTP up")
# TEST_HTTP_DOWN = TestType(TestType.HTTP_DOWN, "HTTP download", "HTTP down")
# TEST_HTTP_MULTI_UP = TestType(TestType.HTTP_UP, "HTTP upload multisessione", "HTTP up multi")
# TEST_HTTP_MULTI_DOWN = TestType(TestType.HTTP_DOWN, "HTTP download multisessione", "HTTP down multi")
# TEST_FTP_UP = TestType(TestType.HTTP_UP, "FTP upload", "FTP up")
# TEST_FTP_DOWN = TestType(TestType.HTTP_DOWN, "FTP download", "FTP down")
