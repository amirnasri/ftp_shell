import ftp_session
from ftp_session import connection_closed_error
from ftp_session import response_error
import sys
import getpass
import readline
import types
from ftp_session import login_error
import socket
import subprocess
import os

class cli_error(BaseException): pass

def get_ftp_commands():
    l = []
    for k, v in ftp_session.ftp_session.__dict__.items() :
        if type(v) == types.FunctionType and hasattr(v, 'ftp_command'):
            l.append(k)
    return l

class Completer(object):
    def __init__(self, options):
        self.options = sorted(options)
        return

    def complete(self, text, state):
        #print("\n|text=%s|, state=%d, |line_buffer=%s|\n" % (text, state, readline.get_line_buffer()))
        origline = readline.get_line_buffer()
        begin = readline.get_begidx()
        end = readline.get_endidx()
        being_completed = origline[begin:end]
        words = origline.split()
        print('origline=%s' % repr(origline))
        print('begin=%s' % begin)
        print('end=%s'% end)
        print('being_completed=%s' % being_completed)
        print('words=%s' % words)
        print()
        response = None
        if state == 0:
            # This is the first time for this text, so build a match list.
            if text:
                if text.startswith('put '):
                    fname_prefix = text[4:]
                    listdir = ''
                    #try:
                    #listdir = subprocess.check_output("ls").split()
                    listdir = os.listdir('.')
                    #print(fname_prefix, listdir)
                    #except (subprocess.CalledProcessError, OSError):
                    #    pass
                    self.matches = [s
                                    for s in listdir
                                    if s and s.startswith(fname_prefix)]
                    if len(self.matches) == 1:
                        self.matches = ["put " + i for i in self.matches]

                else:
                    self.matches = [s
                                    for s in self.options
                                    if s and s.startswith(text)]

            else:
                self.matches = self.options[:]

        # Return the state'th item from the match list,
        # if we have that many.
        try:
            response = self.matches[state]
            print("\nresponse=%s" % response)
        except IndexError:
            response = None
        return response

class LoginState:
    ready = 0
    first_attemp = 1
    logged_in = 2

class FtpCli:
    def __init__(self):
        self.first_attempt = True

    def proc_input_args(self):
        ''' Parse command arguments and use them to start a ftp session. 
        '''
        if len(sys.argv) != 2:
            print('Usage: %s [username[:password]@]server[:port]' % sys.argv[0])
            raise cli_error

        username = ''
        password = None
        server_path = ''
        port = 21
        
        arg1 = sys.argv[1]
        server = arg1
        at = arg1.find('@')
        if (at != -1):
            username = arg1[:at]
            server = arg1[at+1:]
        user_colon = username.find(':')
        if (user_colon != -1):
            password = username[user_colon+1:]
            username = username[:user_colon]
        # Pasrse server segment
        slash = server.find('/')
        if (slash != -1):
            server_path = server[slash + 1:]
            server = server[:slash]
        server_colon = server.find(':')
        if (server_colon != -1):
            port = int(server[server_colon+1:])
            server = server[:server_colon]
        '''
        self.username = username
        self.password = password
        self.server = server
        self.server_path = server_path
        self.port = port
        '''
        return server, port, server_path, username, password

    def get_prompt(self):
        if self.ftp.logged_in:
            return '%s@%s: %s> ' % (self.ftp.username, self.ftp.server, self.ftp.get_cwd())
        else:
            return '-> '

    def proc_cli(self):
        ''' Process user input and translate them to appropriate ftp commands.
        '''
        while True:
            if self.first_attempt:
                self.first_attempt = False
                server, port, server_path, username, password = self.proc_input_args()
                self.ftp = ftp_session.ftp_session(server, port)
                try:
                    self.ftp.login(username, password, server_path)
                except login_error:
                    print("Login failed.")
            else:
                #print("|%s|" % self.get_prompt())
                try:
                    cmd_line = input(self.get_prompt())
                    if not cmd_line.strip():
                        continue
                    try:
                        self.ftp.run_command(cmd_line)
                    except response_error:
                        pass

                except login_error:
                    print("Login failed.")
                except ftp_session.cmd_not_implemented_error:
                    print("Command not implemented")
                except (socket.error, connection_closed_error):
                    self.ftp.disconnect()
                    print("Connection was closed by the server.")
                except ftp_session.quit_error:
                    print("Goodbye.")
                    break
                #except BaseException:
                #    print("")
                #    break


if (__name__ == '__main__'):

    readline.set_completer(Completer(get_ftp_commands()).complete)
    readline.parse_and_bind('tab: complete')
    completer_delims = readline.get_completer_delims()
    readline.set_completer_delims(completer_delims.replace(' ', ''))
    def dhook(a, b):
        print("\n+++++++++++args=%s" % str(a))
    readline.set_completion_display_matches_hook(dhook)

    cli = FtpCli()
    try:
        cli.proc_cli()
    except (EOFError, KeyboardInterrupt):
        print("")
    except (cli_error):
        pass
    
