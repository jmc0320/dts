import unittest
from unittest import mock

from framework import ssh_connection
from framework import utils
from framework import exception

class ConnectionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        utils.create_parallel_locks(1)

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.host = '10.166.189.48'
        self.session_name = 'Test Session'
        self.username = 'root'
        self.password = 's'

        self.session = ssh_connection.SSHConnection(
                self.host,
                self.session_name,
                self.username,
                self.password)

        self.logger = mock.Mock()
        self.session.init_log(self.logger)

    def tearDown(self):
        self.session.close()

    def test_session_initialized(self):
        self.assertIsNotNone(self.session)

    def test_echo_msg(self):
        cmd = "echo 'test message'"
        prompt = '#'
        output = self.session.send_expect(cmd, prompt, timeout = 15, verify=False)
        self.assertEqual(output, 'test message')

    def test_python_prompt(self):
        output = self.session.send_expect('python3', '>>>', timeout=15, verify=False)
        output = self.session.send_expect('quit()', '#', timeout=15, verify=False)

    def test_scapy_prompt(self):
        output = self.session.send_expect('scapy', '>>>', timeout=15, verify=False)
        output = self.session.send_expect('quit()', '#', timeout=15, verify=False)

    def test_whitspace_in_prompt(self):
        cmd = "echo 'test message'"
        white_space_prompt = '# '
        output = self.session.send_expect(cmd, white_space_prompt, timeout = 15, verify=False)
        self.assertEqual(output, 'test message')

    def test_timeout_on_bad_expect(self):
        cmd = 'ls -la'
        bad_expected = 'bad_prompt'
        self.assertRaises(exception.TimeoutException, self.session.send_expect, cmd, bad_expected, timeout=3, verify=False)

    def test_verify_flag_true_valid_command(self):
        cmd = "echo 'test message'"
        prompt = '#'
        output = self.session.send_expect(cmd, prompt, timeout = 15, verify=True)
        self.assertEqual(output, 'test message')

    def test_verify_flag_true_invalid_command(self):
        invalid_cmd = "asdf"
        prompt = '#'
        output = self.session.send_expect(invalid_cmd, prompt, timeout = 15, verify=True)
        self.assertEqual(output, 127)


if __name__ == '__main__':
    unittest.main()
