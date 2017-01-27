'''
Handle responses from the server to ftp raw commands.
'''

from enum import Enum

class protocol_error(Exception): pass

class Transfer(object):
    pass

class FtpRawRespHandler(object):
    READ_BLOCK_SIZE = 1024

    @staticmethod
    def get_resp_handler(ftp_cmd = None):
        if ftp_cmd:
            handler = 'handle_' + ftp_cmd.lower()
            if hasattr(FtpRawRespHandler, handler):
                return getattr(FtpRawRespHandler, handler)
        return None

    @staticmethod
    def handle_pasv(resp):
        if (len(resp.lines) != 1):
            raise protocol_error
        resp_line = resp.lines[0].decode('ascii')
        lpos = resp_line.find('(')
        if (lpos == -1):
            raise protocol_error
        resp_line = resp_line[lpos + 1:]
        rpos = resp_line.find(')')
        if (rpos == -1):
            raise protocol_error
        resp_line = resp_line[:rpos]
        ip_port_array = resp_line.split(',')
        if (len(ip_port_array) != 6):
            raise protocol_error
        trans = Transfer()
        trans.server_address = '.'.join(ip_port_array[0:4])
        trans.server_port = (int(ip_port_array[4]) << 8) + int(ip_port_array[5])
        resp.trans = trans

    @staticmethod
    def handle_pwd(resp):
        first_line = resp.lines[0]
        quote = first_line.find(b'"')
        if (quote == -1):
            raise protocol_error
        first_line = first_line[quote + 1:]
        quote = first_line.find(b'"')
        if (quote == -1):
            raise protocol_error
        resp.cwd = first_line[:quote].decode('ascii')

    @staticmethod
    def handle_cwd(resp):
        #resp.cwd = resp.lines[0].split()[-1].decode('ascii')
        pass
