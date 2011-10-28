# vim: set fileencoding=utf-8 :

"""
Test L{gbp.git.GitModifier}
"""

def test_author():
    """
    Methods tested:
         - L{gbp.git.GitModifer.get_author_env}
         - L{gbp.git.GitModifer.get_comitter_env}

    >>> import gbp.git
    >>> modifier = gbp.git.GitModifier("foo", "bar")
    >>> modifier.name
    'foo'
    >>> modifier.email
    'bar'
    >>> modifier.get_author_env()
    {'GIT_AUTHOR_EMAIL': 'bar', 'GIT_AUTHOR_NAME': 'foo'}
    >>> modifier.get_committer_env()
    {'GIT_COMMITTER_NAME': 'foo', 'GIT_COMMITTER_EMAIL': 'bar'}
    """
