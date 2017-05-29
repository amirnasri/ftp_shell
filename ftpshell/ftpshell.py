from __future__ import print_function
import os
import signal
import sys
import socket
from time import sleep
import readline
import subprocess
import traceback
from .ftp import ftp_session
from .ftp.ftp_parser import parse_response_error
from .ftp.ftp_session import FtpSession
from .ftp.ftp_session import login_error
from .ftp.ftp_session import cmd_not_implemented_error
from .ftp.ftp_session import LsColors
#from .ftpmount import ftp_mount
import ftpmount

class cli_error(Exception): pass

def proc_input_args(usage):
    """ Parse command arguments and use them to start a
    ftp session.
    """
    if len(sys.argv) < 2:
        print(usage)
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
        server = arg1[at + 1:]
    # Parse user segments
    user_colon = username.find(':')
    if user_colon != -1:
        password = username[user_colon + 1:]
        username = username[:user_colon]
    # Parse server segments
    slash = server.find('/')
    if slash != -1:
        server_path = server[slash + 1:]
        server = server[:slash]
    server_colon = server.find(':')
    if server_colon != -1:
        port = int(server[server_colon + 1:])
        server = server[:server_colon]
    mountpoint = None
    if len(sys.argv) > 2:
        mountpoint = sys.argv[2]
    return server, port, server_path, username, password, mountpoint


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

    def get_prompt(self):
        """ Generate color-coded prompt string. """
        if self.ftp.logged_in:
            return '%s%s%s@%s:%s %s%s>%s ' % (LsColors.OKBLUE, LsColors.BOLD, self.ftp.username,
                                          self.ftp.server, LsColors.ENDC, LsColors.OKGREEN,
                                              self.ftp.get_cwd(), LsColors.ENDC)
        else:
            return '%s->%s ' % (LsColors.OKGREEN, LsColors.ENDC)

    def run_command(self, cmd_line):
        """ run a single ftp command on the current ftp session."""

        print("run_command %s" % cmd_line)
        # If the command is preceded by a '!', run it on the local machine.
        if cmd_line[0] == '!':
            subprocess.call(cmd_line[1:], shell=True)
            return
        cmd_line_split = cmd_line.split()
        cmd = cmd_line_split[0]
        cmd_args = cmd_line_split[1:]

        # If the command implemented by the FTPSession, use the FTPSession implementation.
        if hasattr(FtpSession, cmd):
            if not self.ftp.logged_in and (cmd != 'user' and cmd != 'quit'):
                print("Not logged in. Please login first with USER and PASS.")
                return
            getattr(FtpSession, cmd)(self.ftp, cmd_args)
        # Otherwise, try to run the command on the locally mounted ftp-server.
        elif self.mountpoint:
            curr_dir = os.getcwd()
            print("chaning dir")
            os.chdir(self.mountpoint)
            print("calling %s on %s" % (cmd_line, self.mountpoint))
            try:
                subprocess.check_call(cmd_line, shell=True)  # , stderr=self.devnull
                print("return successfully")
            except subprocess.CalledProcessError:
                # raise cmd_not_implemented_error
                pass
            finally:
                os.chdir(curr_dir)
        else:
            raise cmd_not_implemented_error

    def proc_cli(self):
        """ Create an ftp-session and start by logging to the server
        using the user credentials. Then read the input commands from
        the command-line and send them to the ftp session for processing.
        """
        while True:
            try:
                if self.first_attempt:
                    self.first_attempt = False
                    usage = 'Usage: ftpshell [username[:password]@]server[:port]'
                    server_addr, server_port, server_path, username, password, mountpoint = proc_input_args(usage)
                    self.ftp = ftp_session.FtpSession(server_addr, server_port, verbose=True)
                    self.mountpoint = os.path.expanduser('~/.ftpshell21')
                    server = server_addr, server_port, server_path
                    user = username, password
                    self.fuse_process_pid = ftpmount.ftp_mount(server, user, self.mountpoint, use_thread=True)
                    print("pid=%s" % self.fuse_process_pid)
                    self.ftp.login(username, password, server_path)
                else:
                        cmd_line = raw_input(self.get_prompt())
                        if not cmd_line.strip():
                            continue

                        try:
                            # Delegate processing of input command to the
                            # ftp session.
                            self.run_command(cmd_line)
                        except ftp_session.response_error:
                            pass

            except login_error:
                print("Login failed.")
            except ftp_session.cmd_not_implemented_error:
                print("Command not recognized. Please use 'help' to see a list of available commands.")
            except (socket.error, parse_response_error, ftp_session.network_error):
                self.ftp.close_server()
                print("Connection was closed by the server.")
            except KeyboardInterrupt:
                break
            except EOFError:
                print()
                break
            except ftp_session.quit_error:
                print("Goodbye.")
                break
            '''
            except:
                print("An unpexpectd error happened with the following stack trace:\n")
                traceback.print_exc()
                print("\nClosing ftp session.")
                break
            '''
        self.ftp.close()
        os.kill(self.fuse_process_pid, signal.SIGINT)
        os.waitpid(self.fuse_process_pid, 0)
        print("fuse_process joined!")

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
    readline.set_completer(Completer(ftp_session.FtpSession.get_ftp_commands()).complete)
    readline.parse_and_bind('tab: complete')

    cli = FtpCli()
    try:
        cli.proc_cli()
    except cli_error:
        pass
    #except BaseException as e:
    #    print("Received unpexpected exception '%s'. Closing the session." % e.__class__.__name__)

if __name__ == '__main__':
    main()