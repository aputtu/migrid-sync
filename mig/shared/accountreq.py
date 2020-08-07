#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# accountreq - helpers for certificate/OpenID account requests
# Copyright (C) 2003-2020  The MiG Project lead by Brian Vinter
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# -- END_HEADER ---
#

"""This module contains various helper contents for the certificate and OpenID
account request handlers"""
from __future__ import absolute_import

import re
import os
import time

# NOTE: the external iso3166 module is optional and only used if available
try:
    import iso3166
except ImportError:
    iso3166 = None

from mig.shared.base import force_utf8, canonical_user, client_id_dir, \
    distinguished_name_to_user
from mig.shared.defaults import peers_fields, peers_filename, \
    pending_peers_filename
from mig.shared.fileio import delete_file
# Expose some helper variables for functionality backends
from mig.shared.safeinput import name_extras, password_extras, password_min_len, \
    password_max_len, valid_password_chars, valid_name_chars, dn_max_len, \
    html_escape
from mig.shared.serial import load, dump


def account_css_helpers(configuration):
    """CSS to include in the cert/oid account req page header"""
    css = '''
<link rel="stylesheet" type="text/css" href="/images/css/jquery.accountform.css" media="screen"/>
    '''
    return css


def account_js_helpers(configuration, fields):
    """Javascript to include in the cert/oid account req page header"""
    # TODO: change remaining names and messages to fit generic auth account?
    add_import = '''
<script type="text/javascript" src="/images/js/jquery.form.js"></script>
<script type="text/javascript" src="/images/js/jquery.accountform.js"></script>
    '''
    add_init = """
  function rtfm_warn(message) {
      return confirm(message + ': Proceed anyway? (If you read and followed the instructions!)');
  }
  
  function check_account_id() {
      //alert('#account_id_help');
      if ($('#cert_id_field').val().indexOf('/') == -1) {
          return rtfm_warn('Account ID does not look like a proper x509 DN');
      }
      return true;
  }
  function check_account_name() {
      //alert('#account_name_help');
      if ($('#cert_name_field').val().indexOf(' ') == -1) {
          return rtfm_warn('Full name does not look like a real name');
      }
      return true;
  }
  function check_full_name() {
      //alert('#full_name_help');
      if ($('#full_name_field').val().indexOf(' ') == -1) {
          return rtfm_warn('Full name does not look like a real name');
      }
      return true;
  }
  function check_email() {
      //alert('#email_help');
      if ($('#email_field').val().search('@') == -1) {
          return rtfm_warn('Email is invalid');
      }
      if ($('#email_field').val().search('@gmail.com') != -1 || $('#email_field').val().search('@yahoo.com') != -1 || $('#email_field').val().search('@hotmail.com') != -1) {
          return rtfm_warn('Email does not look like a organization address');
      }
      return true;
  }
  function check_organization() {
      //alert('#organization_help');
      if ($('#email_field').val().search('.ku.dk') != -1 || $('#email_field').val().search('diku.dk') != -1 || $('#email_field').val().search('nbi.dk') != -1) {
          if ($('#organization_field').val().indexOf(' ') != -1) {
              return rtfm_warn('Organization does not look like an acronym');
          }
      }
      return true;
  }
  function check_country() {
      //alert('#country_help');
      return true;
  }
  function check_state() {
      //alert('#state_help');
      if ($('#country_field').val().search('US') == -1) {
          if ($('#state_field').val() && $('#state_field').val() != 'NA') {
              return rtfm_warn('State only makes sense for US users');
          }
      }
      return true;
  }
  function check_password() {
      //alert('#password_help');
      if ($('#password_field').val().length < %(password_min_len)d) {
         return rtfm_warn('Password too short');
      } else if ($('#password_field').val().length > %(password_max_len)d) {
         return rtfm_warn('Password too long');
      }
      return true;
  }
  function check_verifypassword() {
      //alert('#verifypassword_help');
      if ($('#verifypassword_field').val().length < %(password_min_len)d) {
         return rtfm_warn('Verify password too short');
      } else if ($('#verifypassword_field').val().length > %(password_max_len)d) {
         return rtfm_warn('Verify password too long');
      } else if ($('#password_field').val() != $('#verifypassword_field').val()) {
         return rtfm_warn('Mismatch between password and verify password');
      }
      return true;
  }
  function check_comment() {
      //alert('#comment_help');
      return true;
  }

  function init_context_help() {
      /* move help text just right of connecting gfx bubble */
      var contextualHelpMessage = $('#contextual_help').find('.help_message');
      contextualHelpMessage.offset({top: -30})
      contextualHelpMessage.offset({left: 40})
  }
  function close_context_help() {
      //alert('close called');
      $('#contextual_help').hide();
      $('#contextual_help').css({top: '', left: ''}); // fix for 'drifting' on IE/Chrome
  }
  function bind_help(input_element, message) {
      input_element.focus(function () {
          close_context_help();
          var contextualHelp = $('#contextual_help');
          var contextualHelpMessage = $('#contextual_help').find('.help_message');
          contextualHelpMessage.html(message);
          var inputOffset = $(this).offset(); // top, left
          var scrollTop = $(window).scrollTop(); // how much should we offset if the user has scrolled down the page?
          contextualHelp.offset({
              //top: (inputOffset.top + scrollTop + .5 * $(this).height()) - .5 * contextualHelp.height(),
              top: inputOffset.top + scrollTop,
              //left: (inputOffset.left + .5 * $(this).width()) - .5 * contextualHelp.width()
              left: inputOffset.left + $(this).width() + 20
              //left: inputOffset.left + 20
          });
          contextualHelp.show();
      });
  }
""" % {'password_min_len': password_min_len, 'password_max_len': password_max_len}
    add_init += """
  function validate_form() {
      //alert('validate form');
"""
    add_init += """
      var status = %s""" % ' && '.join(['check_%s()' % name for name in fields])
    add_init += """
      //alert('old validate form: ' +status);
      return status;
  }

"""
    add_ready = """
      init_context_help();
"""
    for name in fields:
        add_ready += """
      bind_help($('#%s_field'), $('#%s_help').html());
""" % (name, name)
    return (add_import, add_init, add_ready)


def account_request_template(configuration, password=True, default_country=''):
    """A general form template used for various account requests"""
    html = """
<div id='account-request-grid' class=form_container>

<!-- use post here to avoid field contents in URL -->
<form method='%(form_method)s' action='%(target_op)s.py' onSubmit='return validate_form();' class="needs-validation" novalidate>
<input type='hidden' name='%(csrf_field)s' value='%(csrf_token)s' />
<div class="form-row">
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom01">Full name</label>
      <input type="text" class="form-control" id="full_name_field" placeholder="Full name" type=text name=cert_name value='%(full_name)s' required pattern='[^ ]+([ ][^ ]+)+' title='Your full name, i.e. two or more names separated by space' />
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please enter your full name.
      </div>
    </div>
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom02">Email address</label>
      <input class="form-control" id="email_field" type=email name=email value='%(email)s' placeholder="username@organization.org" required title="Email address should match your organization - and you need to read mail sent there" />
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please enter your email address matching your organization/company.
      </div>
    </div>
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom01">Organization</label>
      <input class="form-control" id="organization_field" type=text name=org value='%(organization)s' required pattern='[^ ]+([ ][^ ]+)*' placeholder="Organization or company" title='Name of your organization or company: one or more words or abbreviations separated by space' />
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please enter the name of your organization or company.
      </div>
    </div>
  </div>
  <div class="form-row">
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom03">Country</label>
    """
    # Generate drop-down of countries and codes if available, else simple input
    sorted_countries = list_country_codes(configuration)
    if sorted_countries:
        html += """
        <select class="form-control themed-select html-select" id="country_field" name=country minlength=2 maxlength=2 value='%(country)s' required pattern='[A-Z]{2}' placeholder="Two letter country-code" title='Please select your country from the list'>
"""
        # TODO: detect country based on browser info?
        # Start out without a country selection
        for (name, code) in [('', '')] + sorted_countries:
            selected = ''
            if default_country == code:
                selected = 'selected'
            html += "        <option value='%s' %s>%s</option>\n" % \
                    (code, selected, name)
        html += """
        </select>
    """
    else:
        html += """
        <input class="form-control" id="country_field" type=text name=country value='%(country)s' required pattern='[A-Z]{2}' minlength=2 maxlength=2 placeholder="Two letter country-code" title='The two capital letters used to abbreviate your country' />
        """

    html += """
        <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please select your country or provide your two letter country-code in line with
        https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2.
      </div>
    </div>
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom04">Optional state code</label>
      <input class="form-control" id="state_field" type=text name=state value='%(state)s' pattern='([A-Z]{2})?' maxlength=2 placeholder="NA" title="Mainly for U.S. users - please just leave empty if in doubt" >
    </div>
  </div>
    """

    if password:
        html += """  
  <div class="form-row">
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom01">Password</label>
      <input type="password" class="form-control" id="password_field" type=password name=password minlength=%(password_min_len)d maxlength=%(password_max_len)d value='%(password)s' required pattern='.{%(password_min_len)d,%(password_max_len)d}' placeholder="Your password" title='Password of your choice - site policies about password strength apply and will give you feedback below if refused' />
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please provide a valid and sufficiently strong password.<br/>
        I.e. %(password_min_len)d to %(password_max_len)d characters from at least %(password_min_classes)d of the 4 different character classes: lowercase, uppercase, digits, other.
      </div>
    </div>
    <div class="col-md-4 mb-3 form-cell">
      <label for="validationCustom03">Verify password</label>
      <input type="password" class="form-control" id="verifypassword_field" type=password name=verifypassword minlength=%(password_min_len)d maxlength=%(password_max_len)d value='%(verifypassword)s' required pattern='.{%(password_min_len)d,%(password_max_len)d}' placeholder="Repeat password" title='Repeat your chosen password to rule out most simple typing errors' />
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        Please repeat your chosen password to verify.
      </div>
    </div>
  </div>
        """

    html += """
  <div class="form-row single-entry">
    <div class="col-md-12 mb-3 form-cell">
      <label for="validationCustom03">Optional comment or reason why you should be granted a %(site)s account:</label>
      <textarea rows=4 name=comment title='A free-form comment to justify your account needs' placeholder="Typically a note about which collaboration, project or course you need the account for and the name and email of your affiliated contact" ></textarea>
    </div>
  </div>
  <div class="form-group">
    <div class="form-check">
      <span class="switch-label">I accept the %(site)s <a href="/public/terms.html" target="_blank">terms and conditions</a></span>
      <label class="form-check-label switch" for="acceptTerms">
      <input class="form-check-input" type="checkbox" value="" id="acceptTerms" required>
      <span class="slider round small" title="Required to get an account"></span>
      <br/>
      <div class="valid-feedback">
        Looks good!
      </div>
      <div class="invalid-feedback">
        You <em>must</em> agree to terms and conditions before sending.
      </div>
      </label>
    </div>
  </div>
  <div class="vertical-spacer"></div>
  <input id="submit_button" type=submit value=Send />
</form>

</div>
    """
    return html


def build_accountreqitem_object(configuration, accountreq_dict):
    """Build a accountreq object based on input accountreq_dict"""

    created_epoch = accountreq_dict['created']
    created_asctime = time.ctime(created_epoch)
    accountreq_obj = {
        'object_type': 'accountreq',
        'auth': accountreq_dict.get('auth', ['unknown']),
        'id': accountreq_dict['id'],
        'full_name': accountreq_dict['full_name'],
        'email': accountreq_dict['email'],
        'organization': accountreq_dict['organization'],
        'country': accountreq_dict['country'],
        'state': accountreq_dict['state'],
        'comment': accountreq_dict['comment'],
        'created': "<div class='sortkey'>%d</div>%s" % (created_epoch,
                                                        created_asctime),
    }
    return accountreq_obj


def list_account_reqs(configuration):
    """Find all pending certificate/OpenID accounts requests"""
    logger = configuration.logger
    accountreq_list = []
    dir_content = []

    try:
        dir_content = os.listdir(configuration.user_pending)
    except Exception:
        if not os.path.isdir(configuration.user_pending):
            try:
                os.mkdir(configuration.user_pending)
            except Exception as err:
                logger.error(
                    'accountreq.py: not able to create directory %s: %s' %
                    (configuration.accountreq_home, err))
                return (False, "account request setup is broken")
            dir_content = []

    for entry in dir_content:

        # Skip dot files/dirs

        if entry.startswith('.'):
            continue
        if is_account_req(entry, configuration):
            accountreq_list.append(entry)
        else:
            logger.warning(
                '%s in %s is not a file, move it?'
                % (entry, configuration.user_pending))
    return (True, accountreq_list)


def is_account_req(req_id, configuration):
    """Check that req_id is an existing account request"""
    req_path = os.path.join(configuration.user_pending, req_id)
    if os.path.isfile(req_path):
        return True
    else:
        return False


def get_account_req(req_id, configuration):
    """Helper to fetch dictionary for a pending account request"""
    req_path = os.path.join(configuration.user_pending, req_id)
    req_dict = load(req_path)
    if not req_dict:
        return (False, 'Could not open account request %s' % req_id)
    else:
        req_dict['id'] = req_id
        req_dict['created'] = os.path.getctime(req_path)
        return (True, req_dict)


def accept_account_req(req_id, configuration):
    """Helper to accept a pending account request"""
    _logger = configuration.logger
    req_path = os.path.join(configuration.user_pending, req_id)
    # TODO: run createuser
    _logger.warning('account creation from admin page not implemented yet')
    return False


def delete_account_req(req_id, configuration):
    """Helper to delete a pending account request"""
    req_path = os.path.join(configuration.user_pending, req_id)
    return delete_file(req_path, configuration.logger)


def existing_country_code(country_code, configuration):
    """Check that country_code matches an existing code in line with ISO3166"""

    logger = configuration.logger
    if iso3166 is None:
        logger.info("iso3166 module not available - accept all countries")
        return True
    try:
        country = iso3166.countries.get(country_code)
        logger.debug("found country %s for code %s" % (country, country_code))
        # Country object has 2-letter code in alpha2 attribute
        return (country and country.alpha2 == country_code)
    except KeyError:
        logger.warning("no country found for code %s" % country_code)
        return False


def list_country_codes(configuration):
    """Get a sorted list of available countries and their 2-letter ISO3166
    country code for use in country selection during account sign up.
    """
    logger = configuration.logger
    if iso3166 is None:
        logger.info("iso3166 module not available - manual country code entry")
        return False
    country_list = []
    for entry in iso3166.countries:
        name, code = force_utf8(entry.name), force_utf8(entry.alpha2)
        #logger.debug("found country %s for code %s" % (name, code))
        country_list.append((name, code))
    return country_list


def forced_org_email_match(org, email, configuration):
    """Check that email and organization follow the required policy"""

    logger = configuration.logger
    # Policy regexps: prioritized order with most general last
    force_org_email = [('DIKU', ['^[a-zA-Z0-9_.+-]+@diku.dk$',
                                 '^[a-zA-Z0-9_.+-]+@di.ku.dk$']),
                       ('NBI', ['^[a-zA-Z0-9_.+-]+@nbi.ku.dk$',
                                '^[a-zA-Z0-9_.+-]+@nbi.dk$',
                                '^[a-zA-Z0-9_.+-]+@fys.ku.dk$']),
                       ('IMF', ['^[a-zA-Z0-9_.+-]+@math.ku.dk$']),
                       ('DTU', ['^[a-zA-Z0-9_.+-]+@dtu.dk$']),
                       # Keep this KU catch-all last and do not generalize it!
                       ('KU', ['^[a-zA-Z0-9_.+-]+@(alumni.|)ku.dk$']),
                       ]
    force_org_email_dict = dict(force_org_email)
    is_forced_email = False
    is_forced_org = False
    if org.upper() in force_org_email_dict.keys():
        is_forced_org = True
        # Consistent casing
        org = org.upper()
    email_hit = '__BOGUS__'
    for (forced_org, forced_email_list) in force_org_email:
        for forced_email in forced_email_list:
            if re.match(forced_email, email):
                is_forced_email = True
                email_hit = forced_email
                logger.debug('email match on %s vs %s' % (email, forced_email))
                break

        # Use first hit to avoid catch-all overriding specific hits
        if is_forced_email or is_forced_org and org == forced_org:
            break
    if is_forced_org != is_forced_email or \
            not email_hit in force_org_email_dict.get(org, ['__BOGUS__']):
        logger.error('Illegal email and organization combination: %s' %
                     ([email, org, is_forced_org, is_forced_email,
                       email_hit, force_org_email_dict.get(org,
                                                           ['__BOGUS__'])]))
        return False
    else:
        return True


def peers_permit_allowed(configuration, user_dict):
    """Check if user with user_dict is allowed to manage peers based on
    optional configuration limits.
    """
    for (key, val) in configuration.site_peers_permit:
        if not re.match(val, user_dict.get(key, 'NO SUCH FIELD')):
            return False
    return True


def parse_peers_form(configuration, raw_lines, csv_sep):
    """Parse CSV form of peers into a list of peers"""
    _logger = configuration.logger
    header = None
    peers = []
    err = []
    for line in raw_lines.split('\n'):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        parts = line.split(csv_sep)
        if not header:
            missing = [i for i in peers_fields if i not in parts]
            if missing:
                err.append("Parsed peers did NOT contain required field(s): %s"
                           % ', '.join(missing))
            header = parts
            continue
        if len(header) != len(parts):
            _logger.warning('skip peers line with mismatch in field count: %s'
                            % line)
            err.append("Skip peers line not matching header format: %s" %
                       html_escape(line + ' vs ' + csv_sep.join(header)))
            continue
        raw_user = dict(zip(header, parts))
        peers.append(canonical_user(configuration, raw_user, peers_fields))
    _logger.debug('parsed form into peers: %s' % peers)
    return (peers, err)


def parse_peers_userid(configuration, raw_entries):
    """Parse list of user IDs into a list of peers"""
    _logger = configuration.logger
    peers = []
    err = []
    for entry in raw_entries:
        raw_user = distinguished_name_to_user(entry.strip())
        missing = [i for i in peers_fields if i not in raw_user]
        if missing:
            err.append("Parsed peers did NOT contain required field(s): %s"
                       % ', '.join(missing))
            continue
        peers.append(canonical_user(configuration, raw_user, peers_fields))
    _logger.debug('parsed user id into peers: %s' % peers)
    return (peers, err)


def parse_peers(configuration, peers_content, peers_format, csv_sep=';'):
    """Parse provided peer formats into a list of peer users.
    Please note that peers_content is the accepted list of input values.
    """
    _logger = configuration.logger
    if "userid" == peers_format:
        raw_peers = peers_content
        return parse_peers_userid(configuration, raw_peers)
    elif "csvform" == peers_format:
        # NOTE: first merge the individual textarea(s)
        raw_peers = '\n'.join(peers_content)
        return parse_peers_form(configuration, raw_peers, csv_sep)
    elif "csvupload" == peers_format:
        # TODO: extract upload
        raw_peers = ''
        return parse_peers_form(configuration, raw_peers, csv_sep)
    elif "csvurl" == peers_format:
        # TODO: fetch URL contents
        raw_peers = ''
        return parse_peers_form(configuration, raw_peers, csv_sep)
    elif "fields" == peers_format:
        # TODO: extract fields
        raw_peers = []
        return parse_peers_userid(configuration, raw_peers)
    else:
        _logger.error("unknown peers format: %s" % peers_format)
        return ([], "unknown peers format: %s" % peers_format)


def manage_pending_peers(configuration, client_id, action, change_list):
    """Helper to manage changes to pending peers list of client_id"""
    _logger = configuration.logger
    client_dir = client_id_dir(client_id)
    pending_peers_path = os.path.join(configuration.user_settings, client_dir,
                                      pending_peers_filename)
    try:
        pending_peers = load(pending_peers_path)
    except Exception as exc:
        if os.path.exists(pending_peers_path):
            _logger.warning("could not load pending peers from %s: %s" %
                            (pending_peers_path, exc))
        pending_peers = []
    change_dict = dict(change_list)
    # NOTE: always remove old first to replace any existing and move them last
    pending_peers = [(i, j)
                     for (i, j) in pending_peers if not i in change_dict]
    if action == "add":
        pending_peers += change_list
    elif action == "remove":
        pass
    else:
        _logger.error(
            "unsupported action in manage pending peers: %s" % action)
        return False
    try:
        dump(pending_peers, pending_peers_path)
        return True
    except Exception as exc:
        _logger.warning("could not save pending peers to %s: %s" %
                        (pending_peers_path, exc))
        return False


def get_accepted_peers(configuration, client_id):
    """Helper to get the list of peers accepted by client_id"""
    _logger = configuration.logger
    client_dir = client_id_dir(client_id)
    peers_path = os.path.join(configuration.user_settings, client_dir,
                              peers_filename)
    try:
        accepted_peers = load(peers_path)
    except Exception as exc:
        if os.path.exists(peers_path):
            _logger.warning("could not load peers from %s: %s" %
                            (peers_path, exc))
        accepted_peers = {}
    return accepted_peers
