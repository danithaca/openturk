# coding: utf8

# scripts to handle mturks. based on async_command DrupalApp
# requires jython
from mturk import MTurkServiceCommand, MTurkComputeCommand
from org.drupal.project.async_command.AsyncCommand import Status
from collections import defaultdict

from org.json.simple import JSONValue
from com.amazonaws.mturk.requester import HITStatus
from com.amazonaws.mturk.service.exception import ObjectDoesNotExistException


cv = lambda v: v.getValue() if v!=None else None
ct = lambda t: int(t.getTimeInMillis()/1000) if t!=None else None


class GetBalance(MTurkServiceCommand):

  def execute(self):
    balance = self.service.getAccountBalance()
    msg = "Account balance:" + str(balance)
    self.logger.info(msg)
    self.record.setNumber1(balance)
    return Status.SUCCESS, msg


class SendMessage(MTurkServiceCommand):

  def execute(self):
    message_id = self.record.getId1()
    batch_size = self.record.getNumber1()
    if batch_size == None:
      batch_size = 50
    else:
      batch_size = int(batch_size)
    num = self._send_message(message_id, batch_size)
    return Status.SUCCESS, 'Sent message successfully to ' + str(num) + ' workers'

  def _send_message(self, message_id, batch_size = 50):
    ''' Send message to selected workers. '''
    subject, message = self.db.queryArray('SELECT subject, message FROM {mt_message} WHERE message_id=?', message_id)[0]
    workers = []
    recipients = self.db.queryArray('SELECT worker_id FROM {mt_message_worker} WHERE message_id=?', message_id)
    for worker_id, in recipients:
      workers.append(worker_id)

    batches = (len(workers)-1)/batch_size + 1
    for batch in range(batches):
      rp = workers[batch*batch_size : (batch+1)*batch_size]
      #print "Sending messages to", len(rp), "recipients"
      self.service.notifyWorkers(subject, message, rp)
    return len(workers)


class LoadAllHits(MTurkServiceCommand):

  def execute(self):
    print "Retrieving all HITs. Please wait. Task:", self.task_id
    hits = self.service.searchAllHITs()
    print 'Total number of HITs:', len(hits)

    print 'Now saving to database. WARNING: old HITs will be deleted'
    deleted = self.db.update('DELETE FROM {mt_task_hit} WHERE task_id=?', self.task_id)
    print 'Deleted old HITs:', deleted

    # TODO: allow people to assign hit_type_id and only receive those assigned.
    # current approach is that after loadAllHits, run LoadHits, and will remove all hit_type_ids not specified.

    # process hit types and save to db.
    hit_types = defaultdict(int)
    for hit in hits:
      hit_types[hit.getHITTypeId()] += 1
      self.save_hit_to_db(hit)
    print 'Total number of HITTypes:', len(hit_types)
    return Status.SUCCESS, 'Total # of HITs loaded: '+str(len(hits))+' -- HIT Types and # of HITs: '+'; '.join([k+':'+str(v) for k,v in hit_types.items()])


  # save a hit to db
  def save_hit_to_db(self, hit):
    #print 'Processing:', hit.getHITId()
    # save hit_type
    if self.db.queryValue("SELECT hit_type_id FROM {mt_hit_type} WHERE hit_type_id=?", hit.getHITTypeId()) == None:
      # insert hit_type
      self.db.update("INSERT INTO {mt_hit_type} (hit_type_id, title, reward_amount, reward_currency, assignment_duration, auto_approval_delay, description, keywords, updated) \
                  VALUE (?, ?, ?, ?, ?, ?, ?, ?, ?)", hit.getHITTypeId(), hit.getTitle(), hit.getReward().getAmount(), hit.getReward().getCurrencyCode(),
                  hit.getAssignmentDurationInSeconds(), hit.getAutoApprovalDelayInSeconds(), hit.getDescription(), hit.getKeywords(), self.timestamp)
    else:
      # update changes
      self.db.update("UPDATE {mt_hit_type} SET title=?, reward_amount=?, reward_currency=?, assignment_duration=?, auto_approval_delay=?, description=?, keywords=?, updated=? \
                  WHERE hit_type_id=?", hit.getTitle(), hit.getReward().getAmount(), hit.getReward().getCurrencyCode(),
                  hit.getAssignmentDurationInSeconds(), hit.getAutoApprovalDelayInSeconds(), hit.getDescription(), hit.getKeywords(), self.timestamp, hit.getHITTypeId())

    # save hit
    if self.db.queryValue("SELECT hit_id FROM {mt_hit} WHERE hit_id=?", hit.getHITId()) == None:
      # insert hit
      self.db.update("INSERT INTO {mt_hit} (hit_id, hit_type_id, annotation_id, question, hit_review_status, hit_status, max_assignments, hit_creation, hit_expiration, updated) \
                  VALUE (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", hit.getHITId(), hit.getHITTypeId(), hit.getRequesterAnnotation(), hit.getQuestion(), cv(hit.getHITReviewStatus()),
                  cv(hit.getHITStatus()), hit.getMaxAssignments(), ct(hit.getCreationTime()), ct(hit.getExpiration()), self.timestamp)
    else:
      # update hit
      self.db.update("UPDATE {mt_hit} SET hit_type_id=?, annotation_id=?, question=?, hit_review_status=?, hit_status=?, max_assignments=?, hit_expiration=?, updated=? \
                  WHERE hit_id=?", hit.getHITTypeId(), hit.getRequesterAnnotation(), hit.getQuestion(), cv(hit.getHITReviewStatus()),
                  cv(hit.getHITStatus()), hit.getMaxAssignments(), ct(hit.getExpiration()), self.timestamp, hit.getHITId())

    if self.db.queryValue("SELECT 1 FROM {mt_task_hit} WHERE task_id = ? AND hit_id = ?", self.task_id, hit.getHITId()) == None:
      self.db.update("INSERT INTO {mt_task_hit} (task_id, hit_id, updated) VALUE (?, ?, ?)", self.task_id, hit.getHITId(), self.timestamp)
    else:
      # duplicate data, we don't do anything.
      pass


class LoadHits(LoadAllHits):
  
  # load specified HITs or the latest HITs
  def execute(self):
    # get hit type to save
    hit_type_id_set = set()
    for pname in self.task_settings.keys():
      if pname.startswith('hit_type_id'):
        hit_type_id_set.add(self.task_settings[pname])

    # retrieve hits.
    if len(hit_type_id_set) == 0:
      # TODO: figure out how to do the nice way when people didn't assign the hit_type_id and assumes to use the latest one.
      #print "Retrieving all HITs. Please wait. Task:", self.task_id
      #hits = self.service.searchAllHITs()
      #print 'Total number of HITs:', len(hits)
      print 'Please specify the hit_type_id to use this command.'
      hits = []
    else:
      hits = []
      for hit_type_id in hit_type_id_set:
        print "Retrieving HITs for HIT type:", hit_type_id
        new_hits = self.service.getAllReviewableHITs(hit_type_id)
        print 'Retrieved HITs:', len(new_hits)
        # add Java arraylist to python list.
        for h in new_hits:
          hits.append(h)


    if len(hit_type_id_set) == 0:
      #max_created, max_hit_type_id = 0, ''
      #for hit in hits:
      #  if hit.getCreationTime().getTimeInMillis() > max_created:
      #    max_created = hit.getCreationTime().getTimeInMillis()
      #    max_hit_type_id = hit.getHITTypeId()
      #hit_type_id_set.add(max_hit_type_id)
      #msg = 'No hit_type_id specified. Use the latest hit_type_id: ' +  max_hit_type_id
      msg = 'No hit_type_id specified.'
    else:
      msg = 'Use hit_type_id: ' + ', '.join(list(hit_type_id_set))

    #print 'Now saving to database. WARNING: old HITs will be deleted'
    #deleted = self.db.update('DELETE FROM {mt_task_hit} WHERE task_id=?', self.task_id)
    #print 'Deleted old HITs:', deleted

    total = 0
    for hit in hits:
      total += 1
      # note: for some reason, then
      hit = self.service.getHIT(hit.getHITId())
      self.save_hit_to_db(hit)
      # set reviewing so we don't retrieve it again.
      print 'Set reviewing status:', hit.getHITId()
      self.service.setHITAsReviewing(hit.getHITId())
      hit.setHITStatus(HITStatus.Reviewing)

    # remove all task_hit that are not in hit_type_id_set
    set_str = ','.join(["'" + hit_type_id + "'" for hit_type_id in hit_type_id_set])
    self.db.update("DELETE FROM {mt_task_hit} WHERE task_id=? AND hit_id NOT IN (SELECT hit_id FROM {mt_hit} WHERE hit_type_id IN (" + set_str + "))", self.task_id)

    return Status.SUCCESS, msg+' -- Total # of HITs loaded: '+str(total)



class LoadAllAssignments(MTurkServiceCommand):

  def execute(self):
    hits = self.db.queryArray("SELECT hit_id FROM {mt_task_hit} WHERE task_id=?", self.task_id)
    print "Loading assignments for", len(hits), "HITs. Please wait."
    for hit_id, in hits:
      assignments = self.service.getAllAssignmentsForHIT(hit_id)
      for assignment in assignments:
        self.save_assignment_to_db(assignment)
    return Status.SUCCESS, 'Total assignments loaded: ' + str(len(hits))

  def save_assignment_to_db(self, assignment):
    assignment_status = assignment.getAssignmentStatus()
    if assignment_status != None:
      assignment_status = assignment_status.getValue()

    assignment_id = assignment.getAssignmentId()
    answer_xml = assignment.getAnswer()
    answer_json = self.parse_answer_xml(assignment_id, answer_xml)

    if self.db.queryValue("SELECT assignment_id FROM {mt_assignment} WHERE assignment_id=?", assignment.getAssignmentId()) == None:
      # insert new assignment
      self.db.update("INSERT {mt_assignment} (assignment_id, hit_id, worker_id, assignment_status, accept_time, submit_time, \
                  approval_time, rejection_time, answer, answer_json, requester_feedback, updated) VALUE (?,?,?,?,?,?,?,?,?,?,?,?)",
                  assignment_id, assignment.getHITId(), assignment.getWorkerId(), assignment_status, ct(assignment.getAcceptTime()),
                  ct(assignment.getSubmitTime()), ct(assignment.getApprovalTime()), ct(assignment.getRejectionTime()),
                  answer_xml, answer_json, assignment.getRequesterFeedback(), self.timestamp)
    else:
      # update existing assignment
      self.db.update("UPDATE {mt_assignment} SET assignment_status=?, accept_time=?, submit_time=?, approval_time=?, rejection_time=?,\
                  answer=?, answer_json=?, requester_feedback=?, updated=? WHERE assignment_id=?",
                  assignment_status, ct(assignment.getAcceptTime()),
                  ct(assignment.getSubmitTime()), ct(assignment.getApprovalTime()), ct(assignment.getRejectionTime()),
                  answer_xml, answer_json, assignment.getRequesterFeedback(), self.timestamp, assignment_id)


  def parse_answer_xml(self, assignment_id, answer_xml):
    ''' Return json string '''
    json = {}
    answers = self.service.parseAnswers(answer_xml)
    for answer in answers.getAnswer():
      answer_str = self.service.getAnswerValue(assignment_id, answer, True)
      # according to the implementation of RequesterService.getAnswerValue(), '\t' is the delimeter for question and answer strings.
      delim_pos = answer_str.find('\t')
      q, a = answer_str[:delim_pos], answer_str[delim_pos+1:]
      json[q] = a
    return JSONValue.toJSONString(json)




class LoadAssignments(LoadAllAssignments):
  def execute(self):
    # idea is: if the HIT expires before the last successful run of LoadAssignment, then there shouldn't be any new assignment updates.
    last_run = self.db.queryValue("SELECT MAX(created) FROM {async_command} WHERE app='mturk' AND (command='LoadAssignments' OR command='LoadAllAssignments') AND status='OKOK' AND uid=? AND eid=?", self.user_id, self.task_id)
    print "Last LoadAssignments run:", last_run
    if last_run == None:
      last_run = 0
    #hits = self.db.queryArray("SELECT h.hit_id FROM {mt_task_hit} t INNER JOIN {mt_hit} h ON t.hit_id=h.hit_id WHERE task_id=? AND hit_expiration >= ?", self.task_id, last_run)
    # also, we want to include those that are updated after the last run of LoadAssignment.
    hits = self.db.queryArray("SELECT h.hit_id FROM {mt_task_hit} t INNER JOIN {mt_hit} h ON t.hit_id=h.hit_id WHERE task_id=? AND h.updated >= ?", self.task_id, last_run)
    print "Loading assignments for", len(hits), "HITs. Please wait."
    total = 0
    for hit_id, in hits:
      #print 'Processing assignments for HIT:', hit_id
      try:
        assignments = self.service.getAllAssignmentsForHIT(hit_id)
        for assignment in assignments:
          self.save_assignment_to_db(assignment)
          total += 1
      except ObjectDoesNotExistException:
        print "HIT not exists:", hit_id
    return Status.SUCCESS, 'Total assignments loaded: ' + str(total)



class UpdateWorker(MTurkComputeCommand):
  
  def update_worker_user_mapping(self):
    # build worker_id, user_id mapping.
    mapping = {}
    rows = self.db.queryArray('SELECT uid, name, mt_properties_secure_value FROM {users} u INNER JOIN {field_data_mt_properties_secure} f \
      ON u.uid=f.entity_id WHERE entity_type="user" AND bundle="user"')
    for uid, name, value in rows:
      mt_settings = self.encryption.readSettings[value]
      worker_id = mt_settings['worker_id']
      if worker_id != None:
        worker_id = worker_id.strip()
        # TODO: see #1148280 (http://drupal.org/node/1148280)
        if worker_id in mapping:
          print "WARNING: WORKER_ID ALREADY EXISTED!!!"  # but we do nothing for now.
        mapping[worker_id] = (uid, name)

    # build existing mapping
    existing = {}
    rows = self.db.queryArray("SELECT worker_id, user_id, display_name FROM {mt_worker}")
    for worker_id, user_id, display_name in rows:
      existing[worker_id] = (user_id, display_name)

    # retrieve all workers
    rows = self.db.queryArray("SELECT DISTINCT worker_id FROM {mt_assignment}")
    for worker_id, in rows:
      # first see if we'll update
      if worker_id in existing and worker_id in mapping and existing[worker_id] != mapping[worker_id]:
        self.db.update("UPDATE {mt_worker} SET user_id=?, display_name=?, updated=? WHERE worker_id=?",
                    mapping[worker_id][0], mapping[worker_id][1], self.timestamp, worker_id)
      # only for new worker_id that we insert them.
      elif worker_id not in existing:
        if worker_id in mapping:
          user_id, display_name = mapping[worker_id]
        else:
          user_id, display_name = 0, 'Worker '+worker_id[-4:]  # last 4 chars of worker_id
        self.db.update("INSERT INTO {mt_worker} (worker_id, user_id, display_name, updated) VALUE(?,?,?,?)",
                    worker_id, user_id, display_name, self.timestamp)
      # for existing worker_id, do nothing
      else:
        continue

    return "Updated workers: " + str(len(rows))



  def update_worker_stats(self):
    # TODO: need performance improvement
    rows = self.db.query("SELECT worker_id, COUNT(assignment_id) AS total_assignments FROM {mt_assignment} WHERE assignment_status='Approved' GROUP BY worker_id")
    for row in rows:
      self.db.update("UPDATE {mt_worker} SET assignments_approved=? WHERE worker_id=?", row['total_assignments'], row['worker_id'])
    rows = self.db.query("SELECT worker_id, COUNT(assignment_id) AS total_assignments FROM {mt_assignment} WHERE assignment_status='Rejected' GROUP BY worker_id")
    for row in rows:
      self.db.update("UPDATE {mt_worker} SET assignments_rejected=? WHERE worker_id=?", row['total_assignments'], row['worker_id'])
    rows = self.db.query("SELECT worker_id, SUM(submit_time-accept_time) AS total_time FROM {mt_assignment} GROUP BY worker_id")
    for row in rows:
      self.db.update("UPDATE {mt_worker} SET working_time_total=? WHERE worker_id=?", row['total_time'], row['worker_id'])
    return "Updated worker stats."


  def execute(self):
    ''' Site-wide update worker-user mapping and stats update
    This is entirely based on existing data in {mt_assignment} and will not access AMT.
    '''
    msg = self.update_worker_user_mapping()
    msg += ' -- ' + self.update_worker_stats()
    return Status.SUCCESS, msg, None
