#!/usr/bin/env python
'''Visualize dot graphs via the xdot format.'''

__author__ = "Jose Fonseca"

__version__ = "0.3"


import sys
import subprocess
import math

import gobject
import gtk
import gtk.gdk
import gtk.keysyms
import cairo
import pango
import pangocairo

import pydot


# See http://www.graphviz.org/pub/scm/graphviz-cairo/plugin/cairo/gvrender_cairo.c

# For pygtk inspiration and guidance see:
# - http://mirageiv.berlios.de/
# - http://comix.sourceforge.net/


class Pen:
	"""Store pen attributes."""

	def __init__(self):
		# set default attributes
		self.color = (0.0, 0.0, 0.0, 1.0)
		self.fillcolor = (0.0, 0.0, 0.0, 1.0)
		self.linewidth = 1.0
		self.fontsize = 14.0
		self.fontname = "Times-Roman"

	def copy(self):
		"""Create a copy of this pen."""
		pen = Pen()
		pen.__dict__ = self.__dict__.copy()
		return pen


class Shape:
	"""Abstract base class for all the drawing shapes."""

	def __init__(self):
		pass

	def draw(self, cr):
		"""Draw this shape with the given cairo context"""
		raise NotImplementedError


class TextShape(Shape):
	
	#fontmap = pangocairo.CairoFontMap()
	#fontmap.set_resolution(72)
	#context = fontmap.create_context()

	LEFT, CENTER, RIGHT = -1, 0, 1

	def __init__(self, pen, x, y, j, w, t):
		Shape.__init__(self)
		self.pen = pen.copy()
		self.x = x
		self.y = y
		self.j = j
		self.w = w
		self.t = t

	def draw(self, cr):

		try:
			layout = self.layout
		except AttributeError:
			layout = cr.create_layout()
			
			# set font options
			# see http://lists.freedesktop.org/archives/cairo/2007-February/009688.html
			context = layout.get_context()
			fo = cairo.FontOptions()
			fo.set_antialias(cairo.ANTIALIAS_DEFAULT)
			fo.set_hint_style(cairo.HINT_STYLE_NONE)
			fo.set_hint_metrics(cairo.HINT_METRICS_OFF)
			pangocairo.context_set_font_options(context, fo)
			
			# set font
			font = pango.FontDescription()
			font.set_family(self.pen.fontname)
			font.set_absolute_size(self.pen.fontsize*pango.SCALE)
			layout.set_font_description(font)
			
			# set text
			layout.set_text(self.t)
			
			# cache it
			self.layout = layout
		else:
			cr.update_layout(layout)

		width, height = layout.get_size()
		width = float(width)/pango.SCALE
		height = float(height)/pango.SCALE

		cr.move_to(self.x - self.w/2, self.y)

		if self.j == self.LEFT:
			x = self.x
		elif self.j == self.CENTER:
			x = self.x - 0.5*width
		elif self.j == self.RIGHT:
			x = self.x - width
		else:
			assert 0
		
		y = self.y - height
		
		cr.move_to(x, y)

		cr.set_source_rgba(*self.pen.color)
		cr.show_layout(layout)


class EllipseShape(Shape):

	def __init__(self, pen, x0, y0, w, h, filled=False):
		Shape.__init__(self)
		self.pen = pen.copy()
		self.x0 = x0
		self.y0 = y0
		self.w = w
		self.h = h
		self.filled = filled

	def draw(self, cr):
		cr.save()
		cr.translate(self.x0, self.y0)
		cr.scale(self.w, self.h)
		cr.move_to(1.0, 0.0)
		cr.arc(0.0, 0.0, 1.0, 0, 2.0*math.pi)
		cr.restore()
		if self.filled:
			cr.set_source_rgba(*self.pen.fillcolor)
			cr.fill()
		else:
			cr.set_line_width(self.pen.linewidth)
			cr.set_source_rgba(*self.pen.color)
			cr.stroke()


class PolygonShape(Shape):

	def __init__(self, pen, points, filled=False):
		Shape.__init__(self)
		self.pen = pen.copy()
		self.points = points
		self.filled = filled

	def draw(self, cr):
		x0, y0 = self.points[-1]
		cr.move_to(x0, y0)
		for x, y in self.points:
			cr.line_to(x, y)
		cr.close_path()
		if self.filled:
			cr.set_source_rgba(*self.pen.fillcolor)
			cr.fill_preserve()
			cr.fill()
		else:
			cr.set_line_width(self.pen.linewidth)
			cr.set_source_rgba(*self.pen.color)
			cr.stroke()


class BezierShape(Shape):

	def __init__(self, pen, points):
		Shape.__init__(self)
		self.pen = pen.copy()
		self.points = points

	def draw(self, cr):
		x0, y0 = self.points[0]
		cr.move_to(x0, y0)
		for i in xrange(1, len(self.points), 3):
			x1, y1 = self.points[i]
			x2, y2 = self.points[i + 1]
			x3, y3 = self.points[i + 2]
			cr.curve_to(x1, y1, x2, y2, x3, y3)
		cr.set_line_width(self.pen.linewidth)
		cr.set_source_rgba(*self.pen.color)
		cr.stroke()


class CompoundShape(Shape):

	def __init__(self, shapes):
		Shape.__init__(self)
		self.shapes = shapes

	def draw(self, cr):
		for shape in self.shapes:
			shape.draw(cr)


class Element(CompoundShape):
	"""Base class for graph nodes and edges."""

	def __init__(self, shapes):
		CompoundShape.__init__(self, shapes)
	
	def get_url(self, x, y):
		return None

	def get_jump(self, x, y):
		return None


class Node(Element):

	def __init__(self, x, y, w, h, shapes, url):
		Element.__init__(self, shapes)
		
		self.x = x
		self.y = y

		self.x1 = x - 0.5*w
		self.y1 = y - 0.5*h
		self.x2 = x + 0.5*w
		self.y2 = y + 0.5*h
		
		self.url = url

	def is_inside(self, x, y):
		return self.x1 <= x and x <= self.x2 and self.y1 <= y and y <= self.y2

	def get_url(self, x, y):
		if self.url is None:
			return None
		#print (x, y), (self.x1, self.y1), "-", (self.x2, self.y2)
		if self.is_inside(x, y):
			return self.url
		return None

	def get_jump(self, x, y):
		if self.is_inside(x, y):
			return self.x, self.y
		return None


def square_distance(x1, y1, x2, y2):
	deltax = x2 - x1
	deltay = y2 - y1
	return deltax*deltax + deltay*deltay


class Edge(Element):

	def __init__(self, points, shapes):
		Element.__init__(self, shapes)

		self.points = points

	RADIUS = 10

	def get_jump(self, x, y):
		if square_distance(x, y, *self.points[0]) <= self.RADIUS*self.RADIUS:
			return self.points[-1]
		if square_distance(x, y, *self.points[-1]) <= self.RADIUS*self.RADIUS:
			return self.points[0]
		return None


class Graph(Shape):

	def __init__(self, width=1, height=1, nodes=(), edges=()):
		Shape.__init__(self)
		
		self.width = width
		self.height = height
		self.nodes = nodes
		self.edges = edges

	def get_size(self):
		return self.width, self.height

	def draw(self, cr):
		cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)

		cr.set_line_cap(cairo.LINE_CAP_BUTT)
		cr.set_line_join(cairo.LINE_JOIN_MITER)
		
		for edge in self.edges:
			edge.draw(cr)
		for node in self.nodes:
			node.draw(cr)
	
	def get_url(self, x, y):
		for node in self.nodes:
			url = node.get_url(x, y)
			if url is not None:
				return url
		return None

	def get_jump(self, x, y):
		for edge in self.edges:
			jump = edge.get_jump(x, y)
			if jump is not None:
				return jump
		for node in self.nodes:
			jump = node.get_jump(x, y)
			if jump is not None:
				return jump
		return None


class XDotAttrParser:
	"""Parser for xdot drawing attributes.
	See also:
	- http://www.graphviz.org/doc/info/output.html#d:xdot
	"""

	def __init__(self, parser, buf):
		self.parser = parser
		self.buf = self.unescape(buf)
		self.pos = 0

	def __nonzero__(self):
		return self.pos < len(self.buf)

	def unescape(self, buf):
		buf = buf.replace('\\"', '"')
		buf = buf.replace('\\n', '\n')
		return buf

	def read_code(self):
		pos = self.buf.find(" ", self.pos)
		res = self.buf[self.pos:pos]
		self.pos = pos + 1
		while self.pos < len(self.buf) and self.buf[self.pos].isspace():
			self.pos += 1
		return res

	def read_number(self):
		return int(self.read_code())

	def read_float(self):
		return float(self.read_code())

	def read_point(self):
		x = self.read_number()
		y = self.read_number()
		return self.transform(x, y)

	def read_text(self):
		num = self.read_number()
		pos = self.buf.find("-", self.pos) + 1
		self.pos = pos + num
		res = self.buf[pos:self.pos]
		while self.pos < len(self.buf) and self.buf[self.pos].isspace():
			self.pos += 1
		return res

	def read_polygon(self):
		n = self.read_number()
		p = []
		for i in range(n):
			x, y = self.read_point()
			p.append((x, y))
		return p

	def read_color(self):
		# See http://www.graphviz.org/doc/info/attrs.html#k:color
		c = self.read_text()
		c1 = c[:1]
		if c1 == '#':
			hex2float = lambda h: float(int(h, 16)/255.0)
			r = hex2float(c[1:3])
			g = hex2float(c[3:5])
			b = hex2float(c[5:7])
			try:
				a = hex2float(c[7:9])
			except (IndexError, ValueError):
				a = 1.0
			return r, g, b, a
		elif c1.isdigit():
			h, s, v = map(float, c[1:].split(","))
			raise NotImplementedError
		else:
			color = gtk.gdk.color_parse(c)
			s = 1.0/65535.0
			r = color.red*s
			g = color.green*s
			b = color.blue*s
			a = 1.0
			return r, g, b, a

	def parse(self):
		shapes = []
		pen = Pen()
		s = self

		while s:
			op = s.read_code()
			if op == "c":
				pen.color = s.read_color()
			elif op == "C":
				pen.fillcolor = s.read_color()
			elif op == "S":
				s.read_text()
			elif op == "F":
				pen.fontsize = s.read_float()
				pen.fontname = s.read_text()
			elif op == "T":
				x, y = s.read_point()
				j = s.read_number()
				w = s.read_number()
				t = s.read_text()
				shapes.append(TextShape(pen, x, y, j, w, t))
			elif op == "E":
				x0, y0 = s.read_point()
				w = s.read_number()
				h = s.read_number()
				shapes.append(EllipseShape(pen, x0, y0, w, h, filled=True))
			elif op == "e":
				x0, y0 = s.read_point()
				w = s.read_number()
				h = s.read_number()
				shapes.append(EllipseShape(pen, x0, y0, w, h))
			elif op == "B":
				p = self.read_polygon()
				shapes.append(BezierShape(pen, p))
			elif op == "P":
				p = self.read_polygon()
				shapes.append(PolygonShape(pen, p, filled=True))
			elif op == "p":
				p = self.read_polygon()
				shapes.append(PolygonShape(pen, p))
			else:
				sys.stderr.write("unknown xdot opcode '%s'\n" % op)
				break
		return shapes

	def transform(self, x, y):
		return self.parser.transform(x, y)


class XDotParser:
	
	def __init__(self, xdotcode):
		self.xdotcode = xdotcode

	def parse(self):
		graph = pydot.graph_from_dot_data(self.xdotcode)

		bb = graph.get_bb()
		if bb is None:
			return []

		xmin, ymin, xmax, ymax = map(int, bb.split(","))

		self.xoffset = -xmin
		self.yoffset = -ymax
		self.xscale = 1.0
		self.yscale = -1.0
		# FIXME: scale from points to pixels

		width = xmax - xmin
		height = ymax - ymin

		nodes = []
		edges = []
		
		for node in graph.get_node_list():
			if node.pos is None:
				continue
			x, y = self.parse_node_pos(node.pos)
			w = float(node.width)*72
			h = float(node.height)*72
			shapes = []
			for attr in ("_draw_", "_ldraw_"):
				if hasattr(node, attr):
					parser = XDotAttrParser(self, getattr(node, attr))
					shapes.extend(parser.parse())
			url = node.URL
			if shapes:
				nodes.append(Node(x, y, w, h, shapes, url))

		for edge in graph.get_edge_list():
			if edge.pos is None:
				continue
			points = self.parse_edge_pos(edge.pos)	
			shapes = []
			for attr in ("_draw_", "_ldraw_", "_hdraw_", "_tdraw_", "_hldraw_", "_tldraw_"):
				if hasattr(edge, attr):
					parser = XDotAttrParser(self, getattr(edge, attr))
					shapes.extend(parser.parse())
			if shapes:
				edges.append(Edge(points, shapes))

		return Graph(width, height, nodes, edges)

	def parse_node_pos(self, pos):
		x, y = pos.split(",")
		return self.transform(float(x), float(y))

	def parse_edge_pos(self, pos):
		points = []
		for entry in pos.split(' '):
			fields = entry.split(',')
			try:
				x, y = fields
			except ValueError:
				# TODO: handle start/end points
				continue
			else:
				points.append(self.transform(float(x), float(y)))
		return points

	def transform(self, x, y):
		# XXX: this is not the right place for this code
		x = (x + self.xoffset)*self.xscale
		y = (y + self.yoffset)*self.yscale
		return x, y


class DotWidget(gtk.DrawingArea):
	"""PyGTK widget that draws dot graphs."""

	__gsignals__ = {
		'expose-event': 'override',
		'clicked' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gtk.gdk.Event))
	}

	def __init__(self):
		gtk.DrawingArea.__init__(self)

		self.graph = Graph()

		self.set_flags(gtk.CAN_FOCUS)

		self.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)
		self.connect("button-press-event", self.on_area_button_press)
		self.connect("button-release-event", self.on_area_button_release)
		self.add_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK | gtk.gdk.BUTTON_RELEASE_MASK)
		self.connect("motion-notify-event", self.on_area_motion_notify)
		self.connect("scroll-event", self.on_area_scroll_event)

		self.connect('key-press-event', self.on_key_press_event)

		self.x, self.y = 0.0, 0.0
		self.zoom_ratio = 1.0

	def set_dotcode(self, dotcode):
		p = subprocess.Popen(
			['dot', '-Txdot'],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			shell=False,
			universal_newlines=True
		)
		xdotcode = p.communicate(dotcode)[0]
		self.set_xdotcode(xdotcode)

	def set_xdotcode(self, xdotcode):
		#print xdotcode
		parser = XDotParser(xdotcode)
		self.graph = parser.parse()
		self.zoom_image(self.zoom_ratio, center=True)

	def do_expose_event(self, event):
		cr = self.window.cairo_create()

		# set a clip region for the expose event
		cr.rectangle(
			event.area.x, event.area.y,
			event.area.width, event.area.height
		)
		cr.clip()

		cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
		cr.paint()

		rect = self.get_allocation()
		cr.translate(0.5*rect.width, 0.5*rect.height)
		cr.scale(self.zoom_ratio, self.zoom_ratio)
		cr.translate(-self.x, -self.y)

		self.graph.draw(cr)

		return False

	def get_current_pos(self):
		return self.x, self.y

	def set_current_pos(self, x, y):
		self.x = x
		self.y = y
		self.queue_draw()

	def zoom_image(self, zoom_ratio, center=False):
		if center:
			self.x = self.graph.width/2
			self.y = self.graph.height/2
		self.zoom_ratio = zoom_ratio
		self.queue_draw()

	ZOOM_INCREMENT = 1.25

	def on_zoom_in(self, action):
		self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)

	def on_zoom_out(self, action):
		self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)

	def on_zoom_fit(self, action):
		rect = self.get_allocation()
		zoom_ratio = min(
			float(rect.width)/float(self.graph.width),
			float(rect.height)/float(self.graph.height)
		)
		self.zoom_image(zoom_ratio, center=True)

	def on_zoom_100(self, action):
		self.zoom_image(1.0)

	POS_INCREMENT = 100

	def on_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Left:
			self.x -= self.POS_INCREMENT/self.zoom_ratio
			self.queue_draw()
			return True
		if event.keyval == gtk.keysyms.Right:
			self.x += self.POS_INCREMENT/self.zoom_ratio
			self.queue_draw()
			return True
		if event.keyval == gtk.keysyms.Up:
			self.y -= self.POS_INCREMENT/self.zoom_ratio
			self.queue_draw()
			return True
		if event.keyval == gtk.keysyms.Down:
			self.y += self.POS_INCREMENT/self.zoom_ratio
			self.queue_draw()
			return True
		if event.keyval == gtk.keysyms.Page_Up:
			self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)
			self.queue_draw()
			return True
		if event.keyval == gtk.keysyms.Page_Down:
			self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)
			self.queue_draw()
			return True
		return False

	def on_area_button_press(self, area, event):
		if event.button == 2 or event.button == 1:
			area.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))
			self.prevmousex = event.x
			self.prevmousey = event.y

		if event.type not in (gtk.gdk.BUTTON_PRESS, gtk.gdk.BUTTON_RELEASE):
			return False
		x, y = int(event.x), int(event.y)
		url = self.get_url(x, y)
		if url is not None:
			self.emit('clicked', unicode(url), event)
			return True

		jump = self.get_jump(x, y)
		x, y = self.window2graph(x, y)
		if jump is not None:
			jumpx, jumpy = jump
			self.x += jumpx - x
			self.y += jumpy - y
			self.queue_draw()
		return False

	def on_area_button_release(self, area, event):
		if event.button == 2 or event.button == 1:
			area.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.ARROW))
			self.prevmousex = None
			self.prevmousey = None
			return True
		return False

	def on_area_scroll_event(self, area, event):
		if event.direction == gtk.gdk.SCROLL_UP:
			self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)
			return True
		if event.direction == gtk.gdk.SCROLL_DOWN:
			self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)
			return True
		return False

	def on_area_motion_notify(self, area, event):
		x, y = int(event.x), int(event.y)
		state = event.state

		if state & gtk.gdk.BUTTON2_MASK or state & gtk.gdk.BUTTON1_MASK:
			# pan the image
			self.x += (self.prevmousex - x)/self.zoom_ratio
			self.y += (self.prevmousey - y)/self.zoom_ratio
			self.queue_draw()
			self.prevmousex = x
			self.prevmousey = y
		else:
			# set cursor
			if self.get_url(x, y) is not None:
				area.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
			else:
				area.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.ARROW))

		return True

	def window2graph(self, x, y):
		rect = self.get_allocation()
		x -= 0.5*rect.width
		y -= 0.5*rect.height
		x /= self.zoom_ratio
		y /= self.zoom_ratio
		x += self.x
		y += self.y
		return x, y

	def get_url(self, x, y):
		x, y = self.window2graph(x, y)
		return self.graph.get_url(x, y)

	def get_jump(self, x, y):
		x, y = self.window2graph(x, y)
		return self.graph.get_jump(x, y)


class DotWindow(gtk.Window):

	ui = '''
	<ui>
		<toolbar name="ToolBar">
			<toolitem action="ZoomIn"/>
			<toolitem action="ZoomOut"/>
			<toolitem action="ZoomFit"/>
			<toolitem action="Zoom100"/>
		</toolbar>
	</ui>
	'''

	def __init__(self):
		gtk.Window.__init__(self)

		self.graph = Graph()

		window = self

		window.set_title('Dot')
		window.set_default_size(512, 512)
		vbox = gtk.VBox()
		window.add(vbox)

		self.widget = DotWidget()

		# Create a UIManager instance
		uimanager = self.uimanager = gtk.UIManager()

		# Add the accelerator group to the toplevel window
		accelgroup = uimanager.get_accel_group()
		window.add_accel_group(accelgroup)

		# Create an ActionGroup
		actiongroup = gtk.ActionGroup('Actions')
		self.actiongroup = actiongroup

		# Create actions
		actiongroup.add_actions((
			('ZoomIn', gtk.STOCK_ZOOM_IN, None, None, None, self.widget.on_zoom_in),
			('ZoomOut', gtk.STOCK_ZOOM_OUT, None, None, None, self.widget.on_zoom_out),
			('ZoomFit', gtk.STOCK_ZOOM_FIT, None, None, None, self.widget.on_zoom_fit),
			('Zoom100', gtk.STOCK_ZOOM_100, None, None, None, self.widget.on_zoom_100),
		))

		# Add the actiongroup to the uimanager
		uimanager.insert_action_group(actiongroup, 0)

		# Add a UI description
		uimanager.add_ui_from_string(self.ui)

		# Create a Toolbar
		toolbar = uimanager.get_widget('/ToolBar')
		vbox.pack_start(toolbar, False)

		vbox.pack_start(self.widget)

		self.set_focus(self.widget)

		self.show_all()

	def set_dotcode(self, dotcode):
		self.widget.set_dotcode(dotcode)


def main():
	import optparse
	
	parser = optparse.OptionParser(
		usage="\n\t%prog [file]",
		version="%%prog %s" % __version__)
	
	(options, args) = parser.parse_args(sys.argv[1:])
	
	if len(args) == 0:
		fp = sys.stdin
	elif len(args) == 1:
		fp = file(args[0], 'rt')
	else:
		parser.error('incorrect number of arguments')
	
	win = DotWindow()
	win.set_dotcode(fp.read())
	win.connect('destroy', gtk.main_quit)
	gtk.main()


if __name__ == '__main__':
	main()
