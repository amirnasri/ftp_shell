'''
Handle responses from the server to ftp raw commands.
'''

from enum import Enum

class response_parse_error(Exception): pass

class transfer(object):
    pass


class response:
    def __init__(self):
        self.is_complete = False
        self.lines = []
        self.multiline = False
        self.resp_code = 0
        
    def process_newline(self, newline):
        if not self.multiline:
            # Only the first line of response comes here (for both single-line and multiline responses).
            resp_code = int(newline[:3])
            if (resp_code > 100 and resp_code < 600 and
                    (chr(newline[3]) == ' ' or chr(newline[3]) == '-')):
                self.resp_code = resp_code
            else:
                raise response_parse_error
            
            if (chr(newline[3]) == '-'):
                self.multiline = True
            else:
                self.is_complete = True
        else:
            if (int(newline[:3]) == self.resp_code and chr(newline[3]) == ' '):
                self.is_complete = True
        
    def process_string(self, s):
        ''' Parse a string received from the server into lines
        and then process each line. ''' 
        while True:
            # TODO: change '\r\n' to '\r*\n'
            rn_pos = s.find(b'\r\n')
            if (rn_pos == -1):
                break
            newline = s[:rn_pos + 2]
            s = s[rn_pos + 2:]
            self.process_newline(newline)
            self.lines.append(newline)
        return s

    def print_resp(self):
        for l in self.lines:
            print(l.decode('ascii'), end = '')
        print("")


class ftp_resp_type(Enum):
    interm = 1
    successful = 2
    more_needed = 3
    fail = 4
    error = 5

class ftp_client_parser:
    def __init__(self):
        self.buff = bytearray()
        self.resp = None

    @staticmethod
    def resp_failed(resp):
        return resp.type == ftp_resp_type.error\
               or resp.type == ftp_resp_type.fail

    def get_resp(self, str, verbose):
        if not self.resp:
            self.resp = response()
        resp = self.resp
        self.buff = resp.process_string(self.buff + str)
        if resp.is_complete:
            resp.type = ftp_resp_type(int(resp.resp_code / 100))
            if verbose:
                resp.print_resp()
            self.resp = None
            return resp
        return None
