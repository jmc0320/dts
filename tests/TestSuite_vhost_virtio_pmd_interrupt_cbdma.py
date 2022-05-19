# BSD LICENSE
#
# Copyright(c) <2022> Intel Corporation.
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
vhost virtio pmd interrupt need test with l3fwd-power sample
"""

import re
import time

import framework.utils as utils
from framework.packet import Packet
from framework.pktgen import PacketGeneratorHelper
from framework.pmd_output import PmdOutput
from framework.test_case import TestCase
from framework.virt_common import VM


class TestVhostVirtioPmdInterruptCbdma(TestCase):
    def set_up_all(self):
        """
        Run at the start of each test suite.
        """
        self.fix_ip = False
        self.nb_cores = 4
        self.queues = 4
        self.dut_ports = self.dut.get_ports()
        self.verify(len(self.dut_ports) >= 1, "Insufficient ports for testing")
        self.ports_socket = self.dut.get_numa_id(self.dut_ports[0])
        self.cores_num = len(
            [n for n in self.dut.cores if int(n["socket"]) == self.ports_socket]
        )
        self.core_list = self.dut.get_core_list("all", socket=self.ports_socket)
        self.core_list_vhost = self.core_list[0:17]
        self.tx_port = self.tester.get_local_port(self.dut_ports[0])
        self.dst_mac = self.dut.get_mac_address(self.dut_ports[0])
        self.logger.info(
            "Please comfirm the kernel of vm greater than 4.8.0 and enable vfio-noiommu in kernel"
        )
        self.out_path = "/tmp"
        out = self.tester.send_expect("ls -d %s" % self.out_path, "# ")
        if "No such file or directory" in out:
            self.tester.send_expect("mkdir -p %s" % self.out_path, "# ")
        # create an instance to set stream field setting
        self.pktgen_helper = PacketGeneratorHelper()
        self.base_dir = self.dut.base_dir.replace("~", "/root")
        self.app_l3fwd_power_path = self.dut.apps_name["l3fwd-power"]
        self.app_testpmd_path = self.dut.apps_name["test-pmd"]
        self.testpmd_name = self.app_testpmd_path.split("/")[-1]
        self.l3fwdpower_name = self.app_l3fwd_power_path.split("/")[-1]
        self.vhost_user = self.dut.new_session(suite="vhost-user")
        self.vhost_pmd = PmdOutput(self.dut, self.vhost_user)
        self.vm_dut = None

    def set_up(self):
        """
        Run before each test case.
        """
        # Clean the execution ENV
        self.verify_info = []
        self.dut.send_expect("killall -s INT %s" % self.testpmd_name, "#")
        self.dut.send_expect("killall -s INT qemu-system-x86_64", "#")
        self.dut.send_expect("rm -rf %s/vhost-net*" % self.base_dir, "#")

    def prepare_vm_env(self):
        """
        rebuild l3fwd-power in vm and set the virtio-net driver
        """
        out = self.vm_dut.build_dpdk_apps("examples/l3fwd-power")
        self.verify("Error" not in out, "compilation l3fwd-power error")
        self.vm_dut.send_expect("modprobe vfio enable_unsafe_noiommu_mode=1", "#")
        self.vm_dut.send_expect("modprobe vfio-pci", "#")
        self.vm_dut.ports_info[0]["port"].bind_driver("vfio-pci")

    def launch_l3fwd_power_in_vm(self):
        """
        launch l3fwd-power with a virtual vhost device
        """
        self.verify(
            len(self.vm_dut.cores) >= self.nb_cores,
            "The vm done not has enought cores to use, please config it",
        )
        core_config = "1S/%dC/1T" % self.nb_cores
        core_list_l3fwd = self.vm_dut.get_core_list(core_config)
        core_mask_l3fwd = utils.create_mask(core_list_l3fwd)

        res = True
        self.logger.info("Launch l3fwd_sample sample:")
        config_info = ""
        for queue in range(self.queues):
            if config_info != "":
                config_info += ","
            config_info += "(%d,%d,%s)" % (0, queue, core_list_l3fwd[queue])
            info = {"core": core_list_l3fwd[queue], "port": 0, "queue": queue}
            self.verify_info.append(info)

        command_client = (
            "./%s " % self.app_l3fwd_power_path
            + "-c %s -n 4 --log-level='user1,7' -- -p 1 -P "
            + "--config '%s' --no-numa  --parse-ptype --interrupt-only"
        )
        command_line_client = command_client % (core_mask_l3fwd, config_info)
        self.vm_dut.get_session_output(timeout=2)
        self.vm_dut.send_expect(command_line_client, "POWER", 40)
        time.sleep(10)
        out = self.vm_dut.get_session_output()
        if "Error" in out and "Error opening" not in out:
            self.logger.error("Launch l3fwd-power sample error")
            res = False
        else:
            self.logger.info("Launch l3fwd-power sample finished")
        self.verify(res is True, "Lanuch l3fwd failed")

    def set_vm_vcpu_number(self):
        # config the vcpu numbers
        params_number = len(self.vm.params)
        for i in range(params_number):
            if list(self.vm.params[i].keys())[0] == "cpu":
                self.vm.params[i]["cpu"][0]["number"] = self.queues

    def start_vms(self, mode=0, packed=False):
        """
        start qemus
        """
        self.vm = VM(self.dut, "vm0", "vhost_sample")
        self.vm.load_config()
        vm_params = {}
        vm_params["driver"] = "vhost-user"
        vm_params["opt_path"] = "%s/vhost-net" % self.base_dir
        vm_params["opt_mac"] = "00:11:22:33:44:55"
        vm_params["opt_queue"] = self.queues
        if not packed:
            opt_param = "mrg_rxbuf=on,csum=on,mq=on,vectors=%d" % (2 * self.queues + 2)
        else:
            opt_param = "mrg_rxbuf=on,csum=on,mq=on,vectors=%d,packed=on" % (
                2 * self.queues + 2
            )
        if mode == 0:
            vm_params["opt_settings"] = "disable-modern=true," + opt_param
        elif mode == 1:
            vm_params["opt_settings"] = "disable-modern=false," + opt_param
        self.vm.set_vm_device(**vm_params)
        self.set_vm_vcpu_number()
        try:
            # Due to we have change the params info before,
            # so need to start vm with load_config=False
            self.vm_dut = self.vm.start(load_config=False)
            if self.vm_dut is None:
                raise Exception("Set up VM ENV failed")
        except Exception as e:
            self.logger.error("ERROR: Failure for %s" % str(e))

    def check_related_cores_status_in_l3fwd(self, out_result, status, fix_ip):
        """
        check the vcpu status
        when tester send fix_ip packet, the cores in l3fwd only one can change the status
        when tester send not fix_ip packets, all the cores in l3fwd will change the status
        """
        change = 0
        for i in range(len(self.verify_info)):
            if status == "waked up":
                info = "lcore %s is waked up from rx interrupt on port %d queue %d"
                info = info % (
                    self.verify_info[i]["core"],
                    self.verify_info[i]["port"],
                    self.verify_info[i]["queue"],
                )
            elif status == "sleeps":
                info = (
                    "lcore %s sleeps until interrupt triggers"
                    % self.verify_info[i]["core"]
                )
            if info in out_result:
                change = change + 1
                self.logger.info(info)
        # if use fix ip, only one cores can waked up/sleep
        # if use dynamic ip, all the cores will waked up/sleep
        if fix_ip is True:
            self.verify(change == 1, "There has other cores change the status")
        else:
            self.verify(change == self.queues, "There has cores not change the status")

    def set_fields(self):
        """
        set ip protocol field behavior
        """
        fields_config = {
            "ip": {
                "dst": {"action": "random"},
            },
        }
        return fields_config

    def send_packets(self):
        tgen_input = []
        if self.fix_ip is True:
            pkt = Packet(pkt_type="UDP")
        else:
            pkt = Packet(pkt_type="IP_RAW")
        pkt.config_layer("ether", {"dst": "%s" % self.dst_mac})
        pkt.save_pcapfile(self.tester, "%s/interrupt.pcap" % self.out_path)
        tgen_input.append(
            (self.tx_port, self.tx_port, "%s/interrupt.pcap" % self.out_path)
        )
        self.tester.pktgen.clear_streams()
        vm_config = self.set_fields()
        if self.fix_ip is True:
            vm_config = None
        streams = self.pktgen_helper.prepare_stream_from_tginput(
            tgen_input, 100, vm_config, self.tester.pktgen
        )
        # set traffic option
        traffic_opt = {"delay": 5, "duration": 20}
        _, pps = self.tester.pktgen.measure_throughput(
            stream_ids=streams, options=traffic_opt
        )

    def send_and_verify(self):
        """
        start to send packets and check the cpu status
        stop to send packets and check the cpu status
        """
        # Send random dest ip address packets to host nic
        # packets will distribute to all queues
        self.fix_ip = False
        self.send_packets()
        out = self.vm_dut.get_session_output(timeout=5)
        self.check_related_cores_status_in_l3fwd(out, "waked up", fix_ip=False)
        self.check_related_cores_status_in_l3fwd(out, "sleeps", fix_ip=False)

        # Send fixed dest ip address packets to host nic
        # packets will distribute to 1 queue
        self.fix_ip = True
        self.send_packets()
        out = self.vm_dut.get_session_output(timeout=5)
        self.check_related_cores_status_in_l3fwd(out, "waked up", fix_ip=True)
        self.check_related_cores_status_in_l3fwd(out, "sleeps", fix_ip=True)

    def get_cbdma_ports_info_and_bind_to_dpdk(self, cbdma_num, allow_diff_socket=False):
        """
        get all cbdma ports
        """
        self.all_cbdma_list = []
        self.cbdma_list = []
        self.cbdma_str = ""
        out = self.dut.send_expect(
            "./usertools/dpdk-devbind.py --status-dev dma", "# ", 30
        )
        device_info = out.split("\n")
        for device in device_info:
            pci_info = re.search("\s*(0000:\S*:\d*.\d*)", device)
            if pci_info is not None:
                dev_info = pci_info.group(1)
                # the numa id of ioat dev, only add the device which on same socket with nic dev
                bus = int(dev_info[5:7], base=16)
                if bus >= 128:
                    cur_socket = 1
                else:
                    cur_socket = 0
                if allow_diff_socket:
                    self.all_cbdma_list.append(pci_info.group(1))
                else:
                    if self.ports_socket == cur_socket:
                        self.all_cbdma_list.append(pci_info.group(1))
        self.verify(
            len(self.all_cbdma_list) >= cbdma_num, "There no enough cbdma device"
        )
        self.cbdma_list = self.all_cbdma_list[0:cbdma_num]
        self.cbdma_str = " ".join(self.cbdma_list)
        self.dut.send_expect(
            "./usertools/dpdk-devbind.py --force --bind=%s %s"
            % (self.drivername, self.cbdma_str),
            "# ",
            60,
        )

    def bind_cbdma_device_to_kernel(self):
        self.dut.send_expect("modprobe ioatdma", "# ")
        self.dut.send_expect(
            "./usertools/dpdk-devbind.py -u %s" % self.cbdma_str, "# ", 30
        )
        self.dut.send_expect(
            "./usertools/dpdk-devbind.py --force --bind=ioatdma  %s" % self.cbdma_str,
            "# ",
            60,
        )

    def stop_all_apps(self):
        """
        close all vms
        """
        if self.vm_dut is not None:
            vm_dut2 = self.vm_dut.create_session(name="vm_dut2")
            vm_dut2.send_expect("killall %s" % self.l3fwdpower_name, "# ", 10)
            # self.vm_dut.send_expect("killall l3fwd-power", "# ", 60, alt_session=True)
            self.vm_dut.send_expect("cp /tmp/main.c ./examples/l3fwd-power/", "#", 15)
            out = self.vm_dut.build_dpdk_apps("examples/l3fwd-power")
            self.vm.stop()
            self.dut.close_session(vm_dut2)
        self.vhost_pmd.quit()

    def test_perf_virtio_interrupt_with_16_queues_and_cbdma_enabled(self):
        """
        Test Case1: Basic virtio interrupt test with 16 queues and cbdma enabled
        """
        self.get_cbdma_ports_info_and_bind_to_dpdk(16, allow_diff_socket=True)
        lcore_dma = (
            f"[lcore{self.core_list_vhost[1]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list[2]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list[3]}@{self.cbdma_list[1]},"
            f"lcore{self.core_list[3]}@{self.cbdma_list[2]},"
            f"lcore{self.core_list[4]}@{self.cbdma_list[3]},"
            f"lcore{self.core_list[5]}@{self.cbdma_list[4]},"
            f"lcore{self.core_list[6]}@{self.cbdma_list[5]},"
            f"lcore{self.core_list[7]}@{self.cbdma_list[6]},"
            f"lcore{self.core_list[8]}@{self.cbdma_list[7]},"
            f"lcore{self.core_list[9]}@{self.cbdma_list[8]},"
            f"lcore{self.core_list[10]}@{self.cbdma_list[9]},"
            f"lcore{self.core_list[11]}@{self.cbdma_list[10]},"
            f"lcore{self.core_list[12]}@{self.cbdma_list[11]},"
            f"lcore{self.core_list[13]}@{self.cbdma_list[12]},"
            f"lcore{self.core_list[14]}@{self.cbdma_list[13]},"
            f"lcore{self.core_list[15]}@{self.cbdma_list[14]},"
            f"lcore{self.core_list[16]}@{self.cbdma_list[15]}]"
        )
        vhost_param = "--nb-cores=16 --rxq=16 --txq=16 --rss-ip --lcore-dma={}".format(
            lcore_dma
        )
        vhost_eal_param = "--vdev 'eth_vhost0,iface=vhost-net,queues=16,dmas=[txq0;txq1;txq2;txq3;txq4;txq5;txq6;txq7;txq8;txq9;txq10;txq11;txq12;txq13;txq14;txq15]'"
        ports = self.cbdma_list
        ports.append(self.dut.ports_info[0]["pci"])
        self.vhost_pmd.start_testpmd(
            cores=self.core_list_vhost,
            ports=ports,
            prefix="vhost",
            eal_param=vhost_eal_param,
            param=vhost_param,
        )
        self.vhost_pmd.execute_cmd("start")
        self.queues = 16
        self.start_vms(mode=0, packed=False)
        self.prepare_vm_env()
        self.nb_cores = 16
        self.launch_l3fwd_power_in_vm()
        self.send_and_verify()

    def test_perf_virtio10_interrupt_with_4_queues_and_cbdma_enabled(self):
        """
        Test Case2: Basic virtio-1.0 interrupt test with 4 queues and cbdma enabled
        """
        self.get_cbdma_ports_info_and_bind_to_dpdk(4)
        lcore_dma = (
            f"[lcore{self.core_list_vhost[1]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list_vhost[2]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list_vhost[3]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list_vhost[3]}@{self.cbdma_list[1]},"
            f"lcore{self.core_list_vhost[4]}@{self.cbdma_list[1]}]"
        )
        vhost_param = "--nb-cores=4 --rxq=4 --txq=4 --rss-ip --lcore-dma={}".format(
            lcore_dma
        )
        vhost_eal_param = (
            "--vdev 'net_vhost0,iface=vhost-net,queues=4,dmas=[txq0;txq1;txq2;txq3]'"
        )
        ports = self.cbdma_list
        ports.append(self.dut.ports_info[0]["pci"])
        self.vhost_pmd.start_testpmd(
            cores=self.core_list_vhost,
            ports=ports,
            prefix="vhost",
            eal_param=vhost_eal_param,
            param=vhost_param,
        )
        self.vhost_pmd.execute_cmd("start")
        self.queues = 4
        self.start_vms(mode=1, packed=False)
        self.prepare_vm_env()
        self.nb_cores = 4
        self.launch_l3fwd_power_in_vm()
        self.send_and_verify()

    def test_perf_packed_ring_virtio_interrupt_with_16_queues_and_cbdma_enabled(self):
        """
        Test Case3: Packed ring virtio interrupt test with 16 queues and cbdma enabled
        """
        self.get_cbdma_ports_info_and_bind_to_dpdk(16, allow_diff_socket=True)
        lcore_dma = (
            f"[lcore{self.core_list_vhost[1]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list[2]}@{self.cbdma_list[0]},"
            f"lcore{self.core_list[3]}@{self.cbdma_list[1]},"
            f"lcore{self.core_list[3]}@{self.cbdma_list[2]},"
            f"lcore{self.core_list[4]}@{self.cbdma_list[3]},"
            f"lcore{self.core_list[5]}@{self.cbdma_list[4]},"
            f"lcore{self.core_list[6]}@{self.cbdma_list[5]},"
            f"lcore{self.core_list[7]}@{self.cbdma_list[6]},"
            f"lcore{self.core_list[8]}@{self.cbdma_list[7]},"
            f"lcore{self.core_list[9]}@{self.cbdma_list[8]},"
            f"lcore{self.core_list[10]}@{self.cbdma_list[9]},"
            f"lcore{self.core_list[11]}@{self.cbdma_list[10]},"
            f"lcore{self.core_list[12]}@{self.cbdma_list[11]},"
            f"lcore{self.core_list[13]}@{self.cbdma_list[12]},"
            f"lcore{self.core_list[14]}@{self.cbdma_list[13]},"
            f"lcore{self.core_list[15]}@{self.cbdma_list[14]},"
            f"lcore{self.core_list[16]}@{self.cbdma_list[15]}]"
        )
        vhost_param = "--nb-cores=16 --rxq=16 --txq=16 --rss-ip --lcore-dma={}".format(
            lcore_dma
        )
        vhost_eal_param = "--vdev 'eth_vhost0,iface=vhost-net,queues=16,dmas=[txq0;txq1;txq2;txq3;txq4;txq5;txq6;txq7;txq8;txq9;txq10;txq11;txq12;txq13;txq14;txq15]'"
        ports = self.cbdma_list
        ports.append(self.dut.ports_info[0]["pci"])
        self.vhost_pmd.start_testpmd(
            cores=self.core_list_vhost,
            ports=ports,
            prefix="vhost",
            eal_param=vhost_eal_param,
            param=vhost_param,
        )
        self.vhost_pmd.execute_cmd("start")
        self.queues = 16
        self.start_vms(mode=0, packed=True)
        self.prepare_vm_env()
        self.nb_cores = 16
        self.launch_l3fwd_power_in_vm()
        self.send_and_verify()

    def tear_down(self):
        """
        Run after each test case.
        """
        self.stop_all_apps()
        self.dut.kill_all()
        self.dut.send_expect("killall -s INT %s" % self.testpmd_name, "#")
        self.dut.send_expect("killall -s INT qemu-system-x86_64", "#")
        self.bind_cbdma_device_to_kernel()

    def tear_down_all(self):
        """
        Run after each test suite.
        """
        self.dut.close_session(self.vhost_user)