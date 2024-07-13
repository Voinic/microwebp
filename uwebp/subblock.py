from .globals import (
    COEF_TREE,
    COEF_BANDS,
    DEFAULT_ZIG_ZAG_1D,
    P_CAT_1,
    P_CAT_2,
    P_CAT_3,
    P_CAT_4,
    P_CAT_5,
    P_CAT_6,
    AC_LOOKUP,
    DC_LOOKUP,
)
from .idct import IDCT


class SubBlock:
    class PLANE:
        U = "U"
        V = "V"
        Y1 = "Y1"
        Y2 = "Y2"

    @staticmethod
    def plane_to_type(plane, with_y2):
        if plane == SubBlock.PLANE.Y2:
            return 1
        elif plane == SubBlock.PLANE.Y1:
            return 0 if with_y2 else 3
        elif plane in [SubBlock.PLANE.U, SubBlock.PLANE.V]:
            return 2
        return -1

    def __init__(self, macro_block, above, left, plane):
        self.macro_block = macro_block
        self.plane = plane
        self.above = above
        self.left = left
        self.mode = 0
        self.tokens = [0] * 16
        self.dest = None
        self.diff = None
        self.predicted = None
    
    @micropython.native
    def dct_extra(self, bc, p):
        v = 0
        offset = 0
        while True:
            v = (v << 1) + bc.read_bool(p[offset])
            offset += 1
            if p[offset] <= 0:
                break
        return v
    
    @micropython.native
    def decode_sub_block(self, bc, coef_probs, ilc, probs_type, with_y2):
        start_at = 1 if with_y2 else 0
        lc = ilc
        c = 0
        v = 1
        skip = False

        while v != 11 and c + start_at < 16:
            if not skip:
                v = bc.treed_read(
                    COEF_TREE, coef_probs[probs_type][COEF_BANDS[c + start_at]][lc]
                )
            else:
                v = bc.treed_read(
                    COEF_TREE, coef_probs[probs_type][COEF_BANDS[c + start_at]][lc], 1
                )

            dv = self.decode_token(bc, v)
            lc = 0
            skip = False

            if dv not in [-1, 1]:
                if -1 <= dv <= 1:
                    if dv == 0:
                        skip = True
                else:
                    lc = 2
            else:
                lc = 1

            if v != 11:
                self.tokens[DEFAULT_ZIG_ZAG_1D[c + start_at]] = dv
            c += 1
    
    @micropython.native
    def decode_token(self, bc, v):
        if v == 5:
            r = 5 + self.dct_extra(bc, P_CAT_1)
        elif v == 6:
            r = 7 + self.dct_extra(bc, P_CAT_2)
        elif v == 7:
            r = 11 + self.dct_extra(bc, P_CAT_3)
        elif v == 8:
            r = 19 + self.dct_extra(bc, P_CAT_4)
        elif v == 9:
            r = 35 + self.dct_extra(bc, P_CAT_5)
        elif v == 10:
            r = 67 + self.dct_extra(bc, P_CAT_6)
        else:
            r = v

        if v != 0 and v != 11 and bc.read_bit() > 0:
            r = -r

        return r

    def get_tokens(self):
        return self.tokens
    
    @micropython.native
    def dequant_sub_block(self, frame, dc):
        adjusted_values = [0] * 16

        for diff in range(16):
            q_value = AC_LOOKUP[frame.get_q_index()]
            if diff == 0:
                q_value = DC_LOOKUP[frame.get_q_index()]

            input_value = self.tokens[diff]
            adjusted_values[diff] = input_value * q_value

        if dc is not None:
            adjusted_values[0] = dc

        self.diff = IDCT.idct4x4llm_c(adjusted_values)

    def get_above(self):
        return self.above

    def get_dest(self):
        return self.dest if self.dest is not None else [[0] * 4 for _ in range(4)]

    def is_dest(self):
        return self.dest is not None

    def get_diff(self):
        return self.diff

    def get_left(self):
        return self.left

    def get_macro_block(self):
        return self.macro_block

    def get_mode(self):
        return self.mode

    def get_plane(self):
        return self.plane
    
    @micropython.native
    def get_predict(self, intra_bmode, left):
        if self.dest is not None:
            return self.dest
        elif self.predicted is not None:
            return self.predicted
        else:
            rv = 127
            if intra_bmode in {0, 2, 6, 5, 8} and left:
                rv = 129

            return [[rv] * 4 for _ in range(4)]
    
    @micropython.native
    def get_macro_block_predict(self, intra_mode):
        if self.dest is not None:
            return self.dest
        else:
            rv = 127
            if intra_mode == 2:
                rv = 129

            return [[rv] * 4 for _ in range(4)]

    def has_no_zero_token(self):
        return any(token != 0 for token in self.tokens)
    
    @micropython.native
    def predict(self, frame):
        # Get above and left SubBlocks
        above_sb = frame.get_above_sub_block(self, self.get_plane())
        left_sb = frame.get_left_sub_block(self, self.get_plane())

        # Get pixel values from above and left SubBlocks
        above = [above_sb.get_predict(self.get_mode(), False)[i][3] for i in range(4)]
        left = [left_sb.get_predict(self.get_mode(), True)[3][i] for i in range(4)]

        # Calculate AL and AR
        AL = frame.get_left_sub_block(above_sb, self.get_plane())
        ar = [
            frame.get_above_right_sub_block(self, self.plane).get_predict(
                self.get_mode(), False
            )[i][3]
            for i in range(4)
        ]

        al = AL.get_predict(
            self.get_mode(), not left_sb.is_dest() and not above_sb.is_dest()
        )[3][3]

        # Initialize prediction matrix p
        p = [[0] * 4 for _ in range(4)]

        # Switch based on prediction mode
        mode = self.get_mode()

        if mode == 0:
            expected_dc = sum(above) + sum(left) + 4
            expected_dc = expected_dc >> 3

            for i in range(4):
                for j in range(4):
                    p[i][j] = expected_dc

        elif mode == 1:
            for i in range(4):
                for j in range(4):
                    r = above[i] - al + left[j]
                    r = max(0, min(r, 255))
                    p[i][j] = r

        elif mode == 2:
            ap = [(al + 2 * above[i] + above[i + 1] + 2) >> 2 for i in range(3)] + [
                (above[2] + 2 * above[3] + ar[0] + 2) >> 2
            ]

            for i in range(4):
                for j in range(4):
                    p[i][j] = ap[i]

        elif mode == 3:
            lp = [(al + 2 * left[i] + left[i + 1] + 2) >> 2 for i in range(3)] + [
                (left[2] + 2 * left[3] + left[3] + 2) >> 2
            ]

            for i in range(4):
                for j in range(4):
                    p[i][j] = lp[j]

        elif mode == 4:
            p[0][0] = (above[0] + above[1] * 2 + above[2] + 2) >> 2
            p[1][0] = p[0][1] = (above[1] + above[2] * 2 + above[3] + 2) >> 2
            p[2][0] = p[1][1] = p[0][2] = (above[2] + above[3] * 2 + ar[0] + 2) >> 2
            p[3][0] = p[2][1] = p[1][2] = p[0][3] = (
                above[3] + ar[0] * 2 + ar[1] + 2
            ) >> 2
            p[3][1] = p[2][2] = p[1][3] = (ar[0] + ar[1] * 2 + ar[2] + 2) >> 2
            p[3][2] = p[2][3] = (ar[1] + ar[2] * 2 + ar[3] + 2) >> 2
            p[3][3] = (ar[2] + ar[3] * 2 + ar[3] + 2) >> 2

        elif mode == 5:
            pp = [
                left[3],
                left[2],
                left[1],
                left[0],
                al,
                above[0],
                above[1],
                above[2],
                above[3],
            ]

            p[0][3] = (pp[0] + pp[1] * 2 + pp[2] + 2) >> 2
            p[1][3] = p[0][2] = (pp[1] + pp[2] * 2 + pp[3] + 2) >> 2
            p[2][3] = p[1][2] = p[0][1] = (pp[2] + pp[3] * 2 + pp[4] + 2) >> 2
            p[3][3] = p[2][2] = p[1][1] = p[0][0] = (pp[3] + pp[4] * 2 + pp[5] + 2) >> 2
            p[3][2] = p[2][1] = p[1][0] = (pp[4] + pp[5] * 2 + pp[6] + 2) >> 2
            p[3][1] = p[2][0] = (pp[5] + pp[6] * 2 + pp[7] + 2) >> 2
            p[3][0] = (pp[6] + pp[7] * 2 + pp[8] + 2) >> 2

        elif mode == 6:
            pp = [
                left[3],
                left[2],
                left[1],
                left[0],
                al,
                above[0],
                above[1],
                above[2],
                above[3],
            ]

            p[0][3] = (pp[1] + pp[2] * 2 + pp[3] + 2) >> 2
            p[0][2] = (pp[2] + pp[3] * 2 + pp[4] + 2) >> 2
            p[1][3] = p[0][1] = (pp[3] + pp[4] * 2 + pp[5] + 2) >> 2
            p[1][2] = p[0][0] = (pp[4] + pp[5] + 1) >> 1
            p[2][3] = p[1][1] = (pp[4] + pp[5] * 2 + pp[6] + 2) >> 2
            p[2][2] = p[1][0] = (pp[5] + pp[6] + 1) >> 1
            p[3][3] = p[2][1] = (pp[5] + pp[6] * 2 + pp[7] + 2) >> 2
            p[3][2] = p[2][0] = (pp[6] + pp[7] + 1) >> 1
            p[3][1] = (pp[6] + pp[7] * 2 + pp[8] + 2) >> 2
            p[3][0] = (pp[7] + pp[8] + 1) >> 1

        elif mode == 7:
            p[0][0] = (above[0] + above[1] + 1) >> 1
            p[0][1] = (above[0] + above[1] * 2 + above[2] + 2) >> 2
            p[0][2] = p[1][0] = (above[1] + above[2] + 1) >> 1
            p[1][1] = p[0][3] = (above[1] + above[2] * 2 + above[3] + 2) >> 2
            p[1][2] = p[2][0] = (above[2] + above[3] + 1) >> 1
            p[1][3] = p[2][1] = (above[2] + above[3] * 2 + ar[0] + 2) >> 2
            p[3][0] = p[2][2] = (above[3] + ar[0] + 1) >> 1
            p[3][1] = p[2][3] = (above[3] + ar[0] * 2 + ar[1] + 2) >> 2
            p[3][2] = (ar[0] + ar[1] * 2 + ar[2] + 2) >> 2
            p[3][3] = (ar[1] + ar[2] * 2 + ar[3] + 2) >> 2

        elif mode == 8:
            pp = [
                left[3],
                left[2],
                left[1],
                left[0],
                al,
                above[0],
                above[1],
                above[2],
                above[3],
            ]

            p[0][3] = (pp[0] + pp[1] + 1) >> 1
            p[1][3] = (pp[0] + pp[1] * 2 + pp[2] + 2) >> 2
            p[0][2] = p[2][3] = (pp[1] + pp[2] + 1) >> 1
            p[1][2] = p[3][3] = (pp[1] + pp[2] * 2 + pp[3] + 2) >> 2
            p[2][2] = p[0][1] = (pp[2] + pp[3] + 1) >> 1
            p[3][2] = p[1][1] = (pp[2] + pp[3] * 2 + pp[4] + 2) >> 2
            p[2][1] = p[0][0] = (pp[3] + pp[4] + 1) >> 1
            p[3][1] = p[1][0] = (pp[3] + pp[4] * 2 + pp[5] + 2) >> 2
            p[2][0] = (pp[4] + pp[5] * 2 + pp[6] + 2) >> 2
            p[3][0] = (pp[5] + pp[6] * 2 + pp[7] + 2) >> 2

        elif mode == 9:
            p[0][0] = (left[0] + left[1] + 1) >> 1
            p[1][0] = (left[0] + left[1] * 2 + left[2] + 2) >> 2
            p[2][0] = p[0][1] = (left[1] + left[2] + 1) >> 1
            p[3][0] = p[1][1] = (left[1] + left[2] * 2 + left[3] + 2) >> 2
            p[2][1] = p[0][2] = (left[2] + left[3] + 1) >> 1
            p[3][1] = p[1][2] = (left[2] + left[3] * 2 + left[3] + 2) >> 2
            p[2][2] = p[3][2] = p[0][3] = p[1][3] = p[2][3] = p[3][3] = left[3]

        else:
            print("TODO:", mode)
            exit(0)

        self.set_predict(p)
    
    @micropython.native
    def reconstruct(self):
        p = self.get_predict(1, False)
        dest = [[0 for _ in range(4)] for _ in range(4)]
        diff = self.get_diff()

        for r in range(4):
            for c in range(4):
                a = diff[r][c] + p[r][c]
                a = max(0, min(255, a))
                dest[r][c] = a

        self.set_dest(dest)

    def set_dest(self, dest):
        self.dest = dest

    def set_diff(self, diff):
        self.diff = diff

    def set_mode(self, mode):
        self.mode = mode
    
    def set_pixel(self, x, y, p):
        if self.dest is None:
            self.dest = [[0] * 4 for _ in range(4)]
        self.dest[x][y] = p

    def set_predict(self, predict):
        self.predicted = predict

    def __str__(self):
        return "[" + " ".join(str(token) for token in self.tokens) + "]"

    def draw_debug_v(self):
        if self.dest is not None:
            self.dest[0][0] = 0
            self.dest[0][1] = 0
            self.dest[0][2] = 0
            self.dest[0][3] = 0

    def draw_debug_h(self):
        if self.dest is not None:
            self.dest[0][0] = 0
            self.dest[1][0] = 0
            self.dest[2][0] = 0
            self.dest[3][0] = 0
