# vim: set fileencoding=utf-8 :
#
# (C) 2006,2007 Guido Guenther <agx@sigxcpu.org>
"""Things common to all gbp commands"""

class GbpError(Exception):
    """Generic exception raised in git-buildpackage commands"""
    pass

class GbpNothingImported(GbpError):
    msg = "Nothing to commit, nothing imported."
    def __str__(self):
        return self.msg

# vim:et:ts=4:sw=4:et:sts=4:ai:set list listchars=tab\:»·,trail\:·:
