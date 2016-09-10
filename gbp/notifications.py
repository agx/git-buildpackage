# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Guenther <agx@sigxcpu.org>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, please see
#    <http://www.gnu.org/licenses/>

import warnings

notify_module = None


def enable_notifications():
    global notify_module

    with warnings.catch_warnings():
        # Avoid GTK+ cannot open display warning:
        warnings.simplefilter("ignore")
        try:
            import pynotify
            notify_module = pynotify
        except (ImportError, RuntimeError):
            return False

    return notify_module.init("git-buildpackage")


def build_msg(cp, success):
    summary = "Gbp %s" % ["failed", "successful"][success]
    msg = ("Build of %s %s %s" %
           (cp['Source'], cp['Version'], ["failed", "succeeded"][success]))

    return summary, msg


def send_notification(summary, msg):
    n = notify_module.Notification(summary, msg)
    n.set_hint('transient', True)
    try:
        if not n.show():
            return False
    except:
        return False
    return True


def notify(summary, message, notify_opt):
    """
    Send a notifications
    @return: False on error
    """

    if notify_opt.is_off():
        return True

    enable = enable_notifications()
    if not enable:
        return [True, False][notify_opt.is_on()]

    return notify_opt.do(send_notification, summary, message)
