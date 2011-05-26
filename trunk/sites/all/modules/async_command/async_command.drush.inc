<?php

/**
 * @file
 *   Async Command drush interface.
 *   To use this, please install Drush at http://drupal.org/project/drush
 */

/**
 * Implementation of hook_drush_command().
 */
function async_command_drush_command() {
  $items = array();
  $items['async-command'] = array(
    'description' => "Submit an async command directly from Drush",
    'aliases' => array('ac'),
    'arguments' => array(
      'command' => 'Please write down the command. Remember to enclose spaces into double quotes.',
    ),
    
    'callback' => 'async_command_create_command',
    'callback arguments' => array('default'),
    
    'examples' => array(
      'drush async-command your_command' => "Create the 'your_command' command. Remember to enclose spaces into double quotes."
    ),
    
    'bootstrap' => DRUSH_BOOTSTRAP_MAX,
  );
  return $items;
}

/**
 * Implementation of hook_drush_help().
 */
function async_command_drush_help($section) {
  switch ($section) {
    case 'drush:async-command':
      return dt("Create async command directly from Drush");
  }
}

