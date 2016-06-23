class Pen:
    """Store pen attributes."""

    BOLD = 1
    ITALIC = 2
    UNDERLINE = 4
    SUPERSCRIPT = 8
    SUBSCRIPT = 16
    STRIKE_THROUGH = 32
    OVERLINE = 64

    def __init__(self):
        # set default attributes
        self.color = (0.0, 0.0, 0.0, 1.0)
        self.fillcolor = (0.0, 0.0, 0.0, 1.0)
        self.linewidth = 1.0
        self.fontsize = 14.0
        self.fontname = "Times-Roman"
        self.bold = False
        self.italic = False
        self.underline = False
        self.superscript = False
        self.subscript = False
        self.strikethrough = False
        self.overline = False

        self.dash = ()

    def copy(self):
        """Create a copy of this pen."""
        pen = Pen()
        pen.__dict__ = self.__dict__.copy()
        return pen

    def highlighted(self):
        pen = self.copy()
        pen.color = (1, 0, 0, 1)
        pen.fillcolor = (1, .8, .8, 1)
        return pen
