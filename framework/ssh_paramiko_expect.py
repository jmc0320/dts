import time
import re
import pathlib

import paramiko

from .debugger import aware_keyintr, ignore_keyintr
from .exception import SSHConnectionException, SSHSessionDeadException, TimeoutException
from .utils import GREEN, RED, parallel_lock

INPUT_BUFFER_SIZE = 4096

"""
Module handle ssh sessions between tester and DUT.
Implements send_expect function to send command and get output data.
Also supports transfer files to tester or DUT.
"""
class SSHParamikoExpect:
    def __init__(self, host, username, password, dut_id, os='linux'):
        self.logger = None

        if ":" in host:
            self.host = host.split(":")[0]
            self.port = int(host.split(":")[1])
        else:
            self.host = host
            self.port = 22
        self.username = username
        self.password = password
        self.os = os

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

        # initial terminal setup
        self.channel = self.client.invoke_shell(term='vt100', width=80, height=24)
        self.channel.settimeout(5)
        time.sleep(1)
        if self.os == 'windows':
            self.channel.send('bash.exe\r\n')
            self.get_session_before(1)
        self.channel.send(f"PS1='{self.default_prompt}'\n")
        self.get_session_before(1)
        self.send_expect("stty -echo", self.default_prompt)
        self.send_expect("stty columns 1000", self.default_prompt)

    def init_log(self, logger, name):
        self.logger = logger
        self.logger.info("ssh %s@%s" % (self.username, self.host))

    # sets the terminal prompt
    def set_prompt(self, prompt):
        prompt_set_command = f"PS1='{prompt}'"
        self.send_expect(prompt_set_command, prompt)


    # TODO when this is correct, refactor/cleanup
    def send_expect(self, command, expected, timeout=15, verify=False):

        try:
            ignore_keyintr()
            
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

            # TODO this might hang
            # wait for recv to be ready
            while not self.channel.recv_ready():
                time.sleep(0.2)

            # read from recv until expected is found
            # raise TimeoutException if not found before timeout
            output = ''
            found_prompt = False
            start_time = time.time()
            while not found_prompt:
                # check for timeout
                current_time = time.time()
                if current_time - start_time > timeout:
                    raise TimeoutException(command, expected)

                # get INPUT_BUFFER_SIZE bytes, _recv does not block
                current_output_bytes = self._recv()
                if current_output_bytes == '':
                    # if nothing on output, short pause and try again
                    time.sleep(0.1)
                    continue

                # convert bytes to string
                current_output_decoded = current_output_bytes.decode()

                # TODO find last match?
                # check for a match
                match = re_expected.search(current_output_decoded)
                if match:
                    # save everything UP TO but NOT INCLUDING the matched string
                    current_output_decoded = current_output_decoded[:match.start()]
                    found_prompt = True

                # accumulate the output
                output += current_output_decoded
            
            # remove ansi codes
            ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
            no_ansi = ansi_escape.sub('', output)

            # remove \x08 characters in windows output
            extra_char = re.compile(r'\s*\x08')
            no_ansi = extra_char.sub('', no_ansi)

            # reverse-split on last carriage return, split[0] is 'before', split[1] is possible leftovers from prompt...
            output_split = no_ansi.rsplit('\r\n', 1)

            before = output_split[0]

            # save before to current output
            self.current_output = before

            aware_keyintr()

            # check if command returned an error
            # if error, return error code
            if verify:
                ret_status = self.send_expect("echo $?", expected, timeout)
                if not int(ret_status):
                    return before
                else:
                    self.logger.error("Command: %s failure!" % command)
                    self.logger.error(before)
                    return int(ret_status)
            else:
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
        return self.send_expect(command, '#', timeout=timeout)


    def get_session_before(self, timeout=15):
        """
        Get all output before timeout
            1.  disable interrupts
            2.  set expected to "magic prompt"
            3.  prompt(timeout)
                    clear self.current_output
                    read from recv until timeout
            4.  enable interrupts
            5.  get all output
                   no additional step needed, output is in self.current_output 
            6.  flush recv
            7.  return all output
        """
        ignore_keyintr()

        self.current_output = ''
        expected_prompt = 'magic_prompt'

        output = ''
        found_prompt = False
        start_time = time.time()
        while not found_prompt:
            current_time = time.time()
            if current_time - start_time > timeout:
                break

            current_output_bytes = self._recv()
            if current_output_bytes == b'':
                time.sleep(0.1)
                continue

            current_output_decoded = current_output_bytes.decode()
            re_expected = re.compile(expected_prompt)
            match = re_expected.search(current_output_decoded)
            if match:
                current_output_decoded = current_output_decoded[:match.start()]
                found_prompt = True
            output += current_output_decoded

        ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
        no_ansi = ansi_escape.sub('', output)

        output_split = no_ansi.rsplit('\r\n', 1)
        before = output_split[0]
        self.current_output = before

        aware_keyintr()
        self.__flush()
        return before


    def __flush(self):
        """
        Clear all session buffer
        """
        output = b''
        while self.channel.recv_ready():
            output += self.channel.recv(INPUT_BUFFER_SIZE)
            time.sleep(0.1)
        self.current_output = ''
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
        re_string = r'\n+\s*$'
        tailing_newline = re.compile(re_string)
        if not tailing_newline.search(command):
            command += '\n'
        return command

    # non-blocking recv
    # if nothing to receive, returns empty string
    def _recv(self):
        output = b''
        if self.channel.recv_ready():
            output += self.channel.recv(INPUT_BUFFER_SIZE)
        return output

