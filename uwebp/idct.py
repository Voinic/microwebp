import micropython


class IDCT:
    cospi8sqrt2minus1 = 20091
    sinpi8sqrt2 = 35468

    @staticmethod
    @micropython.native
    def iwalsh4x4(input_array):
        output = [0] * 16
        diff = [[0] * 4 for _ in range(4)]
        offset = 0

        for i in range(4):
            a1 = input_array[offset + 0] + input_array[offset + 12]
            b1 = input_array[offset + 4] + input_array[offset + 8]
            c1 = input_array[offset + 4] - input_array[offset + 8]
            d1 = input_array[offset + 0] - input_array[offset + 12]
            output[offset + 0] = a1 + b1
            output[offset + 4] = c1 + d1
            output[offset + 8] = a1 - b1
            output[offset + 12] = d1 - c1
            offset += 1

        offset = 0

        for i in range(4):
            a1 = output[offset + 0] + output[offset + 3]
            b1 = output[offset + 1] + output[offset + 2]
            c1 = output[offset + 1] - output[offset + 2]
            d1 = output[offset + 0] - output[offset + 3]
            a2 = a1 + b1
            b2 = c1 + d1
            c2 = a1 - b1
            d2 = d1 - c1
            output[offset + 0] = (a2 + 3) >> 3
            output[offset + 1] = (b2 + 3) >> 3
            output[offset + 2] = (c2 + 3) >> 3
            output[offset + 3] = (d2 + 3) >> 3
            diff[0][i] = (a2 + 3) >> 3
            diff[1][i] = (b2 + 3) >> 3
            diff[2][i] = (c2 + 3) >> 3
            diff[3][i] = (d2 + 3) >> 3
            offset += 4

        return diff

    @staticmethod
    @micropython.native
    def idct4x4llm_c(input_array):
        offset = 0
        output = [0] * 16

        for _ in range(4):
            a1 = input_array[offset + 0] + input_array[offset + 8]
            b1 = input_array[offset + 0] - input_array[offset + 8]
            temp1 = input_array[offset + 4] * IDCT.sinpi8sqrt2 >> 16
            temp2 = input_array[offset + 12] + (
                input_array[offset + 12] * IDCT.cospi8sqrt2minus1 >> 16
            )
            c1 = temp1 - temp2
            temp1 = input_array[offset + 4] + (
                input_array[offset + 4] * IDCT.cospi8sqrt2minus1 >> 16
            )
            temp2 = input_array[offset + 12] * IDCT.sinpi8sqrt2 >> 16
            d1 = temp1 + temp2
            output[offset + 0] = a1 + d1
            output[offset + 12] = a1 - d1
            output[offset + 4] = b1 + c1
            output[offset + 8] = b1 - c1
            offset += 1

        diffo = 0
        diff = [[0] * 4 for _ in range(4)]
        offset = 0

        for _ in range(4):
            a1 = output[offset * 4 + 0] + output[offset * 4 + 2]
            b1 = output[offset * 4 + 0] - output[offset * 4 + 2]
            temp1 = output[offset * 4 + 1] * IDCT.sinpi8sqrt2 >> 16
            temp2 = output[offset * 4 + 3] + (
                output[offset * 4 + 3] * IDCT.cospi8sqrt2minus1 >> 16
            )
            c1 = temp1 - temp2
            temp1 = output[offset * 4 + 1] + (
                output[offset * 4 + 1] * IDCT.cospi8sqrt2minus1 >> 16
            )
            temp2 = output[offset * 4 + 3] * IDCT.sinpi8sqrt2 >> 16
            d1 = temp1 + temp2
            output[offset * 4 + 0] = (a1 + d1 + 4) >> 3
            output[offset * 4 + 3] = (a1 - d1 + 4) >> 3
            output[offset * 4 + 1] = (b1 + c1 + 4) >> 3
            output[offset * 4 + 2] = (b1 - c1 + 4) >> 3
            diff[0][diffo] = (a1 + d1 + 4) >> 3
            diff[3][diffo] = (a1 - d1 + 4) >> 3
            diff[1][diffo] = (b1 + c1 + 4) >> 3
            diff[2][diffo] = (b1 - c1 + 4) >> 3
            offset += 1
            diffo += 1

        return diff
