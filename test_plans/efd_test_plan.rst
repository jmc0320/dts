.. SPDX-License-Identifier: BSD-3-Clause
   Copyright(c) 2010-2017 Intel Corporation

==================================================
Sample Application Tests: Elastic Flow Distributor
==================================================

Description
-----------
EFD is a distributor library that uses perfect hashing to determine a
target/value for a given incoming flow key.
It has the following advantages: 
1. It uses perfect hashing it does not store the key itself and hence
lookup performance is not dependent on the key size. 
2. Target/value can be any arbitrary value hence the system designer
and/or operator can better optimize service rates and inter-cluster
network traffic locating. 
3. Since the storage requirement is much smaller than a hash-based flow
table (i.e. better fit for CPU cache), EFD can scale to millions of flow
keys.
4. With the current optimized library implementation, performance is fully
scalable with any number of CPU cores.

For more details, please reference to dpdk online programming guide.

Prerequisites
=============
Two ports connect to packet generator.

DUT board must be two sockets system and each cpu have more than 16 lcores.

Unit test cases
===================

Test Case: EFD function unit test
---------------------------------
Start test application and run efd unit test::

   test> efd_autotest

Verify every function passed in unit test

Test Case: EFD performance unit test
------------------------------------
Start test application and run EFD performance unit test::

   test> efd_perf_autotest

Verify lookup and lookup bulk cpu cycles are reasonable.
Verify when key size increased, no significant increment in cpu cycles.
Verify when value bits increased, no significant increment in cpu cycles.
Compare with cuckoo hash performance result, lookup cycles should be less.

Performance test cases
==============================
In EFD sample, EFD work as a flow-level load balancer. Flows are received at
a front end server before being forwarded to the target back end server for
processing. This case will measure the performance of flow distribution with
different parameters.

Nodes: number of back end nodes
Entries: number of flows to be added in EFD table
Value bits: number of bits of value that be stored in EFD table

Test Case: Load balancer performance based on node numbers
----------------------------------------------------------------------
This case will measure the performance based on node numbers.

+--------------+-------+-----------+------------+
| Value Bits   | Nodes | Entries   | Throughput |
+--------------+-------+-----------+------------+
|  8           |   1   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   3   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   4   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   5   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   6   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   7   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   8   |    2M     |            |
+--------------+-------+-----------+------------+

Test Case: Load balancer performance based on flow numbers
-----------------------------------------------------------------------
This case will measure the performance based on flow numbers.

+--------------+-------+-----------+------------+
| Value Bits   | Nodes | Entries   | Throughput |
+--------------+-------+-----------+------------+
|  8           |   2   |    1M     |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    2M     |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    4M     |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    8M     |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    16M    |            |
+--------------+-------+-----------+------------+
|  8           |   2   |    32M    |            |
+--------------+-------+-----------+------------+

Test Case: Load balancer performance based on value bits
-----------------------------------------------------------------------
Modify different value size which must be between 1 and 32, and it need
to be configured with the ``-Dc_args=-DRTE_EFD_VALUE_NUM_BITS`` option
at compile time.

This case will measure the performance based on value bits.

+--------------+-------+-----------+------------+
| Value Bits   | Nodes | Entries   | Throughput |
+--------------+-------+-----------+------------+
|  8           |   2   |    2M     |            |
+--------------+-------+-----------+------------+
|  16          |   2   |    2M     |            |
+--------------+-------+-----------+------------+
|  24          |   2   |    2M     |            |
+--------------+-------+-----------+------------+
|  32          |   2   |    2M     |            |
+--------------+-------+-----------+------------+
