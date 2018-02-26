# vim: set fileencoding=utf-8 :
#
# (C) 2018 Guido Günther <agx@sigxcpu.org>
"""A git repository for Debian packages that can roll back operations"""


from .. import log
from .. git import GitRepositoryError
from . git import DebianGitRepository


class RollbackError(GitRepositoryError):
    """
    Error raised if the rollback failed
    """
    def __init__(self, errors):
        self.msg = "Automatic rollback failed"
        super(RollbackError, self).__init__(self.msg)
        self.errors = errors

    def __str__(self):
        return "%s %s" % (self.msg, self.errors)


class RollbackDebianGitRepository(DebianGitRepository):
    """
    Like a DebianGitRepository but can also perform rollbacks and knows
    about some of the inner workings upstream vcs_tag, …
    """
    def __init__(self, *args, **kwargs):
        self.rollbacks = []
        self.rollback_errors = []
        DebianGitRepository.__init__(self, *args, **kwargs)

    def has_rollbacks(self):
        return len(self.rollbacks) > 0

    def rrr(self, refname, action, reftype):
        """
        Remember ref for rollback

        @param refname: ref to roll back
        @param action: the rollback action (delete, reset, ...)
        @param reftype: the reference type (tag, branch, ...)
        """
        sha = None

        if action == 'reset':
            try:
                sha = self.rev_parse(refname)
            except GitRepositoryError as err:
                log.warn("Failed to rev-parse '%s': %s" % (refname, err))
        elif action == 'delete':
            pass
        elif action == 'abortmerge':
            pass
        else:
            raise GitRepositoryError("Unknown action '%s' for %s '%s'" % (action, reftype, refname))
        self.rollbacks.append((refname, reftype, action, sha))

    def rrr_branch(self, branchname, action='reset-or-delete'):
        if action == 'reset-or-delete':
            if self.has_branch(branchname):
                return self.rrr(branchname, 'reset', 'branch')
            else:
                return self.rrr(branchname, 'delete', 'branch')
        else:
            return self.rrr(branchname, action, 'branch')

    def rrr_tag(self, tagname, action='delete'):
        return self.rrr(tagname, action, 'tag')

    def rrr_merge(self, commit, action='abortmerge'):
        return self.rrr(commit, action, 'commit')

    def rollback(self):
        """
        Perform a complete rollback

        Try to roll back as much as possible and remember what failed.
        """
        for (name, reftype, action, sha) in self.rollbacks:
            try:
                if action == 'delete':
                    log.info("Rolling back %s '%s' by deleting it" % (reftype, name))
                    if reftype == 'tag':
                        self.delete_tag(name)
                    elif reftype == 'branch':
                        self.delete_branch(name)
                    else:
                        raise GitRepositoryError("Don't know how to delete %s '%s'" % (reftype, name))
                elif action == 'reset' and reftype == 'branch':
                    log.info('Rolling back branch %s by resetting it to %s' % (name, sha))
                    self.update_ref("refs/heads/%s" % name, sha, msg="gbp import-orig: failure rollback of %s" % name)
                elif action == 'abortmerge':
                    if self.is_in_merge():
                        log.info('Rolling back failed merge of %s' % name)
                        self.abort_merge()
                    else:
                        log.info("Nothing to rollback for merge of '%s'" % name)
                else:
                    raise GitRepositoryError("Don't know how to %s %s '%s'" % (action, reftype, name))
            except GitRepositoryError as e:
                self.rollback_errors.append((name, reftype, action, sha, e))
        if self.rollback_errors:
            raise RollbackError(self.rollback_errors)

    # Wrapped methods for rollbacks
    def create_tag(self, *args, **kwargs):
        name = kwargs['name']
        ret = super(RollbackDebianGitRepository, self).create_tag(*args, **kwargs)
        self.rrr_tag(name)
        return ret

    def commit_dir(self, *args, **kwargs):
        import_branch = kwargs['branch']
        self.rrr_branch(import_branch)
        return super(RollbackDebianGitRepository, self).commit_dir(*args, **kwargs)

    def create_branch(self, *args, **kwargs):
        branch = kwargs['branch']
        ret = super(RollbackDebianGitRepository, self).create_branch(*args, **kwargs)
        self.rrr_branch(branch, 'delete')
        return ret

    def merge(self, *args, **kwargs):
        commit = args[0] if args else kwargs['commit']
        try:
            return super(RollbackDebianGitRepository, self).merge(*args, **kwargs)
        except GitRepositoryError:
            # Only cleanup in the error case to undo working copy
            # changes. Resetting the refs handles the other cases.
            self.rrr_merge(commit)
            raise
