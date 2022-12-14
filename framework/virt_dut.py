# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2010-2015 Intel Corporation
#

import os
import re
import time

import framework.settings as settings
from nics.net_device import GetNicObj, RemoveNicObj

from .config import AppNameConf, PortConf
from .dut import Dut
from .project_dpdk import DPDKdut
from .settings import LOG_NAME_SEP, NICS, get_netdev, load_global_setting
from .utils import RED, parallel_lock


class VirtDut(DPDKdut):

    """
    A connection to the CRB under test.
    This class sends commands to the CRB and validates the responses. It is
    implemented using either ssh for linuxapp or the terminal server for
    baremetal.
    All operations are in fact delegated to an instance of either CRBLinuxApp
    or CRBBareMetal.
    """

    def __init__(
        self, hyper, crb, serializer, virttype, vm_name, suite, cpu_topo, dut_id
    ):
        self.vm_ip = crb["IP"]
        self.NAME = "virtdut" + LOG_NAME_SEP + "%s" % self.vm_ip
        # do not create addition alt_session
        super(VirtDut, self).__init__(
            crb, serializer, dut_id, self.NAME, alt_session=False
        )
        self.vm_name = vm_name
        self.hyper = hyper
        self.host_dut = hyper.host_dut
        self.cpu_topo = cpu_topo
        self.migration_vm = False

        # load port config from suite cfg
        self.suite = suite

        self.number_of_cores = 0
        self.tester = None
        self.cores = []
        self.architecture = None
        self.ports_map = []
        self.virttype = virttype
        self.prefix_subfix = (
            str(os.getpid()) + "_" + time.strftime("%Y%m%d%H%M%S", time.localtime())
        )
        self.apps_name_conf = {}
        self.apps_name = {}

    def init_log(self):
        if hasattr(self.host_dut, "test_classname"):
            self.logger.config_suite(self.host_dut.test_classname, "virtdut")

    def close(self, force=False):
        if self.session:
            self.session.close(force)
            self.session = None
        RemoveNicObj(self)

    def set_nic_type(self, nic_type):
        """
        Set CRB NICS ready to validated.
        """
        self.nic_type = nic_type
        # vm_dut config will load from vm configuration file

    @parallel_lock()
    def load_portconf(self):
        """
        Load port config for this virtual machine
        """
        self.conf = PortConf()
        self.conf.load_ports_config(self.vm_name)
        self.ports_cfg = self.conf.get_ports_config()

    @parallel_lock()
    def detect_portmap(self, dut_id):
        """
        Detect port mapping with ping6 message, should be locked for protect
        tester operations.
        """
        # enable tester port ipv6
        self.host_dut.enable_tester_ipv6()

        self.map_available_ports()

        # disable tester port ipv6
        self.host_dut.disable_tester_ipv6()

    def load_portmap(self):
        """
        Generate port mapping base on loaded port configuration
        """
        port_num = len(self.ports_info)
        self.ports_map = [-1] * port_num
        for key in list(self.ports_cfg.keys()):
            index = int(key)
            if index >= port_num:
                print(RED("Can not found [%d ]port info" % index))
                continue

            if "peer" in list(self.ports_cfg[key].keys()):
                tester_pci = self.ports_cfg[key]["peer"]
                # find tester_pci index
                pci_idx = self.tester.get_local_index(tester_pci)
                self.ports_map[index] = pci_idx

    def set_target(self, target, bind_dev=True, driver_name="", driver_mode=""):
        """
        Set env variable, these have to be setup all the time. Some tests
        need to compile example apps by themselves and will fail otherwise.
        Set hugepage on DUT and install modules required by DPDK.
        Configure default ixgbe PMD function.
        """
        self.set_toolchain(target)

        # set env variable
        # These have to be setup all the time. Some tests need to compile
        # example apps by themselves and will fail otherwise.
        self.send_expect("export RTE_TARGET=" + target, "#")
        self.send_expect("export RTE_SDK=`pwd`", "#")
        if not self.skip_setup:
            self.build_install_dpdk(target)

        self.setup_memory(hugepages=1024)

        self.setup_modules(target, driver_name, driver_mode)

        if bind_dev:
            self.bind_interfaces_linux(driver_name)

    def prerequisites(self, pkgName, patch, autodetect_topo):
        """
        Prerequest function should be called before execute any test case.
        Will call function to scan all lcore's information which on DUT.
        Then call pci scan function to collect nic device information.
        At last setup DUT' environment for validation.
        """
        if not self.skip_setup:
            self.prepare_package()

        out = self.send_expect("cd %s" % self.base_dir, "# ")
        assert "No such file or directory" not in out, "Can't switch to dpdk folder!!!"
        out = self.send_expect("cat VERSION", "# ")
        if "No such file or directory" in out:
            self.logger.error("Can't get DPDK version due to VERSION not exist!!!")
        else:
            self.dpdk_version = out

        self.send_expect("alias ls='ls --color=none'", "#")

        if self.get_os_type() == "freebsd":
            self.send_expect("alias make=gmake", "# ")
            self.send_expect("alias sed=gsed", "# ")

        self.init_core_list()
        self.pci_devices_information()

        # scan ports before restore interface
        self.scan_ports()

        # update with real numa id
        self.update_ports()

        # restore dut ports to kernel
        # if current vm is migration vm, skip restore dut ports
        # because there maybe have some app have run
        if not self.migration_vm:
            if self.virttype != "XEN":
                self.restore_interfaces()
            else:
                self.restore_interfaces_domu()
        # rescan ports after interface up
        self.rescan_ports()

        # no need to rescan ports for guest os just bootup
        # load port infor from config file
        self.load_portconf()

        self.mount_procfs()

        if self.ports_cfg:
            self.load_portmap()
        else:
            # if no config ports in port config file, will auto-detect portmap
            if autodetect_topo:
                self.detect_portmap(dut_id=self.dut_id)

        # print latest ports_info
        for port_info in self.ports_info:
            self.logger.info(port_info)

        # load app name conf
        name_cfg = AppNameConf()
        self.apps_name_conf = name_cfg.load_app_name_conf()

        self.apps_name = self.apps_name_conf["meson"]
        # use the dut target directory instead of 'target' string in app name
        for app in self.apps_name:
            cur_app_path = self.apps_name[app].replace("target", self.target)
            self.apps_name[app] = cur_app_path + " "

    def init_core_list(self):
        self.cores = []
        cpuinfo = self.send_expect(
            'grep --color=never "processor"' " /proc/cpuinfo", "#"
        )
        cpuinfo = cpuinfo.split("\r\n")
        if self.cpu_topo != "":
            topo_reg = r"(\d)S/(\d)C/(\d)T"
            m = re.match(topo_reg, self.cpu_topo)
            if m:
                socks = int(m.group(1))
                cores = int(m.group(2))
                threads = int(m.group(3))
                total = socks * cores * threads
                cores_persock = cores * threads
                total_phycores = socks * cores
                # cores should match cpu_topo
                if total != len(cpuinfo):
                    print(RED("Core number not matched!!!"))
                else:
                    for core in range(total):
                        thread = core / total_phycores
                        phy_core = core % total_phycores
                        # if this core is hyper core
                        if thread:
                            idx = core % total_phycores
                            socket = idx / cores
                        else:
                            socket = core / cores

                        # tricky here, socket must be string
                        self.cores.append(
                            {"thread": core, "socket": str(socket), "core": phy_core}
                        )
                    self.number_of_cores = len(self.cores)
                    return

        # default core map
        for line in cpuinfo:
            m = re.search("processor\t: (\d+)", line)
            if m:
                thread = m.group(1)
                socket = 0
                core = thread
            self.cores.append({"thread": thread, "socket": socket, "core": core})

        self.number_of_cores = len(self.cores)

    def restore_interfaces_domu(self):
        """
        Restore Linux interfaces.
        """
        for port in self.ports_info:
            pci_bus = port["pci"]
            pci_id = port["type"]
            driver = settings.get_nic_driver(pci_id)
            if driver is not None:
                addr_array = pci_bus.split(":")
                domain_id = addr_array[0]
                bus_id = addr_array[1]
                devfun_id = addr_array[2]
                port = GetNicObj(self, domain_id, bus_id, devfun_id)
                itf = port.get_interface_name()
                self.send_expect("ifconfig %s up" % itf, "# ")
                time.sleep(30)
                print(self.send_expect("ip link ls %s" % itf, "# "))
            else:
                self.logger.info(
                    "NOT FOUND DRIVER FOR PORT (%s|%s)!!!" % (pci_bus, pci_id)
                )

    def pci_devices_information(self):
        self.pci_devices_information_uncached()

    def get_memory_channels(self):
        """
        Virtual machine has no memory channel concept, so always return 1
        """
        return 1

    def check_ports_available(self, pci_bus, pci_id):
        """
        Check that whether auto scanned ports ready to use
        """
        pci_addr = "%s:%s" % (pci_bus, pci_id)
        if pci_id == "8086:100e":
            return False
        return True
        # load vm port conf need another function
        # need add virtual function device into NICS

    def scan_ports(self):
        """
        Scan ports information, for vm will always scan
        """
        self.scan_ports_uncached()

    def scan_ports_uncached(self):
        """
        Scan ports and collect port's pci id, mac address, ipv6 address.
        """
        scan_ports_uncached = getattr(
            self, "scan_ports_uncached_%s" % self.get_os_type()
        )
        return scan_ports_uncached()

    def update_ports(self):
        """
        Update ports information, according to host pci
        """
        for port in self.ports_info:
            vmpci = port["pci"]
            for pci_map in self.hyper.pci_maps:
                # search pci mapping structure
                if vmpci == pci_map["guestpci"]:
                    hostpci = pci_map["hostpci"]
                    # search host port info structure
                    for hostport in self.host_dut.ports_info:
                        # update port numa
                        if hostpci == hostport["pci"]:
                            port["numa"] = hostport["numa"]
                            port["port"].socket = hostport["numa"]
                            break
                        if (
                            "sriov_vfs_pci" in hostport
                            and hostpci in hostport["sriov_vfs_pci"]
                        ):
                            port["numa"] = hostport["numa"]
                            port["port"].socket = hostport["numa"]
                    break

    def map_available_ports(self):
        """
        Load or generate network connection mapping list.
        """
        self.map_available_ports_uncached()
        self.logger.warning("VM DUT PORT MAP: " + str(self.ports_map))

    def map_available_ports_uncached(self):
        """
        Generate network connection mapping list.
        """
        nrPorts = len(self.ports_info)
        if nrPorts == 0:
            return

        remove = []
        self.ports_map = [-1] * nrPorts

        hits = [False] * len(self.tester.ports_info)

        for vmPort in range(nrPorts):
            vmpci = self.ports_info[vmPort]["pci"]
            peer = self.get_peer_pci(vmPort)
            # if peer pci configured
            if peer is not None:
                for remotePort in range(len(self.tester.ports_info)):
                    if self.tester.ports_info[remotePort]["pci"] == peer:
                        hits[remotePort] = True
                        self.ports_map[vmPort] = remotePort
                        break
                if self.ports_map[vmPort] == -1:
                    self.logger.error("CONFIGURED TESTER PORT CANNOT FOUND!!!")
                else:
                    continue  # skip ping6 map

            # strip pci address on host for pass-through device
            hostpci = "N/A"
            for pci_map in self.hyper.pci_maps:
                if vmpci == pci_map["guestpci"]:
                    hostpci = pci_map["hostpci"]
                    break

            # auto ping port map
            for remotePort in range(len(self.tester.ports_info)):
                # for two vfs connected to same tester port
                # need skip ping from devices on same pf device
                remotepci = self.tester.ports_info[remotePort]["pci"]
                port_type = self.tester.ports_info[remotePort]["type"]
                # IXIA port should not check whether has vfs
                if port_type.lower() not in ("ixia", "trex"):
                    remoteport = self.tester.ports_info[remotePort]["port"]
                    vfs = []
                    # vm_dut and tester in same dut
                    host_ip = self.crb["IP"].split(":")[0]
                    if self.crb["tester IP"] == host_ip:
                        vfs = remoteport.get_sriov_vfs_pci()
                        # if hostpci is vf of tester port
                        if hostpci == remotepci or hostpci in vfs:
                            print(RED("Skip ping from same PF device"))
                            continue

                ipv6 = self.get_ipv6_address(vmPort)
                if ipv6 == "Not connected":
                    continue

                out = self.tester.send_ping6(
                    remotePort, ipv6, self.get_mac_address(vmPort)
                )

                if out and "64 bytes from" in out:
                    self.logger.info(
                        "PORT MAP: [dut %d: tester %d]" % (vmPort, remotePort)
                    )
                    self.ports_map[vmPort] = remotePort
                    hits[remotePort] = True
                    continue

    def kill_all(self, alt_session=False):
        """
        Kill all dpdk applications on VM
        """
        control = getattr(self.hyper, "control_session", None)
        if callable(control):
            out = control("lsof -Fp /var/run/.rte_config")
            pids = []
            pid_reg = r"p(\d+)"
            if len(out):
                lines = out.split("\r\n")
                for line in lines:
                    m = re.match(pid_reg, line)
                    if m:
                        pids.append(m.group(1))
            for pid in pids:
                control("kill -9 %s" % pid)
