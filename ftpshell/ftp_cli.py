import os
import sys
import socket
import readline
import types
from . import ftp_session
from .ftp_session import connection_closed_error
from .ftp_session import response_error
from .ftp_parser import parse_response_error
from .ftp_session import login_error
from .ftp_session import LsColors

class cli_error(BaseException): pass

class FtpCli:
    """ Main class for handling the command-line interface.

    This class provides functions to parse the command-line
    arguments such as username, password, server, and port.
    It then starts an ftp-session using the parsed arguments.
    After a session is established, processing of command-line
    input is delegated to the session.
    """

    def __init__(self):
        self.first_attempt = True

    def proc_input_args(self):
        """ Parse command arguments and use them to start a
        ftp session.
        """
        if len(sys.argv) != 2:
            print('Usage: ftpshell [username[:password]@]server[:port]')
            raise cli_error

        username = ''
        password = None
        server_path = ''
        port = 21
        
        arg1 = sys.argv[1]
        server = arg1
        at = arg1.find('@')
        if at != -1:
            username = arg1[:at]
            server = arg1[at+1:]
        # Parse user segments
        user_colon = username.find(':')
        if user_colon != -1:
            password = username[user_colon+1:]
            username = username[:user_colon]
        # Parse server segments
        slash = server.find('/')
        if slash != -1:
            server_path = server[slash + 1:]
            server = server[:slash]
        server_colon = server.find(':')
        if server_colon != -1:
            port = int(server[server_colon+1:])
            server = server[:server_colon]

        return server, port, server_path, username, password

    def get_prompt(self):
        """ Generate color-coded prompt string. """
        if self.ftp.logged_in:
            return '%s%s%s@%s:%s %s%s>%s ' % (LsColors.OKBLUE, LsColors.BOLD, self.ftp.username,
                                          self.ftp.server, LsColors.ENDC, LsColors.OKGREEN,
                                              self.ftp.get_cwd(), LsColors.ENDC)
        else:
            return '-> '

    def proc_cli(self):
        """ Create an ftp-session and start by logging to the server
        using the user credentials. Then read the input commands from
        the command-line and send them to the ftp session for processing.
        """
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
                try:
                    cmd_line = input(self.get_prompt())
                    if not cmd_line.strip():
                        continue
                    try:
                        # Delegate processing of input command to the
                        # ftp session.
                        self.ftp.run_command(cmd_line)
                    except response_error:
                        pass

                except login_error:
                    print("Login failed.")
                except ftp_session.cmd_not_implemented_error:
                    print("Command not implemented")
                except (socket.error, connection_closed_error, parse_response_error):
                    self.ftp.close_server()
                    print("Connection was closed by the server.")
                except ftp_session.quit_error:
                    print("Goodbye.")
                    break
                except BaseException:
                    print("")
                    break


def get_ftp_commands():
    l = []
    for k, v in ftp_session.ftp_session.__dict__.items() :
        if type(v) == types.FunctionType and hasattr(v, 'ftp_command'):
            l.append(k)
    return l

class Completer(object):
    """ Class to provide tab-completion functionality
    to the command line.
    """
    def __init__(self, options):
        self.options = sorted(options)
        return

    def complete(self, text, state):
        response = None
        if state == 0:
            if text:
                if text.startswith('put '):
                    fname_prefix = text[4:]
                    listdir = os.listdir('.')
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
        except IndexError:
            response = None
        return response

def main():
    # Setup readline to provide tab completion for the command line.
    readline.set_completer(Completer(get_ftp_commands()).complete)
    readline.parse_and_bind('tab: complete')

    cli = FtpCli()
    try:
        cli.proc_cli()
    except (EOFError, KeyboardInterrupt):
        print("")
    except cli_error:
        pass

if __name__ == '__main__':
    main()