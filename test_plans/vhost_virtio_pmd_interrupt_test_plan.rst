.. SPDX-License-Identifier: BSD-3-Clause
   Copyright(c) 2019 Intel Corporation

=========================================
vhost/virtio-pmd interrupt mode test plan
=========================================

Virtio-pmd interrupt need test with l3fwd-power sample, small packets send from traffic generator
to virtio-pmd side，check virtio-pmd cores can be wakeup status，and virtio-pmd cores should be
sleep status after stop sending packets from traffic generator.This test plan cover virtio 0.95,
virtio 1.0 and virtio 1.1 test.For packed virtqueue test, need using qemu version > 4.2.0.

Prerequisites
=============

Test ENV preparation: Kernel version > 4.8.0, mostly linux distribution don't support vfio-noiommu mode by default, so testing this case need rebuild kernel to enable vfio-noiommu.

Test flow
=========

TG --> NIC --> Vhost --> Virtio--> Vhost --> NIC --> TG

Test Case 1: Basic virtio interrupt test with 4 queues
=======================================================

1. Bind one NIC port to vfio-pci, then launch testpmd by below command::

    rm -rf vhost-net*
    ./x86_64-native-linuxapp-gcc/app/dpdk-testpmd -c 0x7c -n 4 --vdev 'net_vhost0,iface=vhost-net,queues=4' -- -i --nb-cores=4 --rxq=4 --txq=4 --rss-ip

2. Launch VM1, set queues=4, vectors>=2xqueues+2, mq=on::

    taskset -c 34-35 \
    qemu-system-x86_64 -name us-vhost-vm2 \
     -cpu host -enable-kvm -m 4096 -object memory-backend-file,id=mem,size=4096M,mem-path=/mnt/huge,share=on -numa node,memdev=mem -mem-prealloc \
     -smp cores=4,sockets=1 -drive file=/home/osimg/ubuntu1910.img \
     -monitor unix:/tmp/vm2_monitor.sock,server,nowait -device e1000,netdev=nttsip1 \
     -netdev user,id=nttsip1,hostfwd=tcp:127.0.0.1:6003-:22 \
     -chardev socket,id=char1,path=./vhost-net -netdev type=vhost-user,id=mynet2,chardev=char1,vhostforce,queues=4 \
     -device virtio-net-pci,mac=52:54:00:00:00:02,netdev=mynet2,mrg_rxbuf=on,csum=on,mq=on,vectors=15  \
     -vnc :10 -daemonize

3. Bind virtio port to vfio-pci::

     modprobe vfio enable_unsafe_noiommu_mode=1
     modprobe vfio-pci
     ./usertools/dpdk-devbind.py --bind=vfio-pci xx:xx.x

4. In VM, launch l3fwd-power sample::

    ./x86_64-native-linuxapp-gcc/examples/dpdk-l3fwd-power -c 0xf -n 4 --log-level='user1,7' -- -p 1 -P --config="(0,0,0),(0,1,1),(0,2,2),(0,3,3)" --no-numa --parse-ptype

5. Send random dest ip address packets to host nic with packet generator, packets will distribute to all queues, check l3fwd-power log that all related cores are waked up.

6. Change dest IP address to fixed ip, packets will distribute to 1 queue, check l3fwd-power log that only one related core is waked up.

7. Stop the date transmitter, check all related cores will be back to sleep status.

Test Case 2: Basic virtio interrupt test with 16 queues
=======================================================

1. Bind one NIC port to vfio-pci, then launch testpmd by below command::

    rm -rf vhost-net*
    ./x86_64-native-linuxapp-gcc/app/dpdk-testpmd -c 0x1ffff -n 4 --vdev 'eth_vhost0,iface=vhost-net,queues=16' -- -i --nb-cores=16 --rxq=16 --txq=16 --rss-ip

2. Launch VM1, set queues=16, vectors>=2xqueues+2, mq=on::

    taskset -c 34-35 \
    qemu-system-x86_64 -name us-vhost-vm2 \
     -cpu host -enable-kvm -m 2048 -object memory-backend-file,id=mem,size=2048M,mem-path=/mnt/huge,share=on -numa node,memdev=mem -mem-prealloc \
     -smp cores=16,sockets=1 -drive file=/home/osimg/ubuntu1910.img \
     -monitor unix:/tmp/vm2_monitor.sock,server,nowait -device e1000,netdev=nttsip1 \
     -netdev user,id=nttsip1,hostfwd=tcp:127.0.0.1:6003-:22 \
     -chardev socket,id=char1,path=./vhost-net -netdev type=vhost-user,id=mynet2,chardev=char1,vhostforce,queues=16 \
     -device virtio-net-pci,mac=52:54:00:00:00:02,netdev=mynet2,mrg_rxbuf=on,csum=on,mq=on,vectors=40  \
     -vnc :11 -daemonize

3. Bind virtio port to vfio-pci::

    modprobe vfio enable_unsafe_noiommu_mode=1
    modprobe vfio-pci
    ./usertools/dpdk-devbind.py --bind=vfio-pci xx:xx.x

4. In VM, launch l3fwd-power sample::

    ./x86_64-native-linuxapp-gcc/examples/dpdk-l3fwd-power -c 0x0ffff -n 4 --log-level='user1,7' -- -p 1 -P  --config '(0,0,0),(0,1,1),(0,2,2),(0,3,3)(0,4,4),(0,5,5),(0,6,6),(0,7,7)(0,8,8),(0,9,9),(0,10,10),(0,11,11)(0,12,12),(0,13,13),(0,14,14),(0,15,15)' --no-numa  --parse-ptype

5. Send random dest ip address packets to host nic with packet generator, packets will distribute to all queues, check l3fwd-power log that all related cores are waked up.

6. Change dest IP address to fixed ip, packets will distribute to 1 queue, check l3fwd-power log that only one related core is waked up.

7. Stop the date transmitter, check all related core will be back to sleep status.

Test Case 3: Basic virtio-1.0 interrupt test with 4 queues
==========================================================

1. Bind one NIC port to vfio-pci, then launch testpmd by below command::

    rm -rf vhost-net*
    ./x86_64-native-linuxapp-gcc/app/dpdk-testpmd -c 0x7c -n 4 --vdev 'net_vhost0,iface=vhost-net,queues=4' -- -i --nb-cores=4 --rxq=4 --txq=4 --rss-ip

2. Launch VM1, set queues=4, vectors>=2xqueues+2, mq=on::

    taskset -c 34-35 \
    qemu-system-x86_64 -name us-vhost-vm2 \
     -cpu host -enable-kvm -m 2048 -object memory-backend-file,id=mem,size=2048M,mem-path=/mnt/huge,share=on -numa node,memdev=mem -mem-prealloc \
     -smp cores=4,sockets=1 -drive file=/home/osimg/ubuntu1910.img \
     -monitor unix:/tmp/vm2_monitor.sock,server,nowait -device e1000,netdev=nttsip1 \
     -netdev user,id=nttsip1,hostfwd=tcp:127.0.0.1:6003-:22 \
     -chardev socket,id=char1,path=./vhost-net -netdev type=vhost-user,id=mynet2,chardev=char1,vhostforce,queues=4 \
     -device virtio-net-pci,mac=52:54:00:00:00:02,netdev=mynet2,disable-modern=false,mrg_rxbuf=on,csum=on,mq=on,vectors=15  \
     -vnc :11 -daemonize

3. Bind virtio port to vfio-pci::

    modprobe vfio enable_unsafe_noiommu_mode=1
    modprobe vfio-pci
    ./usertools/dpdk-devbind.py --bind=vfio-pci xx:xx.x

4. In VM, launch l3fwd-power sample::

    ./x86_64-native-linuxapp-gcc/examples/dpdk-l3fwd-power -c 0xf -n 4 --log-level='user1,7' -- -p 1 -P --config="(0,0,0),(0,1,1),(0,2,2),(0,3,3)" --no-numa --parse-ptype

5. Send random dest ip address packets to host nic with packet generator, packets will distribute to all queues, check l3fwd-power log that all related cores are waked up.

6. Change dest IP address to fixed ip, packets will distribute to 1 queue, check l3fwd-power log that only one related core is waked up.

7. Stop the date transmitter, check all related core will be back to sleep status.

Test Case 4: Packed ring virtio interrupt test with 16 queues
=============================================================

1. Bind one NIC port to vfio-pci, then launch testpmd by below command::

    rm -rf vhost-net*
    ./x86_64-native-linuxapp-gcc/app/dpdk-testpmd -c 0x1ffff -n 4 --vdev 'eth_vhost0,iface=vhost-net,queues=16' -- -i --nb-cores=16 --rxq=16 --txq=16 --rss-ip

2. Launch VM1, set queues=16, vectors>=2xqueues+2, mq=on::

    taskset -c 34-35 \
    qemu-system-x86_64 -name us-vhost-vm2 \
     -cpu host -enable-kvm -m 2048 -object memory-backend-file,id=mem,size=2048M,mem-path=/mnt/huge,share=on -numa node,memdev=mem -mem-prealloc \
     -smp cores=16,sockets=1 -drive file=/home/osimg/ubuntu1910.img \
     -monitor unix:/tmp/vm2_monitor.sock,server,nowait -device e1000,netdev=nttsip1 \
     -netdev user,id=nttsip1,hostfwd=tcp:127.0.0.1:6003-:22 \
     -chardev socket,id=char1,path=./vhost-net -netdev type=vhost-user,id=mynet2,chardev=char1,vhostforce,queues=16 \
     -device virtio-net-pci,mac=52:54:00:00:00:02,netdev=mynet2,mrg_rxbuf=on,csum=on,mq=on,vectors=40,packed=on  \
     -vnc :11 -daemonize

3. Bind virtio port to vfio-pci::

    modprobe vfio enable_unsafe_noiommu_mode=1
    modprobe vfio-pci
    ./usertools/dpdk-devbind.py --bind=vfio-pci xx:xx.x

4. In VM, launch l3fwd-power sample::

    ./x86_64-native-linuxapp-gcc/examples/dpdk-l3fwd-power -c 0x0ffff -n 4 --log-level='user1,7' -- -p 1 -P  --config '(0,0,0),(0,1,1),(0,2,2),(0,3,3)(0,4,4),(0,5,5),(0,6,6),(0,7,7)(0,8,8),(0,9,9),(0,10,10),(0,11,11)(0,12,12),(0,13,13),(0,14,14),(0,15,15)' --no-numa  --parse-ptype

5. Send random dest ip address packets to host nic with packet generator, packets will distribute to all queues, check l3fwd-power log that all related cores are waked up.

6. Change dest IP address to fixed ip, packets will distribute to 1 queue, check l3fwd-power log that only one related core is waked up.

7. Stop the date transmitter, check all related core will be back to sleep status.
