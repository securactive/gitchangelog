#!/usr/bin/env python

##
## TODO:
##
##  - use an external template to format changelog
##


import re
import os
import os.path
import sys
import textwrap
import datetime
import collections

from subprocess import Popen, PIPE


usage_msg = """usage: %(exname)s [REPOS]

Run this command in a git repository to get a ReST changelog in stdout.

%(exname)s uses a config file to filter meaningfull commit or do some
 formatting in commit messages thanks to a config file.

Config file location will be resolved in this order:

  - in shell environment variable GITCHANGELOG_CONFIG_FILENAME
  - in git configuration: ``git config gitchangelog.rc-patch``
  - as '.%(exname)s.rc' in the root of the current git repository
  - as '~/.%(exname)s.rc'
  - as '/etc/%(exname)s'

"""


class ShellError(Exception):
    pass


def die(msg=None):
    if msg:
        sys.stderr.write(msg + "\n")
    sys.exit(1)

##
## config file functions
##


def load_config_file(filename, fail_if_not_present=True):
    """Loads data from a config file."""

    config = {}

    if os.path.exists(filename):
        try:
            execfile(filename, config)
        except SyntaxError, e:
            die('Syntax error in config file: %s\n'
                'Line %i offset %i\n' % (filename, e.lineno, e.offset))
    else:
        if fail_if_not_present:
            die('%r config file is not found and is required.' % (filename, ))

    return config


##
## Common functions
##

def inflate_dict(dct, sep=".", deep=-1):
    """Inflates a flattened dict.

    Will look in simple dict of string key with string values to
    create a dict containing sub dicts as values.

    Samples are better than explanation:

        >>> from pprint import pprint as pp
        >>> pp(inflate_dict({'a.x': 3, 'a.y': 2}))
        {'a': {'x': 3, 'y': 2}}

    The keyword argument ``sep`` allows to change the separator used
    to get subpart of keys:

        >>> pp(inflate_dict({'etc/group': 'geek', 'etc/user': 'bob'}, "/"))
        {'etc': {'group': 'geek', 'user': 'bob'}}

    Warning: you cannot associate a value to a section:

        >>> inflate_dict({'section.key': 3, 'section': 'bad'})
        Traceback (most recent call last):
        ...
        TypeError: 'str' object does not support item assignment

    Of course, dict containing only keys that doesn't use separator will be
    returned without changes:

        >>> inflate_dict({})
        {}
        >>> inflate_dict({'a': 1})
        {'a': 1}

    Argument ``deep``, is the level of deepness allowed to inflate dict:

        >>> pp(inflate_dict({'a.b.c': 3, 'a.d': 4}, deep=1))
        {'a': {'b.c': 3, 'd': 4}}

    Of course, a deepness of 0 won't do anychanges, whereas deepness of -1 is
    the default value and means infinite deepness:

        >>> pp(inflate_dict({'a.b.c': 3, 'a.d': 4}, deep=0))
        {'a.b.c': 3, 'a.d': 4}

    """

    def mset(dct, k, v, sep=".", deep=-1):
        if deep == 0 or sep not in k:
            dct[k] = v
        else:
            khead, ktail = k.split(sep, 1)
            if khead not in dct:
                dct[khead] = {}
            mset(dct[khead], ktail, v,
                 sep=sep,
                 deep=-1 if deep < 0 else deep - 1)

    res = {}
    ## sorting keys ensures that colliding values if any will be string
    ## first set first so mset will crash with a TypeError Exception.
    for k in sorted(dct.keys()):
        mset(res, k, dct[k], sep, deep)
    return res


##
## Text functions
##


def ucfirst(msg):
    return msg[0].upper() + msg[1:]


def final_dot(msg):
    if len(msg) == 0:
        return "No commit message."
    if msg[-1].isalnum():
        return msg + "."
    return msg


def indent(text, chars="  ", first=None):
    """Return text string indented with the given chars

    >>> string = 'This is first line.\\nThis is second line\\n'

    >>> print indent(string, chars="| ") # doctest: +NORMALIZE_WHITESPACE
    | This is first line.
    | This is second line
    |

    >>> print indent(string, first="- ") # doctest: +NORMALIZE_WHITESPACE
    - This is first line.
      This is second line


    """
    if first:
        first_line = text.split("\n")[0]
        rest = '\n'.join(text.split("\n")[1:])
        return '\n'.join([first + first_line,
                          indent(rest, chars=chars)])
    return '\n'.join([chars + line
                      for line in text.split('\n')])


def paragraph_wrap(text, regexp="\n\n"):
    r"""Wrap text by making sure that paragraph are separated correctly

    >>> string = 'This is first paragraph which is quite long don\'t you \
    ... think ? Well, I think so.\n\nThis is second paragraph\n'

    >>> print paragraph_wrap(string) # doctest: +NORMALIZE_WHITESPACE
    This is first paragraph which is quite long don't you think ? Well, I
    think so.
    This is second paragraph

    Notice that that each paragraph has been wrapped separately.

    """
    regexp = re.compile(regexp, re.MULTILINE)
    return "\n".join("\n".join(textwrap.wrap(paragraph.strip()))
                     for paragraph in regexp.split(text)).strip()


##
## System functions
##


def cmd(command):

    p = Popen(command, shell=True,
              stdin=PIPE, stdout=PIPE, stderr=PIPE,
              close_fds=True)
    stdout, stderr = p.communicate()
    return stdout, stderr, p.returncode


def wrap(command, quiet=True, ignore_errlvls=[0]):
    """Wraps a shell command and casts an exception on unexpected errlvl

    >>> wrap('/tmp/lsdjflkjf') # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
    ...
    ShellError: Wrapped command '/tmp/lsdjflkjf' exited with errorlevel 127.
      stderr:
      | /bin/sh: /tmp/lsdjflkjf: not found

    >>> wrap('echo hello') # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    'hello\\n'

    """

    out, err, errlvl = cmd(command)

    if errlvl not in ignore_errlvls:

        formatted = []
        if out:
            if out.endswith('\n'):
                out = out[:-1]
            formatted.append("stdout:\n%s" % indent(out, "| "))
        if err:
            if err.endswith('\n'):
                err = err[:-1]
            formatted.append("stderr:\n%s" % indent(err, "| "))
        formatted = '\n'.join(formatted)

        raise ShellError("Wrapped command %r exited with errorlevel %d.\n%s"
                        % (command, errlvl, indent(formatted, chars="  ")))
    return out


def swrap(command, **kwargs):
    """Same as ``wrap(...)`` but strips the output."""

    return wrap(command, **kwargs).strip()


##
## git information access
##

class SubGitObjectMixin(object):

    def __init__(self, repos):
        self._repos = repos

    def swrap(self, *args, **kwargs):
        """Simple delegation to ``repos`` original method."""
        return self._repos.swrap(*args, **kwargs)


class GitCommit(SubGitObjectMixin):

    def __init__(self, identifier, repos):
        super(GitCommit, self).__init__(repos)

        self.identifier = identifier

        if identifier is "LAST":
            identifier = self.swrap("git log --format=%H | tail -n 1")

        attrs = {'sha1': "%h",
                 'subject': "%s",
                 'author_name': "%an",
                 'author_date': "%ad",
                 'author_date_timestamp': "%at",
                 'committer_name': "%cn",
                 'committer_date_timestamp': "%ct",
                 'raw_body': "%B",
                 'body': "%b",
                 }
        aformat = "%x00".join(attrs.values())
        try:
            ret = self.swrap("git show -s %r --pretty=format:%s"
                       % (identifier, aformat))
        except ShellError:
            raise ValueError("Given commit identifier %r doesn't exists"
                             % identifier)
        attr_values = ret.split("\x00")
        for attr, value in zip(attrs.keys(), attr_values):
            setattr(self, attr, value.strip())

    @property
    def date(self):
        d = datetime.datetime.utcfromtimestamp(
            float(self.author_date_timestamp))
        return d.strftime('%Y-%m-%d')

    def __eq__(self, value):
        if not isinstance(value, GitCommit):
            return False
        return self.sha1 == value.sha1

    def __hash__(self):
        return hash(self.sha1)

    def __sub__(self, value):
        if not isinstance(value, GitCommit):
            raise TypeError("Invalid type for %r in operation" % value)
        if self.sha1 == value.sha1:
            return []
        commits = self.swrap('git rev-list %s..%s'
                             % (value.sha1, self.sha1))
        if not commits:
            raise ValueError('Seems that %r is earlier than %r'
                             % (self.identifier, value.identifier))
        return [GitCommit(commit, self._repos)
                for commit in reversed(commits.split('\n'))]

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.identifier)


def normpath(path, cwd=None):
    """path can be absolute or relative, if relative it uses the cwd given as
    param.

    """
    if os.path.isabs(path):
        return path
    cwd = cwd if cwd else os.getcwd()
    return os.path.normpath(os.path.join(cwd, path))


class GitRepos(object):

    def __init__(self, path):

        ## Saving this original path to ensure all future git commands
        ## will be done from this location.
        self._orig_path = os.path.abspath(path)

        self.bare = self.swrap("git rev-parse --is-bare-repository") == "true"
        self.toplevel = None if self.bare else \
                        self.swrap("git rev-parse --show-toplevel")
        self.gitdir = os.path.normpath(
            os.path.join(self._orig_path,
                         self.swrap("git rev-parse --git-dir")))

    @property
    def config(self):
        all_options = self.swrap("git config -l")
        dct_options = dict(l.split("=", 1) for l in all_options.split('\n'))
        return inflate_dict(dct_options)

    def swrap(self, command, **kwargs):
        """Essential force the CWD of the command to be in self._orig_path"""

        command = "cd %s; %s" % (self._orig_path, command)
        return swrap(command, **kwargs)

    @property
    def tags(self):
        tags = self.swrap('git tag -l').split("\n")
        while '' in tags:
            tags.remove('')
        return sorted([GitCommit(tag, self) for tag in tags],
                      key=lambda x: int(x.committer_date_timestamp))

    def __getitem__(self, key):

        if isinstance(key, basestring):
            return GitCommit(key, self)

        if isinstance(key, slice):
            start, stop = key.start, key.stop

            if start is None:
                start = GitCommit('LAST', self)

            if stop is None:
                stop = GitCommit('HEAD', self)

            return stop - start
        raise NotImplementedError("Unsupported getitem %r object." % key)


##
## The actual changelog code
##


def make_section_string(title, sections, section_label_order):
    s = ""
    if len(sections) != 0:
        title = title.strip()
        s += title + "\n"
        s += "-" * len(title) + "\n\n"

        nb_sections = len(sections)
        for section in section_label_order:
            if section not in sections:
                continue

            section_label = section if section else "Other"

            if not (section_label == "Other" and nb_sections == 1):
                s += section_label + "\n"
                s += "~" * len(section_label) + "\n\n"

            for entry in sections[section]:
                s += entry
    return s


def first_matching(section_regexps, string):
    for section, regexps in section_regexps:
        if regexps is None:
            return section
        for regexp in regexps:
            if re.search(regexp, string) is not None:
                return section


def changelog(repository,
              ignore_regexps=[],
              replace_regexps={},
              section_regexps={},
              unreleased_version_label="unreleased",
              tag_filter_regexp=r"\d+\.\d+(\.\d+)?",
              body_split_regexp="\n\n",
              ):

    s = "Changelog\n"
    s += "=========\n\n"

    tags = [tag
            for tag in reversed(repository.tags)
            if re.match(tag_filter_regexp, tag.identifier)]

    section_order = [k for k, _v in section_regexps]

    title = unreleased_version_label + "\n"
    sections = collections.defaultdict(list)

    for commit in reversed(repository[:]):

        tags_of_commit = [tag for tag in tags
                         if tag == commit]
        if len(tags_of_commit) > 0:
            tag = tags_of_commit[0]
            ## End of sections, let's flush current one.
            s += make_section_string(title, sections, section_order)

            title = "%s (%s)\n" % (tag.identifier, commit.date)
            sections = collections.defaultdict(list)

        ## Ignore some commit subject
        if any([re.search(pattern, commit.subject) is not None
                for pattern in ignore_regexps]):
            continue

        ## Put message in sections if possible

        matched_section = first_matching(section_regexps, commit.subject)

        ## Replace content in commit subject

        subject = commit.subject
        for regexp, replacement in replace_regexps.iteritems():
            subject = re.sub(regexp, replacement, subject)

        ## Finaly print out the commit

        subject = final_dot(subject)
        subject += " [%s]" % (commit.author_name, )
        entry = indent('\n'.join(textwrap.wrap(ucfirst(subject))),
                       first="- ").strip() + "\n\n"

        if commit.body:
            entry += indent(paragraph_wrap(commit.body,
                                           regexp=body_split_regexp))
            entry += "\n\n"

        sections[matched_section].append(entry)

    s += make_section_string(title, sections, section_order)
    return s

##
## Main
##


def main():

    basename = os.path.basename(sys.argv[0])
    if basename.endswith(".py"):
        basename = basename[:-3]

    if len(sys.argv) == 1:
        repos = "."
    elif len(sys.argv) == 2:
        if sys.argv[1] == "--help":
            print usage_msg % {'exname': basename}
            sys.exit(0)
        repos = sys.argv[1]
    else:
        die('usage: %s [REPOS]\n' % basename)

    ## warning: not safe (repos is given by the user)
    repository = GitRepos(repos)

    gc_rc = repository.config.get("gitchangelog", {}).get('rc-path')
    gc_rc = normpath(gc_rc, cwd=repository.toplevel) if gc_rc else None

    ## config file lookup resolution
    for enforce_file_existence, fun in [
        (True, lambda: os.environ.get('GITCHANGELOG_CONFIG_FILENAME')),
        (True, lambda: gc_rc),
        (False, lambda: ('%s/.%s.rc' % (repository.toplevel, basename)) \
                 if not repository.bare else None),
        (False, lambda: os.path.expanduser('~/.%s.rc' % basename)),
        (False, lambda: '/etc/%s.rc' % basename),
        ]:
        changelogrc = fun()
        if changelogrc:
            if not os.path.exists(changelogrc):
                if enforce_file_existence:
                    print "File %r does not exists." % changelogrc
                    sys.exit(1)
                else:
                    continue  ## changelogrc valued, but file does not exists
            else:
                break

    if not changelogrc or not os.path.exists(changelogrc):
        print "Not %s config file found anywhere." % basename
        sys.exit(1)

    config = load_config_file(os.path.expanduser(changelogrc))

    print changelog(repository,
        ignore_regexps=config['ignore_regexps'],
        replace_regexps=config['replace_regexps'],
        section_regexps=config['section_regexps'],
        unreleased_version_label=config['unreleased_version_label'],
        tag_filter_regexp=config['tag_filter_regexp'],
        body_split_regexp=config['body_split_regexp'],
    )

##
## Launch program
##


if __name__ == "__main__":

    # import doctest
    # doctest.testmod()
    # sys.exit(1)

    main()
