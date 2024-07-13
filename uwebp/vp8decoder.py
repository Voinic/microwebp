import micropython

from .globals import (
    VP8_MB_FEATURE_DATA_BITS,
    MB_SEGMENT_TREE,
    BMODE_TREE,
    KF_BMODE_PROB,
    UV_MODE_TREE,
    KF_UV_MODE_PROB,
    VP8_KF_YMODE_TREE,
    KF_YMODE_PROB,
    COEF_UPDATE_PROBS,
    DEFAULT_COEF_PROBS,
)
from .booldecoder import BoolDecoder
from .macroblock import MacroBlock
from .subblock import SubBlock


class DeltaQ:
    def __init__(self):
        self.v = 0
        self.update = False


class VP8Frame:
    MAX_REF_LF_DELTAS = 4
    MAX_MODE_LF_DELTAS = 4
    BLOCK_TYPES = 4
    COEF_BANDS = 8
    PREV_COEF_CONTEXTS = 3
    MAX_ENTROPY_TOKENS = 12

    def __init__(self, frame, coef_probs):
        self.frame = frame
        self.coef_probs = coef_probs
        self.qIndex = 0
        self.mb_no_coeff_skip = 0
        self.macroBlockRows = 0
        self.macroBlockCols = 0
        self.multiTokenPartition = 0
        self.segmentation_enabled = 0
        self.tokenBoolDecoder = None
        self.tokenBoolDecoders = []
        self.macroBlocks = None
        self.filterLevel = 0
        self.filterType = 0
        self.sharpnessLevel = 0
        self.frameType = 0
        self.width = 0
        self.height = 0
        self.mb_segement_abs_delta = 0
        self.mb_segment_tree_probs = None
        self.update_mb_segmentation_map = 0
        self.update_mb_segmentaton_data = 0

    def get_sharpness_level(self):
        return self.sharpnessLevel

    def get_frame_type(self):
        return self.frameType

    def create_macro_blocks(self):
        self.macroBlocks = [
            [MacroBlock(x, y) for y in range(self.macroBlockRows + 2)]
            for x in range(self.macroBlockCols + 2)
        ]

    @staticmethod
    @micropython.native
    def get_delta_q(bc, prev):
        ret = DeltaQ()
        if bc.read_bit() > 0:
            ret.v = bc.read_literal(4)
            if bc.read_bit() > 0:
                ret.v = -ret.v

        if ret.v != prev:
            ret.update = True

        return ret
    
    @micropython.native
    def get_bit(self, data, bit):
        r = data & (1 << bit)
        return 1 if r > 0 else 0
    
    @micropython.native
    def decode_frame(self, debug=False):
        ref_lf_deltas = [0] * self.MAX_REF_LF_DELTAS
        mode_lf_deltas = [0] * self.MAX_MODE_LF_DELTAS
        offset = 0
        var29 = offset + 1
        c = self.frame[offset]
        self.frameType = self.get_bit(c, 0)

        if debug:
            print(f"frame.length: {len(self.frame)} Frame type: {self.frameType}")

        if self.frameType != 0:
            return False
        else:
            version_number = (
                (self.get_bit(c, 1) << 1)
                + (self.get_bit(c, 2) << 1)
                + self.get_bit(c, 3)
            )
            if debug:
                print(
                    f"Version Number: {version_number} show_frame: {self.get_bit(c, 4)}"
                )

            first_partition_length_in_bytes = (
                (self.get_bit(c, 5) << 0)
                + (self.get_bit(c, 6) << 1)
                + (self.get_bit(c, 7) << 2)
            )
            c = self.frame[var29]
            var29 += 1
            first_partition_length_in_bytes += c << 3
            c = self.frame[var29]
            var29 += 1
            first_partition_length_in_bytes += c << 11

            if debug:
                print(
                    f"first_partition_length_in_bytes: {first_partition_length_in_bytes}"
                )

            c = self.frame[var29]
            var29 += 1

            if debug:
                print(f"StartCode: {c}")

            c = self.frame[var29]
            var29 += 1
            if debug:
                print(f" {c}")

            c = self.frame[var29]
            var29 += 1
            if debug:
                print(f" {c}")

            c = self.frame[var29]
            var29 += 1
            hBytes = c
            c = self.frame[var29]
            var29 += 1
            hBytes += c << 8
            self.width = hBytes & 16383
            if debug:
                print(f"width: {self.width} hScale: {hBytes >> 14}")

            c = self.frame[var29]
            var29 += 1
            vBytes = c
            c = self.frame[var29]
            var29 += 1
            vBytes += c << 8
            self.height = vBytes & 16383
            if debug:
                print(f"height: {self.height} vScale: {vBytes >> 14}")

            t_width = self.width
            t_height = self.height
            if t_width & 15 != 0:
                t_width += 16 - (t_width & 15)

            if t_height & 15 != 0:
                t_height += 16 - (t_height & 15)

            self.macroBlockRows = t_height >> 4
            self.macroBlockCols = t_width >> 4
            if debug:
                print(
                    f"macroBlockCols: {self.macroBlockCols} macroBlockRows: {self.macroBlockRows}"
                )

            self.create_macro_blocks()
            bc = BoolDecoder(self.frame, var29)
            if self.frameType == 0:
                mode_ref_lf_delta_enabled = bc.read_bit()
                if debug:
                    print(f"clr_type: {mode_ref_lf_delta_enabled} bc: {bc}")
                Qindex = bc.read_bit()
                if debug:
                    print(f"clamp_type: {Qindex}")

            self.segmentation_enabled = bc.read_bit()
            if debug:
                print(f"segmentation_enabled: {self.segmentation_enabled}")

            if self.segmentation_enabled > 0:
                if debug:
                    print("TODO")
                self.update_mb_segmentation_map = bc.read_bit()
                self.update_mb_segmentaton_data = bc.read_bit()
                if debug:
                    print(
                        f"update_mb_segmentaton_map: {self.update_mb_segmentation_map} update_mb_segmentaton_data: {self.update_mb_segmentaton_data}"
                    )

                if self.update_mb_segmentaton_data > 0:
                    self.mb_segement_abs_delta = bc.read_bit()
                    for mode_ref_lf_delta_enabled in range(2):
                        for Qindex in range(4):
                            if bc.read_bit() > 0:
                                q_update = bc.read_literal(
                                    VP8_MB_FEATURE_DATA_BITS[mode_ref_lf_delta_enabled]
                                )
                                if bc.read_bit() > 0:
                                    q_update = -q_update

                    if self.update_mb_segmentation_map > 0:
                        self.mb_segment_tree_probs = [0] * 3
                        for mode_ref_lf_delta_enabled in range(3):
                            if bc.read_bit() > 0:
                                Qindex = bc.read_literal(8)
                            else:
                                Qindex = 255
                            self.mb_segment_tree_probs[mode_ref_lf_delta_enabled] = (
                                Qindex
                            )

            self.filterType = bc.read_bit()
            if debug:
                print(f"filter_type: {self.filterType}")
            self.filterLevel = bc.read_literal(6)
            if debug:
                print(f"filter_level: {self.filterLevel}")
            self.sharpnessLevel = bc.read_literal(3)
            if debug:
                print(f"sharpness_level: {self.sharpnessLevel}")

            mode_ref_lf_delta_enabled = bc.read_bit()
            if debug:
                print(f"mode_ref_lf_delta_enabled: {mode_ref_lf_delta_enabled}")

            if mode_ref_lf_delta_enabled > 0:
                Qindex = bc.read_bit()
                if debug:
                    print(f"mode_ref_lf_delta_update: {Qindex}")
                if Qindex > 0:
                    for q_update in range(self.MAX_REF_LF_DELTAS):
                        if bc.read_bit() > 0:
                            ref_lf_deltas[q_update] = bc.read_literal(6)
                            if bc.read_bit() > 0:
                                ref_lf_deltas[q_update] *= -1
                            if debug:
                                print(f"ref_lf_deltas[i]: {ref_lf_deltas[q_update]}")

                    for q_update in range(self.MAX_MODE_LF_DELTAS):
                        if bc.read_bit() > 0:
                            mode_lf_deltas[q_update] = bc.read_literal(6)
                            if bc.read_bit() > 0:
                                mode_lf_deltas[q_update] *= -1
                            if debug:
                                print(f"mode_lf_deltas[i]: {mode_lf_deltas[q_update]}")

            if debug:
                print(f"offset: {var29}")

            self.setup_token_decoder(
                bc, self.frame, first_partition_length_in_bytes, var29, debug
            )
            Qindex = bc.read_literal(7)
            if debug:
                print(f"Q: {Qindex}")

            self.qIndex = Qindex
            var31 = False
            v = self.get_delta_q(bc, 0)
            y1dc_delta_q = v.v
            var31 = var31 or v.update
            if debug:
                print(f"y1dc_delta_q: {y1dc_delta_q} q_update: {var31}")

            v = self.get_delta_q(bc, 0)
            y2dc_delta_q = v.v
            var31 = var31 or v.update
            if debug:
                print(f"y2dc_delta_q: {y2dc_delta_q} q_update: {var31}")

            v = self.get_delta_q(bc, 0)
            y2ac_delta_q = v.v
            var31 = var31 or v.update
            if debug:
                print(f"y2ac_delta_q: {y2ac_delta_q} q_update: {var31}")

            v = self.get_delta_q(bc, 0)
            uvdc_delta_q = v.v
            var31 = var31 or v.update
            if debug:
                print(f"uvdc_delta_q: {uvdc_delta_q} q_update: {var31}")

            v = self.get_delta_q(bc, 0)
            uvac_delta_q = v.v
            var31 = var31 or v.update
            if debug:
                print(f"uvac_delta_q: {uvac_delta_q} q_update: {var31}")

            if self.frameType != 0:
                raise ValueError("bad input: not intra")
            else:
                refresh_entropy_probs = bc.read_bit()
                if debug:
                    print(f"refresh_entropy_probs: {refresh_entropy_probs}")

                if self.frameType == 0:
                    refresh_last_frame = 1
                else:
                    refresh_last_frame = bc.read_bit()

                if debug:
                    print(f"refresh_last_frame: {refresh_last_frame}")

                for ibc in range(self.BLOCK_TYPES):
                    for num_part in range(self.COEF_BANDS):
                        for mb_row in range(self.PREV_COEF_CONTEXTS):
                            for l in range(self.MAX_ENTROPY_TOKENS - 1):
                                if (
                                    bc.read_bool(
                                        COEF_UPDATE_PROBS[ibc][num_part][mb_row][l]
                                    )
                                    > 0
                                ):
                                    newp = bc.read_literal(8)
                                    self.coef_probs[ibc][num_part][mb_row][l] = newp

                self.mb_no_coeff_skip = bc.read_bit()
                if debug:
                    print(f"mb_no_coeff_skip: {self.mb_no_coeff_skip}")

                if self.frameType == 0:
                    self.read_modes(bc)
                    ibc = 0
                    num_part = 1 << self.multiTokenPartition
                    if debug:
                        print("num_part:", num_part)

                    for mb_row in range(self.macroBlockRows):
                        if num_part > 1:
                            self.tokenBoolDecoder = self.tokenBoolDecoders[ibc]
                            self.decode_macro_block_row(mb_row)
                            ibc += 1
                            if ibc == num_part:
                                ibc = 0
                        else:
                            self.decode_macro_block_row(mb_row)

                    if debug:
                        self.draw_debug()

                    return True
                else:
                    raise ValueError("bad input: not intra")

    def draw_debug(self):
        for mb_row in range(self.macroBlockRows):
            for mb_col in range(self.macroBlockCols):
                self.macroBlocks[mb_col + 1][mb_row + 1].draw_debug()

    def get_filter_type(self):
        return self.filterType

    def get_filter_level(self):
        return self.filterLevel

    def decode_macro_block_row(self, mbRow):
        for mb_col in range(self.macroBlockCols):
            mb = self.get_macro_block(mb_col, mbRow)
            mb.decode_macro_block(self)
            mb.dequant_macro_block(self)
    
    @micropython.native
    def get_above_right_sub_block(self, sb, plane):
        mb = sb.get_macro_block()
        x = mb.get_subblock_x(sb)
        y = mb.get_subblock_y(sb)
        if plane == SubBlock.PLANE.Y1:
            if y == 0 and x < 3:
                var12 = self.get_macro_block(mb.get_x(), mb.get_y() - 1)
                r = var12.get_sub_block(plane, x + 1, 3)
                return r
            elif y == 0 and x == 3:
                var12 = self.get_macro_block(mb.get_x() + 1, mb.get_y() - 1)
                r = var12.get_sub_block(plane, 0, 3)
                if var12.get_x() == self.get_macro_block_cols():
                    dest = [
                        [
                            (
                                127
                                if var12.get_y() < 0
                                else self.get_macro_block(mb.get_x(), mb.get_y() - 1)
                                .get_sub_block(SubBlock.PLANE.Y1, 3, 3)
                                .get_dest()[3][3]
                            )
                            for _ in range(4)
                        ]
                        for _ in range(4)
                    ]
                    r = SubBlock(var12, None, None, SubBlock.PLANE.Y1)
                    r.set_dest(dest)
                return r
            elif y > 0 and x < 3:
                r = mb.get_sub_block(plane, x + 1, y - 1)
                return r
            else:
                sb2 = mb.get_sub_block(sb.get_plane(), 3, 0)
                return self.get_above_right_sub_block(sb2, plane)
        else:
            raise ValueError("bad input: get_above_right_sub_block()")
    
    @micropython.native
    def get_above_sub_block(self, sb, plane):
        r = sb.get_above()
        if r is None:
            mb = sb.get_macro_block()
            x = mb.get_subblock_x(sb)

            mb2 = self.get_macro_block(mb.get_x(), mb.get_y() - 1)
            while plane == SubBlock.PLANE.Y2 and mb2.get_y_mode() == 4:
                mb2 = self.get_macro_block(mb2.get_x(), mb2.get_y() - 1)

            r = mb2.get_bottom_subblock(x, sb.get_plane())

        return r

    def get_coef_probs(self):
        return self.coef_probs
    
    @micropython.native
    def get_left_sub_block(self, sb, plane):
        r = sb.get_left()
        if r is None:
            mb = sb.get_macro_block()
            y = mb.get_subblock_y(sb)

            mb2 = self.get_macro_block(mb.get_x() - 1, mb.get_y())
            while plane == SubBlock.PLANE.Y2 and mb2.get_y_mode() == 4:
                mb2 = self.get_macro_block(mb2.get_x() - 1, mb2.get_y())

            r = mb2.get_right_subblock(y, sb.get_plane())

        return r

    def get_macro_block(self, mbCol, mbRow):
        return self.macroBlocks[mbCol + 1][mbRow + 1]

    def get_macro_block_cols(self):
        return self.macroBlockCols

    def get_macro_block_rows(self):
        return self.macroBlockRows

    def get_q_index(self):
        return self.qIndex

    def get_token_bool_decoder(self):
        return self.tokenBoolDecoder
    
    @micropython.native
    def get_u_buffer(self):
        r = [[0] * (self.macroBlockRows * 8) for _ in range(self.macroBlockCols * 8)]
        for y in range(self.macroBlockRows):
            for x in range(self.macroBlockCols):
                mb = self.macroBlocks[x + 1][y + 1]
                for b in range(2):
                    for a in range(2):
                        sb = mb.get_u_sub_block(a, b)
                        for d in range(4):
                            for c in range(4):
                                r[x * 8 + a * 4 + c][y * 8 + b * 4 + d] = sb.get_dest()[
                                    c
                                ][d]
        return r
    
    @micropython.native
    def get_v_buffer(self):
        r = [[0] * (self.macroBlockRows * 8) for _ in range(self.macroBlockCols * 8)]
        for y in range(self.macroBlockRows):
            for x in range(self.macroBlockCols):
                mb = self.macroBlocks[x + 1][y + 1]
                for b in range(2):
                    for a in range(2):
                        sb = mb.get_v_sub_block(a, b)
                        for d in range(4):
                            for c in range(4):
                                r[x * 8 + a * 4 + c][y * 8 + b * 4 + d] = sb.get_dest()[
                                    c
                                ][d]
        return r
    
    @micropython.native
    def get_y_buffer(self):
        r = [[0] * (self.macroBlockRows * 16) for _ in range(self.macroBlockCols * 16)]
        for y in range(self.macroBlockRows):
            for x in range(self.macroBlockCols):
                mb = self.macroBlocks[x + 1][y + 1]
                for b in range(4):
                    for a in range(4):
                        sb = mb.get_y_sub_block(a, b)
                        for d in range(4):
                            for c in range(4):
                                r[x * 16 + a * 4 + c][
                                    y * 16 + b * 4 + d
                                ] = sb.get_dest()[c][d]
        return r
    
    @micropython.native
    def read_modes(self, bc):
        mb_row = -1
        prob_skip_false = 0
        if self.mb_no_coeff_skip > 0:
            prob_skip_false = bc.read_literal(8)

        while True:
            mb_row += 1
            if mb_row >= self.macroBlockRows:
                return

            mb_col = -1
            while True:
                mb_col += 1
                if mb_col >= self.macroBlockCols:
                    break

                mb = self.get_macro_block(mb_col, mb_row)
                if (
                    self.segmentation_enabled > 0
                    and self.update_mb_segmentation_map > 0
                ):
                    bc.treed_read(MB_SEGMENT_TREE, self.mb_segment_tree_probs)

                if self.mb_no_coeff_skip > 0:
                    var14 = bc.read_bool(prob_skip_false)
                else:
                    var14 = 0

                mb.set_mb_skip_coeff(var14)
                y_mode = self.read_y_mode(bc)
                mb.set_y_mode(y_mode)

                if y_mode == 4:
                    for var15 in range(4):
                        for x in range(4):
                            var16 = mb.get_y_sub_block(x, var15)
                            sb = self.get_above_sub_block(var16, SubBlock.PLANE.Y1)
                            L = self.get_left_sub_block(var16, SubBlock.PLANE.Y1)
                            mode1 = self.read_sub_block_mode(
                                bc, sb.get_mode(), L.get_mode()
                            )
                            var16.set_mode(mode1)
                else:
                    mode = {0: 0, 1: 2, 2: 3, 3: 1}.get(y_mode, 0)

                    for x in range(4):
                        for y in range(4):
                            sb = mb.get_y_sub_block(x, y)
                            sb.set_mode(mode)

                var15 = self.read_uv_mode(bc)
                mb.set_uv_mode(var15)

    def read_sub_block_mode(self, bc, A, L):
        return bc.treed_read(BMODE_TREE, KF_BMODE_PROB[A][L])

    def read_uv_mode(self, bc):
        return bc.treed_read(UV_MODE_TREE, KF_UV_MODE_PROB)

    def read_y_mode(self, bc):
        return bc.treed_read(VP8_KF_YMODE_TREE, KF_YMODE_PROB)
    
    @micropython.native
    def read_partition_size(self, data, offset):
        return data[offset] + (data[offset + 1] << 8) + (data[offset + 2] << 16)
    
    @micropython.native
    def setup_token_decoder(
        self, bc, data, first_partition_length_in_bytes, offset, debug
    ):
        partitions_start = offset + first_partition_length_in_bytes
        partition = partitions_start
        self.multiTokenPartition = bc.read_literal(2)

        if debug:
            print(f"multi_token_partition: {self.multiTokenPartition}")

        num_part = 1 << self.multiTokenPartition

        if debug:
            print(f"num_part: {num_part}")

        if num_part > 1:
            partition = partitions_start + 3 * (num_part - 1)

        for i in range(num_part):
            if i < num_part - 1:
                var10 = self.read_partition_size(data, partitions_start + i * 3)
            else:
                var10 = len(data) - partition

            self.tokenBoolDecoders.append(BoolDecoder(self.frame, partition))
            partition += var10

        self.tokenBoolDecoder = self.tokenBoolDecoders[0]

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height


class VP8Decoder:
    def __init__(self):
        self.coef_probs = None
        self.frame_count = 0
        self.f = None

    def decode_frame(self, frame_data, debug=False):
        self.coef_probs = [[[[l for l in k] for k in j] for j in i] for i in DEFAULT_COEF_PROBS]
        self.f = VP8Frame(frame_data, self.coef_probs)
        self.f.decode_frame(debug)
        self.frame_count += 1

    def get_width(self):
        return self.f.get_width() if self.f else 0

    def get_height(self):
        return self.f.get_height() if self.f else 0

    def get_frame(self):
        return self.f
