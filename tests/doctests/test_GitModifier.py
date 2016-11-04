# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitModifier}
"""

from .. import context  # noqa: F401


def test_author():
    """
    Methods tested:
         - L{gbp.git.GitModifier.get_author_env}
         - L{gbp.git.GitModifier.get_committer_env}
         - L{gbp.git.GitModifier.keys}

    >>> import gbp.git
    >>> modifier = gbp.git.GitModifier('foo', 'bar')
    >>> modifier.name
    'foo'
    >>> modifier.email
    'bar'
    >>> modifier.get_author_env()['GIT_AUTHOR_EMAIL']
    'bar'
    >>> modifier.get_author_env()['GIT_AUTHOR_NAME']
    'foo'
    >>> modifier.get_committer_env()['GIT_COMMITTER_NAME']
    'foo'
    >>> modifier.get_committer_env()['GIT_COMMITTER_EMAIL']
    'bar'
    >>> modifier._get_env('foo')
    Traceback (most recent call last):
    ...
    GitModifierError: Neither committer nor author
    >>> modifier['name']
    'foo'
    >>> modifier['email']
    'bar'
    >>> modifier['date']
    """


def test_date():
    """
    Methods tested:
         - L{gbp.git.GitModifier.__init__}

    Properties tested:
         - L{gbp.git.GitModifier.date}
         - L{gbp.git.GitModifier.datetime}
         - L{gbp.git.GitModifier.tz_offset}

    >>> import gbp.git
    >>> import datetime
    >>> modifier = gbp.git.GitModifier('foo', 'bar', 1)
    >>> modifier.date
    '1 +0000'
    >>> modifier.date = '1 +0400'
    >>> modifier.date
    '1 +0400'
    >>> modifier['date']
    '1 +0400'
    >>> modifier.datetime   # doctest: +ELLIPSIS
    datetime.datetime(1970, 1, 1, 4, 0, 1, tzinfo=<gbp.git.modifier.GitTz...>)
    >>> modifier.date = datetime.datetime(1970, 1, 1, 0, 0, 1)
    >>> modifier.date
    '1 +0000'
    >>> modifier.datetime   # doctest: +ELLIPSIS
    datetime.datetime(1970, 1, 1, 0, 0, 1, tzinfo=<gbp.git.modifier.GitTz...>)
    >>> modifier.tz_offset
    '+0000'
    """


def test_dict():
    """
    Test C{dict} interface
    >>> import gbp.git
    >>> modifier = gbp.git.GitModifier('foo', 'bar', 1)
    >>> sorted(modifier.keys())
    ['date', 'email', 'name']
    >>> sorted(modifier.items())
    [('date', '1 +0000'), ('email', 'bar'), ('name', 'foo')]
    """
