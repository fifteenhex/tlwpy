import struct
import logging

MHDR_MTYPE_SHIFT = 5
MHDR_MTYPE_MASK = 0b111
MHDR_MTYPE_JOINREQ = 0b000
MHDR_MTYPE_JOINACK = 0b001
MHDR_MTYPE_UNCNFUP = 0b010
MHDR_MTYPE_UNCNFDN = 0b011
MHDR_MTYPE_CNFUP = 0b100
MHDR_MTYPE_CNFDN = 0b101

FCTRL_FOPTSLEN_MASK = 0b1111


def get_packet_type(raw_packet: bytearray):
    mhdr = raw_packet[0]
    return (mhdr >> MHDR_MTYPE_SHIFT) & MHDR_MTYPE_MASK


class Packet:
    __slots__ = ['type', 'mac_payload']

    def __init__(self, raw_packet: bytearray):
        self.type = get_packet_type(raw_packet)
        self.mac_payload = raw_packet[1:-4]


class JoinReq(Packet):
    __slots__ = ['appeui', 'deveui', 'devnonce']

    def __init__(self, raw_packet: bytearray):
        super(JoinReq, self).__init__(raw_packet)
        unpacked = struct.unpack('<QQH', self.mac_payload)
        self.appeui = unpacked[0]
        self.deveui = unpacked[1]
        self.devnonce = unpacked[2]


class JoinAccept(Packet):
    def __init__(self, raw_packet: bytearray):
        super(JoinAccept, self).__init__(raw_packet)


class Data(Packet):
    __slots__ = ['devaddr', 'framecounter', 'port', 'data', 'mic']

    def __init__(self, raw_packet: bytearray):
        super(Data, self).__init__(raw_packet)

        mic = raw_packet[-4:]

        # unpack the header and get the devaddr and framecounter
        fheader = self.mac_payload[0:7]
        unpacked_header = struct.unpack('<IBh', fheader)
        self.devaddr = unpacked_header[0]
        self.framecounter = unpacked_header[2]

        # parse fctrl byte
        fctrl = unpacked_header[1]
        num_fopts = fctrl & FCTRL_FOPTSLEN_MASK
        logging.debug('packet has %d fopts' % num_fopts)

        # pull out the port and payload
        frmpayload = self.mac_payload[7 + num_fopts:]
        if len(frmpayload) == 0:
            logging.debug('packet has no payload')
        self.port = struct.unpack('<B', frmpayload[0:1])[0]

    def decrypt(self):
        pass


class Uplink(Data):

    def __init__(self, raw_packet: bytearray):
        super(Uplink, self).__init__(raw_packet)


class Downlink(Data):

    def __init__(self, raw_packet: bytearray):
        super(Downlink, self).__init__(raw_packet)
