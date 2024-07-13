from uwebp import WebPReader


def render(img, palette=" .:-=+*#%@", contrast=1.3):
    for row in img:
        for column in row:
            factor = sum(column)/(3*255)*contrast
            idx = int((len(palette)-1)*min(1, max(0, factor)))
            print(palette[idx], end="")
        print()


def decode(file):
    with open(file, "rb") as f:
        reader = WebPReader(f)
        image = reader.read()
        print("Width:", reader.get_width())
        print("Height:", reader.get_height())
        del reader
        return image


if __name__ == "__main__":
    image = decode("sample.webp")
    render(image)
    del image
