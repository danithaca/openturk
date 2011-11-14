# coding: utf8

# scripts to handle mturks. based on async_command DrupalApp
# requires jython
from pprint import pprint

import sys, time
from org.drupal.project.async_command import PyDrupalApp, GenericDrupalApp
from org.drupal.project.async_command import CommandLineLauncher
from org.drupal.project.async_command import PyAsyncCommand, EncryptedFieldAdapter, DrupalUtils
from org.drupal.project.async_command.exception import ConfigLoadingException

from com.amazonaws.mturk.util import ClientConfig
from com.amazonaws.mturk.service.axis import RequesterService

from org.drupal.project.async_command.EncryptedFieldAdapter import Method
from org.json.simple import JSONValue


#########################################

class MTurkApp(PyDrupalApp):

  # Override
  def getIdentifier(self):
    return 'mturk'

  def initialize(self):
    # late import to avoid circular import in the sub-folders.
    from mt_task import GetBalance, LoadAllHits, LoadHits, LoadAssignments, LoadAllAssignments, UpdateWorker, SendMessage
    # NOTE: the identifier has to match the one in command.getIdentifier(). otherwise it'll cause problem.
    self.registerCommandClassWithIdentifier('GetBalance', GetBalance)
    self.registerCommandClassWithIdentifier('SendMessage', SendMessage)
    self.registerCommandClassWithIdentifier('LoadAllHits', LoadAllHits)
    self.registerCommandClassWithIdentifier('LoadHits', LoadHits)
    self.registerCommandClassWithIdentifier('LoadAssignments', LoadAssignments)
    self.registerCommandClassWithIdentifier('LoadAllAssignments', LoadAllAssignments)
    self.registerCommandClassWithIdentifier('UpdateWorker', UpdateWorker)

    from mt_bonus import GrantBonus
    self.registerCommandClassWithIdentifier('GrantBonus', GrantBonus)

    from mt_karma import ComputeKarma
    self.registerCommandClassWithIdentifier('ComputeKarma', ComputeKarma)

    from mt_analysis import ComputeAll
    self.registerCommandClassWithIdentifier('ComputeAll', ComputeAll)


##########################################

class MTurkCommand(PyAsyncCommand):

  def getIdentifier(self):
    # by default, just use the class name.
    return self.__class__.__name__
    #raise NotImplementedError('Pleaes override getIdentifier method.')

  # this is executed by Java Thread
  def run(self):
    raise NotImplementedError('Pleaes override execute() method or the run() method.')

  # Abstract method, return Status/Messages
  def execute(self):
    raise NotImplementedError('Pleaes override execute() method or the run() method.')



  def initialize(self):
    self.timestamp = int(time.time())
    self.db = self.getDrupalConnection()
    # don't have to have valid value though
    self.user_id, self.task_id = self.record.getUid(), self.record.getEid()

    encryption_key = self.db.getEncryptedFieldSecretKey()
    assert encryption_key != None
    self.encryption = EncryptedFieldAdapter(Method.MCRYPT, encryption_key)
    self.read_mt_properties()
    


  def read_mt_properties(self):
    self.settings = {}

    # read user settings
    if self.user_id != None:
      user_encrypted_settings = self.db.queryValue('SELECT mt_properties_secure_value FROM {field_data_mt_properties_secure} \
        WHERE entity_type="user" AND bundle="user" AND entity_id=?', self.user_id)
      self.user_settings = {}
      # change it to Python dict
      self.user_settings.update(self.encryption.readSettings(user_encrypted_settings))
      self.settings.update(self.user_settings)

    # read task settings, will override the user's settings if duplicate.
    if self.task_id != None:
      task_encrypted_settings = self.db.queryValue('SELECT mt_properties_secure_value FROM {field_data_mt_properties_secure} \
        WHERE entity_type="node" AND bundle="mt_task" AND entity_id=?', self.task_id)
      self.task_settings = {}
      self.task_settings.update(self.encryption.readSettings(task_encrypted_settings))
      # task settings override user settings
      self.settings.update(self.task_settings)



class MTurkServiceCommand(MTurkCommand):
  ''' Sub class for any mturk command related to the SDK.'''

  # this is hard coded and default to all mt_task instances.
  # could be from mturk.properties.
  def read_service_config(self):
    config = ClientConfig()
    # TODO: this could be from the mturk.properties file, rather than hard coded here. could use "DrupalUtils.locateFile" to find this file.
    config.setServiceURL("https://mechanicalturk.amazonaws.com/?Service=AWSMechanicalTurkRequester")
    config.setRetriableErrors(set(['503', 'AWS.ServiceUnavailable', 'Server.ServiceUnavailable']))
    config.setRetryAttempts(6)
    config.setRetryDelayMillis(500)
    return config




  def initialize(self):
    super(MTurkServiceCommand, self).initialize()
    assert self.user_id != None and self.task_id != None, 'MTurk UserID and TaskID cannot be empty.'

    access_key, secret_key = self.settings['access_key'], self.settings['secret_key']
    assert access_key != None and secret_key != None, 'MTurk "access key" and "secret key" cannot be empty. They could either be unset or wrong mcrypt_secret_key setting in config.properties.'

    config = self.read_service_config()
    config.setAccessKeyId(access_key)
    config.setSecretAccessKey(secret_key)
    try:
      self.service = RequesterService(config)
    except:
      raise ConfigLoadingException("Cannot initialize RequesterService object to AMT. Please check you access key and security key.")



  def run(self):
    self.record.setStart(self.timestamp)

    # execute the command
    status, message = self.execute()

    # finish up.
    self.record.setEnd(int(time.time()))
    self.record.setStatus(status)
    self.record.setMessage(message)



class MTurkComputeCommand(MTurkCommand):
  '''Super class for all commands that don't require mturk SDK, but will do work with MTurk data'''

  def run(self):
    self.record.setStart(self.timestamp)

    # execute the command, output should be a dict
    status, message, output = self.execute()

    # finish up.
    self.record.setEnd(int(time.time()))
    self.record.setStatus(status)
    self.record.setMessage(message)
    if output != None:
      self.record.setOutput(DrupalUtils.convertStringToBlog(JSONValue.toJSONString(output)))




if __name__ == '__main__':
  assert sys.registry['python.security.respectJavaAccessibility'] == 'false', 'Please turn off python.security.respectJavaAccessibility.'
  assert sys.version_info[0] >= 2 and sys.version_info[1] >= 5, 'Please use Jython version > 2.5'
  #pprint(sys.path)
  #pprint(sys.currentWorkingDir)
  launcher = CommandLineLauncher(MTurkApp)
  launcher.launch(sys.argv)
