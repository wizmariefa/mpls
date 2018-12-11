import queue
import threading
from link_3 import LinkFrame
from copy import deepcopy


# wrapper class for a queue of packets
class Interface:
    # @param maxsize - the maximum size of the queue storing packets
    #  @param capacity - the capacity of the link in bps
    def __init__(self, maxsize=0, capacity=500):
        self.in_queue = queue.PriorityQueue(maxsize)
        self.out_queue = queue.PriorityQueue(maxsize)
        self.capacity = capacity  # serialization rate
        self.next_avail_time = 0  # the next time the interface can transmit a packet

    # get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, name, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                self.printQueue(name, in_or_out)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                self.printQueue(name, in_or_out)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None

    # put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, name, pkt, in_or_out, block=False):
        priority = pkt[len(pkt) - 1:]
        pri = -1 * int(priority)

        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put((pri, pkt), block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put((pri, pkt), block)

        self.printQueue(name, in_or_out)

    def printQueue(self, name, in_or_out):

        outputText = 'Queue: ' + in_or_out + ' queue for ' + name + ' is: '

        if in_or_out == 'out':
            outputText += str(list(self.out_queue.queue))

        else:
            outputText += str(list(self.in_queue.queue))

        print(outputText)






# Implements a network layer packet
# NOTE: You will need to extend this class for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    # packet encoding lengths
    dst_S_length = 5

    # @param dst: address of the destination host
    # @param data_S: packet payload
    # @param priority: packet priority
    def __init__(self, src, dst, data_S, priority):
        self.src = src
        self.dst = dst
        self.data_S = data_S
        # TODO: add priority to the packet class
        self.priority = priority

    # called when printing the object
    def __str__(self):
        return self.to_byte_S()

    # convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.src) + str(self.dst)
        byte_S = byte_S.zfill(self.dst_S_length)
        byte_S += self.data_S
        byte_S += str(self.priority)
        return byte_S

    # extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        src = byte_S[0: NetworkPacket.dst_S_length - 2].strip('0')
        dst = byte_S[NetworkPacket.dst_S_length - 2 : NetworkPacket.dst_S_length].strip('0')
        data_S = byte_S[NetworkPacket.dst_S_length : len(byte_S) - 1]
        priority = byte_S[len(byte_S) - 1 : ]
        return self(src, dst, data_S, priority)


class MPLSFrame:
    label_length = 20
    # @param dst: address of the destination host
    # @param data_S: packet payload
    # @param priority: packet priority
    # default label length is 20

    def __init__(self, label, packet, label_length=20):
        self.label_length = label_length
        self.label = label
        self.p = packet

    # called when printing the object
    def __str__(self):
        return self.to_byte_S()

    # convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.label).zfill(self.label_length)
        byte_S += self.p.to_byte_S()
        return byte_S

    # extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        label = byte_S[0:MPLSFrame.label_length].strip('0')
        data_S = byte_S[MPLSFrame.label_length:]
        return self(label, NetworkPacket.from_byte_S(data_S))

# Implements a network host for receiving and transmitting data


class Host:

    # @param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False  # for thread termination

    # called when printing the object
    def __str__(self):
        return self.addr

    # create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    # @param priority: packet priority
    def udt_send(self, src, dst, data_S, priority):


        pkt = NetworkPacket(src, dst, data_S, priority)
        print('%s: sending packet "%s" with priority %d' %
              (self, pkt, priority))
        # encapsulate network packet in a link frame (usually would be done by the OS)
        fr = LinkFrame('Network', pkt.to_byte_S())
        # enque frame onto the interface for transmission

        self.intf_L[0].put(self.addr,fr.to_byte_S(), 'out')

    # receive frame from the link layer
    def udt_receive(self):
        fr_S = self.intf_L[0].get(self.addr,'in')
        if fr_S is None:
            return
        # decapsulate the network packet
        fr = LinkFrame.from_byte_S(fr_S[1])
        # should be receiving network packets by hosts
        assert(fr.type_S == 'Network')
        pkt_S = fr.data_S
        print('%s: received packet "%s"' % (self, pkt_S))

    # thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if(self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return

# Implements a multi-interface router


class Router:

    # @param name: friendly router name for debugging
    # @param intf_capacity_L: capacities of outgoing interfaces in bps
    # @param encap_tbl_D: table used to encapsulate network packets into MPLS frames
    # @param frwd_tbl_D: table used to forward MPLS frames
    # @param decap_tbl_D: table used to decapsulate network packets from MPLS frames
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_capacity_L, encap_tbl_D, frwd_tbl_D, decap_tbl_D, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.intf_L = [Interface(max_queue_size, intf_capacity_L[i])
                       for i in range(len(intf_capacity_L))]
        # save MPLS tables
        self.encap_tbl_D = encap_tbl_D
        self.frwd_tbl_D = frwd_tbl_D
        self.decap_tbl_D = decap_tbl_D

    # called when printing the object

    def __str__(self):
        return self.name

    # look through the content of incoming interfaces and
    # process data and control packets

    def process_queues(self):
        for i in range(len(self.intf_L)):
            fr_S = None  # make sure we are starting the loop with a blank frame
            fr_S = self.intf_L[i].get(self.name,'in')  # get frame from interface i
            if fr_S is None:
                continue  # no frame to process yet
            # decapsulate the packet
            fr = LinkFrame.from_byte_S(fr_S[1])
            pkt_S = fr.data_S
            # process the packet as network, or MPLS
            if fr.type_S == "Network":
                p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                self.process_network_packet(p, i)
            elif fr.type_S == "MPLS":
                # TODO: handle MPLS frames
                fr = MPLSFrame.from_byte_S(pkt_S)  # parse a frame out
                # for now, we just relabel the packet as an MPLS frame without encapsulation
                # send the MPLS frame for processing
                self.process_MPLS_frame(fr, i)
            else:
                print('%s: unknown frame type: %s' % (self, fr.type_S))

    # process a network packet incoming to this router
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def process_network_packet(self, pkt, i):
        # TODO: encapsulate the packet in an MPLS frame based on self.encap_tbl_D
        # for now, we just relabel the packet as an MPLS frame without encapsulation
        if pkt.dst in self.encap_tbl_D or pkt.dst in self.decap_tbl_D:
            mpls_label = pkt.src + pkt.dst
            mpls_frame = MPLSFrame(mpls_label, pkt)

        else:
            mpls_label = pkt.src + pkt.dst
            mpls_frame = MPLSFrame(mpls_label, pkt)
        print('%s: encapsulated packet "%s" as MPLS frame "%s"' %
              (self, pkt, mpls_frame))
        # send the encapsulated packet for processing as MPLS frame
        self.process_MPLS_frame(mpls_frame, i)

    # process an MPLS frame incoming to this router
    #  @param m_fr: MPLS frame to process
    #  @param i Incoming interface number for the frame

    def process_MPLS_frame(self, m_fr, i):
        # TODO: implement MPLS forward, or MPLS decapsulation if this is the last hop router for the path
        print('%s: processing MPLS frame "%s"' % (self, m_fr))
        # default to interface 1
        intf = 1

        label = m_fr.label

        #grab source from label
        src = label[0:2]
        #redefine label to be only destination
        label = label[2:]

        # if this is the last router, decapsulate
        if str(label) in self.decap_tbl_D:
            intf = self.decap_tbl_D[label]
            fr = LinkFrame('Network', m_fr.p.to_byte_S())
        # otherwise find where it should go & forward
        elif str(label) in self.frwd_tbl_D:
            # self : { source : out_interface, source : out_interface }
            intfTable = {
                'RA': {'H1': 2, 'H2': 3},

                'RB': {'H1': 1, 'H2': 1},

                'RC': {'H1': 1, 'H2': 1},

                'RD': {'H1': 1, 'H2': 1}
            }

            intf = intfTable[self.name][src]

            #intf = self.frwd_tbl_D[label]['out']

            fr = LinkFrame('MPLS', m_fr.to_byte_S())

        try:
            self.intf_L[intf].put(self.name,fr.to_byte_S(), 'out', True)
            print('%s: forwarding frame "%s" from interface %d to %d' %
                  (self, fr, i, intf))
        except queue.Full:
            print('%s: frame "%s" lost on interface %d' % (self, m_fr, i))
            pass

    # thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return