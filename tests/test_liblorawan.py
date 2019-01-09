import tlwpy.liblorawan


def test_build_joinreq():
    packet = tlwpy.liblorawan.builder_joinreq()
    print(packet)
    assert type(packet) is bytearray
    assert len(packet) is 23
