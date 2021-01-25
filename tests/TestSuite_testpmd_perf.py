# BSD LICENSE
#
# Copyright(c) 2010-2021 Intel Corporation. All rights reserved.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#   * Neither the name of Intel Corporation nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
DPDK Test suite.
testpmd perf test script.
"""

from test_case import TestCase
from perf_test_base import PerfTestBase, BIN_TYPE, MATCH_MODE, IP_TYPE


class TestPmdPerf(TestCase, PerfTestBase):

    #
    # Test cases.
    #
    @property
    def supported_nics(self):
        return [
            'niantic',
            'fortville_25g',
            'fortville_spirit',
            'columbiaville_100g',
            'columbiaville_25g',
            'ConnectX5_MT4121',
            'ConnectX4_LX_MT4117',
        ]

    def set_up_all(self):
        """
        Run at the start of each test suite.
        """
        self.verify(self.nic in self.supported_nics, "Not required NIC ")
        # Based on h/w type, choose how many ports to use
        self.dut_ports = self.dut.get_ports(self.nic)
        valports = [
            _ for _ in self.dut_ports if self.tester.get_local_port(_) != -1]
        self.logger.debug(valports)
        self.verify_ports_number(valports)
        # get socket and cores
        socket = self.dut.get_numa_id(self.dut_ports[0])
        # init common base class parameters
        PerfTestBase.__init__(self, valports, socket, bin_type=BIN_TYPE.PMD)
        # preset testing environment
        self.perf_preset_test_environment(self.get_suite_cfg())

    def tear_down_all(self):
        """
        Run after each test suite.
        """
        self.perf_test_save_results()
        self.perf_destroy_resource()

    def set_up(self):
        """
        Run before each test case.
        """
        pass

    def tear_down(self):
        """
        Run after each test case.
        """
        self.dut.kill_all()
        self.perf_reset_cur_case()

    def test_perf_rfc2544_ipv4_lpm(self):
        self.perf_set_cur_case('test_perf_rfc2544_ipv4_lpm')
        self.qt_rfc2544(l3_proto=IP_TYPE.V4, mode=MATCH_MODE.LPM)

    def test_perf_rfc2544_ipv6_lpm(self):
        self.perf_set_cur_case('test_perf_rfc2544_ipv6_lpm')
        self.qt_rfc2544(l3_proto=IP_TYPE.V6, mode=MATCH_MODE.LPM)
