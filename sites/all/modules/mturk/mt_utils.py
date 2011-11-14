'''
Currently, we only use the read-only operations in mturk SDK. For 'write' operations, we provide this script. You can write your own script extends it.
You can use the default '-e' option to directly run some commands without using commands saved in the database.
Make sure you have the mt_task sub-directory in PYTHONPATH
'''
from ConfigParser import ConfigParser
from mt_task import MTTaskApp


DEFAULT_UID = 0
DEFAULT_EID = 0
DEFAULT_DB_CONF = 'mysql.conf'


class MTUtilsStandalone(MTTaskApp):

  #Override
  def identifier(self):
    return 'mt_utils'

  def __init__(self):
    self.init(DEFAULT_UID, DEFAULT_EID)

  def get_db_conn(config_file=DEFAULT_DB_CONF):
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    db = "jdbc:mysql://" + config.get('client', 'host') + '/' + config.get('client', 'database')
    user = config.get('client', 'user')
    passwd = config.get('client', 'password')
    driver = "org.gjt.mm.mysql.Driver"
    #print (db, user, passwd, driver)
    conn = zxJDBC.connect(db, user, passwd, driver)
    cursor = conn.cursor()
    return conn, cursor


  ##########################################################

  def message_qual(self, qual_id, subject, message):
    workers = []
    qrs = self.service.getAllQualificationRequests(qual_id)
    for i in range(len(qrs)):
      q = qrs[i]
      workers.append(q.getSubjectId())
    self._notify_workers(subject, message, workers)


  def _notify_workers(self, subject, message, workers, batch_size = 100):
    print "Total recipients:", len(workers)
    batches = (len(workers)-1)/batch_size + 1
    for batch in range(batches):
      rp = workers[batch*batch_size : (batch+1)*batch_size]
      print "Sending messages to", len(rp), "recipients"
      self.service.notifyWorkers(subject, message, rp)


  def _register_hit_type(self, hit_properties):
    props = HITProperties(hit_properties)
    hittypeid = self.service.registerHITType(
      props.getAutoApprovalDelay(),
      props.getAssignmentDuration(),
      props.getRewardAmount(),
      #props.getTitle() + appendix,
      props.getTitle(),
      props.getKeywords(),
      props.getDescription(),
      props.getQualificationRequirements() )
    print "Created hittype:", hittypeid
    return hittypeid


  # hit_properties: the file that defines HIT properties
  # question_template: the file that defines the question template.
  def upload_hits_from_db(self, hit_properties, question_template, sql):
    import cgi
    props = HITProperties(hit_properties)
    hq = HITQuestion(question_template)
    hit_type_id = self._register_hittype()
    conn, cursor = self.get_db_conn()
    limit = 50

    cursor.execute(sql)
    for id, title, url, teaser, diggs_fromapi in cursor.fetchall():
      if diggs_fromapi < 10:
        cursor.execute("select count(*) from digg_digg where storyid='%s'" % (id))
        diggs_crawler = cursor.fetchone()[0]
        if diggs_crawler < 10:
          continue  # if diggs < 10, we don't pump into mturk.
      row = {}
      row['id'] = id
      row['title'] = cgi.escape(title).replace('"', "'").decode('utf-8', 'replace')
      row['teaser'] = cgi.escape(teaser).replace('"', "'").decode('utf-8', 'replace')
      row['url'] = url
      if url.find('nytimes.com')!=-1 or url.find("newsweek.com")!=-1:
        row['preview'] = "no"
      else:
        row['preview'] = "yes"

      #print row['title'], row['teaser']
      question = hq.getQuestion(row)
      #print id, question
      # this is actually to RequestServiceRaw.
      hit = self.service.createHIT( hittypeid, None, None, None, question, None, None, None, props.getLifetime(), props.getMaxAssignments(), id, None, None)
      hitid = hit.getHITId()
      print "Created", id, hitid
      cursor.execute("INSERT INTO mt_task_hit(mt_task_id, annotation_id, hit_id, created) VALUE(%s, '%s', '%s', unix_timestamp())" % (self.mt_task_id, id, hitid))
    conn.close()