#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# --- BEGIN_HEADER ---
#
#
# pwhash - helpers for passwords and hashing
# Copyright (C) 2003-2022  The MiG Project lead by Brian Vinter
#
# This file is part of MiG.
#
# MiG is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# MiG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
# --- END_HEADER ---
#

"""Helpers for various password policy and hashing activities.

Includes some parts for pbkdf2 handling from
https://github.com/mitsuhiko/python-pbkdf2

Relevant info and rights inlined below:
    ---
    Securely hash and check passwords using PBKDF2.

    Use random salts to protect againt rainbow tables, many iterations against
    brute-force, and constant-time comparaison againt timing attacks.

    Keep parameters to the algorithm together with the hash so that we can
    change the parameters and keep older hashes working.

    See more details at http://exyr.org/2011/hashing-passwords/

    Author: Simon Sapin
    License: BSD
    ---
"""

from __future__ import print_function
from __future__ import absolute_import

from builtins import zip, range
import hashlib
from base64 import b64encode, b64decode, b16encode, b16decode
from os import urandom
from random import SystemRandom
from string import ascii_lowercase, ascii_uppercase, digits

from mig.shared.base import force_utf8
from mig.shared.pbkdf2 import pbkdf2_bin

try:
    import cracklib
except ImportError:
    # Optional cracklib not available - fail gracefully and check before use
    cracklib = None

from mig.shared.defaults import POLICY_NONE, POLICY_WEAK, POLICY_MEDIUM, \
    POLICY_HIGH, POLICY_MODERN, POLICY_CUSTOM, PASSWORD_POLICIES

# Parameters to PBKDF2. Only affect new passwords.
SALT_LENGTH = 12
KEY_LENGTH = 24
HASH_FUNCTION = 'sha256'  # Must be in hashlib.
# Linear to the hashing time. Adjust to be high but take a reasonable
# amount of time on your server. Measure with:
# python -m timeit -s 'import passwords as p' 'p.make_hash("something")'
COST_FACTOR = 10000


def make_hash(password):
    """Generate a random salt and return a new hash for the password."""
    password = force_utf8(password)
    salt = b64encode(urandom(SALT_LENGTH))
    # Python 2.6 fails to parse implicit positional args (-Jonas)
    # return 'PBKDF2${}${}${}${}'.format(
    return 'PBKDF2${0}${1}${2}${3}'.format(
        HASH_FUNCTION,
        COST_FACTOR,
        salt,
        b64encode(pbkdf2_bin(password, salt, COST_FACTOR, KEY_LENGTH,
                             getattr(hashlib, HASH_FUNCTION))))


def check_hash(configuration, service, username, password, hashed,
               hash_cache=None, strict_policy=True, allow_legacy=False):
    """Check a password against an existing hash. First make sure the provided
    password satisfies the local password policy. The optional hash_cache
    dictionary argument can be used to cache recent lookups to save time in
    e.g. webdav where each operation triggers hash check.
    The optional boolean strict_policy argument decides whether or not the site
    password policy is enforced. It is used to disable checks for e.g.
    sharelinks where the policy is not guaranteed to apply.
    The optional boolean allow_legacy argument extends the strict_policy check
    so that passwords matching any configured password legacy policy are also
    accepted. Use only during active log in checks.
    """
    _logger = configuration.logger
    password = force_utf8(password)
    pw_hash = hashlib.md5(password).hexdigest()
    if isinstance(hash_cache, dict) and \
            hash_cache.get(pw_hash, None) == hashed:
        # print("got cached hash: %s" % hash_cache.get(pw_hash, None))
        return True
    # We check policy AFTER cache lookup since it is already verified for those
    if strict_policy:
        try:
            assure_password_strength(configuration, password, allow_legacy)
        except Exception as exc:
            _logger.warning("%s password for %s does not fit local policy: %s"
                            % (service, username, exc))
            return False
    else:
        _logger.debug("password policy check disabled for %s login as %s" %
                      (service, username))
    algorithm, hash_function, cost_factor, salt, hash_a = hashed.split('$')
    assert algorithm == 'PBKDF2'
    hash_a = b64decode(hash_a)
    hash_b = pbkdf2_bin(password, salt, int(cost_factor), len(hash_a),
                        getattr(hashlib, hash_function))
    assert len(hash_a) == len(hash_b)  # we requested this from pbkdf2_bin()
    # Same as "return hash_a == hash_b" but takes a constant time.
    # See http://carlos.bueno.org/2011/10/timing.html
    diff = 0
    for char_a, char_b in zip(hash_a, hash_b):
        diff |= ord(char_a) ^ ord(char_b)
    match = (diff == 0)
    if isinstance(hash_cache, dict) and match:
        hash_cache[pw_hash] = hashed
        # print("cached hash: %s" % hash_cache.get(pw_hash, None))
    return match


def scramble_digest(salt, digest):
    """Scramble digest for saving"""
    b16_digest = b16encode(digest)
    xor_int = int(salt, 16) ^ int(b16_digest, 16)
    # Python 2.6 fails to parse implicit positional args (-Jonas)
    # return '{:X}'.format(xor_int)
    return '{0:X}'.format(xor_int)


def unscramble_digest(salt, digest):
    """Unscramble loaded digest"""
    xor_int = int(salt, 16) ^ int(digest, 16)
    # Python 2.6 fails to parse implicit positional args (-Jonas)
    # b16_digest = '{:X}'.format(xor_int)
    b16_digest = '{0:X}'.format(xor_int)
    return b16decode(b16_digest)


def make_digest(realm, username, password, salt):
    """Generate a digest for the credentials"""
    merged_creds = ':'.join([realm, username, password])
    # TODO: can we switch to proper md5 hexdigest without breaking webdavs?
    digest = 'DIGEST$custom$CONFSALT$%s' % scramble_digest(salt, merged_creds)
    return digest


def check_digest(configuration, service, realm, username, password, digest,
                 salt, digest_cache=None, strict_policy=True,
                 allow_legacy=False):
    """Check credentials against an existing digest. First make sure the
    provided password satisfies the local password policy. The optional
    digest_cache dictionary argument can be used to cache recent lookups to
    save time in e.g. webdav where each operation triggers digest check.
    The optional boolean strict_policy argument changes warnings about password
    policy incompliance to unconditional rejects.
    The optional boolean allow_legacy argument extends the strict_policy check
    so that passwords matching any configured password legacy policy are also
    accepted. Use only during active log in checks.
    """
    _logger = configuration.logger
    realm = force_utf8(realm)
    username = force_utf8(username)
    password = force_utf8(password)
    merged_creds = ':'.join([realm, username, password])
    creds_hash = hashlib.md5(merged_creds).hexdigest()
    if isinstance(digest_cache, dict) and \
            digest_cache.get(creds_hash, None) == digest:
        # print("got cached digest: %s" % digest_cache.get(creds_hash, None))
        return True
    # We check policy AFTER cache lookup since it is already verified for those
    try:
        assure_password_strength(configuration, password, allow_legacy)
    except Exception as exc:
        _logger.warning("%s password for %s does not fit local policy: %s"
                        % (service, username, exc))
        if strict_policy:
            return False
    match = (make_digest(realm, username, password, salt) == digest)
    if isinstance(digest_cache, dict) and match:
        digest_cache[creds_hash] = digest
        # print("cached digest: %s" % digest_cache.get(creds_hash, None))
    return match


def scramble_password(salt, password):
    """Scramble password for saving with fallback to base64 encoding if no salt
    is provided.
    """
    if not salt:
        return b64encode(password)
    xor_int = int(salt, 16) ^ int(b16encode(password), 16)
    return '{0:X}'.format(xor_int)


def unscramble_password(salt, password):
    """Unscramble loaded password with fallback to base64 decoding if no salt
    is provided.
    """
    if not salt:
        return b64decode(password)
    xor_int = int(salt, 16) ^ int(password, 16)
    b16_password = '{0:X}'.format(xor_int)
    return b16decode(b16_password)


def make_scramble(password, salt):
    """Generate a scrambled password"""
    return scramble_password(salt, password)


def check_scramble(configuration, service, username, password, scrambled,
                   salt=None, scramble_cache=None, strict_policy=True,
                   allow_legacy=False):
    """Make sure provided password satisfies local password policy and check
    match against existing scrambled password. The optional scramble_cache
    dictionary argument can be used to cache recent lookups to save time in
    e.g. openid where each operation triggers check.

    NOTE: we force strict password policy here since we may find weak legacy
    passwords in the user DB and they would easily give full account access.
    The optional boolean allow_legacy argument extends the strict_policy check
    so that passwords matching any configured password legacy policy are also
    accepted. Use only during active log in checks.
    """
    _logger = configuration.logger
    password = force_utf8(password)
    if isinstance(scramble_cache, dict) and \
            scramble_cache.get(password, None) == scrambled:
        # print("got cached scramble: %s" % scramble_cache.get(password, None))
        return True
    # We check policy AFTER cache lookup since it is already verified for those
    try:
        assure_password_strength(configuration, password, allow_legacy)
    except Exception as exc:
        _logger.warning('%s password for %s does not satisfy local policy: %s'
                        % (service, username, exc))
        if strict_policy:
            return False
    match = (make_scramble(password, salt) == scrambled)
    if isinstance(scramble_cache, dict) and match:
        scramble_cache[password] = scrambled
        # print("cached digest: %s" % scramble_cache.get(password, None))
    return match


def make_csrf_token(configuration, method, operation, client_id, limit=None):
    """Generate a Cross-Site Request Forgery (CSRF) token to help verify the
    authenticity of user requests. The optional limit argument can be used to
    e.g. put a timestamp into the mix, so that the token automatically expires.
    """
    salt = configuration.site_digest_salt
    merged = "%s:%s:%s:%s" % (method, operation, client_id, limit)
    # configuration.logger.debug("CSRF for %s" % merged)
    xor_id = "%s" % (int(salt, 16) ^ int(b16encode(merged), 16))
    token = hashlib.sha256(xor_id).hexdigest()
    return token


def make_csrf_trust_token(configuration, method, operation, args, client_id,
                          limit=None, skip_fields=[]):
    """A special version of the Cross-Site Request Forgery (CSRF) token used
    for cases where we already know the complete query arguments and just need
    to validate that they were passed untampered from us self.
    Packs the query args into the operation in a deterministic order by
    appending in sorted order from args.keys then just applies make_csrf_token.
    The optional skip_fields list can be used to exclude args from the token.
    That is mainly used to allow use for checking where the trust token is
    already part of the args and therefore should not be considered.
    """
    _logger = configuration.logger
    csrf_op = '%s' % operation
    if args:
        sorted_keys = sorted(list(args))
    else:
        sorted_keys = []
    for key in sorted_keys:
        if key in skip_fields:
            continue
        csrf_op += '_%s' % key
        for val in args[key]:
            csrf_op += '_%s' % val
    _logger.debug("made csrf_trust from url %s" % csrf_op)
    return make_csrf_token(configuration, method, csrf_op, client_id, limit)


def password_requirements(site_policy, logger=None):
    """Parse the custom password policy value to get the number of required
    characters and different character classes.
    """
    min_len, min_classes, errors = -1, 42, []
    if site_policy == POLICY_NONE:
        if logger:
            logger.debug('site password policy allows ANY password')
        min_len, min_classes = 0, 0
    elif site_policy == POLICY_WEAK:
        min_len, min_classes = 6, 2
    elif site_policy == POLICY_MEDIUM:
        min_len, min_classes = 8, 3
    elif site_policy == POLICY_HIGH:
        min_len, min_classes = 10, 4
    elif site_policy.startswith(POLICY_MODERN):
        try:
            _, min_len_str = site_policy.split(':', 1)
            min_len, min_classes = int(min_len_str), 1
        except Exception as exc:
            errors.append('modern password policy %s on invalid format: %s' %
                          (site_policy, exc))
    elif site_policy.startswith(POLICY_CUSTOM):
        try:
            _, min_len_str, min_classes_str = site_policy.split(':', 2)
            min_len, min_classes = int(min_len_str), int(min_classes_str)
        except Exception as exc:
            errors.append('custom password policy %s on invalid format: %s' %
                          (site_policy, exc))
    else:
        errors.append('unknown password policy keyword: %s' % site_policy)
    if logger:
        logger.debug('password policy %s requires %d chars from %d classes' %
                     (site_policy, min_len, min_classes))
    return min_len, min_classes, errors


def parse_password_policy(configuration, use_legacy=False):
    """Parse the custom password policy in configuration to get the number of
    required characters and different character classes.
    NOTE: fails hard later if invalid policy is used for best security.
    The optional boolean use_legacy argument results in any configured
    password legacy policy being used instead of the default password policy.
    """
    _logger = configuration.logger
    if use_legacy:
        policy = configuration.site_password_legacy_policy
    else:
        policy = configuration.site_password_policy
    min_len, min_classes, errors = password_requirements(policy, _logger)
    for err in errors:
        _logger.error(err)
    return min_len, min_classes


def __assure_password_strength_helper(configuration, password, use_legacy=False):
    """Helper to check if password fits site password policy or password legacy
    policy in terms of length and required number of different character classes.
    We split into four classes for now, lowercase, uppercase, digits and other.
    The optional use_legacy argument is used to decide if the configured normal
    password policy or any configured password legacy policy should apply.
    """
    _logger = configuration.logger
    if use_legacy:
        policy_fail_msg = 'password does not fit password legacy policy'
    else:
        policy_fail_msg = 'password does not fit password policy'
    min_len, min_classes = parse_password_policy(configuration, use_legacy)
    if min_len < 0 or min_classes > 4:
        raise Exception('parse password policy failed: %d %d (use_legacy: %s)'
                        % (min_len, min_classes, use_legacy))
    if len(password) < min_len:
        raise ValueError('%s: password too short, at least %d chars required' %
                         (policy_fail_msg, min_len))
    char_class_map = {'lower': ascii_lowercase, 'upper': ascii_uppercase,
                      'digits': digits}
    base_chars = ''.join(list(char_class_map.values()))
    pw_classes = []
    for i in password:
        if i not in base_chars and 'other' not in pw_classes:
            pw_classes.append('other')
            continue
        for (char_class, values) in list(char_class_map.items()):
            if i in values and not char_class in pw_classes:
                pw_classes.append(char_class)
                break
    if len(pw_classes) < min_classes:
        raise ValueError('%s: password too simple, >= %d char classes required' %
                         (policy_fail_msg, min_classes))
    if configuration.site_password_cracklib:
        if cracklib:
            # NOTE: min_len does not exactly match cracklib.MIN_LENGTH meaning
            #       but we just make sure cracklib does not directly increase
            #       policy requirements.
            cracklib.MIN_LENGTH = min_len + min_classes
            try:
                # NOTE: this raises ValueError if password is too simple
                cracklib.VeryFascistCheck(password)
            except Exception as exc:
                raise ValueError("cracklib refused password: %s" % exc)
        else:
            raise Exception('cracklib requested in conf but not available')
    return True


def assure_password_strength(configuration, password, allow_legacy=False):
    """Make sure password fits site password policy in terms of length and
    required number of different character classes.
    We split into four classes for now, lowercase, uppercase, digits and other.
    The optional allow_legacy argument should be supplied for calls where any
    configured password legacy policy should apply. Namely for cases where only
    an actual password log in is checked, but not when saving a new password
    anywhere.
    """
    _logger = configuration.logger
    site_policy = configuration.site_password_policy
    site_legacy_policy = configuration.site_password_legacy_policy
    try:
        __assure_password_strength_helper(configuration, password, False)
        _logger.debug('password compliant with password policy (%s)' %
                      site_policy)
        return True
    except ValueError as err:
        if site_legacy_policy and allow_legacy:
            _logger.info("%s. Proceed with legacy policy check." % err)
        else:
            _logger.warning("%s" % err)
            raise err

    try:
        __assure_password_strength_helper(configuration, password, True)
        _logger.debug('password compliant with password legacy policy (%s)' %
                      site_legacy_policy)
        return True
    except ValueError as err:
        _logger.warning("%s" % err)
        raise err


def valid_login_password(configuration, password):
    """Helper to verify that provided password is valid for login purposes.
    This is a convenience wrapper for assure_password_strength to get a boolean
    result. Used in grid_webdavs and from sftpsubsys PAM helper.
    """
    _logger = configuration.logger
    try:
        assure_password_strength(configuration, password, allow_legacy=True)
        return True
    except ValueError as err:
        return False
    except Exception as exc:
        _logger.error("unexpected exception in valid_login_password: %s" % exc)
        return False


def make_simple_hash(val):
    """Generate a simple md5 hash for val and return the 32-char hexdigest"""
    return hashlib.md5(val).hexdigest()


def make_path_hash(configuration, path):
    """Generate a 128-bit md5 hash for path and return the 32 char hexdigest.
    Used to compress long paths into a fixed length string ID without
    introducing serious collision risks, under the assumption that the
    total number of path hashes is say in the millions or less. Please refer
    to the collision risk calculations at e.g
    http://preshing.com/20110504/hash-collision-probabilities/
    https://en.wikipedia.org/wiki/Birthday_attack
    for the details.
    """
    _logger = configuration.logger
    _logger.debug("make path hash for %s" % path)
    return make_simple_hash(path)


def generate_random_ascii(count, charset):
    """Generate a string of count random characters from given charset"""
    return ''.join(SystemRandom().choice(charset) for _ in range(count))


def generate_random_password(configuration, tries=42):
    """Generate a password string of random characters from allowed password
    charset and taking any active password policy in configuration into
    account.
    Tries can be used to tune the number of attempts to make sure random
    selection does not yield too weak a password.
    """
    _logger = configuration.logger
    count, classes = parse_password_policy(configuration)
    # TODO: use the password charset from safeinput instead?
    charset = ascii_lowercase
    if classes > 1:
        charset += ascii_uppercase
    if classes > 2:
        charset += digits
    if classes > 3:
        charset += ',.;:+=&%#@£$/?*'
    for i in range(tries):
        _logger.debug("make password with %d chars from %s" % (count, charset))
        password = generate_random_ascii(count, charset)
        try:
            assure_password_strength(configuration, password)
            return password
        except ValueError as err:
            _logger.warning("generated password %s didn't fit policy - retry"
                            % password)
            pass
    _logger.error("failed to generate password to fit site policy")
    raise ValueError("Failed to generate suitable password!")


if __name__ == "__main__":
    from mig.shared.conf import get_configuration_object
    configuration = get_configuration_object()
    for policy in PASSWORD_POLICIES:
        if policy == POLICY_MODERN:
            policy += ':12'
        elif policy == POLICY_CUSTOM:
            policy += ':12:4'
        configuration.site_password_policy = policy
        for pw in ('', 'abc', 'dbey3h', 'abcdefgh', '12345678', 'test1234',
                   'password', 'djeudmdj', 'Password12', 'P4s5W0rd',
                   'GoofBall', 'b43kdn22', 'Dr3Ab3_2', 'kasd#D2s',
                   'fsk34dsa-.32d', 'd3kk3mdkkded', 'Loh/p4iv,ahk',
                   'MinimumIntrusionGrid', 'correcthorsebatterystaple'):
            try:
                res = assure_password_strength(configuration, pw)
            except Exception as exc:
                res = "False (%s)" % exc
            print("Password %r follows %s password policy: %s" %
                  (pw, policy, res))
