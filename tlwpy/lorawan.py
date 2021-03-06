import struct
import logging
from enum import IntEnum

from tlwpy.liblorawan import decrypt_joinack, calculate_mic, calculate_sessionkeys

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


class PacketType(IntEnum):
    JOIN_REQ = 0b000,
    JOIN_ACK = 0b001,
    UNCONFIRMED_UP = 0b010,
    UNCONFIRMED_DOWN = 0b011,
    CONFIRMED_UP = 0b100,
    CONFIRMED_DOWN = 0b101


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
    __slots__ = ['appnonce', 'netid', 'devaddr', 'dlsetting', 'rxdelay']

    def __init__(self, raw_packet: bytearray):
        super(JoinAccept, self).__init__(raw_packet)

        fixed_part = self.mac_payload[:12]
        fixed_part[3:3] = [0]
        fixed_part[7:7] = [0]
        unpacked = struct.unpack('<LLLBB', fixed_part)
        self.appnonce = unpacked[0]
        self.netid = unpacked[1]
        self.devaddr = unpacked[2]
        self.dlsetting = unpacked[3]
        self.rxdelay = unpacked[4]


class SessionKeys:
    __slots__ = ['network_key', 'app_key']

    def __init__(self, key: bytes, appnonce: int, netid: int, devnonce: int):
        keys = calculate_sessionkeys(key, appnonce, netid, devnonce)
        assert len(keys) is 32
        self.network_key = keys[:16]
        self.app_key = keys[16:]

    def from_join_req_and_accept(self, key: bytes, req: JoinReq, accept: JoinAccept):
        return SessionKeys(key, accept.appnonce, accept.netid, req.devnonce)


class EncryptedJoinAccept:
    __slots__ = ['data']

    def __init__(self, data: bytes):
        assert (len(data) - 1) % 16 == 0
        self.data = data

    def decrypt(self, key: bytes):
        decrypted = decrypt_joinack(key, self.data)
        assert (len(decrypted) - 1) % 16 == 0
        packet_mic = struct.unpack('<L', decrypted[-4:])[0]
        actual_mic = calculate_mic(key, bytes(decrypted[:-4]))
        assert packet_mic == actual_mic, ('Calculated mic of %x but expected %x' % (actual_mic, packet_mic))
        return JoinAccept(decrypted)


class Data(Packet):
    __slots__ = ['devaddr',
                 'adr',
                 'ack',
                 'framecounter',
                 'port',
                 'data',
                 'mic',
                 'fctrl',
                 '__micced_part']

    FCTRL_ADR_SHIFT = 7
    FCTRL_ACK_SHIFT = 5

    def __init__(self, raw_packet: bytearray):
        super(Data, self).__init__(raw_packet)

        self.__micced_part = raw_packet[:-4]

        self.mic = raw_packet[-4:]

        # unpack the header and get the devaddr and framecounter
        fheader = self.mac_payload[0:7]
        unpacked_header = struct.unpack('<IBh', fheader)
        self.devaddr = unpacked_header[0]
        self.framecounter = unpacked_header[2]

        # parse fctrl byte
        self.fctrl = unpacked_header[1]
        self.adr = bool(self.fctrl >> self.FCTRL_ADR_SHIFT)
        self.ack = bool(self.fctrl >> self.FCTRL_ACK_SHIFT)
        num_fopts = self.fctrl & FCTRL_FOPTSLEN_MASK
        logging.debug('packet has %d fopts' % num_fopts)

        # pull out the port and payload
        frmpayload = self.mac_payload[7 + num_fopts:]
        if len(frmpayload) != 0:
            self.port = struct.unpack('<B', frmpayload[0:1])[0]
        else:
            logging.debug('packet has no payload')
            self.port = 0

    def verify_mic(self, key: bytes):
        return calculate_mic(key, self.__micced_part) == self.mic

    def decrypt(self):
        pass


class Uplink(Data):

    def __init__(self, raw_packet: bytearray):
        super(Uplink, self).__init__(raw_packet)


class Downlink(Data):
    __slots__ = ['fpending']

    FCTRL_FPENDING_SHIFT = 4

    def __init__(self, raw_packet: bytearray):
        super(Downlink, self).__init__(raw_packet)
        self.fpending = bool(self.fctrl >> self.FCTRL_FPENDING_SHIFT)
