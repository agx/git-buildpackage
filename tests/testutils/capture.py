# vim: set fileencoding=utf-8 :

import sys
from contextlib import contextmanager
from six import StringIO


class _StderrCapture(StringIO):
    def save(self):
        self.safed = sys.stdout
        sys.stderr = self

    def restore(self):
        if self.safed is not None:
            sys.stderr = self.safed
            self.safed = None

    def output(self):
        self.seek(0)
        return self.read()


class _StdoutCapture(StringIO):
    def save(self):
        self.safed = sys.stdout
        sys.stdout = self

    def restore(self):
        if self.safed is not None:
            sys.stdout = self.safed
            self.safed = None

    def output(self):
        self.seek(0)
        return self.read()


@contextmanager
def capture_stderr():
    """Capture an output and return its content"""
    c = _StderrCapture()
    c.save()
    yield c
    c.restore()


@contextmanager
def capture_stdout():
    """Capture an output and return its content"""
    c = _StdoutCapture()
    c.save()
    yield c
    c.restore()
