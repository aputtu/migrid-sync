#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# migcore - a library of core selenium-based web helpers
# Copyright (C) 2003-2018  The MiG Project lead by Brian Vinter
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

"""A collection of functions using selenium and a webdriver of choice to remote
control your browser through a number of web page interactions.

Import and use for interactive purposes in stand-alone scripts something like:
driver = init_driver(browser)
driver.get(url)
mig_login(driver, url, login, passwd)
...
"""

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


def init_driver(browser):
    """Init the requested browser driver"""
    if browser.lower() == 'chrome':
        driver = webdriver.Chrome()
    elif browser.lower() == 'firefox':
        driver = webdriver.Firefox()
    elif browser.lower() == 'safari':
        driver = webdriver.Safari()
    elif browser.lower() == 'ie':
        driver = webdriver.Ie()
    elif browser.lower() == 'edge':
        driver = webdriver.Edge()
    elif browser.lower() == 'phantomjs':
        driver = webdriver.PhantomJS()
    else:
        print "ERROR: Browser _NOT_ supported: %s" % browser
        driver = None
    return driver


def scroll_to_elem(driver, elem):
    """Scroll elem into view"""
    action_chains = ActionChains(driver)
    # NOTE: move_to_element fails if outside viewport - try this workaround
    # action_chains.move_to_element(elem).perform()
    elem.send_keys(Keys.ARROW_DOWN)


def doubleclick_elem(driver, elem):
    """Trigger a double-click on elem"""
    action_chains = ActionChains(driver)
    action_chains.double_click(elem).perform()


def save_screen(driver, path):
    """Save a screenshot of current page in path"""
    driver.save_screenshot(path)


def ucph_login(driver, url, login, passwd, callbacks={}):
    """Login through the UCPH OpenID web form and optionally execute any
    provided callbacks for ready and filled states. The callbacks dictionary
    should contain state names bound to functions accepting driver and state
    name like do_stuff(driver, state) .
    """
    status = True
    do_login = False
    try:
        elem = driver.find_element_by_class_name('form-signin')
        action = elem.get_property('action')
        if action == "https://openid.ku.dk/processTrustResult":
            do_login = True
            state = 'login-ready'
            if callbacks.get(state, None):
                callbacks[state](driver, state)
    except Exception, exc:
        print "ERROR: failed in UCPH login: %s" % exc

    if do_login:
        print "Starting UCPH OpenID login"
        login_elem = driver.find_element_by_name("user")
        pass_elem = driver.find_element_by_name("pwd")
        login_elem.send_keys(login)
        pass_elem.send_keys(passwd)
        state = 'login-filled'
        if callbacks.get(state, None):
            callbacks[state](driver, state)
        driver.find_element_by_name("allow").click()
    else:
        status = False
        print "UCPH OpenID login _NOT_ found"

    print "Starting UCPH OpenID login: %s" % status
    return status


def mig_login(driver, url, login, passwd, callbacks={}):
    """Login through the MiG OpenID web form and optionally execute any
    provided callbacks for ready and filled states. The callbacks dictionary
    should contain state names bound to functions accepting driver and state
    name like do_stuff(driver, state) .
    """
    status = True
    do_login = False
    try:
        elem = driver.find_element_by_class_name('openidlogin')
        form = elem.find_element_by_xpath("//form")
        action = form.get_property('action')
        if action == "%s/openid/allow" % url:
            do_login = True
            state = 'login-ready'
            if callbacks.get(state, None):
                callbacks[state](driver, state)
    except Exception, exc:
        print "ERROR: failed in MiG login: %s" % exc

    if do_login:
        print "Starting MiG OpenID login"
        login_elem = driver.find_element_by_name("identifier")
        pass_elem = driver.find_element_by_name("password")
        login_elem.send_keys(login)
        pass_elem.send_keys(passwd)
        state = 'login-filled'
        if callbacks.get(state, None):
            callbacks[state](driver, state)
        driver.find_element_by_name("yes").click()
    else:
        status = False
        print "MiG OpenID login _NOT_ found"

    print "Starting MiG OpenID login: %s" % status
    return status


def shared_logout(driver, url, login, passwd, callbacks={}):
    """Logout through the shared logout navmenu entry and confirm. Optionally
    execute any provided callbacks for confirm states. The callbacks dictionary
    should contain state names bound to functions accepting driver and state
    name like do_stuff(driver, state) .
    """
    status = True
    do_logout = False
    print "DEBUG: run logout: %s" % url
    try:
        link = driver.find_element_by_link_text('Logout')
        print "DEBUG: found link: %s" % link
        if link:
            print "DEBUG: use link: %s" % link
            do_logout = True
            state = 'logout-ready'
            if callbacks.get(state, None):
                print "DEBUG: callback for: %s" % state
                callbacks[state](driver, state)
            print "DEBUG: click link: %s" % link
            link.click()
    except Exception, exc:
        print "ERROR: failed in logout: %s" % exc

    if do_logout:
        print "Confirm logout"
        confirm_elem = driver.find_element_by_link_text("Yes")
        print "DEBUG: found confirm elem: %s" % confirm_elem
        state = 'logout-confirm'
        if callbacks.get(state, None):
            callbacks[state](driver, state)
        print "DEBUG: click confirm elem: %s" % confirm_elem
        confirm_elem.click()
    else:
        status = False
        print "Confirm login _NOT_ found"

    print "Finished logout: %s" % status
    return status
