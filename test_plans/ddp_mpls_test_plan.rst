.. SPDX-License-Identifier: BSD-3-Clause
   Copyright(c) 2017 Intel Corporation

=====================================================================
Intel® Ethernet 700 Series DDP (Dynamic Device Personalization) Tests
=====================================================================

Intel® Ethernet 700 Series supports DDP (Dynamic Device Personalization) to
program analyzer/parser via AdminQ. Profile can be used to update Intel®
Ethernet 700 Series configuration tables via MMIO configuration space, not
microcode or firmware itself. For microcode/FW changes new HW/FW/NVM image
must be uploaded to the NIC. Profiles will be stored in binary files and
need to be passed to AQ to program Intel® Ethernet 700 Series during
initialization stage.

With DDP, MPLS (Multi-protocol Label Switching) can be supported by NVM with
profile updated.
Below HW features have be enabled for MPLS:

- MPLS packet type recognition
- Cloud filter for MPLS with MPLS label

Only 25G NIC supports DDP and MPLS so far.

Prerequisites
=============

1. Host PF in DPDK driver. Create 1 VF from 1 PF with DPDK driver::

     ./tools/dpdk-devbind.py -b igb_uio 81:00.0
     echo 1 >/sys/bus/pci/devices/0000:81:00.0/max_vfs

2. Detach VF from the host::

     rmmod iavf

3. Pass through VF 81:10.0 to vm0, start vm0.

4. Login vm0, then bind VF0 device to igb_uio driver.

5. Start testpmd on host and vm0 in chained port topology, add txq/rxq to
   enable multi-queues. In general, PF's max queue is 64, VF's max queue
   is 4::

     ./<build>/app/dpdk-testpmd -c f -n 4 -- -i --port-topology=chained
     --txq=4 --rxq=4


Test Case 1: Load dynamic device personalization
================================================

1. Stop testpmd port before loading profile::

     testpmd > stop port all

2. Load profile mplsogre-l2.pkgo which is a binary file::

     testpmd > ddp add (port_id) (profile_path

3. Check profile info successfully::

     testpmd > ddp get list (port_id)

4. Start testpmd port

      testpmd > start port all

.. Note::

   Loading ddp is the prerequisite for below MPLS relative cases, operate
   global reset or lanconf tool to recover original setting. Global Reset
   Trigger reg is 0xb8190, first cmd is core reset, second cmd is global
   reset::

      testpmd > write reg 0 0xb8190 1
      testpmd > write reg 0 0xb8190 2


Test Case 2: MPLS udp packet for PF
===================================

1. Add udp flow rule for PF, set label as random 20 bits, queue should be among
   configured queue number::

     testpmd > flow create 0 ingress pattern eth / ipv4 / udp / mpls label
     is 0x12345 / end actions pf / queue index <id> / end

2. Set fwd rxonly, enable output and start PF and VF testpmd

3. Send udp MPLS packet with good checksum, udp dport is 6635, label is same
   as configured rule::

     sendp([Ether()/IP()/UDP(dport=6635)/MPLS(label=0x12345)/Ether()/IP()
     /TCP()], iface=txItf)

4. Check PF could receive configured label udp packet, checksum is good,
   queue is configured queue

5. Send udp MPLS packet with bad checksum, udp dport is 6635, label is same
   as configured rule::

     sendp([Ether()/IP()/UDP(chksum=0x1234,dport=6635)/MPLS(label=0x12345)/Ether()
     /IP()/TCP()], iface=txItf)

6. Check PF could receive configured label udp packet, checksum is good, queue is
   configured queue


Test Case 3: MPLS gre packet for PF
===================================

1. Add gre flow rule for PF, set label as random 20 bits, queue should be among
   configured queue number::

     testpmd > flow create 0 ingress pattern eth / ipv4 / gre / mpls label is
     0xee456 / end actions pf / queue index <id> / end

2. Set fwd rxonly, enable output and start PF and VF testpmd

3. Send gre MPLS packet with good checksum, gre proto is 8847, label is same
   as configured rule::

     sendp([Ether()/IP(proto=47)/GRE(proto=0x8847)/MPLS(label=0xee456)/Ether()
     /IP()/UDP()], iface=txItf)

4. Check VF could receive configured label gre packet, checksum is good, queue
   is configured queue

5. Send gre MPLS packet with bad checksum, gre proto is 8847, label is same as
   configured rule::

     sendp([Ether()/IP(proto=47)/GRE(chksum=0x1234,proto=0x8847)/MPLS(label=0xee456)
     /Ether()/IP()/UDP()], iface=txItf)

6. Check VF could receive configured label gre packet, checksum is good, queue is
   configured queue


Test Case 4: MPLS udp packet for VF
===================================

1. Add udp flow rule for VF, set label as random 20 bits, queue should be among
   configured queue number::

     testpmd > flow create 0 ingress pattern eth / ipv4 / udp / mpls label is 0x234
     / end actions vf id 0 / queue index <id> / end

2. Set fwd rxonly, enable output and start PF and VF testpmd

3. Send udp MPLS packet with good checksum, udp dport is 6635, label is same as
   configured rule::

     sendp([Ether()/IP()/UDP(dport=6635)/MPLS(label=0x234)/Ether()/IP()/TCP()],
     iface=txItf)

4. Check VF could receive configured label udp packet, checksum is good, queue is
   configured queue

5. Send udp MPLS packet with bad checksum, udp dport is 6635, label is same as
   configured rule::

     sendp([Ether()/IP()/UDP(chksum=0x1234,dport=6635)/MPLS(label=0x234)/Ether()
     /IP()/TCP()], iface=txItf)

6. Check VF could receive configured label udp packet, checksum is good, queue is
   configured queue


Test Case 5: MPLS gre packet for VF
===================================

1. Add gre flow rule for VF, set label as random 20 bit, queue should be among
   configured queue number::

     testpmd > flow create 0 ingress pattern eth / ipv4 / gre / mpls label is
     0xffff / end actions vf id 0 / queue index <id> / end

2. Set fwd rxonly, enable output and start PF and VF testpmd

3. Send gre MPLS packet with good checksum, gre proto is 8847, label is same as
   configured rule::

     sendp([Ether()/IP(proto=47)/GRE(proto=0x8847)/MPLS(label=0xffff)/Ether()
     /IP()/UDP()], iface=txItf)

4. Check VF could receive configured label gre packet, checksum is good, queue is
   configured queue

5. Send gre MPLS packet with bad checksum, gre proto is 8847, label is same as
   configured rule::

     sendp([Ether()/IP(proto=47)/GRE(chksum=0x1234,proto=0x8847)/MPLS(label=0xffff)
     /Ether()/IP()/UDP()], iface=txItf)

6. Check VF could receive configured label gre packet, checksum is good, queue is
   configured queue
