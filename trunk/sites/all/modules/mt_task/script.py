# coding: utf8

# scripts to handle mturks. based on async_command DrupalApp
# requires jython

import sys, time
from collections import defaultdict

from java.text import SimpleDateFormat

from org.drupal.project.async_command import JythonDrupalApp
from org.drupal.project.async_command import Result

from com.amazonaws.mturk.util import ClientConfig
from com.amazonaws.mturk.service.axis import RequesterService
from com.amazonaws.mturk.service.exception import ServiceException

cv = lambda v: v.getValue() if v!=None else None
ct = lambda t: int(t.getTimeInMillis()/1000) if t!=None else None

class MTTaskApp(JythonDrupalApp):

  #Override
  def identifier(self):
    return 'mt_task'

  #Override
  def prepareCommand(self, uid, eid, created):
    self.timestamp = int(time.time())
    if uid!=0 and eid!=0:
      self.init(uid, eid)

  # each method should call this first to setup the RequesterService
  def init(self, user_id, task_id):
    self.user_id, self.task_id = user_id, task_id
    config = self._default_config()
    access_key, secret_key = self._read_mt_properties(user_id, task_id)
    config.setAccessKeyId(access_key)
    config.setSecretAccessKey(secret_key)
    self.service = RequesterService(config)

  # this is hard coded and default to all mt_task instances.
  def _default_config(self):
    config = ClientConfig()
    config.setServiceURL("http://mechanicalturk.amazonaws.com/?Service=AWSMechanicalTurkRequester")
    config.setRetriableErrors(set(['503', 'AWS.ServiceUnavailable', 'Server.ServiceUnavailable']))
    config.setRetryAttempts(6)
    config.setRetryDelayMillis(500)
    return config

  def _read_mt_properties(self, user_id, task_id):
    # read user settings
    user_encrypted_settings = self.queryValue('SELECT mt_properties_secure_value FROM {field_data_mt_properties_secure} \
      WHERE entity_type="user" AND bundle="user" AND entity_id=?', user_id)
    settings = self.readEncryptedSettingsField(user_encrypted_settings, self.EncryptionMethod.MCRYPT)

    # read task settings
    task_encrypted_settings = self.queryValue('SELECT mt_properties_secure_value FROM {field_data_mt_properties_secure} \
      WHERE entity_type="node" AND bundle="mt_task" AND entity_id=?', task_id)
    settings.putAll(self.readEncryptedSettingsField(task_encrypted_settings, self.EncryptionMethod.MCRYPT))

    self.mt_properties = settings
    return (settings.getProperty('access_key'), settings.getProperty('secret_key'))

  ############## commands to be executed below ###########

  def get_balance(self):
    msg = "Account balance:" + str(RequesterService.formatCurrency(self.service.getAccountBalance()))
    print msg
    return Result(True, msg)


  def _save_hit_to_db(self, hit):
    # save hit_type
    if self.queryValue("SELECT hit_type_id FROM {mt_hit_type} WHERE hit_type_id=?", hit.getHITTypeId()) == None:
      # insert hit_type
      self.update("INSERT INTO {mt_hit_type} (hit_type_id, title, reward_amount, reward_currency, assignment_duration, auto_approval_delay, description, keywords, updated) \
                  VALUE (?, ?, ?, ?, ?, ?, ?, ?, ?)", hit.getHITTypeId(), hit.getTitle(), hit.getReward().getAmount(), hit.getReward().getCurrencyCode(),
                  hit.getAssignmentDurationInSeconds(), hit.getAutoApprovalDelayInSeconds(), hit.getDescription(), hit.getKeywords(), self.timestamp)
    else:
      # update changes
      self.update("UPDATE {mt_hit_type} SET title=?, reward_amount=?, reward_currency=?, assignment_duration=?, auto_approval_delay=?, description=?, keywords=?, updated=? \
                  WHERE hit_type_id=?", hit.getTitle(), hit.getReward().getAmount(), hit.getReward().getCurrencyCode(),
                  hit.getAssignmentDurationInSeconds(), hit.getAutoApprovalDelayInSeconds(), hit.getDescription(), hit.getKeywords(), self.timestamp, hit.getHITTypeId())

    # save hit
    if self.queryValue("SELECT hit_id FROM {mt_hit} WHERE hit_id=?", hit.getHITId()) == None:
      # insert hit
      self.update("INSERT INTO {mt_hit} (hit_id, hit_type_id, annotation_id, question, hit_review_status, hit_status, max_assignments, hit_creation, hit_expiration, updated) \
                  VALUE (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", hit.getHITId(), hit.getHITTypeId(), hit.getRequesterAnnotation(), hit.getQuestion(), cv(hit.getHITReviewStatus()),
                  cv(hit.getHITStatus()), hit.getMaxAssignments(), ct(hit.getCreationTime()), ct(hit.getExpiration()), self.timestamp)
    else:
      # update hit
      self.update("UPDATE {mt_hit} SET hit_type_id=?, annotation_id=?, question=?, hit_review_status=?, hit_status=?, max_assignments=?, hit_expiration=?, updated=? \
                  WHERE hit_id=?", hit.getHITTypeId(), hit.getRequesterAnnotation(), hit.getQuestion(), cv(hit.getHITReviewStatus()),
                  cv(hit.getHITStatus()), hit.getMaxAssignments(), ct(hit.getExpiration()), self.timestamp, hit.getHITId())

    # save task_hit mapping, all old mappings should have been purged already.
    self.update("INSERT INTO {mt_task_hit} (task_id, hit_id, updated) VALUE (?, ?, ?)", self.task_id, hit.getHITId(), self.timestamp)




  # load all HITs into table.
  def load_all_hits(self):
    print "Retrieving all HITs. Please wait. Task:", self.task_id
    hits = self.service.searchAllHITs()
    print 'Total number of HITs:', len(hits)

    print 'Now saving to database. WARNING: old HITs will be deleted'
    deleted = self.update('DELETE FROM {mt_task_hit} WHERE task_id=?', self.task_id)
    print 'Deleted old HITs:', deleted

    # process hit types and save to db.
    hit_types = defaultdict(int)
    for hit in hits:
      hit_types[hit.getHITTypeId()] += 1
      self._save_hit_to_db(hit)
    print 'Total number of HITTypes:', len(hit_types)
    return Result(True, 'Total # of HITs loaded: '+str(len(hits))+' -- HIT Types and # of HITs: '+'; '.join([k+':'+str(v) for k,v in hit_types.items()]))



  # load specified HITs or the latest HITs
  def load_hits(self):
    # note: there's no AMT API to retrieve HITs based on HIT TYPE, so we can only get all HITs and then filter.
    print "Retrieving all HITs. Please wait. Task:", self.task_id
    hits = self.service.searchAllHITs()
    #print 'Total number of HITs:', len(hits)

    # get hit type to save
    hit_type_id_set = set()
    for pname in self.mt_properties.propertyNames():
      if pname.startswith('hit_type_id'):
        hit_type_id_set.add(self.mt_properties.getProperty(pname))

    if len(hit_type_id_set) == 0:
      max_created, max_hit_type_id = 0, ''
      for hit in hits:
        if hit.getCreationTime().getTimeInMillis() > max_created:
          max_created = hit.getCreationTime().getTimeInMillis()
          max_hit_type_id = hit.getHITTypeId()
      hit_type_id_set.add(max_hit_type_id)
      msg = 'No hit_type_id specified. Use the latest hit_type_id: ' +  max_hit_type_id
    else:
      msg = 'Use hit_type_id: ' + ', '.join(list(hit_type_id_set))

    print 'Now saving to database. WARNING: old HITs will be deleted'
    deleted = self.update('DELETE FROM {mt_task_hit} WHERE task_id=?', self.task_id)
    print 'Deleted old HITs:', deleted

    total = 0
    for hit in hits:
      if hit.getHITTypeId() in hit_type_id_set:
        total += 1
        self._save_hit_to_db(hit)

    return Result(True, msg+' -- Total # of HITs loaded: '+str(total))




  def _save_assignment_to_db(self, assignment):
    assignment_status = assignment.getAssignmentStatus()
    if assignment_status != None:
      assignment_status = assignment_status.getValue()
    if self.queryValue("SELECT assignment_id FROM {mt_assignment} WHERE assignment_id=?", assignment.getAssignmentId()) == None:
      # insert new assignment
      self.update("INSERT {mt_assignment} (assignment_id, hit_id, worker_id, assignment_status, accept_time, submit_time, \
                  approval_time, rejection_time, answer, requester_feedback, updated) VALUE (?,?,?,?,?,?,?,?,?,?,?)",
                  assignment.getAssignmentId(), assignment.getHITId(), assignment.getWorkerId(), assignment_status, ct(assignment.getAcceptTime()),
                  ct(assignment.getSubmitTime()), ct(assignment.getApprovalTime()), ct(assignment.getRejectionTime()),
                  assignment.getAnswer(), assignment.getRequesterFeedback(), self.timestamp)
    else:
      # update existing assignment
      self.update("UPDATE {mt_assignment} SET assignment_status=?, accept_time=?, submit_time=?, approval_time=?, rejection_time=?,\
                  answer=?, requester_feedback=?, updated=? WHERE assignment_id=?", assignment_status, ct(assignment.getAcceptTime()),
                  ct(assignment.getSubmitTime()), ct(assignment.getApprovalTime()), ct(assignment.getRejectionTime()),
                  assignment.getAnswer(), assignment.getRequesterFeedback(), self.timestamp, assignment.getAssignmentId())




  def load_assignments(self):
    rows = self.query("SELECT hit_id FROM {mt_task_hit} WHERE task_id=?", self.task_id)
    print "Loading assignments for", len(rows), "HITs. Please wait."
    for row in rows:
      hit_id = row['hit_id']
      assignments = self.service.getAllAssignmentsForHIT(hit_id)
      for assignment in assignments:
        self._save_assignment_to_db(assignment)
    return Result(True, 'Total assignments loaded: ' + str(len(rows)))



  def update_worker_user_mapping(self):
    # build worker_id, user_id mapping.
    mapping = {}
    rows = self.query('SELECT uid, name, mt_properties_secure_value FROM {users} u INNER JOIN {field_data_mt_properties_secure} f \
      ON u.uid=f.entity_id WHERE entity_type="user" AND bundle="user"')
    for row in rows:
      mt_settings = self.readEncryptedSettingsField(row['mt_properties_secure_value'], self.EncryptionMethod.MCRYPT)
      worker_id = mt_settings['worker_id']
      if worker_id != None:
        # TODO: see #1148280 (http://drupal.org/node/1148280)
        if worker_id in mapping:
          print "WARNING: WORKER_ID ALREADY EXISTED!!!"  # but we do nothing for now.
        mapping[worker_id] = (row['uid'], row['name'])

    # build existing mapping
    existing = {}
    rows = self.query("SELECT worker_id, user_id, display_name FROM {mt_worker}")
    for row in rows:
      existing[row['worker_id']] = (row['user_id'], row['display_name'])

    # retrieve all workers
    rows = self.query("SELECT DISTINCT worker_id FROM {mt_assignment}")
    for row in rows:
      worker_id = row['worker_id']
      # first see if we'll update
      if worker_id in existing and worker_id in mapping and existing[worker_id] != mapping[worker_id]:
        self.update("UPDATE {mt_worker} SET user_id=?, display_name=?, updated=? WHERE worker_id=?",
                    mapping[worker_id][0], mapping[worker_id][1], self.timestamp, worker_id)
      # only for new worker_id that we insert them.
      elif worker_id not in existing:
        if worker_id in mapping:
          user_id, display_name = mapping[worker_id]
        else:
          user_id, display_name = 0, 'Worker '+worker_id[-4:]  # last 4 chars of worker_id
        self.update("INSERT INTO {mt_worker} (worker_id, user_id, display_name, updated) VALUE(?,?,?,?)",
                    worker_id, user_id, display_name, self.timestamp)
      # for existing worker_id, do nothing
      else:
        continue

    return Result(True, "Updated workers: " + str(len(rows)))



  def update_worker_stats(self):
    # TODO: need performance improvement
    rows = self.query("SELECT worker_id, COUNT(assignment_id) AS total_assignments FROM {mt_assignment} WHERE assignment_status='Approved' GROUP BY worker_id")
    for row in rows:
      self.update("UPDATE {mt_worker} SET assignments_approved=? WHERE worker_id=?", row['total_assignments'], row['worker_id'])
    rows = self.query("SELECT worker_id, COUNT(assignment_id) AS total_assignments FROM {mt_assignment} WHERE assignment_status='Rejected' GROUP BY worker_id")
    for row in rows:
      self.update("UPDATE {mt_worker} SET assignments_rejected=? WHERE worker_id=?", row['total_assignments'], row['worker_id'])
    rows = self.query("SELECT worker_id, SUM(submit_time-accept_time) AS total_time FROM {mt_assignment} GROUP BY worker_id")
    for row in rows:
      self.update("UPDATE {mt_worker} SET working_time_total=? WHERE worker_id=?", row['total_time'], row['worker_id'])
    return Result(True, "Updated worker stats.")


  def update_worker(self):
    ''' Site-wide update worker-user mapping and stats update
    This is entirely based on existing data in {mt_assignment} and will not access AMT.
    '''
    r = self.update_worker_user_mapping()
    msg = r.getMessage()
    r = self.update_worker_stats()
    msg += ' -- ' + r.getMessage()
    return Result(True, msg)


if __name__ == '__main__':
  app = MTTaskApp()
  app.handleCLI(sys.argv)