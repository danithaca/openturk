==== Install/Config ====


This module comes with a few Java libraries to help you write scripts that access data stored in Drupal database. You can then use Drupal as the front end to display data, and the script to all computational intensive data processing. To install/config the module, follow these steps:

1. Follow the example of config.properties.example and create a config.properties file, which specifies the Drupal database access information.
(optional: Move config.properties to sites/default to avoid getting wiped out during module update.)
2. Follow the example of run.sh.example, and create a run.sh execution file to run Async Command script.
(optional: Move run.sh to your home directory to avoid getting wiped out during update.)
3. In a terminal window, execute "run.sh".

What happens then is that the script in "run.sh" will directly access the Drupal database, and run the commands in {async_command} table in the terminal.

You can copy the module to a remote server (doesn't require Drupal installation) and have the script run in the remote server.




===== For Developers =====


Please see some examples of how to use the Java libraries in:
http://drupal.org/project/mt_task
http://drupal.org/project/recommender (developing)

Basically, you'll need to write a Drupal module for user interaction and put commands in the {async_command} table using "async_command_create_command()". Then you'll write your data processing script by extending org.drupal.project.async_command.AbstractDrupalApp. For example, if you put command 'dummy("hello,world")' in {async_command}, the dummy() method in your script will get executed.



===== FAQ =====


Q: Why not using Drupal Queue (D7)?
A: Drupal Queue requires working in the same Drupal server, and requires PHP. Async Command intends to do it on a remote server with different programming languages.

Q: What's the difference with background_queue.module or imageinfo_cache.module
A: Those modules run in PHP, whereas this module runs for any scripts/programs

Q: Where to get support?
A: Please create issues on http://drupal.org/project/async_command.



===== Contact =====

Daniel Zhou
danithaca@gmail.com
http://michiza.com