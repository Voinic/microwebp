import micropython
from .vp8decoder import VP8Decoder

@micropython.native
def yuv_to_rgb(y_buffer, u_buffer, v_buffer, width, height):
    # Create a blank image
    dst = [[[] for _ in range(width)] for _ in range(height)]

    for _x in range(width):
        for _y in range(height):
            y = y_buffer[_x][_y]
            u = u_buffer[_x // 2][_y // 2]
            v = v_buffer[_x // 2][_y // 2]
            c = [
                1.164 * (y - 16) + 1.596 * (v - 128),
                1.164 * (y - 16) - 0.813 * (v - 128) - 0.391 * (u - 128),
                1.164 * (y - 16) + 2.018 * (u - 128),
            ]
            dst[_y][_x] = [max(0, min(255, int(val))) for val in c]
    
    return dst
    

class WebPImage:
    def __init__(self, decoder):
        self.decoder = decoder
        self.stream = None
        self.width = 0
        self.height = 0
        self.header_defined = False

    def is_header_defined(self):
        return self.header_defined

    def set_header_defined(self, value):
        self.header_defined = value

    def get_stream(self):
        return self.stream

    def set_stream(self, stream):
        self.stream = stream

    def get_width(self):
        return self.width

    def set_width(self, width):
        self.width = width

    def get_height(self):
        return self.height

    def set_height(self, height):
        self.height = height

    def get_decoder(self):
        return self.decoder


class WebPImageType:
    RIFF = b"RIFF"
    WEBP = b"WEBP"
    VP8_ = b"VP8 "
    VP8X = b"VP8X"


class WebPReader:
    def __init__(self, input_stream):
        self.image_read = WebPImage(VP8Decoder())
        self.image_read.set_stream(input_stream)

    def _read_header(self):
        if self.image_read.is_header_defined():
            return

        signature = self.image_read.get_stream().read(4)
        self.image_read.set_header_defined(True)

        if not signature:
            raise ValueError("No input stream provided")

        if signature == WebPImageType.RIFF:
            try:
                self.image_read.get_stream().read(4)  # Skip over 4 bytes
                signature = self.image_read.get_stream().read(4)
            except OSError as e:
                raise OSError("Error reading WEBP signature")

            if signature == WebPImageType.WEBP:
                try:
                    signature = self.image_read.get_stream().read(4)
                except OSError as e:
                    raise OSError("Error reading VP8 signature")

                if signature == WebPImageType.VP8X:
                    signature = bytearray(4)
                    signature[:] = self.image_read.get_stream().read(4)

                    while True:
                        try:
                            next_byte = self.image_read.get_stream().read(1)
                            if not next_byte:
                                break  # End of stream

                            signature = signature[1:] + next_byte

                            if signature == WebPImageType.VP8_:
                                break
                        except OSError as e:
                            raise OSError(
                                "Error reading stream while searching for VP8_"
                            )

                if signature == WebPImageType.VP8_:
                    try:
                        frame_size = int.from_bytes(
                            self.image_read.get_stream().read(4), "little"
                        )
                    except OSError as e:
                        raise OSError("Error reading frame size")

                    print("VP8 image data size:", frame_size)

                    frame = self.image_read.get_stream().read(frame_size)

                    if len(frame) != frame_size:
                        raise ValueError("Error reading frame: incorrect size")

                    self.image_read.get_decoder().decode_frame(frame)
                    self.image_read.set_width(self.image_read.get_decoder().get_width())
                    self.image_read.set_height(
                        self.image_read.get_decoder().get_height()
                    )
                else:
                    raise ValueError("Bad VP8 signature!")
            else:
                raise ValueError("Bad WEBP signature!")
        else:
            raise ValueError("Bad RIFF signature!")

    def get_width(self):
        self._read_header()
        return self.image_read.get_width()

    def get_height(self):
        self._read_header()
        return self.image_read.get_height()
    
    def read(self):
        self._read_header()  # get image width and height

        # Get image width and height
        width = self.image_read.get_width()
        height = self.image_read.get_height()

        frame = self.image_read.get_decoder().get_frame()
        y_buffer = frame.get_y_buffer()
        u_buffer = frame.get_u_buffer()
        v_buffer = frame.get_v_buffer()
        
        img_rgb = yuv_to_rgb(y_buffer, u_buffer, v_buffer, width, height)
        
        del y_buffer, u_buffer, v_buffer

        return img_rgb
