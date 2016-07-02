# Copyright 2008-2015 Jose Fonseca
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import math
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib


class Animation(object):

    step = 0.03  # seconds

    def __init__(self, dot_widget):
        self.dot_widget = dot_widget
        self.timeout_id = None

    def start(self):
        self.timeout_id = GLib.timeout_add(int(self.step * 1000), self.__real_tick)

    def stop(self):
        self.dot_widget.animation = NoAnimation(self.dot_widget)
        if self.timeout_id is not None:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

    def __real_tick(self):
        try:
            if not self.tick():
                self.stop()
                return False
        except AttributeError as e:
            self.stop()
            raise e
        return True

    def tick(self):
        return False


class NoAnimation(Animation):

    def start(self):
        pass

    def stop(self):
        pass


class LinearAnimation(Animation):

    duration = 0.6

    def start(self):
        self.started = time.time()
        Animation.start(self)

    def tick(self):
        t = (time.time() - self.started) / self.duration
        self.animate(max(0, min(t, 1)))
        return (t < 1)

    def animate(self, t):
        pass


class MoveToAnimation(LinearAnimation):

    def __init__(self, dot_widget, target_x, target_y):
        Animation.__init__(self, dot_widget)
        self.source_x = dot_widget.x
        self.source_y = dot_widget.y
        self.target_x = target_x
        self.target_y = target_y

    def animate(self, t):
        sx, sy = self.source_x, self.source_y
        tx, ty = self.target_x, self.target_y
        self.dot_widget.x = tx * t + sx * (1 - t)
        self.dot_widget.y = ty * t + sy * (1 - t)
        self.dot_widget.queue_draw()


class ZoomToAnimation(MoveToAnimation):

    def __init__(self, dot_widget, target_x, target_y):
        MoveToAnimation.__init__(self, dot_widget, target_x, target_y)
        self.source_zoom = dot_widget.zoom_ratio
        self.target_zoom = self.source_zoom
        self.extra_zoom = 0

        middle_zoom = 0.5 * (self.source_zoom + self.target_zoom)

        distance = math.hypot(self.source_x - self.target_x,
                              self.source_y - self.target_y)
        rect = self.dot_widget.get_allocation()
        visible = min(rect.width, rect.height) / self.dot_widget.zoom_ratio
        visible *= 0.9
        if distance > 0:
            desired_middle_zoom = visible / distance
            self.extra_zoom = min(0, 4 * (desired_middle_zoom - middle_zoom))

    def animate(self, t):
        a, b, c = self.source_zoom, self.extra_zoom, self.target_zoom
        self.dot_widget.zoom_ratio = c*t + b*t*(1 - t) + a*(1 - t)
        self.dot_widget.zoom_to_fit_on_resize = False
        MoveToAnimation.animate(self, t)
