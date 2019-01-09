import tlwpy.liblorawan


def test_build_joinreq():
    packet = tlwpy.liblorawan.builder_joinreq(b'0000000000000000', b'00000000', b'00000000', b'00')
    print(packet)
    assert type(packet) is bytearray
    assert len(packet) is 23
