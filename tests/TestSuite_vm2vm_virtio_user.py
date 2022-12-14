# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2019 Intel Corporation
#

"""
DPDK Test suite.

Test cases for vm2vm virtio-user
This suite include split virtqueue vm2vm in-order mergeable, in-order non-mergeable,
mergeable, non-mergeable, vector_rx path test
and packed virtqueue vm2vm in-order mergeable, in-order non-mergeable,
mergeable, non-mergeable path test
"""
import re
import time

from framework.packet import Packet
from framework.pmd_output import PmdOutput
from framework.test_case import TestCase


class TestVM2VMVirtioUser(TestCase):
    def set_up_all(self):
        self.memory_channel = self.dut.get_memory_channels()
        self.dump_virtio_pcap = "/tmp/pdump-virtio-rx.pcap"
        self.dump_vhost_pcap = "/tmp/pdump-vhost-rx.pcap"
        self.vhost_prefix = "vhost"
        self.virtio_prefix_0 = "virtio0"
        self.virtio_prefix_1 = "virtio1"
        socket_num = len(set([int(core["socket"]) for core in self.dut.cores]))
        self.socket_mem = ",".join(["1024"] * socket_num)
        self.get_core_list()
        self.rebuild_flag = False
        self.app_pdump = self.dut.apps_name["pdump"]
        self.dut_ports = self.dut.get_ports()
        self.cbdma_dev_infos = []
        self.ports_socket = self.dut.get_numa_id(self.dut_ports[0])
        self.vhost_user = self.dut.new_session(suite="vhost-user")
        self.virtio_user0 = self.dut.new_session(suite="virtio-user0")
        self.virtio_user1 = self.dut.new_session(suite="virtio-user1")
        self.pdump_user = self.dut.new_session(suite="pdump-user")
        self.vhost_user_pmd = PmdOutput(self.dut, self.vhost_user)
        self.virtio_user0_pmd = PmdOutput(self.dut, self.virtio_user0)
        self.virtio_user1_pmd = PmdOutput(self.dut, self.virtio_user1)
        self.dump_port = "device_id=net_virtio_user1"

    def set_up(self):
        """
        run before each test case.
        """
        self.nopci = True
        self.queue_num = 1
        self.dut.send_expect("rm -rf ./vhost-net*", "#")
        self.dut.send_expect("rm -rf %s" % self.dump_virtio_pcap, "#")
        self.dut.send_expect("rm -rf %s" % self.dump_vhost_pcap, "#")

    def get_core_list(self):
        """
        create core mask
        """
        self.core_config = "1S/6C/1T"
        self.cores_list = self.dut.get_core_list(self.core_config)
        self.verify(
            len(self.cores_list) >= 6, "There no enough cores to run this suite"
        )
        self.core_list_vhost = self.cores_list[0:2]
        self.core_list_virtio0 = self.cores_list[2:4]
        self.core_list_virtio1 = self.cores_list[4:6]

    def launch_vhost_testpmd(
        self, vdev_num, fixed_prefix=False, fwd_mode="io", vdevs=None, no_pci=True
    ):
        eal_params = ""
        if vdevs:
            eal_params = vdevs
            params = "--nb-cores=1 --rxq=2 --txq=2 --txd=4096 --rxd=4096 --no-flush-rx"
        else:
            for i in range(vdev_num):
                eal_params += (
                    "--vdev 'net_vhost{},iface=./vhost-net{},queues={}' ".format(
                        i, i, self.queue_num
                    )
                )
            params = "--nb-cores=1 --no-flush-rx"
        self.vhost_user_pmd.start_testpmd(
            cores=self.core_list_vhost,
            param=params,
            eal_param=eal_params,
            no_pci=no_pci,
            ports=[],
            prefix=self.vhost_prefix,
            fixed_prefix=fixed_prefix,
        )
        self.vhost_user_pmd.execute_cmd("set fwd %s" % fwd_mode)

    @property
    def check_2M_env(self):
        out = self.dut.send_expect(
            "cat /proc/meminfo |grep Hugepagesize|awk '{print($2)}'", "# "
        )
        return True if out == "2048" else False

    def start_virtio_testpmd_with_vhost_net1(self, path_mode, extern_params, ringsize):
        """
        launch the testpmd as virtio with vhost_net1
        """
        eal_params = (
            " --socket-mem {} --vdev=net_virtio_user1,mac=00:01:02:03:04:05,path=./vhost-net1,queues={},{},"
            "queue_size={} ".format(
                self.socket_mem, self.queue_num, path_mode, ringsize
            )
        )
        if self.check_2M_env:
            eal_params += " --single-file-segments"
        if "vectorized_path" in self.running_case:
            eal_params += " --force-max-simd-bitwidth=512"
        params = "--nb-cores=1 --txd={} --rxd={} {}".format(
            ringsize, ringsize, extern_params
        )
        self.virtio_user1_pmd.start_testpmd(
            cores=self.core_list_virtio1,
            param=params,
            eal_param=eal_params,
            no_pci=True,
            ports=[],
            prefix=self.virtio_prefix_1,
            fixed_prefix=True,
        )
        self.virtio_user1_pmd.execute_cmd("set fwd rxonly")
        self.virtio_user1_pmd.execute_cmd("start")

    def start_virtio_testpmd_with_vhost_net0(self, path_mode, extern_params, ringsize):
        """
        launch the testpmd as virtio with vhost_net0
        and start to send 251 small packets with diff burst
        """
        eal_params = (
            " --socket-mem {} --vdev=net_virtio_user0,mac=00:01:02:03:04:05,path=./vhost-net0,queues={},"
            "{},queue_size={} ".format(
                self.socket_mem, self.queue_num, path_mode, ringsize
            )
        )
        if self.check_2M_env:
            eal_params += " --single-file-segments"
        if "vectorized_path" in self.running_case:
            eal_params += " --force-max-simd-bitwidth=512"
        params = "--nb-cores=1 --txd={} --rxd={} {}".format(
            ringsize, ringsize, extern_params
        )
        self.virtio_user0_pmd.start_testpmd(
            cores=self.core_list_virtio0,
            param=params,
            eal_param=eal_params,
            no_pci=True,
            ports=[],
            prefix=self.virtio_prefix_0,
            fixed_prefix=True,
        )
        self.virtio_user0_pmd.execute_cmd("set burst 1")
        self.virtio_user0_pmd.execute_cmd("start tx_first 27")
        self.virtio_user0_pmd.execute_cmd("stop")
        self.virtio_user0_pmd.execute_cmd("set burst 32")
        self.virtio_user0_pmd.execute_cmd("start tx_first 7")

    def send_32_2k_pkts_from_virtio0(self):
        """
        send 32 2k length packets from virtio_user0 testpmd
        """
        self.virtio_user0_pmd.execute_cmd("stop")
        self.virtio_user0_pmd.execute_cmd("set burst 32")
        self.virtio_user0_pmd.execute_cmd("set txpkts 2000")
        self.virtio_user0_pmd.execute_cmd("start tx_first 1")

    def launch_pdump_to_capture_pkt(self, dump_port, file_prefix, filename):
        """
        launch pdump app with dump_port and file_prefix
        the pdump app should start after testpmd started
        if dump the vhost-testpmd, the vhost-testpmd should started before launch pdump
        if dump the virtio-testpmd, the virtio-testpmd should started before launch pdump
        """
        eal_params = self.dut.create_eal_parameters(
            cores="Default", prefix=file_prefix, fixed_prefix=True, ports=[]
        )
        command_line = (
            self.app_pdump
            + " %s -v -- "
            + "--pdump  '%s,queue=*,rx-dev=%s,mbuf-size=8000'"
        )
        self.pdump_user.send_expect(
            command_line % (eal_params, dump_port, filename), "Port"
        )

    def get_dump_file_of_virtio_user(self, path_mode, extern_param, ringsize):
        """
        get the dump file of virtio user
        the virtio_user0 always send 251 small pkts + 32 large pkts(8k) to verify
        how many pkts can received by virtio1
        """
        dump_port = "device_id=net_virtio_user1"
        self.launch_vhost_testpmd(vdev_num=2)
        self.start_virtio_testpmd_with_vhost_net1(path_mode, extern_param, ringsize)
        self.launch_pdump_to_capture_pkt(
            dump_port, self.virtio_prefix_1, self.dump_virtio_pcap
        )
        # the virtio0 will send 251 small pkts
        self.start_virtio_testpmd_with_vhost_net0(path_mode, extern_param, ringsize)
        # then send 32 large pkts
        self.virtio_user0_pmd.execute_cmd("stop")
        self.virtio_user0_pmd.execute_cmd("set burst 32")
        self.virtio_user0_pmd.execute_cmd("set txpkts 2000,2000,2000,2000")
        self.virtio_user0_pmd.execute_cmd("start tx_first 1")
        # packet will fwd after vhost testpmd start
        self.vhost_user_pmd.execute_cmd("start")

    def get_dump_file_of_vhost_user(self, path_mode, extern_params, ringsize):
        """
        get the dump file of vhost testpmd
        the virtio0 will alway send 251 small pkts + some large pkts(depend on
        diff path_mode send diff pkts num) to verify how many pkts can received by vhost
        """
        dump_port = "port=0"
        self.launch_vhost_testpmd(vdev_num=1, fixed_prefix=True, fwd_mode="rxonly")
        self.vhost_user_pmd.execute_cmd("start")
        self.launch_pdump_to_capture_pkt(
            dump_port, self.vhost_prefix, self.dump_vhost_pcap
        )
        # the virtio0 send 251 small pkts
        self.start_virtio_testpmd_with_vhost_net0(path_mode, extern_params, ringsize)
        # if the path_mode is mergeable, then send large pkt to verify
        # and packed mergeable and split mergeable is diff about large pkt
        # in packed mergeable, 1 large pkt will occupies 5 ring, so send 1 large pkt to verify
        # in split mergeable, 1 large pkt will occupied 1 ring, so send 5 large pkt to verify
        mergeable = re.search("mrg_rxbuf\s*=\s*1", path_mode)
        split = re.search("packed_vq\s*=\s*0", path_mode)
        no_inorder = re.search("in_order\s*=\s*1", path_mode)
        pkt_num = 5
        if split and mergeable and no_inorder:
            pkt_num = 1
        if mergeable:
            self.virtio_user0_pmd.execute_cmd("stop")
            self.virtio_user0_pmd.execute_cmd("set burst %d" % pkt_num)
            self.virtio_user0_pmd.execute_cmd("set txpkts 2000,2000,2000,2000")
            self.virtio_user0_pmd.execute_cmd("start tx_first 1")

    def check_packet_payload_valid(self, filename, check_dict):
        """
        check the payload is valid
        """
        self.pdump_user.send_expect("^c", "# ", 60)
        self.dut.session.copy_file_from(src=filename, dst=filename)
        pkt = Packet()
        pkts = pkt.read_pcapfile(filename)
        for key, value in check_dict.items():
            count = 0
            for i in range(len(pkts)):
                if len(pkts[i]) == key:
                    count += 1
            self.verify(
                value == count,
                "pdump file: have not include enough packets, length %d, count: %d"
                % (key, count),
            )

    def check_vhost_and_virtio_pkts_content(self):
        """
        vhost received pkts in self.dump_vhost_pcap, virtio received pkts self.dump_virtio_pcap
        check headers and payload of all pkts are same.
        """
        pk_rx_virtio = Packet()
        pk_rx_vhost = Packet()
        pk_rx_virtio.read_pcapfile(self.dump_virtio_pcap)
        pk_rx_vhost.read_pcapfile(self.dump_vhost_pcap)
        # check the headers and payload is same of vhost and virtio
        for i in range(len(pk_rx_virtio)):
            self.verify(
                pk_rx_virtio[i].haslayer("Raw"),
                "The pkt index %d, virtio pkt has no layer Raw" % i,
            )
            self.verify(
                pk_rx_vhost[i].haslayer("Raw"),
                "The pkt index %d, vhost pkt has no layer Raw" % i,
            )
            self.verify(
                pk_rx_virtio[i].haslayer("UDP"),
                "The pkt index %d, virtio pkt has no layer UDP" % i,
            )
            self.verify(
                pk_rx_vhost[i].haslayer("UDP"),
                "The pkt index %d, vhost pkt has no layer UDP" % i,
            )
            rx_virtio_load = pk_rx_virtio[i]["Raw"].load
            rx_vhost_load = pk_rx_vhost[i]["Raw"].load
            rx_virtio_head = pk_rx_virtio[i]["UDP"].remove_payload()
            rx_vhost_head = pk_rx_vhost[i]["UDP"].remove_payload()
            # check header is same
            self.verify(
                pk_rx_virtio[i] == pk_rx_vhost[i],
                "the head is different on index: %d" % i
                + "virtio head: %s, vhost head: %s"
                % (pk_rx_virtio[i].show, pk_rx_vhost[i].show()),
            )
            # check payload is same
            self.verify(
                len(rx_virtio_load) == len(rx_vhost_load),
                "the len is diff between virtio pcap and vhost pcap,"
                "virtio len:%d, vhost len: %d"
                % (len(rx_virtio_load), len(rx_vhost_load)),
            )
            diff_list = [
                s
                for s in range(len(rx_virtio_load))
                if rx_virtio_load[s] != rx_vhost_load[s]
            ]
            self.verify(
                len(diff_list) == 0,
                "there have some diff between the load of virtio and vhost pcap"
                + "pkt index is: %d, the load index include %s" % (i, diff_list),
            )

    def quit_all_testpmd(self):
        self.vhost_user_pmd.quit()
        self.virtio_user0_pmd.quit()
        self.virtio_user1_pmd.quit()
        self.pdump_user.send_expect("^c", "# ", 60)

    def test_vm2vm_virtio_user_packed_virtqueue_mergeable_path(self):
        """
        Test Case 1: packed virtqueue vm2vm mergeable path test
        about packed virtqueue path, the 8k length pkt will occupies 1 ring since indirect feature enabled
        """
        path_mode = "packed_vq=1,mrg_rxbuf=1,in_order=0"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 256 pkts
        # then resend 32(5 8k and 32 2k) large pkts, all will received
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.send_32_2k_pkts_from_virtio0()
        check_dict = {64: 251, 2000: 32, 8000: 5}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.send_32_2k_pkts_from_virtio0()
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_inorder_mergeable_path(self):
        """
        Test Case 2: packed virtqueue vm2vm inorder mergeable path test
        about packed inorder mergeable path, the 8k length pkt will occupies 1 ring since indirect feature enabled
        """
        path_mode = "packed_vq=1,mrg_rxbuf=1,in_order=1"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 256 pkts
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        check_dict = {64: 251, 2000: 0, 8000: 5}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_no_mergeable_path(self):
        """
        Test Case 3: packed virtqueue vm2vm non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=1,mrg_rxbuf=0,in_order=0"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        # the no-mergeable path can not received large pkts
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_inorder_no_mergeable_path(self):
        """
        Test Case 4: packed virtqueue vm2vm inorder non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=1,mrg_rxbuf=0,in_order=1,vectorized=1"
        extern_params = "--rx-offloads=0x10"
        ringsize = 256
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        # the no-mergeable path can not received large pkts
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_vectorized_path(self):
        """
        Test Case 10: packed virtqueue vm2vm inorder non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=1,mrg_rxbuf=0,in_order=1,vectorized=1"
        extern_params = ""
        ringsize = 256
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        # the no-mergeable path can not received large pkts
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_vectorized_path_ringsize_not_powerof_2(
        self,
    ):
        """
        Test Case 11: packed virtqueue vm2vm inorder non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=1,mrg_rxbuf=0,in_order=1,vectorized=1"
        extern_params = ""
        ringsize = 255
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        # the no-mergeable path can not received large pkts
        self.logger.info("check pcap file info about virtio")
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_split_virtqueue_mergeable_path(self):
        """
        Test Case 5: split virtqueue vm2vm mergeable path test
        about split virtqueue path, the 8k length pkt will occupies 1 ring,
        so, as the rxt=256, if received pkts include 8k chain pkt, also will received up to 256 pkts
        """
        path_mode = "packed_vq=0,mrg_rxbuf=1,in_order=0"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 256 pkts
        # then virtio send 32 large pkts, the virtio will all received
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 32, 8000: 5}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.send_32_2k_pkts_from_virtio0()
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.send_32_2k_pkts_from_virtio0()
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_split_virtqueue_inorder_mergeable_path(self):
        """
        Test Case 6: split virtqueue vm2vm inorder mergeable path test
        about split virtqueue path, the 8k length pkt will occupies 5 ring,
        2000,2000,2000,2000 will need 4 consequent ring, still need one ring put header
        so, as the rxt=256, if received pkts include 8k chain pkt, it will received up to 252 pkts
        """
        path_mode = "packed_vq=0,mrg_rxbuf=1,in_order=1"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 252 pkts
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 0, 8000: 1}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_split_virtqueue_no_mergeable_path(self):
        """
        Test Case 7: split virtqueue vm2vm non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=0,mrg_rxbuf=0,in_order=0,vectorized=1"
        ringsize = 256
        extern_params = "--enable-hw-vlan-strip"
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_split_virtqueue_inorder_no_mergeable_path(self):
        """
        Test Case 8: split virtqueue vm2vm inorder non-mergeable path test
        about non-mergeable path, it can not received large pkts
        """
        path_mode = "packed_vq=0,mrg_rxbuf=0,in_order=1"
        ringsize = 256
        extern_params = "--rx-offloads=0x10"
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_split_virtqueue_vector_rx_path(self):
        """
        Test Case 9: split virtqueue vm2vm vector_rx path test
        about vector_rx path, it can not received large pkts
        """
        path_mode = "packed_vq=0,mrg_rxbuf=0,in_order=0,vectorized=1"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        # the virtio0 will send 283 pkts, but the virtio only will received 251 pkts
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 0, 8000: 0}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)
        # get dump pcap file of vhost
        self.logger.info("check pcap file info about vhost")
        self.quit_all_testpmd()
        self.get_dump_file_of_vhost_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_vhost_pcap, check_dict)
        self.logger.info("diff the pcap file of vhost and virtio")
        self.check_vhost_and_virtio_pkts_content()

    def test_vm2vm_virtio_user_packed_virtqueue_vectorized_path_test_indirect_desc(
        self,
    ):
        """
        Test Case 12: packed virtqueue vm2vm vectorized-tx path multi-queues test indirect descriptor
        """
        path_mode = "packed_vq=1,mrg_rxbuf=1,in_order=1,vectorized=1"
        ringsize = 256
        extern_params = ""
        # get dump pcap file of virtio
        self.logger.info("check pcap file info about virtio")
        check_dict = {64: 251, 2000: 0, 8000: 5}
        self.get_dump_file_of_virtio_user(path_mode, extern_params, ringsize)
        self.check_packet_payload_valid(self.dump_virtio_pcap, check_dict)

    def close_all_session(self):
        if getattr(self, "vhost_user", None):
            self.dut.close_session(self.vhost_user)
        if getattr(self, "virtio-user0", None):
            self.dut.close_session(self.virtio_user0)
        if getattr(self, "virtio-user1", None):
            self.dut.close_session(self.virtio_user1)
        if getattr(self, "pdump_session", None):
            self.dut.close_session(self.pdump_user)

    def tear_down(self):
        """
        Run after each test case.
        """
        self.quit_all_testpmd()
        self.dut.kill_all()
        time.sleep(2)

    def tear_down_all(self):
        """
        Run after each test suite.
        """
        self.close_all_session()
