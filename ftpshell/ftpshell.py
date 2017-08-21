from __future__ import print_function
import argparse
import getpass
import logging
import os
import readline
import signal
import socket
import subprocess
import sys
import traceback
from .ftp import ftp_session
from .auto_completer import Completer
from .ftp.ftp_parser import parse_response_error, connection_closed_error
from .ftp.ftp_session import FtpSession
from .ftp.ftp_session import login_error
from .ftp.ftp_session import cmd_not_implemented_error
from .ftp.ftp_session import LsColors
from .ftpmount import ftp_mount

class cli_error(Exception): pass

def proc_input_args():
    """ Parse command arguments and use them to start a
    ftp session.
    """
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
    while not username:
        username = raw_input('Username: ')
    if username == 'anonymous' and password is None:
        password = 'guest'
    if password is None:
        password = getpass.getpass(prompt='Password:')
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

    def __init__(self, args):
        self.first_attempt = True
        self.args = args

    def get_prompt(self):
        """ Generate color-coded prompt string. """
        if self.ftp.logged_in:
            #if self.ftp.home_dir != '/':
            curr_dir = '~%s' % self.ftp.get_cwd()[len(self.ftp.home_dir):]
            #else:
            #curr_dir = self.ftp.get_cwd().replace('/', '~/')
            return '%s%s%s@%s:%s %s%s>%s ' % (LsColors.OKBLUE, LsColors.BOLD, self.ftp.username,
                                          self.ftp.server, LsColors.ENDC, LsColors.OKGREEN,
                                              curr_dir, LsColors.ENDC)
        else:
            return '%s->%s ' % (LsColors.OKGREEN, LsColors.ENDC)

    def run_command(self, cmd_line):
        """ run a single ftp command on the current ftp session."""

        # If the command is preceded by '!', run it on the local machine.
        if cmd_line[0] == '!':
            subprocess.call(cmd_line[1:], shell=True)
            return
        if cmd_line.strip() == '?':
            cmd = 'help'
            cmd_args = []
        else:
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
            os.chdir(self.mountpoint)
            #print("calling %s on %s" % (cmd_line, self.mountpoint))
            try:
                subprocess.check_call(cmd_line, shell=True)  # , stderr=self.devnull
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
        try:
            while True:
                try:
                    if self.first_attempt:
                        self.first_attempt = False
                        server_addr, server_port, server_path, username, password, mountpoint = proc_input_args()
                        self.ftp = ftp_session.FtpSession(server_addr,
                                                          server_port,
                                                          verbose=self.args.verbose,
                                                          transfer_type=self.args.transfer_type,
                                                          transfer_mode=self.args.transfer_mode)
                        self.completer.set_ftp_session(self.ftp)
                        self.mountpoint = os.path.expanduser('~/.ftpshell/mp')
                        server = server_addr, server_port, server_path
                        user = username, password
                        self.fuse_process_pid = ftp_mount(server, user, self.mountpoint, use_thread=True)
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

                except KeyboardInterrupt:
                    break
                except EOFError:
                    print()
                    break
                except ftp_session.quit_error:
                    print("Goodbye.")
                    break

        except login_error:
            print("Login failed.")
        except ftp_session.cmd_not_implemented_error:
            print("Command not recognized. Please use 'help' to see a list of available commands.")
        except (socket.error, parse_response_error, connection_closed_error, ftp_session.network_error):
            self.ftp.close_server()
            print("Connection was closed by the server.")
        except:
            print("An unexpected error happened.", end='')
            if self.args.logfile:
                logging.error(traceback.print_exc())
                print("Please see log file %s for more information.\n" % self.args.logfile)
            else:
                print(end="\n")

            print("\nClosing ftp session.")
            raise
        finally:
            if hasattr(self, 'ftp') and self.ftp:
                self.ftp.close()
            if hasattr(self, 'fuse_process_pid') and self.fuse_process_pid:
                os.kill(self.fuse_process_pid, signal.SIGINT)
                os.waitpid(self.fuse_process_pid, 0)

'''
usage = ('%sUsage:%s ftpshell [username[:password]@]server[:port] \n' %(LsColors.BOLD, LsColors.ENDC)
            + '\n%sExample usage%s:\n'  %(LsColors.BOLD, LsColors.ENDC)
            + '\tftpshell anonymous@ftp.example.com/upload/\n'
            + '\tftpshell user:passwd@ftp.example.com\n'
            + '\tftpshell user:passwd@ftp.example.com:2121/upload/\n'
        )
'''

def arg_parse(*args, **kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '{{u{:p}}@}server{:port}',
        help='Server and user information. '
             '{u}: user, {p}:password, {server}: remote server, {port}: server port. example: anonymous@ftp.example.com/upload/')
    parser.add_argument(
        '-t', '--transfer-type',
        choices=('binary', 'ascii'),
        default='binary',
        help='Type of data transfer (default: %(default)s).')
    parser.add_argument(
        '-m', '--transfer-mode',
        choices=('active', 'passive'),
        default='passive',
        help='Mode of data transfer (default: %(default)s).')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Increase output verbose level (default: %(default)s).')
    parser.add_argument(
        '-l', '--logfile', default='~/.ftpshell/log',
        help='File to use for logging (default: %(default)s).')

    return parser.parse_args(*args, **kwargs)


def main():
    args = arg_parse()

    # Setup readline to provide tab completion for the command line.
    completer = Completer(ftp_session.FtpSession.get_ftp_commands())
    # we want to treat '/' as part of a word, so override the delimiters
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind('tab: complete')
    readline.set_completer(completer.complete)
    if args.logfile == '~/.ftpshell/log':
        if not os.path.isdir(os.path.expanduser('~/.ftpshell/')):
            try:
                os.mkdir(os.path.expanduser('~/.ftpshell/'))
            except OSError:
                args.logfile = ''
    if args.logfile:
        try:
            logging.basicConfig(filename=args.logfile, level=logging.DEBUG)
        except IOError:
            args.logfile = ''

    cli = FtpCli(args)
    cli.completer = completer
    try:
        cli.proc_cli()
    except cli_error:
        pass
    #except BaseException as e:
    #    print("Received unpexpected exception '%s'. Closing the session." % e.__class__.__name__)

if __name__ == '__main__':
    main()