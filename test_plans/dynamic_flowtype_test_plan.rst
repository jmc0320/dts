.. SPDX-License-Identifier: BSD-3-Clause
   Copyright(c) 2017 Intel Corporation

=========================================================================
Intel® Ethernet 700 Series Dynamic Mapping of Flow Types to PCTYPEs Tests
=========================================================================

More protocols can be added dynamically using dynamic device personalization 
profiles (DDP).

A packet can be identified by hardware as different flow types. Different
NIC hardwares may support different flow types. Basically, the NIC hardware 
identifies the flow type as deep protocol as possible, and exclusively.
To address requirements for new PCTYPEs configuration for post 
filters(RSS/FDIR), a set of functions providing dynamic HW PCTYPE to 
SW RTE_ETH_FLOW type mapping is proposed. 

Dynamic flow type mapping will eliminate usage of number of hard-coded flow 
types in bulky if-else statements. For instance, when configure hash enable 
flags for RSS in i40e_config_hena() function and will make partitioning
Intel® Ethernet 700 Series in i40e PMD more scalable.

I40e PCTYPEs are statically mapped to RTE_ETH_FLOW_* types in DPDK, defined in 
rte_eth_ctrl.h, and flow types used to define ETH_RSS_* offload types in 
rte_ethdev.h. 
RTE_ETH_FLOW_MAX is defined now as 22, leaves 42 flow type unassigned. 

New protocols GTP can be decomposed into separate protocols, GTP-C, GTP-U. 
According to DDP profile request, list GTP PCTYPEs as below::
    
    22 - GTP-U IPv4
    23 - GTP-U IPv6
    24 - GTP-U PAY4
    25 - GTP-C PAY4

Select flow types value between 23 and 63, pctype and flow type mapping as
below::

    +-------------+------------+------------+
    | Packet Type |   PCTypes  | Flow Types |
    +-------------+------------+------------+
    | GTP-U IPv4  |     22     |    26      |
    +-------------+------------+------------+
    | GTP-U IPv6  |     23     |    23      |
    +-------------+------------+------------+
    | GTP-U PAY4  |     24     |    24      |
    +-------------+------------+------------+
    | GTP-C PAY4  |     25     |    25      |
    +-------------+------------+------------+

Prerequisites
=============

1. Host PF in DPDK driver::

    ./tools/dpdk-devbind.py -b igb_uio 81:00.0

2. Start testpmd on host, set chained port topology mode, add txq/rxq to 
   enable multi-queues. In general, PF's max queue is 64::

    ./<build>/app/dpdk-testpmd -c f -n 4 -- -i --port-topology=chained --txq=64 --rxq=64

3. Load profile gtp.pkgo which is a binary file::

    testpmd > port stop all
    testpmd > ddp add (port_id) (profile_path)
    testpmd > port start all

 .. note::

   1. Gtp.pkgo profile is not released by ND yet, only have engineer version for
      internal use so far. Plan to keep public reference profiles at Intel
      Developer Zone, release versions of profiles and supply link later.

   2. Loading DDP profile is the prerequisite for below dynamic mapping relative
      cases, operate global reset or lanconf tool to recover original setting.
      Global reset trigger reg is 0xb8190, cmd is global reset:

        testpmd > write reg 0 0xb8190 2

4. Set rxonly forwarding and enable output

5. Scapy vesrion >= 2.3

Test Case: Check profile info correctness
=========================================
   Check profile information correctness, includes used protocols, packet 
   classification types, defined packet types and so on, no core dump or 
   crash issue::
      
    testpmd> ddp get info <profile_path>


Test Case: Reset flow type to pctype mapping 
============================================
1. Check flow type to pctype mapping::

    testpmd> show port 0 pctype mapping
	
2. Update GTP-U IPv4 flow type id 26 to pcytpe id 22 mapping item::

    testpmd> port config 0 pctype mapping update 22 26
	
3. Check mapping table adds 26 this mapping::

    testpmd> show port 0 pctype mapping
	
4. Reset flow type to pctype mapping to default value::

    testpmd> port config 0 pctype mapping reset
	
5. Check mapping table doesn't have 26 this mapping::

    testpmd> show port 0 pctype mapping

6. Start testpmd

7. Send normal packet to port, check RSS could work, print RTE_MBUF_F_RX_RSS_HASH::
    
    >>> p=Ether()/IP()/Raw('x'*20)


Test Case: Update flow type to GTP-U IPv4 pctype mapping item
=============================================================
1. Check flow type to pctype mapping::

    testpmd> show port 0 pctype mapping
	
2. Update GTP-U IPv4 flow type id 26 to pcytpe id 22 mapping item::

    testpmd> port config 0 pctype mapping update 22 26
	
3. Check flow ptype to pctype mapping adds 26 this mapping::

    testpmd> show port 0 pctype mapping
	
4. Enable flow type id 26's RSS::

    testpmd> port config all rss 26

5. Start testpmd

6. Send GTP-U IPv4 packets, check RSS could work, print RTE_MBUF_F_RX_RSS_HASH::

    >>> p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/Raw('x'*20)
    >>> p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/Raw('x'*20)

7. Send GTP-U IPv6, GTP-U PAY4 and GTP-C PAY4 packets, check receive packets 
   from queue 0 and don't have RTE_MBUF_F_RX_RSS_HASH print.
  

Test Case: Update flow type to GTP-U IPv6 pctype mapping item
=============================================================
1. Check flow type to pctype mapping::

    testpmd> show port 0 pctype mapping

2. Update GTP-U IPv4 flow type id 23 to pcytpe id 23 mapping item::

    testpmd> port config 0 pctype mapping update 23 23
	
3. Check flow ptype to pctype mapping adds 23 this mapping::

    testpmd> show port 0 pctype mapping
	
4. Enable flow type id 23's RSS::

    testpmd> port config all rss 23

5. Start testpmd

6. Send GTP-U IPv6 packets, check RSS could work, print RTE_MBUF_F_RX_RSS_HASH::

    >>> p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/Raw('x'*20)
    >>> p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/Raw('x'*20)

7. Send GTP-U IPv4, GTP-U PAY4 and GTP-C PAY4 packets, check receive 
   packets from queue 0 and don't have RTE_MBUF_F_RX_RSS_HASH print
  

  
Test Case: Update flow type to GTP-U PAY4 pctype mapping item
=============================================================
1. Check flow type to pctype mapping::

    testpmd> show port 0 pctype mapping
	
2. Update GTP-U IPv4 flow type id 24 to pcytpe id 24 mapping item::

    testpmd> port config 0 pctype mapping update 24 24
	
3. Check flow ptype to pctype mapping adds 24 this mapping::

    testpmd> show port 0 pctype mapping
	
4. Enable flow type id 24's RSS::

    testpmd> port config all rss 24

5. Start testpmd

6. Send GTP-U, PAY4 packets, check RSS could work, print RTE_MBUF_F_RX_RSS_HASH::

    >>> p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/Raw('x'*20)
    >>> p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/Raw('x'*20)

7. Send GTP-U IPv4, GTP-U IPv6 and GTP-C PAY4 packets, check receive 
   packets from queue 0 and don't have RTE_MBUF_F_RX_RSS_HASH print.
 
	  
Test Case: Update flow type to GTP-C PAY4 pctype mapping item
=============================================================
1. Check flow ptype to pctype mapping::

    testpmd> show port 0 pctype mapping
	
2. Update GTP-C PAY4 flow type id 25 to pcytpe id 25 mapping item::

    testpmd> port config 0 pctype mapping update 25 25
	
3. Check flow ptype to pctype mapping adds 25 this mapping 
	
4. Enable flow type id 25's RSS::

    testpmd> port config all rss 25

5. Start testpmd

6. Send GTP-C PAY4 packets, check RSS could work, print RTE_MBUF_F_RX_RSS_HASH::

    >>> p=Ether()/IP()/UDP(dport=2123)/GTP_U_Header()/Raw('x'*20)
    >>> p=Ether()/IPv6()/UDP(dport=2123)/GTP_U_Header()/Raw('x'*20)

7. Send GTP-U IPv4, GTP-U IPv6 and GTP-U PAY4 packets, check receive packets
   from queue 0 and don't have RTE_MBUF_F_RX_RSS_HASH print.

   
GTP packet
==========

Note:

1. List all of profile supported GTP packets as below, also could use "ddp get
   info gtp.pkgo" to check profile information. Below left number is ptype
   value, right are layer types::

    167: IPV4, GTP-C, PAY4

2. Scapy 2.3.3+ versions support to send GTP packet. Please check your scapy
   tool could send below different GTP types' packets successfully then run
   above tests.


GTP-C packet types
==================

167: IPV4, GTP-C, PAY4::

    p=Ether()/IP()/UDP(dport=2123)/GTP_U_Header()/Raw('x'*20)

168: IPV6, GTP-C, PAY4::

    p=Ether()/IPv6()/UDP(dport=2123)/GTP_U_Header()/Raw('x'*20)
 
GTP-U data packet types, IPv4 transport, IPv4 payload
=====================================================

169: IPV4 GTPU IPV4 PAY3::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/Raw('x'*20)

170: IPV4 GTPU IPV4FRAG PAY3::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP(frag=5)/Raw('x'*20)

171: IPV4 GTPU IPV4 UDP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/UDP()/Raw('x'*20)

172: IPV4 GTPU IPV4 TCP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/TCP()/Raw('x'*20)

173: IPV4 GTPU IPV4 SCTP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/SCTP()/Raw('x'*20)

174: IPV4 GTPU IPV4 ICMP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IP()/ICMP()/Raw('x'*20)

GTP-U data packet types, IPv6 transport, IPv4 payload
=====================================================

175: IPV6 GTPU IPV4 PAY3::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/Raw('x'*20)

176: IPV6 GTPU IPV4FRAG PAY3::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP(frag=5)/Raw('x'*20)

177: IPV6 GTPU IPV4 UDP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/UDP()/Raw('x'*20)

178: IPV6 GTPU IPV4 TCP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/TCP()/Raw('x'*20)

179: IPV6 GTPU IPV4 SCTP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/SCTP()/Raw('x'*20)

180: IPV6 GTPU IPV4 ICMP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IP()/ICMP()/Raw('x'*20)

GTP-U control packet types
==========================

181: IPV4, GTP-U, PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/Raw('x'*20)

182: PV6, GTP-U, PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/Raw('x'*20)
 
GTP-U data packet types, IPv4 transport, IPv6 payload
=====================================================

183: IPV4 GTPU IPV6FRAG PAY3::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/IPv6ExtHdrFragment()/Raw('x'*20)

184: IPV4 GTPU IPV6 PAY3::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/Raw('x'*20)

185: IPV4 GTPU IPV6 UDP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/UDP()/Raw('x'*20)

186: IPV4 GTPU IPV6 TCP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/TCP()/Raw('x'*20)

187: IPV4 GTPU IPV6 SCTP PAY4::

    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6()/SCTP()/Raw('x'*20)

188: IPV4 GTPU IPV6 ICMPV6 PAY4::
    
    p=Ether()/IP()/UDP(dport=2152)/GTP_U_Header()/IPv6(nh=58)/ICMP()/Raw('x'*20)

GTP-U data packet types, IPv6 transport, IPv6 payload
=====================================================

189: IPV6 GTPU IPV6 PAY3::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/Raw('x'*20)

190: IPV6 GTPU IPV6FRAG PAY3::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/IPv6ExtHdrFragment()/Raw('x'*20)

191: IPV6 GTPU IPV6 UDP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/UDP()/Raw('x'*20)

113: IPV6 GTPU IPV6 TCP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/TCP()/Raw('x'*20)

120: IPV6 GTPU IPV6 SCTP PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6()/SCTP()/Raw('x'*20)

128: IPV6 GTPU IPV6 ICMPV6 PAY4::

    p=Ether()/IPv6()/UDP(dport=2152)/GTP_U_Header()/IPv6(nh=58)/ICMP()/Raw('x'*20)


