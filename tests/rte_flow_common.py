# BSD LICENSE
#
# Copyright(c) 2010-2019 Intel Corporation. All rights reserved.
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

import json
import time
import re
from utils import GREEN, RED

# switch filter common functions
def get_packet_number(out,match_string):
    """
    get the rx packets number.
    """
    out_lines=out.splitlines()
    pkt_num =0
    for i in range(len(out_lines)):
        if  match_string in out_lines[i]:
            result_scanner = r'RX-packets:\s?(\d+)'
            scanner = re.compile(result_scanner, re.DOTALL)
            m = scanner.search(out_lines[i+1])
            pkt_num = int(m.group(1))
            break
    return pkt_num

def get_port_rx_packets_number(out,port_num):
    """
    get the port rx packets number.
    """
    match_string="---------------------- Forward statistics for port %d" % port_num
    pkt_num = get_packet_number(out,match_string)
    return pkt_num

def get_queue_rx_packets_number(out, port_num, queue_id):
    """
    get the queue rx packets number.
    """
    match_string="------- Forward Stats for RX Port= %d/Queue= %d" % (port_num, queue_id)
    pkt_num = get_packet_number(out,match_string)
    return pkt_num

def check_output_log_in_queue(out, func_param, expect_results):
    """
    check if the expect queue received the expected number packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    expect_queue = func_param["expect_queues"]
    expect_pkts = expect_results["expect_pkts"]

    pkt_num = get_queue_rx_packets_number(out,expect_port,expect_queue)
    log_msg = ""
    #check the result
    if pkt_num == expect_pkts:
        return True, log_msg
    else:
        log_msg = "Port= %d/Queue= %d receive %d packets" % (expect_port, expect_queue, pkt_num)
        return False, log_msg

def check_output_log_queue_region(out, func_param, expect_results):
    """
    Check if the expect queues received the expected number packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    expect_queues = func_param["expect_queues"]
    expect_pkts = expect_results["expect_pkts"]

    packet_sumnum = 0
    for queue_id in expect_queues:
        pkt_num = get_queue_rx_packets_number(out, expect_port, queue_id)
        packet_sumnum += pkt_num

    #check the result
    log_msg = ""
    if packet_sumnum == expect_pkts:
        return True, log_msg
    else:
        log_msg = "queue region: Not all packets are received in expect_queues"
        return False, log_msg

def check_output_log_queue_region_mismatched(out, func_param, expect_results):
    """
    when the action is queue region, check the expect port received the expect
    number packets, while the corresponding queues not receive any packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    expect_queues = func_param["expect_queues"]
    expect_pkts = expect_results["expect_pkts"]

    log_msg = ""
    #check expect_port received expect number packets
    pkt_num = get_port_rx_packets_number(out, expect_port)
    if pkt_num != expect_pkts:
        log_msg = "queue region mismatched: port %d receive %d packets, not receive %d packet" % (expect_port, pkt_num, expect_pkts)
        return False, log_msg
    else:
        #check expect queues not received packets
        packet_sumnum = 0
        for queue_id in expect_queues:
            pkt_num = get_queue_rx_packets_number(out, expect_port, queue_id)
            packet_sumnum += pkt_num

        log_msg = ""
        if packet_sumnum == 0:
            return True, log_msg
        else:
            log_msg = "queue region mismatched: expect queues should receive 0 packets, but it received %d packets" % packet_sumnum
            return False, log_msg

def check_output_log_in_queue_mismatched(out, func_param, expect_results):
    """
    when the action is to queue, check the expect port received the expect
    number packets, while the corresponding queue not receive any packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    expect_queue = func_param["expect_queues"]
    expect_pkts = expect_results["expect_pkts"]

    log_msg = ""
    #check expect_port received expect number packets
    pkt_num = get_port_rx_packets_number(out, expect_port)
    if pkt_num != expect_pkts:
        log_msg = "mismatched: port %d receive %d packets, not receive %d packet" % (expect_port, pkt_num, expect_pkts)
        return False, log_msg
    else:
        #check expect queue not received packets
        pkt_num = get_queue_rx_packets_number(out, expect_port, expect_queue)
        log_msg = ""
        if pkt_num == 0:
            return True, log_msg
        else:
            log_msg = "mismatched: expect queue Port= %d/Queue= %d should receive 0 packets, but it received %d packets" % (expect_port, expect_queue, pkt_num)
            return False, log_msg

def check_output_log_drop(out, func_param, expect_results):
    """
    check the expect port not receive any packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    #check expect_port not received the packets
    pkt_num = get_port_rx_packets_number(out, expect_port)

    log_msg = ""
    if pkt_num == 0:
        return True, log_msg
    else:
        log_msg = "Port %d packets not dropped, received %d packets" % (expect_port, pkt_num)
        return False, log_msg

def check_output_log_drop_mismatched(out, func_param, expect_results):
    """
    check the expect port received the mismatched packets.
    """
    #parse input parameters
    expect_port = func_param["expect_port"]
    expect_pkts = expect_results["expect_pkts"]

    log_msg = ""
    #check expect_port received expect number packets
    pkt_num = get_port_rx_packets_number(out, expect_port)
    if pkt_num == expect_pkts:
        return True, log_msg
    else:
        log_msg = "drop mismatched: port %d receive %d packets, should receive %d packet" % (expect_port, pkt_num, expect_pkts)
        return False, log_msg

def check_rule_in_list_by_id(out, rule_num, only_last=True):
    """
    check if the rule with ID "rule_num" is in list, after
    executing the command "flow list 0".
    """
    out_lines=out.splitlines()
    if len(out_lines) == 1:
        return False
    if only_last:
        last_rule = out_lines[len(out_lines)-1]
        last_rule_list = last_rule.split('\t')
        rule_id = int(last_rule_list[0])
        if rule_id == rule_num:
            return True
        else:
            return False
    else:
        #check the list for the rule
        for i in range(len(out_lines)):
            if "ID" in out_lines[i]:
                rules_list = out_lines[i+1:]
                break
        for per_rule in rules_list:
            per_rule_list = per_rule.split('\t')
            per_rule_id = int(per_rule_list[0])
            if per_rule_id == rule_num:
                return True
        return False


# fdir common functions
def verify(passed, description):
    if not passed:
        raise AssertionError(description)

def check_queue(out, pkt_num, check_param, stats=True):
    port_id = check_param["port_id"] if check_param.get("port_id") is not None else 0
    queue = check_param["queue"]
    p = re.compile(
        r"Forward Stats for RX Port= %s/Queue=(\s?\d+)\s.*\n.*RX-packets:(\s?\d+)\s+TX-packets" % port_id)
    res = p.findall(out)
    if res:
        res_queue = [int(i[0]) for i in res]
        pkt_li = [int(i[1]) for i in res]
        res_num = sum(pkt_li)
        verify(res_num == pkt_num, "fail: got wrong number of packets, expect pakcet number %s, got %s." % (pkt_num, res_num))
        if stats:
            if isinstance(queue, int):
                verify(all(q == queue for q in res_queue), "fail: queue id not matched, expect queue %s, got %s" % (queue, res_queue))
                print(GREEN("pass: queue id %s matched" % res_queue))
            elif isinstance(queue, list):
                verify(all(q in queue for q in res_queue), "fail: queue id not matched, expect queue %s, got %s" % (queue, res_queue))
                print(GREEN("pass: queue id %s matched" % res_queue))
            else:
                raise Exception("wrong queue value, expect int or list")
        else:
            if isinstance(queue, int):
                verify(not any(q == queue for q in res_queue), "fail: queue id should not matched, expect queue %s, got %s" % (queue, res_queue))
                print(GREEN("pass: queue id %s not matched" % res_queue))
            elif isinstance(queue, list):
                verify(not any(q in queue for q in res_queue), "fail: each queue in %s should not in queue %s" % (res_queue, queue))
                print(GREEN("pass: queue id %s not matched" % res_queue))
            else:
                raise Exception("wrong action value, expect queue_index or queue_group")
    else:
        raise Exception("got wrong output, not match pattern %s" % p.pattern)


def check_drop(out, pkt_num, check_param, stats=True):
    port_id = check_param["port_id"] if check_param.get("port_id") is not None else 0
    p = re.compile(
        'Forward\sstatistics\s+for\s+port\s+%s\s+.*\n.*RX-packets:\s(\d+)\s+RX-dropped:\s(\d+)\s+RX-total:\s(\d+)\s' % port_id)
    title_li = ["rx-packets", "rx-dropped", "rx-total"]
    pkt_li = p.findall(out)
    if pkt_li:
        res = {k: v for k, v in zip(title_li, map(int, list(pkt_li[0])))}
        verify(pkt_num == res["rx-total"], "failed: get wrong amount of packet %d, expected %d" % (res["rx-total"], pkt_num))
        if stats:
            verify(res["rx-dropped"] == pkt_num, "failed: dropped packets number %s not match" % res["rx-dropped"])
        else:
            verify(res["rx-dropped"] == 0 and res["rx-packets"] == pkt_num, "failed: dropped packets number should be 0")
    else:
        raise Exception("got wrong output, not match pattern %s" % p.pattern)


def check_mark(out, pkt_num, check_param, stats=True):
    mark_scanner = "FDIR matched ID=(0x\w+)"
    res = re.findall(mark_scanner, out[0])
    if stats:
        if check_param.get("queue") is not None:
            check_queue(out[1], pkt_num, check_param, stats)
            mark_list = [i[0] for i in res]
            verify(len(res) == pkt_num, "get wrong number of packet with mark_id")
            verify(all([int(i, 16) == check_param["mark_id"] for i in res]),
                        "failed: some packet mark id of %s not match" % mark_list)
        else:
            check_drop(out[1], pkt_num, check_param, stats)
            verify(not res, "should has no mark_id in %s" % res)
    else:
        if check_param.get("queue") is not None:
            check_queue(out[1], pkt_num, check_param, stats)
        else:
            check_drop(out[1], pkt_num, check_param, stats)
        verify(not res, "should has no mark_id in %s" % res)

# rss common functions
def check_packets_of_each_queue(out):
    """
    check each queue has receive packets
    """
    queue_result = re.findall(r"-------(.*)-------\s*(.*)", out)
    queueid_rxpackets_list = []
    log_msg = ""
    for q in queue_result:
        queue_id =get_queue_id(q[0])
        rx_packets=get_rxpackets(q[1])
        if (queue_id != -1):
            queueid_rxpackets_list.append([queue_id, rx_packets])

    if (len(queueid_rxpackets_list) == 10):
        if (queueid_rxpackets_list > 0):
            return True, log_msg
        else :
            log_msg = "The queue is rx-packets" % id
            return False, log_msg

    p = re.compile("\sForward Stats for RX Port=(.*?)/Queue=(.*?)\s->")
    li = re.findall(p, out)
    queue_set = set([int(i[1].strip()) for i in li])
    verify_set = set(range(64))
    log_msg = ""
    if queue_set.issubset(verify_set):
        return True, log_msg
    else:
        return False, "queue %s out of range %s" % (queue_set, verify_set)

def check_symmetric_queue(out):
    """
    check each packets in which queue
    """
    queue_list = re.findall('RSS queue=(\S*)', out)
    m = len(queue_list)
    log_msg = ""
    for i in range(m - 1):
        if queue_list[i] == queue_list[i + 1]:
           return True, log_msg
        else:
           log_msg = "packets not in same queue and cause to fail"
           return False, log_msg

def check_simplexor_queue(out):
    """
    check each packets in which queue
    """
    queue_list = re.findall('RSS queue=(\S*)', out)
    m = len(queue_list)
    log_msg = ""
    for i in range(m - 1):
        if queue_list[i] == queue_list[i + 1]:
           return True, log_msg
        else:
           log_msg = "packets not in same queue and cause to fail"
           return False, log_msg

def check_rx_tx_packets_match(out, count):
    rx_stats = int(re.findall('RX-total:\s+(\d*)', out)[0])
    if rx_stats == count :
       return True, "The Rx packets has matched to the Tx packets"
    else:
       return False, "rx and tx packets error!"

def get_queue_id(line1):
    try:
        result = re.search(r"RX Port=\s*\d*/Queue=\s*(\d*)", line1)
        return result.group(1)
    except:
        return -1

def get_rxpackets(line2):
    try:
        result = re.search(r"RX-packets:\s*(\d*)", line2)
        return result.group(1)
    except:
        return -1

def find_queueid_rxpackets_list(id, q_rx_list):
    for item in q_rx_list:
        if (int(item[0]) == id):
            return int(item[1])
    return 0