# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2020 Intel Corporation
# Copyright(c) 2018-2019 The University of New Hampshire
#

"""
DPDK Test suite.
"""
import re

from framework.pmd_output import PmdOutput
from framework.test_case import TestCase


class TestFirmwareVersion(TestCase):
    def set_up_all(self):
        """
        Run at the start of each test suite.
        """
        self.ports = self.dut.get_ports()

        self.pmdout = PmdOutput(self.dut)

    def set_up(self):
        """
        Run before each test case.
        """
        pass

    def check_firmware_version(self, exp_fwversion, fwversion):
        vf = ["major", "minor", "path", "build"]
        fwversion = re.split("\\.", fwversion)
        exp_fwversion = re.split("\\.", exp_fwversion)

        self.verify(len(exp_fwversion) == len(fwversion), "Invalid version format")

        for i in range(len(exp_fwversion)):
            if fwversion[i] != exp_fwversion[i] and i == 0:
                self.verify(
                    False,
                    f"Fail: {vf[i]} version is different expected {exp_fwversion[i]} but was {fwversion[i]}",
                )
            elif fwversion[i] != exp_fwversion[i] and i > 0:
                print(
                    f"Warning: {vf[i]} version is different expected {exp_fwversion[i]} but was {fwversion[i]}"
                )

    def check_format(self, exp, out, name, pattern, match):
        if match is None:
            self.verify(
                re.search(pattern, exp) is not None, f"Invalid expected {name} format"
            )
            self.verify(re.search(pattern, out) is not None, f"Invalid {name} format")
        else:
            exp = re.findall(pattern, exp)
            out = re.findall(pattern, out)

            self.verify(exp[0] == match, f"Invalid expected {name} format")
            self.verify(out[0] == match, f"Invalid {name} format")

    def test_firmware_version(self):
        self.pmdout.start_testpmd("Default")

        # Read the version cfg
        expected_version_list = self.get_suite_cfg()["expected_firmware_version"]

        self.verify(
            self.kdriver in expected_version_list, "driver is not in the cfg file"
        )
        expected_version_info = expected_version_list[self.kdriver]

        for port in self.ports:
            out = self.dut.send_expect(f"show port info {port}", "testpmd> ")
            self.verify("Firmware-version:" in out, "Firmware version not detected")

            version_info = self.pmdout.get_firmware_version(port)

            if self.kdriver == "i40e":
                # Get the version information from output and cfg file
                fwversion, etrackid, networkdriver = version_info.split()
                exp_etrackid, exp_fwversion, exp_networkdriver = expected_version_info
                self.check_format(
                    exp_fwversion, fwversion, "version", r"^\d{1,4}\.\d{1,4}$", None
                )

                self.check_firmware_version(exp_fwversion, fwversion)

                self.check_format(
                    exp_etrackid, etrackid, "etrackid", r"^.{0,6}", "0x8000"
                )

                self.check_format(
                    exp_networkdriver,
                    networkdriver,
                    "network driver",
                    r"^\d{1,4}\.\d{1,4}\.\d{1,4}$",
                    None,
                )

            elif self.kdriver == "mlx5":
                # Get the version information from output and cfg file
                exp_fwversion, exp_psid = expected_version_info
                fwversion, psid = version_info.split()

                self.check_format(
                    exp_fwversion,
                    fwversion,
                    "version",
                    r"^\d{1,4}\.\d{1,4}\.\d{1,4}$",
                    None,
                )

                self.check_firmware_version(exp_fwversion, fwversion)

                # remove "(" and ")" from the string
                psid = re.sub("[()]", "", psid)

                self.check_format(exp_psid, psid, "psid", r"^.{0,3}", "MT_")

            elif self.kdriver == "bnxt":
                # Get the version information from output and cfg file
                exp_pkg, exp_fwversion = expected_version_info
                pkg, fwversion = version_info.split()

                self.check_format(
                    exp_fwversion,
                    fwversion,
                    "version",
                    r"^\d{1,4}\.\d{1,4}\.\d{1,4}\.\d{1,4}$",
                    None,
                )

                self.check_firmware_version(exp_fwversion, fwversion)

                self.check_format(
                    exp_pkg,
                    pkg,
                    "pkg",
                    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\S{1,3}$",
                    None,
                )

            else:
                self.verify(False, f"Test: case fails on {self.kdriver} driver")

    def tear_down(self):
        """
        Run after each test case.
        """
        self.dut.kill_all()

    def tear_down_all(self):
        """
        Run after each test suite.
        """
        self.dut.kill_all()
