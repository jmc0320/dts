import time
import re
import pathlib

import paramiko
import paramiko_expect

from .debugger import aware_keyintr, ignore_keyintr
from .exception import SSHConnectionException, SSHSessionDeadException, TimeoutException
from .utils import GREEN, RED, parallel_lock

"""
Module handle ssh sessions between tester and DUT.
Implements send_expect function to send command and get output data.
Also supports transfer files to tester or DUT.
"""
class SSHParamikoExpect:
    def __init__(self, host, username, password, dut_id):
        self.logger = None

        if ":" in host:
            self.host = host.split(":")[0]
            self.port = int(host.split(":")[1])
        else:
            self.host = host
            self.port = 22
        self.username = username
        self.password = password

        self.prompt = r'root@.*:.*#\s+'
        self.current_output = ''

        self.client = None
        self.channel = None

        self._connect_host(dut_id=dut_id)

    @parallel_lock(num=8)
    def _connect_host(self, dut_id=0):
        """
        Create connection to assigned crb, parameter dut_id will be used in
        parallel_lock thus can assure isolated locks for each crb.
        Parallel ssh connections are limited to MaxStartups option in SSHD
        configuration file. By default concurrent number is 10, so default
        threads number is limited to 8 which less than 10. Lock number can
        be modified along with MaxStartups value.
        """
        retry_times = 10
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            while retry_times:
                try:
                    self.client.connect(
                        self.host,
                        self.port,
                        self.username,
                        self.password
                    )
                except Exception as e:
                    print(e)
                    time.sleep(2)
                    retry_times -= 1
                    print("retry %d times connecting..." % (10 - retry_times))
                else:
                    break
            else:
                raise Exception("connect to %s:%s failed" % (self.host, self.port))
        except Exception as e:
            print(RED(e))
            if getattr(self, "port", None):
                suggestion = (
                    "\nSuggession: Check if the firewall on [ %s ] " % self.host
                    + "is stopped\n"
                )
                print(GREEN(suggestion))
            raise SSHConnectionException(self.host)
        # we've connected to paramiko, now let's make a paramiko_expect session
        self.channel = self.client.invoke_shell(term='vt100', width=80, height=24)
        self.channel.settimeout(5)

        # give shell time to initialize
        time.sleep(1)

        # initial terminal setup
        self.send_expect("stty -echo", "#")
        self.send_expect("stty columns 1000", "#")

    def init_log(self, logger, name):
        self.logger = logger
        self.logger.info("ssh %s@%s" % (self.username, self.host))

    def send_expect(self, command, expected, timeout=15, verify=False):
        try:
            output = self._execute_command(command)
            self.current_output = output
            return output
        except Exception as e:
            print(
                RED(
                    "Exception happened in [%s] and output is [%s]"
                    % (command, self.current_output)
                )
            )
            raise (e)

    def send_command(self, command, timeout=1):
        output = self.send_expect(command, expected=self.prompt, timeout=timeout)
        return output

    def get_session_before(self, timeout=15):
        """
        Get all output before timeout
        """
        extra_output = self.__flush()
        if extra_output:
            self.current_output += extra_output
        return self.current_output

    def __flush(self):
        """
        Clear all session buffer
        """
        self._recv()

    def close(self, force=False):
        if force is True:
            self.client.close()
        else:
            if self.isalive():
                self.client.close()

    def isalive(self):
        return self.client.get_transport().is_active()

    def copy_file_from(self, src, dst=".", password="", crb_session=None):
        """
        Copies a file from a remote place into local.
        """
        # TODO
        pass

    def copy_file_to(self, src, dst="~/", password="", crb_session=None):
        """
        Sends a local file to a remote place.
        """
        # create pathlib.Path objects
        full_src_path = pathlib.Path(src).resolve()
        full_dst_path = pathlib.Path(dst)
        
        # fix relative path on remote side - repace ~ with /root
        full_dst_path = pathlib.Path(str(full_dst_path).replace('~', '/root'))

        # get filename from src
        filename = full_src_path.name

        # add filename to dest
        full_dst_path = full_dst_path / filename

        # send via sftp_client
        sftp_client = self.client.open_sftp()
        sftp_client.put(str(full_src_path), str(full_dst_path))
        sftp_client.close()


    def _execute_command(self, command, wait_for_command=1, display=False):
        command = self._format_command(command)
        self._send(command)
        time.sleep(wait_for_command)
        output = self._recv()
        output = self._cleanup_byte_string(output)

        if display:
            print(output, end='')

        return output


    def _format_command(self, command):
        # make sure command ends with a newline character
        tailing_newline = re.compile(r'\n+\s*$')
        if not tailing_newline.search(command):
            command += '\n'
        return command


    def _cleanup_byte_string(self, byte_string):
        # convert to string
        decoded = byte_string.decode()

        # remove ansi codes
        ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
        no_ansi = ansi_escape.sub('', decoded)

        # TODO remove command from beginning
        # TODO remove prompt from end

        return no_ansi


    # will block/timout if send is not ready
    def _send(self, data):
        bytes_sent = 0
        while bytes_sent < len(data):
            bytes_sent += self.channel.send(data[bytes_sent:])
        return bytes_sent


    # will not block
    # might not get everything if there are delays in output
    def _recv(self):
        output = b''
        while self.channel.recv_ready():
            output += self.channel.recv(4096)
        return output

