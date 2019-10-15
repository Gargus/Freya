from PIL.ImageDraw import ImageDraw
from sys import platform

class OSImageDraw(ImageDraw):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.os_xy_alignment = None
        if platform == "linux" or platform == "linux2":
            self.os_xy_alignment = (0, -7)

    def text(self, xy, text, fill=None, font=None, anchor=None, *args, **kwargs):
        # If the OS specific aligment tuple exists, add the values
        xya = self.os_xy_alignment
        if xya:
            xy = (xy[0]+xya[0], xy[1]+xya[1])
        if self._multiline_check(text):
            return self.multiline_text(xy, text, fill, font, anchor, *args, **kwargs)
        ink, fill = self._getink(fill)
        if font is None:
            font = self.getfont()
        if ink is None:
            ink = fill
        if ink is not None:
            try:
                mask, offset = font.getmask2(text, self.fontmode, *args, **kwargs)
                xy = xy[0] + offset[0], xy[1] + offset[1]
            except AttributeError:
                try:
                    mask = font.getmask(text, self.fontmode, *args, **kwargs)
                except TypeError:
                    mask = font.getmask(text)
            self.draw.draw_bitmap(xy, mask, ink)


def OSDraw(im, mode=None):
    """
    A simple 2D drawing interface for PIL images.

    :param im: The image to draw in.
    :param mode: Optional mode to use for color values.  For RGB
       images, this argument can be RGB or RGBA (to blend the
       drawing into the image).  For all other modes, this argument
       must be the same as the image mode.  If omitted, the mode
       defaults to the mode of the image.
    """
    try:
        return im.getdraw(mode)
    except AttributeError:
        return OSImageDraw(im, mode)