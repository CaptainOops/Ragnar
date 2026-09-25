"""Transient Toolkit activity shared by the job runner and physical display."""
import threading
import time


class Activity:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.running = {}
        self.last = None
        self.expires = 0

    def update(self, report):
        # No targets, payload source or credentials belong on the status strip.
        item = {k: report[k] for k in ('id', 'name', 'status')}
        with self.lock:
            if item['status'] == 'running':
                self.running[item['id']] = item
            else:
                self.running.pop(item['id'], None)
                self.last = item
                self.expires = self.clock() + 20

    def snapshot(self):
        with self.lock:
            if self.running:
                return dict(next(reversed(self.running.values())), active=len(self.running))
            if self.last and self.clock() < self.expires:
                return dict(self.last, active=0)
            return None


activity = Activity()


def draw_activity(image, font):
    """A bounded footer on the existing frame; never changes orchestrator state."""
    from PIL import ImageDraw
    item = activity.snapshot()
    if not item:
        return
    draw = ImageDraw.Draw(image)
    label = 'Toolkit: ' + item['name']
    status = item['status'].capitalize()
    if item['active'] > 1:
        status += ' (%s jobs)' % item['active']
    width, height = image.size
    line_height = font.getbbox('Ag')[3] - font.getbbox('Ag')[1] + 5
    top = max(0, height - line_height * 2 - 6)
    draw.rectangle((0, top, width, height), fill=255, outline=0)
    for index, text in enumerate((label, status)):
        while text and draw.textlength(text, font=font) > width - 8:
            text = text[:-1]
        draw.text((4, top + 2 + index * line_height), text, font=font, fill=0)
