import time
import re
import pathlib

import paramiko

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

        self.default_prompt = '#'
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

        # we've connected to paramiko, now let's make a channel that is connected to a shell session
        self.channel = self.client.invoke_shell(term='vt100', width=80, height=24)

        # default timeout, overridded by timout value given in send_expect
        self.channel.settimeout(5)

        # give shell time to initialize
        time.sleep(1)

        # initial terminal setup
        self.set_prompt(self.default_prompt)
        self.send_expect("stty -echo", self.default_prompt)
        self.send_expect("stty columns 1000", self.default_prompt)

    def init_log(self, logger, name):
        self.logger = logger
        self.logger.info("ssh %s@%s" % (self.username, self.host))

    # overwrites the default prompt
    # call with self.default_prompt to go back to default prompt
    def set_prompt(self, prompt):
        prompt_set_command = f"PS1='{prompt}'"
        self.send_expect(prompt_set_command, prompt)


    def send_expect(self, command, expected, timeout=15, verify=False):
        try:
            ignore_keyintr()
            
            self.channel.settimeout(timeout)

            # flush any output sitting on the recv socket
            self.__flush()

            # clear current output so we can get new output
            self.current_output = ''

            # make sure there is a newline at end of command
            command = self._format_command(command)

            # send command, might take multiple calls to channel.send()
            bytes_sent = 0
            while bytes_sent < len(command):
                bytes_sent += self.channel.send(command[bytes_sent:])

            # setup regex for expected
            expected = expected.strip()
            re_expected = re.compile(expected)

            try:
                output = ''
                found_prompt = False
                while not found_prompt:
                    current_output_bytes = self.channel.recv(4096)
                    current_output_decoded = current_output_bytes.decode()
                    match = re_expected.search(current_output_decoded)
                    if match:
                        # save everything UP TO but NOT INCLUDING the matched string
                        current_output_decoded = current_output_decoded[:match.start()]
                        output += current_output_decoded
                        found_prompt = True
            except Exception as e:
                raise TimeoutException(command, expected)
            
            # remove ansi codes
            ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
            no_ansi = ansi_escape.sub('', output)

            # reverse-split on last carriage return, split[0] is 'before', split[1] is '\r\n' + possible leftovers from prompt...
            output_split = no_ansi.rsplit('\r\n', 1)

            before = output_split[0]

            # save before to current output
            self.current_output = before

            aware_keyintr()

            return before

        except Exception as e:
            print(
                RED(
                    "Exception happened in [%s] and output is [%s]"
                    % (command, self.current_output)
                )
            )
            raise (e)


    def send_command(self, command, timeout=1):
        # this should be no different than send_expect?
        output = self.send_expect(command, '#', timeout=timeout)
        return output

    def get_session_before(self, timeout=15):
        """
        Get all output before timeout
        """
        extra_output = self._recv()
        if extra_output:
            self.current_output += extra_output.decode()
        return self.current_output

    def __flush(self):
        """
        Clear all session buffer
        """
        output = self._recv()
        return output

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


    def _format_command(self, command):
        # make sure command ends with a newline character
        tailing_newline = re.compile(r'\n+\s*$')
        if not tailing_newline.search(command):
            command += '\n'
        return command


    # non-blocking recv
    # if nothing to receive, returns empty string
    def _recv(self):
        output = b''
        while self.channel.recv_ready():
            output += self.channel.recv(4096)
        return output

