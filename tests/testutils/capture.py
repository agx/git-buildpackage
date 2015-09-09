# vim: set fileencoding=utf-8 :

import sys
from contextlib import contextmanager
from six import StringIO


class StderrCapture(StringIO):
    def save(self):
        self.safed = sys.stderr
        sys.stderr = self

    def restore(self):
        if self.safed is not None:
            sys.stderr = self.safed
            self.safed = None

    def output(self):
        self.seek(0)
        return self.read()


@contextmanager
def capture_stderr():
    """Capture an output and return its content"""
    c = StderrCapture()
    c.save()
    yield c
    c.restore()
