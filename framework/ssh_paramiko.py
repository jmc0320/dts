import re
import time

import paramiko
import pexpect

from .debugger import aware_keyintr, ignore_keyintr
from .exception import SSHConnectionException, SSHSessionDeadException, TimeoutException
from .utils import GREEN, RED, parallel_lock

"""
Module handle ssh sessions between tester and DUT for windows
Implements send_expect function to send command and get output data.
Also supports transfer files to tester or DUT.
"""

class SSHParamiko:
    #WIN = 'windows'
    #LIN = 'linux'
    def __init__(self, host, username, password, dut_id, os_type):
        self.os_type = os_type
        if self.os_type == "windows":
        #if os_type == self.WIN:
            #self.os_type = os_type
            self.default_prompt = '$'
            self.new_line = '\r\n'
        elif self.os_type == "linux":
        #elif os_type == self.LIN:
            #self.os_type = os_type
            self.default_prompt = '#'
            self.new_line = '\n'
        self.magic_prompt = "MAGIC PROMPT"
        self.logger = None
        self.host = host
        self.username = username
        self.password = password
        self.auto_prompt_reset = False
        self.isAlive = False
        self.shout = []
        self.shin = []
        self.sherr = []
        self.f = open('/home/newuser/terminal.txt', 'a')
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
            if ":" in self.host:
                while retry_times:
                    self.ip = self.host.split(":")[0]
                    self.port = int(self.host.split(":")[1])
                    self.session = paramiko.SSHClient()
                    self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy)
                    try:
                        self.session.connect(
                            self.ip,
                            self.username,
                            22,
                            self.password,
                        )
                        channel = self.session.invoke_shell()
                        self.stdin = channel.makefile('wb')
                        self.stdout = channel.makefile('r')
                        self.isAlive = True
                    except Exception as e:
                        print(e)
                        time.sleep(2)
                        retry_times -= 1
                        print("retry %d times connecting..." % (10 - retry_times))
                    else:
                        break
                else:
                    raise Exception("connect to %s:%s failed" % (self.ip, self.port))
            else:
                self.session = paramiko.SSHClient()
                self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.session.connect(self.host, 22, self.username, self.password)
                channel = self.session.invoke_shell()
                self.stdin = channel.makefile('wb')
                self.stdout = channel.makefile('r')
                self.isAlive = True

            if self.os_type == "linux":
                self.send_expect("stty columns 1000", self.default_prompt)
            if self.os_type == "windows":
                self.send_expect("bash.exe", '$')
            """if self.os_type == self.LIN:
                self.send_expect("stty columns 1000", self.default_prompt)
            if self.os_type == self.WIN:
                self.send_expect("bash.exe", '$')"""
        except Exception as e:
            print(RED(e))
            if getattr(self, "port", None):
                suggestion = (
                    "\nSuggession: Check if the firewall on [ %s ] " % self.ip
                    + "is stopped\n"
                )
                print(GREEN(suggestion))
            raise SSHConnectionException(self.host)

    def init_log(self, logger, name):
        self.logger = logger
        self.logger.info("ssh %s@%s" % (self.username, self.host))

    def send_expect_base(self, command, expected, timeout):
        ignore_keyintr()
        self.clean_session()
        self.session.PROMPT = expected
        self.__sendline(command, expected, timeout)
        self.__prompt(command, timeout)
        aware_keyintr()

        before = self.get_output_before()

        return before

    def send_expect(self, command, expected='null', timeout=15, verify=False):
        if expected == 'null':
            expected = self.default_prompt
        try:
            ret = self.send_expect_base(command, expected, timeout)
            if verify:
                ret_status = self.send_expect_base("echo $?", expected, timeout)
                if not int(ret_status):
                    # Debug
                    print(ret)
                    return ret
                else:
                    self.logger.error("Command: %s failure!" % command)
                    self.logger.error(ret)
                    return int(ret_status)
            else:
                # Debug
                print(ret)
                return ret
        except Exception as e:
            print(
                RED(
                    "Exception happened in [%s] and output is [%s]"
                    % (command, self.get_output_before())
                )
            )
            raise (e)

    def send_command(self, command, timeout=1):
        try:
            ignore_keyintr()
            self.clean_session()
            self.__sendline(command, self.default_prompt, timeout)
            aware_keyintr()
        except Exception as e:
            raise (e)

        output = self.get_session_before(timeout=timeout)
        # self.session.PROMPT = self.session.UNIQUE_PROMPT
        # self.session.prompt(0.1)

        return output

    def clean_session(self):
        self.get_session_before(timeout=0.01)

    def get_session_before(self, timeout=15):
        """
        Get all output before timeout
        """
        ignore_keyintr()
        self.session.PROMPT = self.magic_prompt
        # try:
        #     self.session.prompt(timeout)
        # except Exception as e:
        #     pass

        aware_keyintr()
        before = self.get_output_all()
        self.__flush()
        return before

    def __flush(self):
        """
        Clear all session buffer
        """
        # self.session.buffer = ""
        # self.session.before = ""
        # self.stdout =
        # self.stderr = ""
        # self.stdin = ""

    def __prompt(self, command, timeout):
        string = "Hello world"
        # print("Not sure what to do here")
        # if not self.session.prompt(timeout):
        #     raise TimeoutException(command, self.get_output_all()) from None

    def __sendline(self, command, prompt="null", timeout=1):
        if prompt == 'null':
            prompt = self.default_prompt
        if not self.isalive():
            raise SSHSessionDeadException(self.host)
        if len(command) == 2 and command.startswith("^"):
            self.session.sendcontrol(command[1])
        else:
            cmd = command.strip(self.new_line)
            self.stdin.write(cmd + self.new_line)
            self.stdin.write(self.new_line + self.new_line)
            #self.shin = self.stdin
            self.stdin.flush()

            #self.shout = []
            #self.sherr = []
            exit_status = 0
            done = False
            compare = ""
            re_obj = re.compile(r"\w")
            re_cmd = "".join(re_obj.findall(cmd))
            time.sleep(int(timeout * 0.01))
            for line in self.stdout:
                #print(line.strip())
                self.f.write(self.host + " --- " + line)
                compare = "".join(re_obj.findall(compare))
                terminal_line = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]').sub('', line).replace('\b', '').replace(
                    '\r', '')
                #line = terminal_line
                # If it is a long command, then we need to combine multiple lines together to compare
                #if prompt == 'scp' and done:
                #    ssh_newkey = "Are you sure you want to continue connecting"
                #    if ssh_newkey in line:
                #        self.__sendline('yes', 'scp')
                #        break
                #    elif 'Password' in line or 'password' in line:
                #        self.__sendline(self.scp_password)
                #        break
                #if len(cmd) > 30 and cmd and not done:
                if len(cmd) > 30 and re_cmd in compare and not done:
                    self.shout = []
                    # self.shout.append(line)
                    done = True
                    compare = ""
                elif len(cmd) <= 30 and cmd in str(line) and not done:
                    self.shout = []
                    if '$' in line:
                        line = line.split(cmd, 1)[1]
                        line = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]').sub('', line).replace('\b', '').replace('\r', '')
                        line = line.strip()
                        if len(line) >= 1 and line != '\n':
                            self.shout.append(line)
                    done = True
                elif prompt in str(line) and done:
                    break
                else:
                    if prompt == '#' and '$' in str(line) and done:
                        break
                    # get rid of 'coloring and formatting' special characters
                    # terminal_line = line
                    if terminal_line != '\n':
                        # if terminal_line[-1] == '\n':
                        #     terminal_line[-1]
                        terminal_line = terminal_line.replace("\n","")
                        self.shout.append(terminal_line)
                        compare += terminal_line
            self.stdout.flush()

    def get_output_before(self):
        if not self.isalive():
            raise SSHSessionDeadException(self.host)
        output = self.shout
        before = '\n'.join(output)

        if before == '':
            output = self.sherr
            before = '\n'.join(output)
        before = before.rsplit("\r\n", 1)
        if before[0] == "[PEXPECT]":
            before[0] = ""
        return before[0]

    def get_output_all(self):
        output = self.shout
        output = '\n'.join(output)
        if output == '':
            output = self.sherr
            output = '\n'.join(output)
        output.replace("[PEXPECT]", "")
        return output

    def close(self, force=False):
        self.isAlive = False
        self.session.close()
        self.f.close()

    def isalive(self):
        return self.isAlive

    def copy_file_from(self, src, dst=".", password="", crb_session=None):
        """
        Copies a file from a remote place into local.
        """
        command = "scp -v {0}@{1}:{2} {3}".format(self.username, self.host, src, dst)
        if ":" in self.host:
            command = "scp -v -P {0} -o NoHostAuthenticationForLocalhost=yes {1}@{2}:{3} {4}".format(
                str(self.port), self.username, self.ip, src, dst
            )
        if password == "":
            self._spawn_scp(command, self.password, crb_session)
        else:
            self._spawn_scp(command, password, crb_session)

    def copy_file_to(self, src, dst="~/", password="", crb_session=None):
        """
        Sends a local file to a remote place.
        """
        command = "scp {0} {1}@{2}:{3}".format(src, self.username, self.host, dst)
        if ":" in self.host:
            command = "scp -v -P {0} -o NoHostAuthenticationForLocalhost=yes {1} {2}@{3}:{4}".format(
                str(self.port), src, self.username, self.ip, dst
            )
        else:
            command = "scp -v {0} {1}@{2}:{3}".format(
                src, self.username, self.host, dst
            )
        if password == "":
            self._spawn_scp(command, self.password, crb_session)
        else:
            self._spawn_scp(command, password, crb_session)

    def _spawn_scp(self, scp_cmd, password, crb_session):
        """
        Transfer a file with SCP
        """
        self.logger.info(scp_cmd)
        # if crb_session is not None, copy file from/to crb env
        # if crb_session is None, copy file from/to current dts env
        if crb_session is not None:
            crb_session.session.clean_session()
            crb_session.session.__sendline(scp_cmd)
            p = crb_session.session.session
        # CANT USE PEXPECT ON WINDOWS
        else:
            # if self.os_type == 'linux':
            p = pexpect.spawn(scp_cmd)
            # else:
            #     p = self.session
        # if self.os_type == 'linux':
        time.sleep(0.5)
        ssh_newkey = "Are you sure you want to continue connecting"
        i = p.expect(
            [ssh_newkey, "[pP]assword", "# ", pexpect.EOF, pexpect.TIMEOUT], 120
        )
        if i == 0:  # add once in trust list
            p.sendline("yes")
            i = p.expect([ssh_newkey, "[pP]assword", pexpect.EOF], 2)

        if i == 1:
            time.sleep(0.5)
            p.sendline(password)
            p.expect("Exit status 0", 60)
        if i == 4:
            self.logger.error("SCP TIMEOUT error %d" % i)
        if crb_session is None:
            p.close()
        # else:
        #     time.sleep(0.5)
        #     self.scp_password = password
        #     self.__sendline(scp_cmd, 'scp')

