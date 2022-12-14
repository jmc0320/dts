.. SPDX-License-Identifier: BSD-3-Clause
   Copyright(c) 2010-2019 Intel Corporation

========================================
VM Power Management Tests (Policy/Turbo)
========================================

Inband Policy Control
=====================

A feature allows workload to deliver policy to the host to manage power controls
such as p-states extends the thinking of the current scheme moving away
from direct controls to policy controls to avoid latency & jitter
penalties. Also provides the ability to react faster.

VM Power Manager would use a hint based mechanism by which a VM can
communicate to a host based governor about its current processing
requirements. By mapping VMs virtual CPUs to physical CPUs the Power Manager
can then make decisions according to some policy as to what power state the
physical CPUs can transition to.

VM Agent shall have the ability to send the following policy to host.
- traffic policy
- time policy

turbo
=====
A new feature extend the library to enable 'per-core' turbo among other APIs.

VM Agent shall have the ability to send the following hints to host::

    - core disable turbo
    - core enable turbo

The power manager will manage the file handles for each core as below::

    ``/dev/cpu/%d/msr``

DPDK technical document refer to::

    ``doc/guides/prog_guide/power_man.rst``
    ``doc/guides/sample_app_ug/vm_power_management.rst``

Prerequisites
=============
#. Hardware::

    - NIC: i40e series('Ethernet Controller X710 for 10GbE SFP+ 1572')

#. BIOS::

    - Enable VT-d and VT-x
    - Enable Enhanced Intel SpeedStep(R) Tech
    - Enable Intel(R) Turbo Boost Technology

#. OS and Kernel::

    - Fedora 30
        vim /boot/grub2/grubenv
        - Enable Kernel features IOMMU
            iommu=pt
        - Enable Intel IOMMU
            intel_iommu=on
        - Disable intel_pstate
            intel_pstate=disable

#. Virtualization::

    - QEMU emulator version >= 2.3.1
    - libvirtd (libvirt) >= 1.2.13.2
      libvirt configuration refer to dpdk/doc/guides/howto/pvp_reference_benchmark.rst ``Libvirt way`` chapter

#. port topology diagram::

       packet generator                         DUT
        .-----------.                      .-----------.
        | .-------. |                      | .-------. |
        | | portA | | <------------------> | | port0 | |
        | | portB | | <------------------> | | port1 | |
        | '-------' |                      | '-------' |
        |           |                      |    nic    |
        '-----------'                      '-----------'


Set up testing environment
==========================
#. Configure VM XML to pin VCPUs/CPUs.

   .. code-block:: xml

    <vcpu placement='static'>8</vcpu>
    <cputune>
        <vcpupin vcpu='0' cpuset='1'/>
        <vcpupin vcpu='1' cpuset='2'/>
        <vcpupin vcpu='2' cpuset='3'/>
        <vcpupin vcpu='3' cpuset='4'/>
        <vcpupin vcpu='4' cpuset='5'/>
        <vcpupin vcpu='5' cpuset='6'/>
        <vcpupin vcpu='6' cpuset='7'/>
        <vcpupin vcpu='7' cpuset='8'/>
    </cputune>

#. Configure VM XML to set up virtio serial ports.

    Create temporary folder for vm_power socket.

        mkdir /tmp/powermonitor
        chmod 777 /tmp/powermonitor

    Setup one serial port for every one vcpu in VM.

    .. code-block:: xml

        <channel type='unix'>
            <source mode='bind' path='/tmp/powermonitor/<vm_name>.<channel_num>'/>
            <target type='virtio' name='virtio.serial.port.poweragent.<channel_num>'/>
            <address type='virtio-serial' controller='0' bus='0' port='4'/>
        </channel>

#. Create vf and passthrough it to VM.

    Create vf on one pf with system driver.

        echo 1 > /sys/bus/pci/devices/0000:d8:00.0/sriov_numvfs

    .. code-block:: xml

        <hostdev managed="yes" mode="subsystem" type="pci">
            <driver name="vfio"/>
            <source>
                <address bus="0xd8" domain="0x0000" function="0x0" slot="0x02"/>
            </source>
            <address bus="0x00" domain="0x0000" function="0x0" slot="0x07" type="pci"/>
        </hostdev>

#. Bind the vf passthrough on VM to igb_uio, bind pf on host to default system driver.

    ./usertools/dpdk-devbind.py --force --bind=igb_uio 0000:00:07.0

#. Compile and run power-manager in host, core number should >= 3, add vm in host.

    CC=gcc meson -Denable_kmods=True -Dlibdir=lib  --default-library=static <build_target>
    ninja -C <build_target>

    meson configure -Dexamples=vm_power_manager <build_target>
    ninja -C <build_target>

   ./<build_target>/examples/dpdk-vm_power_manager -c 0xffff -n 4

    vmpower> add_vm <vm_name>
    vmpower> add_channels <vm_name> all
    vmpower> set_channel_status <vm_name> all enabled

#. Run testpmd on vm0 when do traffic policy testing, other test cases ignore
   this step.

    ./<build_target>/app/dpdk-testpmd -c 0x3 -n 1 -v -m 1024 --file-prefix=vmpower1 -- -i --port-topology=loop

    testpmd> set fwd mac
    testpmd> set promisc all on
    testpmd> port start all
    testpmd> start

#. Compile and run dpdk-guest_cli on VM.

    CC=gcc meson -Denable_kmods=True -Dlibdir=lib  --default-library=static <build_target>
    ninja -C <build_target>

    meson configure -Dexamples=vm_power_manager/guest_cli <build_target>
    ninja -C <build_target>

   ./<build_target>/examples/dpdk-guest_cli \
   -c 0xff -n 4 --file-prefix=vmpower2 -- -i --vm-name=<vm name> \
   --policy=<policy name> --vcpu-list=<vcpus list> --busy-hours=<time stage>

    options description::

        -n or --vm-name
           sets the name of the vm to be used by the host OS.
        -b or --busy-hours
           sets the list of hours that are predicted to be busy
        -q or --quiet-hours
           sets the list of hours that are predicted to be quiet
        -l or --vcpu-list
           sets the list of vcpus to monitor
        -o or --policy
           sets the default policy type
              ``TIME``
              ``WORKLOAD``

        The format of the hours or list paramers is a comma-separated
        list of integers, which can take the form of
           a. x    e.g. --vcpu-list=1
           b. x,y  e.g. --quiet-hours=3,4
           c. x-y  e.g. --busy-hours=9-12
           d. combination of above (e.g. --busy-hours=4,5-7,9)


Test Case : time policy
=======================
check these content.
#. when dut clock is set to a desired busy hours, put core to max freq.
#. when dut clock is set to a desired quiet hours, put core to min freq.

This case test multiple dpdk-guest_cli options, they are composited
by these content as below::

    #. --policy
       TIME
    #. --vm-name
      vm0
    #. --vcpu-list
      0
      0,1,2,3,4,5,6,7
    #. --busy-hours or --quiet-hours
      23
      0-23
      4,5-7,23

example::

    --vm-name=vm0 --policy=TIME --vcpu-list=0,1,2,3,4,5,6,7 --busy-hours=0-23,5-7,23

steps:

#. set DUT system time to desired time.

#. set up testing environment refer to ``Set up testing environment`` steps.

#. trigger policy on vm DUT from dpdk-guest_cli console::

    vmpower(guest)> send_policy now

#. check DUT platform cores frequency, which are in vcpu-list.


Test Case : traffic policy
==========================
check these content.
#. use packet generator to send a stream with a pps rate bigger 2000000,
vcpu frequency will run at max frequency.
#. use packet generator to send a stream with a pps rate between 1800000 and 2000000,
vcpus frequency will run at med frequency.
#. use packet generator to send a stream with a pps rate less than 1800000,
vcpu frequency will run at min frequency.

This case test multiple dpdk-guest_cli options, they are composited
by these content as below::

    #. --policy
       TRAFFIC
    #. --vm-name
      vm0
    #. --vcpu-list
      0
      0,1,2,3,4,5,6,7

example::

    --vm-name=vm0 --policy=TRAFFIC --vcpu-list=0,1,2,3,4,5,6,7

steps:

#. set up testing environment refer to ``Set up testing environment`` steps.

#. trigger policy on vm DUT from dpdk-guest_cli console::

    vmpower(guest)> send_policy now

#. configure stream in traffic generator, set traffic generator line rate
   to desired pps and send packet continuously.

#. check DUT platform cores frequency, which are in vcpu-list.


Test Case : disable CPU turbo
=============================
check a custom cpu turbo status can be disable.

steps:

#. set up testing environment refer to ``Set up testing environment`` steps.

#. set cpu turbo disable on vm DUT from dpdk-guest_cli console::

    vmpower(guest)> set_cpu_freq <core_num> disable_turbo

#. verify the DUT physical CPU's turbo has been disable correctly, core frequency
   should be secondary max value in scaling_available_frequencies::

    cat /sys/devices/system/cpu/cpu1/cpufreq/cpuinfo_cur_freq
    cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_available_frequencies

Test Case : enable CPU turbo
============================
check a custom cpu turbo status can be enable.

steps:

#. set up testing environment refer to ``Set up testing environment`` steps.

#. set cpu turbo enable on vm DUT from dpdk-guest_cli console::

    vmpower(guest)> set_cpu_freq <vm_core_num> enable_turbo

#. Verify the DUT physical CPU's turbo has been enable correctly, core frequency
   should be max value in scaling_available_frequencies::

    cat /sys/devices/system/cpu/cpu1/cpufreq/cpuinfo_cur_freq
    cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_available_frequencies
