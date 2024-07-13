import micropython

from .globals import AC_LOOKUP, DC_LOOKUP
from .subblock import SubBlock
from .idct import IDCT


class MacroBlock:
    @micropython.native
    def __init__(self, x, y):
        self.x = x - 1
        self.y = y - 1
        self.ySubBlocks = [[None] * 4 for _ in range(4)]
        self.uSubBlocks = [[None] * 2 for _ in range(2)]
        self.vSubBlocks = [[None] * 2 for _ in range(2)]
        self.mb_skip_coeff = 0
        self.yMode = 0
        self.uvMode = 0

        # Initialize Y sub-blocks
        for i in range(4):
            for j in range(4):
                left = self.ySubBlocks[j - 1][i] if j > 0 else None
                above = self.ySubBlocks[j][i - 1] if i > 0 else None
                self.ySubBlocks[j][i] = SubBlock(self, above, left, SubBlock.PLANE.Y1)

        # Initialize U sub-blocks
        for i in range(2):
            for j in range(2):
                left = self.uSubBlocks[j - 1][i] if j > 0 else None
                above = self.uSubBlocks[j][i - 1] if i > 0 else None
                self.uSubBlocks[j][i] = SubBlock(self, above, left, SubBlock.PLANE.U)

        # Initialize V sub-blocks
        for i in range(2):
            for j in range(2):
                left = self.vSubBlocks[j - 1][i] if j > 0 else None
                above = self.vSubBlocks[j][i - 1] if i > 0 else None
                self.vSubBlocks[j][i] = SubBlock(self, above, left, SubBlock.PLANE.V)

        self.y2SubBlock = SubBlock(self, None, None, SubBlock.PLANE.Y2)

    def get_y_mode(self):
        return self.yMode

    def set_y_mode(self, y_mode):
        self.yMode = y_mode

    def get_mb_skip_coeff(self):
        return self.mb_skip_coeff

    def set_mb_skip_coeff(self, mb_skip_coeff):
        self.mb_skip_coeff = mb_skip_coeff

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_y_sub_block(self, i, j):
        return self.ySubBlocks[i][j]

    def get_y2_sub_block(self):
        return self.y2SubBlock

    def get_u_sub_block(self, i, j):
        return self.uSubBlocks[i][j]

    def get_v_sub_block(self, i, j):
        return self.vSubBlocks[i][j]

    def get_sub_block(self, plane, i, j):
        if plane == SubBlock.PLANE.Y1:
            return self.get_y_sub_block(i, j)
        elif plane == SubBlock.PLANE.U:
            return self.get_u_sub_block(i, j)
        elif plane == SubBlock.PLANE.V:
            return self.get_v_sub_block(i, j)
        elif plane == SubBlock.PLANE.Y2:
            return self.get_y2_sub_block()
        return None

    def __str__(self):
        return "x: " + str(self.x) + " y: " + str(self.y)

    def get_subblock_y(self, sb):
        if sb.get_plane() == SubBlock.PLANE.Y1:
            for y in range(4):
                for x in range(4):
                    if self.ySubBlocks[x][y] == sb:
                        return y
        elif sb.get_plane() == SubBlock.PLANE.U:
            for y in range(2):
                for x in range(2):
                    if self.uSubBlocks[x][y] == sb:
                        return y
        elif sb.get_plane() == SubBlock.PLANE.V:
            for y in range(2):
                for x in range(2):
                    if self.vSubBlocks[x][y] == sb:
                        return y
        elif sb.get_plane() == SubBlock.PLANE.Y2:
            return 0
        return -100

    def get_subblock_x(self, sb):
        if sb.get_plane() == SubBlock.PLANE.Y1:
            for y in range(4):
                for x in range(4):
                    if self.ySubBlocks[x][y] == sb:
                        return x
        elif sb.get_plane() == SubBlock.PLANE.U:
            for y in range(2):
                for x in range(2):
                    if self.uSubBlocks[x][y] == sb:
                        return x
        elif sb.get_plane() == SubBlock.PLANE.V:
            for y in range(2):
                for x in range(2):
                    if self.vSubBlocks[x][y] == sb:
                        return x
        elif sb.get_plane() == SubBlock.PLANE.Y2:
            return 0
        return -100

    def get_right_subblock(self, y, plane):
        if plane == SubBlock.PLANE.Y1:
            return self.ySubBlocks[3][y]
        elif plane == SubBlock.PLANE.U:
            return self.uSubBlocks[1][y]
        elif plane == SubBlock.PLANE.V:
            return self.vSubBlocks[1][y]
        elif plane == SubBlock.PLANE.Y2:
            return self.y2SubBlock
        else:
            return None

    def get_left_subblock(self, y, plane):
        if plane == SubBlock.PLANE.Y1:
            return self.ySubBlocks[0][y]
        elif plane == SubBlock.PLANE.V:
            return self.vSubBlocks[0][y]
        elif plane == SubBlock.PLANE.Y2:
            return self.y2SubBlock
        elif plane == SubBlock.PLANE.U:
            return self.uSubBlocks[0][y]
        else:
            return None

    def get_bottom_subblock(self, x, plane):
        if plane == SubBlock.PLANE.Y1:
            return self.ySubBlocks[x][3]
        elif plane == SubBlock.PLANE.U:
            return self.uSubBlocks[x][1]
        elif plane == SubBlock.PLANE.V:
            return self.vSubBlocks[x][1]
        elif plane == SubBlock.PLANE.Y2:
            return self.y2SubBlock
        else:
            return None
    
    @micropython.native
    def predict_uv(self, frame):
        above_mb = frame.get_macro_block(self.x, self.y - 1)
        left_mb = frame.get_macro_block(self.x - 1, self.y)

        if self.uvMode == 0:
            up_available = False
            left_available = False
            u_average = 0
            v_average = 0

            if self.x > 0:
                left_available = True
            if self.y > 0:
                up_available = True

            if not up_available and not left_available:
                u_average = 128
                v_average = 128
            else:
                if up_available:
                    for u_fill in range(2):
                        above_u_sb = above_mb.get_u_sub_block(u_fill, 1)
                        above_v_sb = above_mb.get_v_sub_block(u_fill, 1)
                        for var34 in range(4):
                            u_average += above_u_sb.get_dest()[var34][3]
                            v_average += above_v_sb.get_dest()[var34][3]

                if left_available:
                    for u_fill in range(2):
                        left_u_sb = left_mb.get_u_sub_block(1, u_fill)
                        left_v_sb = left_mb.get_v_sub_block(1, u_fill)
                        for var34 in range(4):
                            u_average += left_u_sb.get_dest()[3][var34]
                            v_average += left_v_sb.get_dest()[3][var34]

                u_fill = 2
                if up_available:
                    u_fill += 1
                if left_available:
                    u_fill += 1

                u_average = (u_average + (1 << (u_fill - 1))) >> u_fill
                v_average = (v_average + (1 << (u_fill - 1))) >> u_fill

            u_predict = [[u_average for _ in range(4)] for _ in range(4)]
            v_predict = [[v_average for _ in range(4)] for _ in range(4)]

            for i in range(2):
                for j in range(2):
                    self.uSubBlocks[j][i].set_predict(u_predict)
                    self.vSubBlocks[j][i].set_predict(v_predict)

        elif self.uvMode == 1:
            above_u_sb = [above_mb.get_u_sub_block(i, 1) for i in range(2)]
            above_v_sb = [above_mb.get_v_sub_block(i, 1) for i in range(2)]

            for i in range(2):
                for j in range(2):
                    u_sb = self.uSubBlocks[j][i]
                    v_sb = self.vSubBlocks[j][i]
                    u_predict = [
                        [
                            above_u_sb[j].get_macro_block_predict(1)[i][3]
                            for _ in range(4)
                        ]
                        for _ in range(4)
                    ]
                    v_predict = [
                        [
                            above_v_sb[j].get_macro_block_predict(1)[i][3]
                            for _ in range(4)
                        ]
                        for _ in range(4)
                    ]
                    u_sb.set_predict(u_predict)
                    v_sb.set_predict(v_predict)

        elif self.uvMode == 2:
            left_u_sb = [left_mb.get_u_sub_block(1, i) for i in range(2)]
            left_v_sb = [left_mb.get_v_sub_block(1, i) for i in range(2)]

            for i in range(2):
                for j in range(2):
                    u_sb = self.uSubBlocks[j][i]
                    v_sb = self.vSubBlocks[j][i]
                    u_predict = [
                        [
                            left_u_sb[i].get_macro_block_predict(2)[3][j]
                            for j in range(4)
                        ]
                        for _ in range(4)
                    ]
                    v_predict = [
                        [
                            left_v_sb[i].get_macro_block_predict(2)[3][j]
                            for j in range(4)
                        ]
                        for _ in range(4)
                    ]
                    u_sb.set_predict(u_predict)
                    v_sb.set_predict(v_predict)

        elif self.uvMode == 3:
            al_mb = frame.get_macro_block(self.x - 1, self.y - 1)
            al_u_sb = al_mb.get_u_sub_block(1, 1)
            al_v_sb = al_mb.get_v_sub_block(1, 1)
            al_u = al_u_sb.get_dest()[3][3]
            al_v = al_v_sb.get_dest()[3][3]

            above_u_sb = [above_mb.get_u_sub_block(i, 1) for i in range(2)]
            left_u_sb = [left_mb.get_u_sub_block(1, i) for i in range(2)]
            above_v_sb = [above_mb.get_v_sub_block(i, 1) for i in range(2)]
            left_v_sb = [left_mb.get_v_sub_block(1, i) for i in range(2)]

            for b in range(2):
                for a in range(4):
                    for d in range(2):
                        for c in range(4):
                            u_pred = (
                                left_u_sb[b].get_dest()[3][a]
                                + above_u_sb[d].get_dest()[c][3]
                                - al_u
                            )
                            v_pred = (
                                left_v_sb[b].get_dest()[3][a]
                                + above_v_sb[d].get_dest()[c][3]
                                - al_v
                            )
                            self.uSubBlocks[d][b].set_pixel(c, a, u_pred)
                            self.vSubBlocks[d][b].set_pixel(c, a, v_pred)

        else:
            print("TODO predict_mb_uv: ", self.yMode)
    
    @micropython.native
    def predict_y(self, frame):
        above_mb = frame.get_macro_block(self.x, self.y - 1)
        left_mb = frame.get_macro_block(self.x - 1, self.y)

        if self.yMode == 0:
            up_available = False
            left_available = False
            average = 0

            if self.x > 0:
                left_available = True
            if self.y > 0:
                up_available = True

            if not up_available and not left_available:
                average = 128
            else:
                if up_available:
                    for var21 in range(4):
                        above_y_sb = above_mb.get_y_sub_block(var21, 3)
                        for var24 in range(4):
                            average += above_y_sb.get_dest()[var24][3]

                if left_available:
                    for var21 in range(4):
                        left_y_sb = left_mb.get_y_sub_block(3, var21)
                        for var24 in range(4):
                            average += left_y_sb.get_dest()[3][var24]

                var21 = 3
                if up_available:
                    var21 += 1
                if left_available:
                    var21 += 1

                average = (average + (1 << (var21 - 1))) >> var21

            fill = [[average for _ in range(4)] for _ in range(4)]

            for var23 in range(4):
                for var24 in range(4):
                    self.ySubBlocks[var24][var23].set_predict(fill)

        elif self.yMode == 1:
            above_y_sb = [above_mb.get_y_sub_block(i, 3) for i in range(4)]

            for var24 in range(4):
                for left_u_sb in range(4):
                    y_sb = self.ySubBlocks[left_u_sb][var24]
                    y_predict = [
                        [
                            above_y_sb[left_u_sb].get_predict(2, False)[i][3]
                            for i in range(4)
                        ]
                        for _ in range(4)
                    ]
                    y_sb.set_predict(y_predict)

        elif self.yMode == 2:
            left_y_sb = [left_mb.get_y_sub_block(3, i) for i in range(4)]

            for left_u_sb in range(4):
                for var26 in range(4):
                    al_sb = self.ySubBlocks[var26][left_u_sb]
                    y_predict = [
                        [
                            left_y_sb[left_u_sb].get_predict(0, True)[3][i]
                            for i in range(4)
                        ]
                        for _ in range(4)
                    ]
                    al_sb.set_predict(y_predict)

            left_y_sb = [left_mb.get_y_sub_block(1, i) for i in range(2)]

        elif self.yMode == 3:
            al_mb = frame.get_macro_block(self.x - 1, self.y - 1)
            al_sb = al_mb.get_y_sub_block(3, 3)
            al = al_sb.get_dest()[3][3]
            above_y_sb = [above_mb.get_y_sub_block(i, 3) for i in range(4)]
            left_y_sb = [left_mb.get_y_sub_block(3, i) for i in range(4)]
            fill = [[0 for _ in range(4)] for _ in range(4)]

            for b in range(4):
                for a in range(4):
                    for d in range(4):
                        for c in range(4):
                            pred = (
                                left_y_sb[b].get_dest()[3][a]
                                + above_y_sb[d].get_dest()[c][3]
                                - al
                            )
                            self.ySubBlocks[d][b].set_pixel(c, a, pred)

        else:
            print("TODO predict_mb_y:", self.yMode)
    
    @micropython.native
    def recon_mb(self):
        for j in range(4):
            for i in range(4):
                sb = self.ySubBlocks[i][j]
                sb.reconstruct()

        for j in range(2):
            for i in range(2):
                sb = self.uSubBlocks[i][j]
                sb.reconstruct()

        for j in range(2):
            for i in range(2):
                sb = self.vSubBlocks[i][j]
                sb.reconstruct()

    def set_uv_mode(self, mode):
        self.uvMode = mode

    def get_uv_mode(self):
        return self.uvMode
    
    def decode_macro_block(self, frame):
        if self.get_mb_skip_coeff() <= 0:
            if self.get_y_mode() != 4:
                self.decode_macro_block_tokens(frame, True)
            else:
                self.decode_macro_block_tokens(frame, False)

    def decode_macro_block_tokens(self, frame, with_y2):
        if with_y2:
            self.decode_plane_tokens(frame, 1, SubBlock.PLANE.Y2, False)
        self.decode_plane_tokens(frame, 4, SubBlock.PLANE.Y1, with_y2)
        self.decode_plane_tokens(frame, 2, SubBlock.PLANE.U, False)
        self.decode_plane_tokens(frame, 2, SubBlock.PLANE.V, False)
    
    @micropython.native
    def dequant_macro_block(self, frame):
        if self.get_y_mode() != 4:
            i = self.get_y2_sub_block()
            j = AC_LOOKUP[frame.get_q_index()] * 155 // 100
            sb = DC_LOOKUP[frame.get_q_index()] * 2
            inp = [0] * 16
            inp[0] = i.get_tokens()[0] * sb

            for i1 in range(1, 16):
                inp[i1] = i.get_tokens()[i1] * j

            i.set_diff(IDCT.iwalsh4x4(inp))

            for i1 in range(4):
                for j1 in range(4):
                    uvsb = self.get_y_sub_block(j1, i1)
                    uvsb.dequant_sub_block(frame, i.get_diff()[j1][i1])

            self.predict_y(frame)
            self.predict_uv(frame)

            for i1 in range(2):
                for j1 in range(2):
                    uvsb = self.get_u_sub_block(j1, i1)
                    uvsb.dequant_sub_block(frame, None)
                    uvsb = self.get_v_sub_block(i1, j1)
                    uvsb.dequant_sub_block(frame, None)

            self.recon_mb()
        else:
            for var10 in range(4):
                for j in range(4):
                    var11 = self.get_y_sub_block(j, var10)
                    var11.dequant_sub_block(frame, None)
                    var11.predict(frame)
                    var11.reconstruct()

            self.predict_uv(frame)

            for var10 in range(2):
                for j in range(2):
                    var11 = self.get_u_sub_block(j, var10)
                    var11.dequant_sub_block(frame, None)
                    var11.reconstruct()

            for var10 in range(2):
                for j in range(2):
                    var11 = self.get_v_sub_block(j, var10)
                    var11.dequant_sub_block(frame, None)
                    var11.reconstruct()
    
    @micropython.native
    def decode_plane_tokens(self, frame, dimensions, plane, with_y2):
        for y in range(dimensions):
            for x in range(dimensions):
                l = 0
                a = 0
                lc = 0
                sb = self.get_sub_block(plane, x, y)
                left = frame.get_left_sub_block(sb, plane)
                above = frame.get_above_sub_block(sb, plane)
                if left.has_no_zero_token():
                    l = 1
                var14 = lc + l
                if above.has_no_zero_token():
                    a = 1
                var14 += a
                sb.decode_sub_block(
                    frame.get_token_bool_decoder(),
                    frame.get_coef_probs(),
                    var14,
                    SubBlock.plane_to_type(plane, with_y2),
                    with_y2,
                )

    def draw_debug(self):
        for j in range(4):
            for i in range(4):
                sb = self.ySubBlocks[i][0]
                sb.draw_debug_h()
                sb = self.ySubBlocks[0][j]
                sb.draw_debug_v()
