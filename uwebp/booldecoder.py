import micropython
from .globals import VP8DX_BITREADER_NORM


class BoolDecoder:
    def __init__(self, frame, offset):
        self.data = frame
        self.offset = offset
        self.init_bool_decoder()

    def __str__(self):
        return f"bc: {self.value}"

    def init_bool_decoder(self):
        self.value = 0
        self.value = self.data[self.offset] << 8
        self.offset += 1
        self.range = 255
        self.bit_count = 0
    
    @micropython.native
    def read_bool(self, probability):
        bit = 0
        _range = self.range
        value = self.value
        split = 1 + ((_range - 1) * probability >> 8)
        bigsplit = split << 8
        _range = split
        if value >= bigsplit:
            _range = self.range - split
            value -= bigsplit
            bit = 1

        count = self.bit_count
        shift = VP8DX_BITREADER_NORM[_range]
        _range <<= shift
        value <<= shift
        count -= shift
        if count <= 0:
            value |= self.data[self.offset] << -count
            self.offset += 1
            count += 8

        self.bit_count = count
        self.value = value
        self.range = _range
        return bit
    
    @micropython.native
    def read_literal(self, num_bits):
        v = 0
        for _ in range(num_bits):
            v = (v << 1) + self.read_bool(128)
        return v

    def read_bit(self):
        return self.read_bool(128)
    
    @micropython.native
    def treed_read(self, t, p, skip_branches=0):
        i = skip_branches * 2
        i = t[i + self.read_bool(p[i >> 1])]
        while i > 0:
            i = t[i + self.read_bool(p[i >> 1])]
        return -i

